// flow-factory 无头检查：用本机 Chrome 打开生成的页面，收集报错、读自检结果、按需截图。
// 用法：node check.mjs page.html [--size 1440x900] [--theme light|dark] [--shot out.png] [--view flow|write|fault] [--station <id>] [--sample <id>] [--beat N] [--focus <站 id> [--zoom 1.2]] [--fit]
// 不带参数时截的是页面打开约 2.6 秒后的样子（已推到入口开演第一件）；--fit 截全图
// 需要 Node 18+（自带 WebSocket 用 Node 22；更早版本请装 ws 包）与本机 Chrome / Edge。只读，不改页面。
import {spawn} from 'node:child_process'; import fs from 'node:fs'; import path from 'node:path'; import os from 'node:os';
const args=process.argv.slice(2); const file=args[0]; if(!file){ console.error('用法：node check.mjs page.html [--shot out.png]'); process.exit(2); }
const opt=k=>{ const i=args.indexOf('--'+k); return i>0?args[i+1]:null; };
const [W,H]=(opt('size')||'1440x900').split('x').map(Number);
const cands=[process.env.CHROME,'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','/usr/bin/google-chrome','/usr/bin/chromium'].filter(Boolean);
const exe=cands.find(p=>fs.existsSync(p)); if(!exe){ console.error('找不到 Chrome / Edge，设环境变量 CHROME 指向可执行文件'); process.exit(2); }
const port=9300+Math.floor(Math.random()*500), prof=fs.mkdtempSync(path.join(os.tmpdir(),'ffchk'));
const ch=spawn(exe,['--headless=new','--disable-gpu',`--remote-debugging-port=${port}`,`--user-data-dir=${prof}`,'--no-first-run','about:blank'],{stdio:'ignore'});
const sl=ms=>new Promise(r=>setTimeout(r,ms));
let tg; for(let i=0;i<60;i++){ try{ const j=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); tg=j.find(t=>t.type==='page'); if(tg) break; }catch(e){} await sl(200); }
if(!tg){ console.error('Chrome 没起来'); ch.kill(); process.exit(2); }
const ws=new WebSocket(tg.webSocketDebuggerUrl); await new Promise(r=>ws.onopen=r);
let id=0; const P={}, logs=[];
ws.onmessage=m=>{ const d=JSON.parse(m.data); if(d.id&&P[d.id]){ P[d.id](d); delete P[d.id]; }
  if(d.method==='Runtime.exceptionThrown') logs.push('页面异常：'+(d.params.exceptionDetails.exception?.description||d.params.exceptionDetails.text).slice(0,400));
  if(d.method==='Runtime.consoleAPICalled'&&['error','warning'].includes(d.params.type)) logs.push('控制台'+d.params.type+'：'+d.params.args.map(a=>a.value||a.description).join(' ').slice(0,300)); };
const C=(method,params={})=>new Promise(r=>{ const i=++id; P[i]=r; ws.send(JSON.stringify({id:i,method,params})); });
await C('Runtime.enable'); await C('Page.enable');
await C('Emulation.setDeviceMetricsOverride',{width:W,height:H,deviceScaleFactor:1,mobile:W<600});
await C('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:opt('theme')||'light'}]});
await C('Page.navigate',{url:'file:///'+path.resolve(file).replace(/\\/g,'/')}); await sl(2600);
const ev=async js=>(await C('Runtime.evaluate',{expression:js,awaitPromise:true,returnByValue:true})).result.result?.value;
const steps=[]; if(opt('view')) steps.push(`document.querySelector('[data-view="${opt('view')}"]').click()`);
if(opt('sample')) steps.push(`playFrom(${JSON.stringify(opt('sample'))})`);
steps.push('stop()');
if(opt('beat')) steps.push(`setBeat(${+opt('beat')},false)`);
if(opt('station')) steps.push(`selectStation(${JSON.stringify(opt('station'))})`);
if(opt('focus')) steps.push(`st.follow=false;centerOn(N[${JSON.stringify(opt('focus'))}].x,N[${JSON.stringify(opt('focus'))}].y,${+(opt('zoom')||1)},0)`);
else if(opt('station')) steps.push(`st.follow=false;centerOn(N[${JSON.stringify(opt('station'))}].x,N[${JSON.stringify(opt('station'))}].y,${+(opt('zoom')||1)},0)`);
else if(args.includes('--fit')) steps.push('st.follow=false;fit(false)');
steps.push("document.getElementById('toast').classList.remove('on')");
await ev(steps.join(';')); await sl(opt('view')||opt('beat')?2200:900);   // 切视图 / 跳拍后货要滑到新位置（最长约 2.1 秒），等它停稳再截，免得截到半路
const r=await ev(`({self:document.documentElement.dataset.selfcheck,fail:(window.__selfcheck||[]).filter(x=>!x.pass).map(x=>x.n+'：'+x.why),stations:Object.keys(S).length,edges:EDGES.length,samples:SAMPLES.length,overflowX:document.documentElement.scrollWidth-innerWidth})`);
console.log(JSON.stringify(r));
if(opt('shot')){ const s=await C('Page.captureScreenshot',{format:'png'}); fs.writeFileSync(opt('shot'),Buffer.from(s.result.data,'base64')); console.log('截图：'+opt('shot')); }
console.log(logs.length?logs.join('\n'):'没有报错');
ws.close(); ch.kill(); process.exit(logs.length||(r&&r.fail&&r.fail.length)?1:0);
