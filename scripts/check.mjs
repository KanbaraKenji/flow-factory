// flow-factory 无头检查：用本机 Chrome 打开生成的页面，收集报错、读自检结果、按需截图。
// 用法：node check.mjs page.html [选项]
//   --size 1440x900        画布尺寸（宽 < 600 按手机模拟）
//   --theme light|dark     系统深浅色
//   --skin <配色>          页面配色：auto light dark report（汇报）或皮肤名；等于在链接里写 skin=
//   --hash "<参数>"        原样拼到页面链接 # 后面，和用户点链接打开时一样，比如 "skin=report&drill=1&sample=s2"
//   --speed 0.5~2          播放速度
//   --view flow|write|fault|run|metro
//   --sample <id>          演哪件货（样例货 id，或全部路线里的 r1、r2…）
//   --beat N               跳到第 N 拍（截图时镜头对准货）
//   --station <id>         选中一站（截图时镜头对准它）
//   --focus <站 id> [--zoom 1.2]   镜头对准某站
//   --fit                  截全图
//   --shot out.png         截图
//   --timeout 60           整个检查最多等几秒，超时以失败退出（退出码 3）
// 不带视图类参数时截的是页面打开约 2.6 秒后的样子（已推到入口开演第一件）。
// 退出码：0 通过；1 自检没过或页面有报错；2 用法错 / 找不到浏览器；3 超时。
// 需要 Node 18+（自带 WebSocket 用 Node 22；更早版本请装 ws 包）与本机 Chrome / Edge。只读，不改页面。
import {spawn} from 'node:child_process'; import fs from 'node:fs'; import path from 'node:path'; import os from 'node:os';
const args=process.argv.slice(2);
const VAL=['size','theme','skin','hash','speed','view','sample','beat','station','focus','zoom','shot','timeout'], FLAG=['fit'];
const bad=[], o={}; let file=null;
for(let i=0;i<args.length;i++){ const a=args[i];
  if(a.startsWith('--')){ const k=a.slice(2);
    if(VAL.includes(k)){ const v=args[i+1]; if(v==null||v.startsWith('--')) bad.push(`${a} 后面要跟一个值`); else { o[k]=v; i++; } }
    else if(FLAG.includes(k)) o[k]=true;
    else bad.push(`不认识的参数 ${a}`); }
  else if(!file) file=a; else bad.push(`多余的参数 ${a}`); }
if(!file) bad.push('缺页面文件');
else if(!fs.existsSync(file)) bad.push(`找不到文件 ${file}`);
if(o.size&&!/^\d+x\d+$/.test(o.size)) bad.push('--size 要写成 宽x高，比如 1440x900');
if(o.theme&&!['light','dark'].includes(o.theme)) bad.push('--theme 只能是 light 或 dark');
if(o.view&&!['flow','write','fault','run','metro'].includes(o.view)) bad.push('--view 只能是 flow write fault run metro');
if(o.beat!=null&&!/^\d+$/.test(o.beat)) bad.push('--beat 要是整数');
if(o.timeout!=null&&!(+o.timeout>0)) bad.push('--timeout 要是正数（秒）');
if(o.speed!=null&&![.5,.75,1,1.25,1.5,2].includes(+o.speed)) bad.push('--speed 只能是 0.5 0.75 1 1.25 1.5 2');
if(bad.length){ console.error(bad.join('\n')+'\n用法：node check.mjs page.html [--size 1440x900] [--theme light|dark] [--skin report] [--hash "skin=report&drill=1"] [--speed 1] [--view fault] [--sample s1] [--beat 3] [--station id] [--focus id --zoom 1.2] [--fit] [--shot out.png] [--timeout 60]'); process.exit(2); }

const [W,H]=(o.size||'1440x900').split('x').map(Number);
const cands=[process.env.CHROME,'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Microsoft/Edge/Application/msedge.exe','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge','/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium','/usr/bin/chromium-browser','/usr/bin/microsoft-edge'].filter(Boolean);
const exe=cands.find(p=>fs.existsSync(p)); if(!exe){ console.error('找不到 Chrome / Edge，设环境变量 CHROME 指向可执行文件'); process.exit(2); }
const port=9300+Math.floor(Math.random()*500), prof=fs.mkdtempSync(path.join(os.tmpdir(),'ffchk'));
const ch=spawn(exe,['--headless=new','--disable-gpu',`--remote-debugging-port=${port}`,`--user-data-dir=${prof}`,'--no-first-run','about:blank'],{stdio:'ignore'});
let stage='启动浏览器';
const quit=code=>{ try{ ch.kill(); }catch(e){} try{ fs.rmSync(prof,{recursive:true,force:true}); }catch(e){} process.exit(code); };
const TO=(+o.timeout||60)*1000;
setTimeout(()=>{ console.error(`超时：${TO/1000} 秒内没做完（卡在「${stage}」）。页面可能死循环，或浏览器没响应；可加 --timeout 调长`); quit(3); },TO).unref();
const sl=ms=>new Promise(r=>setTimeout(r,ms));
let tg; for(let i=0;i<60;i++){ try{ const j=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); tg=j.find(t=>t.type==='page'); if(tg) break; }catch(e){} await sl(200); }
if(!tg){ console.error('Chrome 没起来'); quit(2); }
const ws=new WebSocket(tg.webSocketDebuggerUrl); await new Promise((r,j)=>{ ws.onopen=r; ws.onerror=()=>j(new Error('连不上浏览器调试端口')); });
let id=0; const P={}, logs=[];
ws.onmessage=m=>{ const d=JSON.parse(m.data); if(d.id&&P[d.id]){ P[d.id](d); delete P[d.id]; }
  if(d.method==='Runtime.exceptionThrown') logs.push('页面异常：'+(d.params.exceptionDetails.exception?.description||d.params.exceptionDetails.text).slice(0,400));
  if(d.method==='Runtime.consoleAPICalled'&&['error','warning'].includes(d.params.type)) logs.push('控制台'+d.params.type+'：'+d.params.args.map(a=>a.value||a.description).join(' ').slice(0,300)); };
const C=(method,params={})=>new Promise(r=>{ const i=++id; P[i]=r; ws.send(JSON.stringify({id:i,method,params})); });
stage='打开页面';
await C('Runtime.enable'); await C('Page.enable');
await C('Emulation.setDeviceMetricsOverride',{width:W,height:H,deviceScaleFactor:1,mobile:W<600});
await C('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:o.theme||'light'}]});
const hp=[]; if(o.hash) hp.push(o.hash.replace(/^#/,'')); if(o.skin) hp.push('skin='+encodeURIComponent(o.skin)); if(o.speed) hp.push('speed='+o.speed);
const url='file:///'+path.resolve(file).replace(/\\/g,'/')+(hp.length?'#'+hp.join('&'):'');
await C('Page.navigate',{url}); await sl(2600);
const ev=async js=>{ const r=await C('Runtime.evaluate',{expression:js,awaitPromise:true,returnByValue:true}); if(r.result?.exceptionDetails) logs.push('检查脚本出错：'+(r.result.exceptionDetails.exception?.description||r.result.exceptionDetails.text).slice(0,300)); return r.result?.result?.value; };
stage='摆到要截的样子';
const J=JSON.stringify, steps=[]; if(o.view) steps.push(`(document.querySelector('[data-view="${o.view}"]')||{click(){}}).click()`);
if(o.sample) steps.push(`playFrom(${J(o.sample)})`);
if(!o.hash||o.view||o.sample||o.beat!=null||o.station||o.focus||o.fit) steps.push('stop()');
if(o.beat!=null) steps.push(`setBeat(${+o.beat},false)`);
if(o.station) steps.push(`selectStation(${J(o.station)})`);
if(o.focus) steps.push(`st.follow=false;centerOn(N[${J(o.focus)}].x,N[${J(o.focus)}].y,${+(o.zoom||1)},0)`);
else if(o.station) steps.push(`st.follow=false;centerOn(N[${J(o.station)}].x,N[${J(o.station)}].y,${+(o.zoom||1)},0)`);
else if(o.fit) steps.push('st.follow=false;fit(false)');
else if(o.beat!=null) steps.push('st.follow=false;centerOn(TK.x,TK.y,null,0)');   // 跳拍后镜头对准货，免得货在画面外
steps.push("document.getElementById('toast').classList.remove('on')");
await ev(steps.join(';')); await sl(o.view||o.beat!=null||o.hash?2200:900);   // 切视图 / 跳拍后货要滑到新位置（最长约 2.1 秒），等它停稳再截
if(o.beat!=null&&!o.focus&&!o.station&&!o.fit) await ev('centerOn(TK.x,TK.y,null,0)');
stage='读自检';
const r=await ev(`({self:document.documentElement.dataset.selfcheck,fail:(window.__selfcheck||[]).filter(x=>!x.pass).map(x=>x.n+'：'+x.why),stations:Object.keys(S).length,edges:EDGES.length,samples:SAMPLES.length,skin:document.documentElement.dataset.skin||document.documentElement.dataset.theme||'auto',calm:document.documentElement.hasAttribute('data-calm'),overflowX:document.documentElement.scrollWidth-innerWidth})`);
console.log(JSON.stringify(r));
if(o.shot){ stage='截图'; await sl(200); const s=await C('Page.captureScreenshot',{format:'png'}); fs.writeFileSync(o.shot,Buffer.from(s.result.data,'base64')); console.log('截图：'+o.shot); }
console.log(logs.length?logs.join('\n'):'没有报错');
ws.close(); quit(logs.length||!r||(r.fail&&r.fail.length)?1:0);
