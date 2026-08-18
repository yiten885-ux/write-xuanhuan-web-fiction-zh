# Release notes

## 1.0.0

- 首次以 skills-only Codex Plugin 形式封装 `write-xuanhuan-web-fiction-zh`。
- 市场展示名定为“玄章天工｜Xuanhuan Storyforge”，保持原 Skill 技术 ID 兼容。
- 汇总中文玄幻网文规划、前三章、续写、重写、人物与世界观、节奏与连续性工作流。
- 强化读者可见正文隔离，避免内部约束标签、自检块和 QA 元数据混入小说正文。
- 默认逐章检查 2000–3000 个净正文有效字符，防止跨章凑字和隐藏内容补字。
- QA JSON 仅记录源文件名与 SHA-256，不再暴露使用者本机绝对路径。
