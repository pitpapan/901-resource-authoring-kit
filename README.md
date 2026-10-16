# 901 Resource Authoring Kit

**901 资源撰写库**：供 Sol 等具备文件读取能力的模型使用，包含901融合规则、PHB／RE完整来源、特性预算、定标样板和本地检索工具。整个目录可以独立放入Git仓库，再克隆到别处使用；无需原项目、旧磁盘、原会话、额外插件或Python第三方包。

模型由使用者选择和运行；本库不自行调用模型API。建议常规撰写使用Sol High。库中不包含完整世界设定、人物状态或个人取得记录，具体主题由本次需求提供。

## 拉取后开始

环境：Python **3.9及以上**（本次实测3.12），仅标准库；Git仅用于版本管理／拉取，不是撰写工具的运行依赖。普通读取和生成无需解包CHM，Windows的`hh.exe`只用于从原始CHM重新提取源文件。

1. 克隆或下载**整个仓库**，进入根目录；保留`.gitattributes`，它保证原文哈希不受Git换行转换影响。
2. 运行 `python -X utf8 tools/check_library.py`。Linux/macOS若命令名为`python3`，替换命令前缀即可。
3. 在支持本地文件和命令工具的Sol会话中打开这个目录，直接发送类似请求：

> 请按本库AGENTS.md与authoring/README.md，撰写一项D级、无能量的普通军伍撤离技艺，采用901规则。强调实际新增选择，给出效果、动作、预算和XP候选，明确类比定价。只使用本库和本次需求，结果写入outputs/撤离技艺.md。

想更精确地说明对象、数量、风格和限制，可填写 [需求简表](authoring/brief-template.md)。`outputs/`按需创建，默认不进入Git。对不同主题提出新需求即可，不需要先读取旧聊天。

## 先看哪里

- 模型工作约定：[AGENTS.md](AGENTS.md)；写作流程：[authoring/README.md](authoring/README.md)
- 已采用规则：[rules/README.md](rules/README.md)；常用短卡：[common_rules.md](authoring/common_rules.md)
- 特性预算：[traits.md](authoring/traits.md)；设计比较：[samples.md](authoring/samples.md)
- 完整原书与检索方式见下文；规则快照日期为2026-10-17，历史证据与采用边界见[rules/source-notes.md](rules/source-notes.md)。

已收录 **PHB v0.3 16 页＋RE v1.03先行版 964 页，共 980 页**。原有 185 页及其路径保留，补入 795 页；原始 HTML、HHC、HHK、配套图片与两份 CHM 均保留。完整指这两份原书实际存在的文件；原 RE 目录中两个本已缺失的目标仍作为来源缺口记录，不补造正文。

**来源收录不等于 901 采用。** 规则优先看 [901 已采用核心](rules/901-core-rules-v0.1.md)，创作从 [资源撰写入口](authoring/README.md) 开始。

## 按需入口

- [按问题找规则与机制](indices/mechanisms.md)
- [资源：723 页](indices/resources.md)（能力组、技艺、血统、改造、物品、能量等）
- [特性列表：5 页](indices/traits.md)；[怪物：19 页](indices/bestiary.md)
- [PHB](indices/PHB.md)；[核心规则](indices/rules.md)；[版本与序言](indices/meta.md)
- [杂项、待重置、移除、施工：48 页](indices/misc.md)

## 少量检索，再读原段落

从本目录执行（只需 Python 标准库；`-X utf8` 避免 Windows 控制台乱码）：

```powershell
python -X utf8 tools/library.py cards CR-04 TB-01 T-02 S-01 S-08
python -X utf8 tools/library.py search 剑盾战斗 --kind rules --limit 3
python -X utf8 tools/library.py search --kind resources --tag 协作 --limit 5
python -X utf8 tools/library.py search 武士 C级 --kind resources --limit 2
python -X utf8 tools/library.py read 'content/RE/02_resources/能力组/近战类型/武器类型/武士.md' --start 6 --lines 32
```

`catalog.jsonl`／`catalog.tsv` 为全页目录，含原文路径、版本、来源状态、哈希。`passages.jsonl` 为 **5004 个有少量重叠的定位片段**，包含行号、原文和粗略机制标签。它不是全书人工逐技能拆解，也不自动推断阶段价格和预算。默认搜索排除待重置、已移除、施工内容；确需比较时加 `--include-legacy`。`称号／训练→能力组`、`技能→技艺` 等别名仅帮助搜索，不修改原文名称。

## 来源与维护

每篇 Markdown 顶部链接原始 HTML。新增页按文本块转换；表格单元内容保留，复杂合并单元格、图像和排版必须核对原始 HTML。保留原有转码页，不批量重排已被引用的内容。

[来源指纹与原书缺页](source_archives/provenance.json) 记录 CHM 的 SHA-256；[转换报告](REPORT.md) 说明完整性和边界。

```powershell
python -X utf8 tools/check_library.py
python -X utf8 tools/library.py index
```

第一条只读检查完整性及库内链接（含路径越界与文件名大小写）；第二条重建自动索引，不修改正文或人工规则／样板卡。运行 `python -X utf8 tools/smoke_test.py` 可从其他工作目录检查取卡、搜索和读取。若要重新核对保留的 HTML 并重建目录，可执行：

```powershell
python -X utf8 tools/library.py import --re source_html/RE --phb source_html/PHB
```

首次从 CHM 重建原始文件时，使用 Windows `hh.exe -decompile <输出目录> <CHM>`，建议用本库 `source_archives` 中的 ASCII 文件名、隐藏窗口；导入工具遇到同名不同原文会停止，禁止静默覆盖。人工规则卡和样板卡由作者维护，不从样例自动提升为通则。

独立迁移的实际验收记录见 [PORTABILITY.md](PORTABILITY.md)，附[全新上下文Sol首次试写](examples/portable-trial.md)与[阅读日志](examples/portable-trial-reading-log.json)。试写是流程验证材料，未进入已采用规则或定标样板。

本目录可以作为仓库根目录直接提交；不要仅上传Markdown而漏掉工具、目录数据或来源档案。原项目中的旧资料目录不参与本库运行，也不会自动与此库同步。
