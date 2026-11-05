# spellcode

检查源码里的拼写错误。零配置，单文件，只报有把握的。

```bash
python spellcode.py            # 检查当前目录
python spellcode.py src tests  # 检查指定目录
python spellcode.py --fix src  # 就地修正
```

只用标准库，Python 3.9 以上，没有任何依赖，没有配置文件。

---

## 它解决的是什么问题

代码里的错拼，人眼扫不出来，CI 也不会拦。`recieve` 写一次，后面所有人都跟着写 `recieve`——因为它看起来「跟别处一样」。

市面上的源码拼写检查器不少，但多数有两个毛病：要么把哈希、版本号、缩写当成错别字，让你在一屏红字里翻半天；要么需要一份几十行的配置来告诉它「这个词别管」。

`spellcode` 的取舍很直接：**词典里只放「唯一确定」的错拼，代码里只查「确实像词」的地方。** 漏掉一些冷僻错拼可以接受，误报不可接受。

---

## 三层判断

一行代码进来，要过三道关才可能被报出来。

### 第一层：这段东西像词吗

`sha256`、`9ba8df137936`、`FhDomw6BaHU`、`deadbeef`、`v2.1.3`、`x86_64` 都不像人写的词。它们有共同特征：字母数字混杂、数字占比高、几乎没有元音、或者长得离谱。

```python
COMMIT = "9ba8df137936"      # 数字占 10/12，跳过
YT_ID  = "FhDomw6BaHU"       # 拆出来是 Fh / Domw6 / Ba / HU，全是两三个字母的碎片，跳过
VER    = "v2.1.3"            # 语义化版本，整段屏蔽
URL    = "https://x.com/seperate/guide"   # URL 整段屏蔽
```

这一层是误报的主要防线。最常见的两类误报——`FhDomw6BaHU` 里的 `Ba` 被当成单词、`go.mod` 里 `9ba8df137936` 的 `ba` 被当成单词——都死在这一层。

### 第二层：怎么拆词

标识符要拆开才知道里面有没有错拼，但拆错地方就会凭空造出词。

```
recieve_payload   -> recieve, payload
RecievePayload    -> Recieve, Payload
MAX_LENGHT        -> MAX, LENGHT
HTMLParser        -> HTML, Parser      # 缩写不切开
First10HTMLTokens -> First, 10, HTML, Tokens
```

规则就三条：下划线断、大小写转换处断、字母数字交界断；连续大写视为缩写，整体保留。

### 第三层：词典里有没有

词典不是「正确词表」，是「错拼 → 正确写法」的对照表。查的时候先查整词，再剥一层后缀查词干：

| 遇到 | 命中 | 结果 |
|---|---|---|
| `recieve` | `recieve -> receive` | `receive` |
| `recieves` | 剥 `s` 命中 `recieve` | `receives`，不是 `receivees` |
| `supressed` | 剥 `ed` 命中 `supress` | `suppressed` |
| `standard` | 剥 `d` 命中 `standar`，但修正结果就是原词 | 不报 |

最后一行是关键。`standar` 是错拼，`standard` 不是——如果只做无脑后缀剥离，`standard` 会被「修正」成 `standardd`。

---

## 上手

```bash
git clone https://github.com/z15346183030/spellcode
cd spellcode
python spellcode.py examples
```

输出：

```
examples\demo.py:9:5  recieve -> receive
    def recieve_payload(raw, timeout=30):
        ^^^^^^^
examples\demo.py:10:15  seperate -> separate
        """从示例文件取数据。seperate 这里故意拼错。"""
                         ^^^^^^^^

2 处可疑拼写，分布在 1 个文件；共检查 1 个文件、37 行，用时 0.00s
确认无误的可以加一行注释 spell:ignore 跳过。
```

同一份文件里还埋了版本号、哈希、随机 ID、URL、`DELETEs` 这样的复数形式，一个都没被报出来。

修掉：

```bash
python spellcode.py --fix examples
```

```
examples\demo.py  已修正 2 处

修正 2 处，涉及 1 个文件；共检查 1 个文件、37 行，用时 0.01s
```

---

## 不想改的地方，加一行注释

没有配置文件，需要放行就在代码里说清楚。

```python
# spell:ignore                      这一行剩下的部分不检查
# spell:ignore-next-line            下一行不检查
# spell:ignore-file                 整个文件不检查
msg = "recieve"  # spell:ignore=recieve,seperate   只放行这几个词
```

比在 TOML 里写 `extend-ignore-re` 正则更直接：放行的理由就写在放行的地方，review 的时候看得见。

---

## 接入 CI 与编辑器

```bash
python spellcode.py --json src     # 每行一个 JSON 对象
python spellcode.py --stat src     # 只要统计
python spellcode.py --quiet src    # 什么都不打印，只看退出码
```

退出码：`0` 干净，`2` 有发现，`1` 参数或路径错误。

```bash
# pre-commit 之类的钩子里
python spellcode.py --quiet src || { echo "有拼写问题，跑 --fix 看看"; exit 1; }
```

`--json` 的输出长这样：

```json
{"path": "src/a.py", "line": 9, "col": 5, "word": "recieve", "suggestion": "receive", "context": "def recieve_payload(raw):"}
```

---

## 实测

| 语料 | 文件 | 行数 | 报告 | 结果 |
|---|---|---|---|---|
| 本机 4 个 Python 仓库 | 40 | 6,124 | 0 | 无 |
| 本仓库（不含示例）+ 索引仓库 | 16 | 3,420 | 0 | 无 |
| CPython 标准库（含 site-packages） | 1,000 | 404,927 | 9 | 9 处全是真错拼 |

那 9 处分别是 `seperator`（4 次，pygments）、`prefered`（resolvelib）、`occuring`、`minumum`、`ommit`、`compatability`——没有一处是哈希、版本号或缩写被误伤。

速度：40 万行 10.5 秒，约 3.8 万行/秒。单核、纯 Python、单文件。

---

## 词典是怎么收的

大约 435 条，只收「一个错拼唯一对应一个正确写法」的词。刻意不收三类：

- **本身是合法英文词的**：`dependant`、`thru`、`alot`
- **是某个正确词前缀的**：`delet`、`optio`——否则 `DELETEs` 会被报成 `DELET`
- **两三个字母的碎片**：`ba`、`teh` 之外的短词在哈希里太容易撞上

想加词，直接改 `spellcode.py` 顶部的 `TYPOS` 表，键是错拼、值是正确写法，全小写。

---

## 局限

- **只查英文错拼**。中文、其他语言的拼写不查。
- **不判断上下文**。注释里写 `# recieve` 会报，字符串里写 `"recieve"` 也会报——它不知道哪个是给人看的、哪个是协议字段。
- **词典是手工维护的**，覆盖率远不如那些带完整词库的方案。它的定位是「在 CI 里长期开着也不会烦你的那个」。
- **不做 Git 历史扫描**，只看工作区里的文件。

---

## 许可证

MIT。见 [LICENSE](LICENSE)。
