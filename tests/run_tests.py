#!/usr/bin/env python3
"""flow-factory 回归测试：只用标准库。

  python -X utf8 tests/run_tests.py            # 校验器用例 + 构建示例
  python -X utf8 tests/run_tests.py --headless # 再用 scripts/check.mjs 无头打开示例页（要 Node 18+ 与本机 Chrome / Edge）

用例在 tests/fixtures/：bad_* 是故意写坏的 flow.json，ok_* 是应当通过的；每个用例的期望在 tests/expect.json
（expect = error / warn / clean，contains = 第一条错误或提醒里该出现的字）。
改了校验规则后：python -X utf8 tests/run_tests.py --update 重新生成 expect.json，再人工看一遍 diff。
退出码：0 全过；1 有用例不符。
"""
import json, os, subprocess, sys, shutil, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, 'scripts', 'build.py')
CHECK = os.path.join(ROOT, 'scripts', 'check.mjs')
FIX = os.path.join(HERE, 'fixtures')
EXP = os.path.join(HERE, 'expect.json')
EXAMPLE = os.path.join(ROOT, 'assets', 'example.flow.json')
PY = [sys.executable, '-X', 'utf8']


def run_build(src, *extra):
    r = subprocess.run(PY + [BUILD, src, *extra], capture_output=True, text=True, encoding='utf-8', errors='replace')
    lines = (r.stdout + r.stderr).splitlines()
    errs = [l[3:] for l in lines if l.startswith('错误：')]
    warns = [l[3:] for l in lines if l.startswith('提醒：')]
    lvl = 'error' if errs else 'warn' if warns else 'clean'
    return r.returncode, lvl, (errs or warns or [''])[0], lines


def main():
    update = '--update' in sys.argv
    headless = '--headless' in sys.argv
    exp = json.load(open(EXP, encoding='utf-8')) if os.path.exists(EXP) else {}
    fails, new = [], {}
    for f in sorted(os.listdir(FIX)):
        if not f.endswith('.json'):
            continue
        code, lvl, msg, _ = run_build(os.path.join(FIX, f), '--check')
        new[f] = {'expect': lvl, 'contains': msg[:22].rstrip()} if msg else {'expect': lvl}
        want = exp.get(f)
        if update or want is None:
            print(f'  记录  {f}: {lvl}  {msg[:60]}')
            continue
        ok = lvl == want['expect'] and want.get('contains', '') in msg
        if f.startswith('bad_') and lvl == 'clean':
            ok = False
        if lvl == 'error' and code == 0 or lvl != 'error' and code != 0:
            ok = False
        print(('  通过  ' if ok else '  不符  ') + f'{f}: 期望 {want["expect"]}「{want.get("contains", "")}」，得到 {lvl}「{msg[:60]}」')
        if not ok:
            fails.append(f)
    if update:
        json.dump(new, open(EXP, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=1)
        print(f'已重写 {EXP}（{len(new)} 条），请人工看一遍 diff')

    # 示例必须 0 错误 0 提醒，并能输出页面
    tmp = tempfile.mkdtemp(prefix='fftest')
    out = os.path.join(tmp, 'example.html')
    code, lvl, msg, lines = run_build(EXAMPLE, '-o', out)
    ok = code == 0 and lvl == 'clean' and os.path.exists(out) and os.path.getsize(out) > 100_000
    print(('  通过  ' if ok else '  不符  ') + f'assets/example.flow.json 构建：{lines[-1] if lines else "(无输出)"}')
    if not ok:
        fails.append('example')
    selfflow = os.path.join(ROOT, 'docs', 'how-it-works.flow.json')
    code, lvl, msg, lines = run_build(selfflow, '-o', os.path.join(tmp, 'self.html'))
    ok = code == 0 and lvl == 'clean'
    print(('  通过  ' if ok else '  不符  ') + f'docs/how-it-works.flow.json 构建：{lines[-1] if lines else "(无输出)"}')
    if not ok:
        fails.append('how-it-works')
    prev = os.path.join(HERE, 'example.prev.flow.json')
    code, lvl, msg, lines = run_build(EXAMPLE, '--prev', prev, '-o', os.path.join(tmp, 'cmp.html'))
    ok = code == 0 and lvl == 'clean'
    print(('  通过  ' if ok else '  不符  ') + f'示例 --prev 版本对比：{lines[-1] if lines else "(无输出)"}')
    if not ok:
        fails.append('example --prev')

    if headless and ok:
        node = shutil.which('node')
        if not node:
            print('  跳过  无头检查：找不到 node')
        else:
            # （参数, 期望退出码, 输出里要有的字）：汇报配色、链接直达演练、传错参数报错、超时以失败退出
            cases = [([], 0, ''), (['--size', '390x844'], 0, ''), (['--theme', 'dark'], 0, ''), (['--view', 'fault'], 0, ''),
                     (['--skin', 'report'], 0, '"calm":true'), (['--hash', 'skin.report~drill~speed.0.75'], 0, '"skin":"report"'),
                     (['--beat', '3', '--sample', 's1'], 0, ''), (['--sampel', 's1'], 2, '不认识的参数'), (['--timeout', '1'], 3, '超时')]
            for extra, want, has in cases:
                r = subprocess.run([node, CHECK, out, *extra], capture_output=True, text=True, encoding='utf-8', errors='replace')
                txt = r.stdout + r.stderr
                last = r.stdout.strip().splitlines()[-2:] if r.stdout.strip() else [r.stderr.strip().splitlines()[0][:200] if r.stderr.strip() else '']
                good = r.returncode == want and has in txt
                print(('  通过  ' if good else '  不符  ') + f'无头 {" ".join(extra) or "默认"}：{" ".join(last)}')
                if not good:
                    fails.append('headless ' + ' '.join(extra))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f'\n{len(fails)} 项不符' if fails else '\n全部通过')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
