# 已整理资源索引

本目录保存已由用户要求收库的 901 资源正文及其核算依据。资源级别、未决项和单项适配以各自条目为准；收库不把类比价格变成 RE 明价，也不把 NPC 福利推广为全局规则。

| 资源 | 内容 | 依据与边界 |
| --- | --- | --- |
| [帝国法师](imperial-mage.md) | D／C 两阶能力组、九系主副专精；D 15 XP、C 35 XP；NPC 自动辨识不计预算 | [预算与近例](imperial-mage-notes.md)、[艾利来源摘录](imperial-mage-source.md) |
| [帝国通用法术](imperial-magic/README.md) | 120 项 D、88 项原生 C，共 208 项合法法术；D 的 C 版本写在同条；另有魔水融合配方及 7 项禁术附录 | [施法通则](imperial-magic/00-施法通则.md)、[状态与特殊机制](imperial-magic/07-状态与特殊机制.md)、[逐源校核入口](imperial-magic/校核/README.md) |
| [帝国军伍](imperial-military.md) | 两阶能力组、九项配套技艺 | 预算与 XP 依据在同一文件；保留类比估价身份 |
| [启剑式·风·狂岚](kuanglan.md) | 暂定 C 级独立技艺、25 XP | [核算依据](kuanglan-notes.md)；免疫交互仍待定 |
| [正十七](zheng-shiqi.md) | 暂定 C 级独立技艺、25 XP | [核算依据](zheng-shiqi-notes.md)；4C 容量为单项口径，类比分配仍有未决核算 |
| [观澜法·窥波](guanlan-fa.md) | 御临风D级血统＋能力组捆绑包；共享内力、统一技能树与六项本体特性 | [核算依据](guanlan-fa-notes.md)；14D，整体取得候选26XP |
| [风游涉世步](fengyou-sheshibu.md) | D级身法；＋40米速度、受击五尺快步与化劲 | [核算依据](fengyou-sheshibu-notes.md)；D＋1000，5D；15XP，一理贯通后14XP |
| [澄心玄鉴](chengxin-xuanjian.md) | D级心法，御临风《观澜法》技能树；四类目标观察取势、化劲与破隙 | [核算依据](chengxin-xuanjian-notes.md)；正文已确认收录，候选6D，原模板差1D，取得价未定 |

## Sol 使用顺序

1. 读[撰写入口](../authoring/README.md)和本次需求；需要经验检查时读[独立执行指南](../authoring/lessons.md)的相关章节。
2. 续写或调用已有资源时，从本索引找当前正文；帝国魔法使用其本批施法通则。核价或调整机制时，再读对应依据和库内原文。
3. 新稿通常写入 `outputs/`，该目录默认不进入 Git；正式收库需同时维护正文、依据及本索引。不得把旧输出或聊天当作隐含依赖。

`tools/library.py search` 检索 PHB／RE 原书，`cards` 读取规则／特性／样板卡；它们不混入本目录的改编资源。已整理法术按[等级与法系目录](imperial-magic/README.md)查找，其他资源可在本目录按机制文本搜索。`read` 同时支持本目录，例如 `python -X utf8 tools/library.py read resources/imperial-mage.md --start 43 --lines 14`。

本库只需 Python 标准库。运行 `python -X utf8 tools/check_resources.py` 检查本目录的相对链接、法术逐源覆盖和正文目录；全库检查及迁移记录见[独立迁移验收](../PORTABILITY.md)。
