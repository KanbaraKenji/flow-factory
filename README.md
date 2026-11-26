# flow-factory — 把代码画成一条生产线

一个给 Claude Code / Codex 用的 skill：AI 读完一段代码或一个工作流，填一份 `flow.json`，构建器把它塞进渲染器，出一张**自包含的 HTML 流程图**——原料从左边进来，沿带子一站站加工，变成右边的成品；样例货会动，点它看它一路变成什么；故障视图标出每站出错时货去哪、要不要人关注；页面里能一键生成反馈文字贴回对话。

*flow-factory is an agent skill that turns code or a workflow into an interactive "production line" diagram: the AI reads the code, writes a `flow.json`, and `build.py` renders a single self-contained HTML page with animated sample cargo, a fault view, drill-down stations, a rehearsal mode and a report theme for slides. Prompts and docs are in Chinese.*

## 它长什么样

- **流程视图**：所有站卡同尺寸落在网格上，实带是正常顺序，岔路平时很淡、货走到才亮；成品库在线尾。
- **写入视图**：每站往哪写（数据库 / 文件 / 外部服务），货到站时写入包飞过去。
- **故障视图**：每站出错去向用三行人话说清——什么情况会走到、你会看到什么、AI 的判断（不用管 / 有隐患 / 需要补）；收不回的动作（删除 / 覆盖 / 外发）单独标记。
- **样例货与演练**：自动演典型样例或全部路线；演练模式每到岔路口由你选路，走到头可以收藏或复制成样例货贴回对话。
- **站内小流程**：一站里的判断要走好几步时画成盒中盒，镜头一镜到底推进去。
- **只演这条流程**：多条流程时只画当前这一条并重新排成紧凑的图。
- **汇报主题**：给 PPT 截图用，去掉装饰性动效，人工 / 检查站当关卡上色、其余中性灰，鼠标静止 2.5 秒控件淡出。
- **播放速度**：播放栏「速度」钮选 0.5× ~ 2×（快捷键 `[` `]`），记在浏览器里。
- 还有：寻路、总览（地铁图）、运行记录视图（`runs`）、版本对比（`--prev`）、六套皮肤、深浅色自动跟随、手机宽度可用。

## 安装

把整个目录放进 skill 目录即可，没有依赖：

| 环境 | 位置 |
|---|---|
| Claude Code | `~/.claude/skills/flow-factory/` |
| Codex | `~/.codex/skills/flow-factory/` |

构建只要 Python 3.8+（标准库）。无头自查另需 Node 18+（22 更好，自带 WebSocket）和本机 Chrome / Edge；找不到时设环境变量 `CHROME` 指向可执行文件。

## 用法

对 AI 说「画给我看」「这段怎么跑的」「画个流程图」，skill 会自动触发：它读代码、写 `flow.json`、构建、自检，然后把 HTML 给你（在 claude.ai 里会发布成 Artifact）。

手动跑：

```bash
python -X utf8 scripts/build.py flow.json -o flow.html          # 校验并构建；有错误不出页面
python -X utf8 scripts/build.py flow.json --check               # 只校验，顺便数全部路线
python -X utf8 scripts/build.py flow.json --prev old.json -o flow.html   # 附上一版做对比
node scripts/check.mjs flow.html --shot a.png                   # 无头打开：报错、自检、截图
node scripts/check.mjs flow.html --view fault --sample s1 --beat 3 --shot b.png
node scripts/check.mjs flow.html --skin report --hash "drill=1" --shot c.png   # 汇报配色 + 演练
```

页面能用链接直接打开到某个场景，汇报时很方便：

```
flow.html?skin=report&drill=1                 # 汇报配色，打开就进演练
flow.html#skin=report&sample=s2&view=fault    # 汇报配色，故障视图，先演 s2
<Artifact 链接>#skin.report~drill~speed.0.75  # claude.ai 的 Artifact 链接只能用这种写法
```

参数全表（`skin` `view` `sample` `drill` `station` `speed` `solo` `inner` `play`）见 `SKILL.md` 第 4 节。

想先看它自己是怎么工作的，构建 `docs/how-it-works.flow.json`：

```bash
python -X utf8 scripts/build.py docs/how-it-works.flow.json -o how-it-works.html
```

再看 `assets/example.flow.json`（网店订单，2 条线 10 站 4 件样例货）：

```bash
python -X utf8 scripts/build.py assets/example.flow.json -o example.html
```

## 文件

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 给 AI 的操作手册：什么时候出图、出图七步、写作规则、页面里有什么、接反馈 |
| `references/data-format.md` | `flow.json` 格式（schema `flow-factory/0`）：线、站、岔路、成品库、写入目标、样例货、站内小流程、五种结构、运行记录 |
| `references/case-law.md` | 判例库（append-only）：每条规则从哪次纠正来 |
| `references/report-style.md` | 汇报主题参照的风格规范 |
| `assets/renderer.html` | 渲染器模板：布局、布线、动画、视图、盒中盒、演练、寻路、配色、面板、自检 |
| `assets/example.flow.json` | 中性完整示例 |
| `scripts/build.py` | 校验 + 构建 |
| `scripts/check.mjs` | 无头 Chrome 检查：参数写错报错、默认 60 秒超时、能截汇报配色和链接场景 |
| `docs/how-it-works.flow.json` | 本 skill 自己的流程图（用它自己画的）：出图主线 7 站 + 反馈回炉 3 站，「校验构建」带站内小流程 |
| `tests/` | 回归测试：`python -X utf8 tests/run_tests.py --headless` |

## 测试

```bash
python -X utf8 tests/run_tests.py             # 32 个校验用例 + 示例构建 + 版本对比
python -X utf8 tests/run_tests.py --headless  # 再无头打开示例页（桌面 / 手机 / 深色 / 故障视图）
```

改了校验规则后 `--update` 重生成 `tests/expect.json`，人工看一遍 diff 再提交。

## 设计取向

- 字少、主次分明：站名 ≤ 8 字、岔路条件 ≤ 14 字，校验器把关；依据写进折叠区，首屏只留结论。
- 关注等级只回答「要不要你关注」，有隐患 / 需要补的必须给能直接改的建议。
- 画布交互先去模拟经营游戏找先例（点货即跟踪、拖动即离开、准星回到跟踪）。
- 动效要有含义；汇报主题里只留表示流程推进的那几种。
- 方法不设门槛：skill 给判断依据，取舍交给出图的 AI；只有会让页面坏掉的才进校验器的「错误」。

## 许可

MIT，见 `LICENSE`。
