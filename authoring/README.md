# 901 资源撰写入口

本目录与库根的 `content/`、`indices/`、`rules/`、`tools/` 一起复制，即可在别处使用。这里的卡片是检索与写作参考，不新增规则权威、审批程序或引擎接口。先读[撰写指南](guide.md)，按需要再读[常用规则卡](common_rules.md)、[特性速查](traits.md)与 2—3 张[定标样板](samples.md)。样板是 RE 原文比较材料，不代表 901 已采用，也不是质量金标准。

## 一批资源的最短流程

1. 用[需求简表](brief-template.md)明确用途、对象、类型、强度上限和风格；先定核心打法或实际解决的问题，再分配预算。D/C 等原书等级不能直接等同某世界的战力档。
2. 查相关规则卡、特性卡和少量相近样板。只有具体机制缺口再到[按问题索引](../indices/mechanisms.md)或完整底库定点找原文；不要每批通读全部材料。
3. 写可审阅资源正文，紧邻写简短的原文比较、预算和价格依据。区分原文、901 已采用、原创候选及仍待单项适配的效果。
4. 核对前提、动作、消耗、持续、叠加、进阶增量或替换，以及人物取得与引擎支持边界。未决数值标候选，不补造来源或 901 Canon。

从**库根目录**运行本地检索命令，搜索只定位，须回看命中原文前后段：

```powershell
python -X utf8 tools/library.py cards CR-04 TB-01 S-01 S-08
python -X utf8 tools/library.py search 剑盾战斗 --kind rules --limit 3
python -X utf8 tools/library.py read 'content/RE/01_rules/01_建卡与属性/战斗专长.md' --start 178 --lines 20
```

检索默认排除待重置、已移除和施工条目；明确研究旧例时才用 `--include-legacy`。机器片段、别名与标签只帮助找出处，不能证明语义匹配、完整前提或采用状态。

可直接复制给 Sol 的启动请求：

> 请依据本库 `authoring/README.md`、`authoring/guide.md` 和 `authoring/brief-template.md` 中填写的需求，撰写一批可审阅的 901 资源草案。按需查 `authoring/common_rules.md`、`authoring/traits.md`、2—3 张相近样板及原文；先说明核心玩法，再给效果、前提、进阶和价格依据。明确标注原文、原创候选、未决校准及未支持部分，不把草案当作已采用或已取得。结果写入库根 `outputs/` 下一个清楚命名的 Markdown 文件，并在答复中给出路径。

常规撰写可由 Sol 完成；具体来源冲突或缺少可比标尺时只标出问题供作者决定，无需为每份草案另做高成本重写。
