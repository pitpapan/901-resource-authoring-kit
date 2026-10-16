# 901-Rules 工作读取建议

这是独立库入口。新会话先读本库 [AGENTS.md](AGENTS.md)；仅使用库内规则、来源与本次用户需求，输出到 `outputs/`。无需原项目或旧聊天。

资源创作先到 [撰写入口](authoring/README.md)，普通规则问题先看 [按问题索引](indices/mechanisms.md)，不需每次读全书。

1. 本地已完整收录 PHB v0.3 16 页、RE v1.03先行版 964 页；不用另找分包或临时解 CHM。
2. 找整类资料使用 [资源](indices/resources.md)、[特性](indices/traits.md)、[规则](indices/rules.md)、[怪物](indices/bestiary.md)；旧版、待重置、施工条目单列 [杂项](indices/misc.md)。
3. 通常先用 `tools/library.py search` 返回至多 5 个片段，再 `read` 按行读取相关原文。命令示例与限制见 [README](README.md)。别名和关键词标签只作定位，不作规则判断。
4. 每篇 Markdown 都链接原始 HTML；数字、表格、图片或转换疑问回看原页。新增转换以文本块保留内容，复杂表格不保证排版保真。
5. 区分原书明文、901 已采用、样例惯例和待确认推断。完整收录、现行目录和引擎支持均不代表 901 已采用。
