#!/usr/bin/env python3
"""flow-factory 构建器：校验 flow.json，塞进渲染器，出一个自包含的 HTML。

用法：
  python build.py flow.json                 # 校验并输出 flow.html（同目录同名）
  python build.py flow.json -o out.html
  python build.py flow.json --check         # 只校验不输出
退出码：0 通过（可能有提醒）；1 有错误（不输出页面）。只用标准库。
"""
import json, sys, os, re, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, '..', 'assets', 'renderer.html')
KINDS = {'in', 'step', 'check', 'gate', 'hand', 'ai', 'out'}
END_KINDS = {'done', 'wait', 'blocked', 'returned', 'failed', 'stuck'}
FAULT_KINDS = {'retry', 'human', 'degrade', 'stop', 'stuck'}
LEVELS = {'ok', 'risk', 'bad'}
IRR = {'delete', 'overwrite', 'send'}
STORE_KINDS = {'db', 'kv', 'file', 'queue', 'api', 'log', 'notify'}
KEYS = {
    'top': {'schema', 'page', 'title', 'subtitle', 'summary', 'source', 'lines', 'stations', 'products', 'stores', 'samples', 'layout', 'runs'},
    'line': {'id', 'name', 'color', 'stations', 'product', 'then', 'trigger', 'per', 'via', 'every'},
    'station': {'name', 'kind', 'actor', 'does', 'detail', 'input', 'output', 'code', 'writes', 'reads', 'irreversible', 'default', 'branches', 'unhandled', 'runs', 'inner', 'split', 'join', 'modes'},
    'inner': {'lines', 'stations', 'layout', 'samples'},
    'branch': {'k', 'when', 'to', 'end', 'exit', 'fault', 'writes', 'runs', 'count', 'only', 'head'},
    'sample': {'id', 'name', 'badge', 'desc', 'input', 'path'},
    'step': {'st', 'br', 'form', 'in', 'mode', 'n'},
}
CODEY = re.compile(r'(\w+\(\)|_\w+_|==|!=|->|\bNone\b|\bnull\b|\btrue\b|\bfalse\b|\breturn\b|\[\w+\]|\w+\.\w+\(|^\w+_\w+$)')


def cjk_len(t):
    return sum(1 if ord(c) > 255 else 0.55 for c in str(t))


# 文字上限（汉字数）与 AI 腔词：用户 2026-10-24 裁定「描述删掉无意义的 AI 味叙述，岔路文字精简」
LIMITS = {'when': 14, 'does': 24, 'input': 16, 'output': 16, 'user_sees': 24, 'note': 48, 'form': 18, 'desc': 16, 'summary': 26}
AI_TONE = ['负责', '确保', '从而', '以便', '这一站', '该站', '进行', '相应', '用于', '能够', '旨在', '对其', '予以', '所有的', '一系列']


def too_long(text, kind):
    return cjk_len(text or '') > LIMITS[kind] + 0.5


def ai_tone(text):
    return [w for w in AI_TONE if w in (text or '')]


def validate(d, ctx=None):
    """ctx 为空 = 整张图；ctx = {'parent': 外面那一站, 'pid': 站 id 路径, 'stores': 外面的 stores} = 某一站的站内小流程。
    站内契约（用户 2026-10-25 批准）：站内每个出口（to: "exit"）对应外面一条岔路（exit 写外面岔路的 k），
    外面每条岔路都要有站内出口能走到。"""
    err, warn = [], []
    pre = f'站「{ctx["pid"]}」站内：' if ctx else ''
    E = lambda m: err.append(pre + m)
    W = lambda m: warn.append(pre + m)
    say = lambda m: print('信息：' + pre + m)
    if not ctx and d.get('schema') != 'flow-factory/0':
        E('schema 必须是 "flow-factory/0"')
    for k in (('lines', 'stations') if ctx else ('title', 'lines', 'stations', 'products')):
        if not d.get(k):
            E(f'缺字段 {k}')
    if err:
        return err, warn, (lambda *a, **k: None)

    def keys(obj, kind, where):
        bad = sorted(set(obj) - KEYS[kind])
        if bad:
            W(where + f' 有不认识的字段 {bad}（拼错了？不认识的字段会被忽略）')
    keys(d, 'inner' if ctx else 'top', '这一层')
    for L in d['lines']:
        keys(L, 'line', f'线「{L.get("id")}」')
    for sid, st in d['stations'].items():
        keys(st, 'station', f'站「{sid}」')
        for b in st.get('branches') or []:
            keys(b, 'branch', f'站「{sid}」岔路「{b.get("k")}」')
    samples = d.get('samples') or []
    for c in samples:
        keys(c, 'sample', f'样例货「{c.get("id")}」')
        for p in c.get('path') or []:
            keys(p, 'step', f'样例货「{c.get("id")}」的路线')
    if not ctx and (not d.get('summary') or not d['summary'].get('input') or not d['summary'].get('output')):
        W('summary.input / summary.output 没写：页头的「输入 → 成品」是让人一眼看懂全过程的地方，建议写')
    for k in ('input', 'output'):
        if too_long((d.get('summary') or {}).get(k), 'summary'):
            W(f'summary.{k} 太长（≤ {LIMITS["summary"]} 字）')
    if not ctx and d.get('title') and not (2 <= cjk_len(d['title']) <= 12.5):
        W(f'标题「{d["title"]}」建议 2~12 字（页头和画廊卡片放得下）')
    if not ctx and (d.get('layout') or {}).get('cols') is not None and not (isinstance(d['layout']['cols'], int) and 3 <= d['layout']['cols'] <= 10):
        W('layout.cols 要是 3~10 的整数，超出会被夹到 3 或 10')
    if not ctx and not (d.get('source') or {}).get('rev'):
        W('source.rev 没写：以后判断要不要重画全靠它')
    S = d['stations']
    prods = {p['id'] for p in d.get('products') or []}
    stores = {t['id'] for t in (ctx['stores'] if ctx else d.get('stores', []))}
    pks = [b.get('k') for b in (ctx['parent'].get('branches') or [])] if ctx else []
    for p in d.get('products') or []:
        if cjk_len(p.get('desc', '')) > 30:
            W(f'成品库「{p["id"]}」的 desc 太长（≤ 30 字），卡片放不下')
    for t in ([] if ctx else d.get('stores', [])):
        if cjk_len(t.get('name', '')) > 10:
            W(f'写入目标「{t["id"]}」的名字太长（≤ 10 字）')
        if t.get('kind') not in STORE_KINDS:
            W(f'写入目标 {t["id"]} 的 kind「{t.get("kind")}」不在 {sorted(STORE_KINDS)} 里')
    line_of = {}
    for L in d['lines']:
        if not L.get('id') or not L.get('name'):
            E('每条 line 要有 id 和 name')
        if ctx and L.get('product'):
            E(f'线 {L.get("id")} 写了 product：站内的线不进成品库，走到头用 to: "exit" 回到外面')
        elif L.get('product') and L['product'] not in prods:
            E(f'线 {L.get("id")} 的 product「{L["product"]}」不在 products 里')
        line_ids = {x.get('id') for x in d['lines']}
        if L.get('then') and L['then'] not in line_ids and L['then'] not in S:
            E(f'线 {L.get("id")} 的 then「{L["then"]}」既不是线也不是站')
        if L.get('product') and L.get('then'):
            W(f'线 {L.get("id")} 同时写了 product 和 then：二选一（现在 then 优先）')
        if not ctx and not L.get('product') and not L.get('then'):
            W(f'线 {L.get("id")} 没写 product 也没写 then：最后一站正常走完不知道去哪')
        for i, sid in enumerate(L.get('stations', [])):
            if sid not in S:
                E(f'线 {L["id"]} 里的站「{sid}」在 stations 里没有')
            if sid in line_of:
                E(f'站「{sid}」同时属于两条线 {line_of[sid]} 和 {L["id"]}')
            line_of[sid] = L['id']

    vias = {}
    for L in d['lines']:
        v = L.get('via')
        if v:
            if v not in S:
                E(f'线 {L.get("id")} 的 via「{v}」不是站')
            elif v in line_of:
                E(f'线 {L.get("id")} 的 via「{v}」是某条线上的站：公共站不放在线上')
            else:
                vias.setdefault(v, []).append(L)
        if L.get('every') and cjk_len(L['every']) > 8.5:
            W(f'线 {L.get("id")} 的 every「{L["every"]}」太长（≤ 8 字，比如「1 分钟」「每天 05:00」）')

    def head_of(sid):
        L = next((x for x in d['lines'] if sid in x.get('stations', [])), None)
        if not L:
            return None
        for _ in range(20):
            p = next((x for x in d['lines'] if then_of(x) == L['stations'][0]), None)
            if not p:
                break
            L = p
        return L.get('via') if L.get('via') in vias else L['stations'][0]

    def then_of(L):
        t = L.get('then')
        if not t:
            return None
        T = next((x for x in d['lines'] if x.get('id') == t), None)
        return T['stations'][0] if T else (t if t in S else None)

    def next_of(sid):
        for L in d['lines']:
            st = L['stations']
            if sid in st:
                i = st.index(sid)
                if i + 1 < len(st):
                    return st[i + 1]
                return then_of(L) or ('P:' + L['product'] if L.get('product') else None)
        return None

    inner_walk = {}
    for sid, s in S.items():
        where = f'站「{sid}」'
        if not s.get('name'):
            E(where + ' 没有 name')
        elif cjk_len(s['name']) > 8.5:
            E(where + f' 的站名「{s["name"]}」太长（≤ 8 个汉字），细节写进 does')
        if s.get('actor') and cjk_len(s['actor']) > 8.5:
            W(where + f' 的 actor「{s["actor"]}」太长（≤ 8 字），站卡放不下')
        if s.get('kind') not in KINDS:
            E(where + f' 的 kind「{s.get("kind")}」不在 {sorted(KINDS)} 里')
        if not s.get('does'):
            W(where + ' 没写 does（这一站干什么）')
        texts = [('does', s.get('does')), ('input', s.get('input')), ('output', s.get('output'))]
        u = s.get('unhandled') or {}
        texts += [('user_sees', u.get('user_sees')), ('note', (u.get('verdict') or {}).get('note'))]
        irs0 = s.get('irreversible')
        for ir in (irs0 if isinstance(irs0, list) else [irs0] if irs0 else []):
            texts += [('note', (ir.get('protection') or {}).get('note'))]
        for b in s.get('branches') or []:
            f = b.get('fault') or {}
            texts += [('when', b.get('when')), ('user_sees', f.get('user_sees')), ('note', (f.get('verdict') or {}).get('note'))]
        for kind, t in texts:
            if t and too_long(t, kind):
                W(where + f' 的 {kind}「{t[:20]}…」太长（≤ {LIMITS[kind]} 字）：只写要点，删掉解释和铺垫')
            hit = ai_tone(t)
            if hit:
                W(where + f' 的 {kind} 有 AI 腔「{"、".join(hit)}」：换成直接的说法')
        if not s.get('input') or not s.get('output'):
            W(where + ' 没写 input / output：货在这一站从什么变成什么，是看懂全过程的关键')
        brs = s.get('branches') or []
        if not brs:
            E(where + ' 没有 branches')
        ks = [b.get('k') for b in brs]
        if len(set(ks)) != len(ks):
            E(where + ' 有重复的岔路 k')
        if s.get('default') and s['default'] not in ks:
            E(where + f' 的 default「{s["default"]}」不是它的岔路')
        if sid not in line_of and sid not in vias and not any((b.get('to') == sid) for x in S.values() for b in x.get('branches', [])):
            W(where + ' 不属于任何线，也没有别的站跳过来：画出来会是一座孤岛')
        has_fault = False
        for b in brs:
            bw = where + f' 岔路「{b.get("k")}」'
            if not b.get('when'):
                E(bw + ' 没写 when（什么情况走这条）')
            elif CODEY.search(b['when']):
                W(bw + f' 的 when 像代码「{b["when"]}」：写人话，写触发条件本身')
            to = b.get('to', 'next')
            if to == 'again':
                h = b.get('head') or head_of(sid)
                if b.get('head') and b['head'] not in S:
                    E(bw + f' 的 head「{b["head"]}」不是站')
                if not h:
                    E(bw + ' 是 again（下一轮从线头再来），但这一站不在任何线上')
                else:
                    root = next((x for x in d['lines'] if x['stations'][0] == h or x.get('via') == h), {})
                    if not (root.get('every') or root.get('trigger')):
                        W(bw + ' 是 again，但线头那条线没写 every / trigger：看图的人不知道「下一轮」是什么时候')
                c = b.get('count')
                if c is not None and (not isinstance(c, dict) or not c.get('name')):
                    E(bw + ' 的 count 要写成 {"name": "值守尝试", "max": 3}')
            elif to == 'next' and sid in vias:
                pass
            elif to == 'next':
                if sid not in line_of:
                    E(bw + ' 是 next，但这一站不属于任何线，没有「下一站」')
                elif next_of(sid) is None:
                    E(bw + (' 是 next，但它是站内线的最后一站：改成 to: "exit"，exit 写走外面哪条岔路' if ctx else ' 是 next，但它是线的最后一站且线没写 product / then'))
            elif to == 'exit':
                if not ctx:
                    E(bw + ' 用了 to: "exit"：只有站内小流程能用它')
                elif b.get('exit') not in pks:
                    E(bw + f' 的 exit「{b.get("exit")}」不是外面那一站的岔路（外面有 {pks}）')
            elif to == 'end' and ctx:
                E(bw + ' 停在了站内：站内的货最终都要出站，用 to: "exit" 并写 exit')
            elif to == 'end':
                e = b.get('end') or {}
                if e.get('kind') not in END_KINDS:
                    E(bw + f' 停在这里，end.kind 要是 {sorted(END_KINDS)} 之一')
                if not e.get('label'):
                    W(bw + ' 没写 end.label（货停住时显示什么）')
            elif to not in ('back', 'exit', 'again') and to not in S and to not in prods:
                E(bw + f' 的 to「{to}」既不是站也不是成品库')
            f = b.get('fault')
            if f:
                has_fault = True
                if f.get('kind') not in FAULT_KINDS:
                    E(bw + f' 的 fault.kind 要是 {sorted(FAULT_KINDS)} 之一')
                if not f.get('user_sees'):
                    E(bw + ' 的 fault 缺 user_sees（用户会看到什么）')
                v = f.get('verdict') or {}
                if v.get('level') not in LEVELS:
                    E(bw + ' 的 fault 缺 verdict.level（ok / risk / bad）')
                elif v.get('level') in ('risk', 'bad') and '建议' not in (v.get('note') or ''):
                    E(bw + ' 判成有隐患 / 需要补，verdict.note 里要写「建议：……」')
            elif to == 'end' and (b.get('end') or {}).get('kind') in ('failed', 'stuck', 'blocked', 'wait', 'returned'):
                W(bw + ' 停在非成功结局却没写 fault：故障视图里看不到它的后果和判断')
        if not has_fault:
            u = s.get('unhandled')
            if not u:
                W(where + ' 一个出错出口都没有，也没写 unhandled：故障视图会标「未处理」，建议读代码后写清出错会怎样')
            elif (u.get('verdict') or {}).get('level') not in LEVELS:
                E(where + ' 的 unhandled 缺 verdict.level')
        irs = s.get('irreversible')
        for ir in (irs if isinstance(irs, list) else [irs] if irs else []):
            if ir.get('type') not in IRR:
                E(where + f' 的 irreversible.type 要是 {sorted(IRR)} 之一')
            p = ir.get('protection') or {}
            if p.get('level') not in LEVELS:
                E(where + ' 的 irreversible 缺 protection.level')
            elif p.get('level') in ('risk', 'bad') and '建议' not in (p.get('note') or ''):
                E(where + ' 的收不回动作判成有隐患 / 需要补，protection.note 里要写「建议：……」')
        for w in s.get('writes', []) + s.get('reads', []):
            if w.get('store') not in stores:
                E(where + f' 读写的目标「{w.get("store")}」不在 stores 里')
        md = s.get('modes')
        mids = []
        if md is not None:
            if not isinstance(md, list) or len(md) < 2 or not all(isinstance(m, dict) and m.get('id') and m.get('name') for m in md):
                E(where + ' 的 modes 要是两项以上的 [{"id", "name", "how", "diff": {...}}]')
            else:
                mids = [m['id'] for m in md]
                for m in md:
                    if cjk_len(m['name']) > 4.5:
                        W(where + f' 的入口名「{m["name"]}」太长（≤ 4 字，卡上要并排放两个）')
        for b in brs:
            if b.get('only') and b['only'] not in mids:
                E(where + f' 岔路「{b.get("k")}」的 only「{b["only"]}」不是这一站 modes 里的入口')
        for key in ('split', 'join'):
            v = s.get(key)
            if v is not None and not isinstance(v, dict):
                E(where + f' 的 {key} 要写成 {{"by": "镜"}}（split 可加 "n": 6）')
        inn = s.get('inner')
        if inn is not None:
            if not isinstance(inn, dict) or not inn.get('lines') or not inn.get('stations'):
                E(where + ' 的 inner 要有 lines 和 stations')
            else:
                clash = set(inn['stations']) & set(S)
                if clash:
                    E(where + f' 站内的站 id 和外面重名：{sorted(clash)}')
                sub = {'parent': s, 'pid': (ctx['pid'] + '/' if ctx else '') + sid, 'stores': ctx['stores'] if ctx else d.get('stores', [])}
                ie, iw, iwalk = validate(inn, sub)
                err.extend(ie); warn.extend(iw); inner_walk[sid] = (iwalk, ie, iw)
                exits = {b.get('exit') for x in inn['stations'].values() for b in (x.get('branches') or []) if b.get('to') == 'exit'}
                miss = [k for k in (b.get('k') for b in brs) if k not in exits]
                if miss:
                    E(where + f' 的岔路 {miss} 在站内没有出口能走到：站内出口要和外面的岔路一一对得上')
    def check_path(cw, path, expect_exit=None):
        came = None
        for i, p in enumerate(path):
            s = S.get(p.get('st'))
            if not s:
                E(cw + f' 第 {i+1} 步的站「{p.get("st")}」不存在')
                return
            b = next((x for x in s.get('branches', []) if x.get('k') == p.get('br')), None)
            if not b:
                E(cw + f' 第 {i+1} 步：站「{p["st"]}」没有岔路「{p.get("br")}」')
                return
            if too_long(p.get('form'), 'form'):
                W(cw + f' 的 form「{p["form"][:20]}…」太长（≤ {LIMITS["form"]} 字）')
            if p.get('mode') is not None and p['mode'] not in [m.get('id') for m in (s.get('modes') or [])]:
                E(cw + f' 第 {i+1} 步的 mode「{p["mode"]}」不是站「{p["st"]}」的入口')
            if p.get('n') is not None and not (isinstance(p['n'], int) and p['n'] > 0):
                E(cw + f' 第 {i+1} 步的 n 要是正整数（这时货拆成几份）')
            if p.get('in') is not None:
                if p['st'] not in inner_walk:
                    E(cw + f' 第 {i+1} 步写了 in，但站「{p["st"]}」没有站内小流程')
                elif not p['in']:
                    E(cw + f' 第 {i+1} 步的 in 是空的')
                else:
                    fn, ie, iw = inner_walk[p['st']]; n1, n2 = len(ie), len(iw)  # 站内那层的消息落在它自己的列表里，搬过来
                    fn(cw + f' 第 {i+1} 步的站内路线', p['in'], expect_exit=p['br'])
                    err.extend(ie[n1:]); warn.extend(iw[n2:])
            to = b.get('to', 'next')
            if i + 1 < len(path):
                if to == 'exit':
                    E(cw + f' 第 {i+1} 步已经出站了，后面不能再有站内的步子')
                    return
                want = path[i + 1].get('st')
                if to == 'next' and p['st'] in vias:
                    if want not in [L['stations'][0] for L in vias[p['st']]]:
                        E(cw + f' 第 {i+1}→{i+2} 步：公共站「{p["st"]}」之后要进它接的某条线的第一站，写的却是「{want}」')
                        return
                    came = p['st']
                    continue
                real = next_of(p['st']) if to == 'next' else came if to == 'back' else (b.get('head') or head_of(p['st'])) if to == 'again' else to
                if real != want:
                    E(cw + f' 第 {i+1}→{i+2} 步接不上：「{p["st"]}」走「{b["k"]}」去的是「{real}」，下一步却写的「{want}」')
                    return
            elif expect_exit is not None:
                if to != 'exit' or b.get('exit') != expect_exit:
                    E(cw + f' 最后一步要从站内出口走外面的「{expect_exit}」，写的却是「{b.get("exit") if to == "exit" else to}」')
            elif ctx:
                if to != 'exit':
                    W(cw + ' 最后一步没有出站')
            elif to not in ('next', 'end') and to not in prods:
                W(cw + ' 最后一步既没进成品库也没停住，画面上会停在最后一站')
            came = p['st']

    # 运行记录（可选，接日志 / 数据库统计出来的真实次数；没有就不写，页面不出「运行」视图）
    if not ctx and d.get('page') not in (None, 'dev', 'monitor'):
        E('page 只能是 "dev"（研发流程图，默认）或 "monitor"（运行监控图）')
    if not ctx and d.get('page') == 'monitor' and not d.get('runs'):
        W('page 是 monitor（运行监控图），但没有 runs：页面会没有运行数据可看')
    if not ctx and d.get('runs') is not None:
        r = d['runs']
        if not isinstance(r, dict):
            E('runs 要写成 {"from": "10-24 00:00", "to": "10-25 23:59", "total": 120, "note": "数据来源"}')
        for sid, x in S.items():
            for obj, where in [(x.get('runs'), f'站「{sid}」')] + [(b.get('runs'), f'站「{sid}」岔路「{b.get("k")}」') for b in x.get('branches', [])]:
                if obj is None:
                    continue
                if not isinstance(obj, dict) or not isinstance(obj.get('n', 0), int):
                    E(where + ' 的 runs 要写成 {"n": 走过几次, "last": "最近一次", "stuck": 卡住几件(只站点)}')
    if any(x.get('split') for x in S.values()) and not any(x.get('join') for x in S.values()):
        W('有扇出站（split）却没有汇合站（join）：拆出去的份永远合不回来，确认一下')

    # 样例货
    sids = set()
    for c in samples:
        cw = f'样例货「{c.get("id")}」'
        if c.get('id') in sids:
            E(cw + ' id 重复')
        sids.add(c.get('id'))
        if not c.get('name'):
            E(cw + ' 没有 name')
        if c.get('badge') and cjk_len(c['badge']) > 1.2:
            W(cw + f' 的 badge「{c["badge"]}」要一个字（货箱上只放得下一个字）')
        if not c.get('input'):
            W(cw + ' 没写 input（原料）')
        if too_long(c.get('desc'), 'desc'):
            W(cw + f' 的 desc 太长（≤ {LIMITS["desc"]} 字）')
        path = c.get('path') or []
        if not path:
            E(cw + ' 没有 path')
            continue
        check_path(cw, path)
    walked = {(p.get('st'), p.get('br')) for c in samples for p in (c.get('path') or [])}
    def lv(b):
        return (b.get('fault') or {}).get('verdict', {}).get('level')
    bad = [f'{sid}.{b["k"]}' for sid, x in S.items() for b in x.get('branches', []) if lv(b) == 'bad' and (sid, b['k']) not in walked]
    risk = [f'{sid}.{b["k"]}' for sid, x in S.items() for b in x.get('branches', []) if lv(b) == 'risk' and (sid, b['k']) not in walked]
    # 全部路线：与渲染器 buildRoutes 同一套规则（每站先走正常那条；同站最多进两次；同一条岔路一条路线里不走两次）
    CAP = 60
    routes = []
    def walk(sid, path):
        if len(routes) > CAP or len(path) > 40 or sid not in S:
            return
        if sum(1 for p in path if p[0] == sid) >= 2:
            return
        st = S[sid]
        for b in sorted(st.get('branches', []), key=lambda b: b.get('k') != st.get('default')):
            if len(routes) > CAP:
                return
            if (sid, b['k']) in path:
                continue
            np = path + [(sid, b['k'])]
            to = b.get('to', 'next')
            if to in ('end', 'exit'):
                routes.append(np); continue
            if to == 'next' and sid in vias:
                for L in vias[sid]:
                    walk(L['stations'][0], np)
                continue
            nx = (path[-1][0] if path else None) if to == 'back' else next_of(sid) if to == 'next' else (b.get('head') or head_of(sid)) if to == 'again' else (to if to in S else None)
            if not nx or str(nx).startswith('P:'):
                routes.append(np); continue
            walk(nx, np)
    got = ({then_of(L) for L in d['lines']} | {L['stations'][0] for L in d['lines'] if L.get('via') in vias}) - {None}
    for v in vias:
        walk(v, [])
    for L in d['lines']:
        if L['stations'] and L['stations'][0] not in got:
            walk(L['stations'][0], [])
    n = len(routes)
    # 只报事实，要不要写样例货、写几件由出图的人判断（用户 2026-10-25：skill 给方法和建议，不给硬门槛）
    shown = f'超过 {CAP} 条（页面只算前 {CAP} 条）' if n > CAP else f'共 {n} 条'
    longest = max((len(r) for r in routes), default=0)
    if ctx:
        say(f'{len(d["stations"])} 站，全部路线{shown}，最长 {longest} 步；外面的自动播放默认不进站内，样例货某一步写了 in 才进')
    elif samples:
        say(f'全部路线{shown}，最长 {longest} 步；自动播放演你写的 {len(samples)} 件样例货，全部路线在菜单「全部路线」组里')
    else:
        say(f'全部路线{shown}，最长 {longest} 步；没写 samples，自动播放把全部路线挨个演一遍')
    if not samples:  # 不写样例货时自动播放演的是全部路线，算它们走到过的岔路
        covered = {x for r in routes[:CAP] for x in r}
        bad = [k for k in bad if tuple(k.split('.', 1)) not in covered]
        risk = [k for k in risk if tuple(k.split('.', 1)) not in covered]
    if bad:
        W(f'「需要补」的出错去向没有样例货走到：{"、".join(bad)}。至少给它一件样例货，让人看着它出事')
    if risk:
        say(f'{len(risk)} 条「有隐患」的出错去向没有样例货走到（不强求，挑最要紧的走一两条即可）：{"、".join(risk[:8])}')
    return err, warn, check_path


LVN = {'ok': '不用管', 'risk': '有隐患', 'bad': '需要补'}


def compare(old, new):
    """两版 flow.json 的差别：新加 / 删掉 / 挪动（换线或前后站变了）/ 改动（文字、岔路、去向、判断）。每站一条，原因用人话拼起来。"""
    so, sn = old.get('stations', {}), new.get('stations', {})
    both = set(so) & set(sn)   # 只按两版都有的站比前后：旁边加了 / 删了一站不算挪动
    def pos(d):
        P = {}
        for L in d.get('lines', []):
            st = [x for x in L.get('stations', []) if x in both]
            for i, x in enumerate(st):
                P[x] = (L.get('id'), L.get('name'), st[i - 1] if i else None, st[i + 1] if i + 1 < len(st) else None)
        return P
    po, pn = pos(old), pos(new)
    lv = lambda b: ((b.get('fault') or {}).get('verdict') or {}).get('level')
    items = []
    for sid, x in sn.items():
        if sid not in so:
            items.append({'k': 'add', 'st': sid, 'name': x.get('name', sid), 'what': '新加的站'})
            continue
        o, why = so[sid], []
        for f, lab in (('name', '站名'), ('does', '一句话'), ('kind', '种类'), ('actor', '执行者')):
            if (o.get(f) or '') != (x.get(f) or ''):
                why.append(f'{lab}改了')
        bo = {b.get('k'): b for b in o.get('branches', [])}
        bn = {b.get('k'): b for b in x.get('branches', [])}
        for k in bn.keys() - bo.keys():
            why.append(f'新岔路「{bn[k].get("when", k)}」')
        for k in bo.keys() - bn.keys():
            why.append(f'去掉岔路「{bo[k].get("when", k)}」')
        for k in bn.keys() & bo.keys():
            a, b = bo[k], bn[k]
            if a.get('when') != b.get('when'):
                why.append(f'岔路条件「{a.get("when")}」→「{b.get("when")}」')
            if a.get('to', 'next') != b.get('to', 'next'):
                why.append(f'岔路「{b.get("when", k)}」改道')
            if lv(a) != lv(b) and (lv(a) or lv(b)):
                why.append(f'岔路「{b.get("when", k)}」的判断 {LVN.get(lv(a), "无")} → {LVN.get(lv(b), "无")}')
        if bool(o.get('inner')) != bool(x.get('inner')) or json.dumps(o.get('inner'), sort_keys=True) != json.dumps(x.get('inner'), sort_keys=True):
            why.append('站内流程改了' if o.get('inner') and x.get('inner') else '加了站内流程' if x.get('inner') else '去掉了站内流程')
        moved = po.get(sid) != pn.get(sid)
        if moved:
            a, b = po.get(sid), pn.get(sid)
            if a and b and a[0] != b[0]:
                txt = f'从「{a[1]}」挪到「{b[1]}」'
            else:
                txt = '前后站变了' + (f'（现在接在「{sn[b[2]]["name"]}」后面）' if b and b[2] in sn else '')
            items.append({'k': 'move', 'st': sid, 'name': x.get('name', sid), 'what': '；'.join([txt] + why)})
        elif why:
            items.append({'k': 'mod', 'st': sid, 'name': x.get('name', sid), 'what': '；'.join(why)})
    for sid, x in so.items():
        if sid not in sn:
            items.append({'k': 'del', 'st': None, 'id': sid, 'name': x.get('name', sid), 'what': '这一站删掉了'})
    return {'from': (old.get('source') or {}).get('rev') or '上一版', 'items': items}


def build(src, out, prev=None):
    d = json.load(open(src, encoding='utf-8'))
    err, warn, _ = validate(d)
    for w in warn:
        print('提醒：' + w)
    for e in err:
        print('错误：' + e)
    if err:
        print(f'没有输出页面：{len(err)} 个错误，{len(warn)} 个提醒')
        return 1
    if out is None and not prev:
        return 0
    if out is None:
        out = os.devnull
    if prev:
        d['compare'] = compare(json.load(open(prev, encoding='utf-8')), d)
        c = d['compare']['items']
        print(f'信息：对比上一版（{d["compare"]["from"]}）：' + ('、'.join(f'{n} {sum(1 for x in c if x["k"] == k)}' for k, n in (('add', '新加'), ('mod', '改动'), ('move', '挪动'), ('del', '删掉')) if any(x['k'] == k for x in c)) or '没有差别'))
    tpl = open(TPL, encoding='utf-8').read()
    data = json.dumps(d, ensure_ascii=False).replace('</', '<\\/')
    title = re.sub(r'[<>&]', '', d.get('title', '流程图'))
    html = tpl.replace('__FLOW_TITLE__', title).replace('__FLOW_DATA__', data)
    open(out, 'w', encoding='utf-8').write(html)
    print(f'已输出 {out}（{len(html)//1024} KB）：0 个错误，{len(warn)} 个提醒')
    return 0


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('-o', '--out')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--prev', help='上一版 flow.json：页面里多出「对比上一版」')
    a = ap.parse_args()
    out = None if a.check else (a.out or os.path.splitext(a.src)[0] + '.html')
    sys.exit(build(a.src, out, a.prev))
