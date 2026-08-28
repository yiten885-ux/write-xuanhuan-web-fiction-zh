# 玄章天工｜Xuanhuan Storyforge

`write-xuanhuan-web-fiction-zh` 是面向中文玄幻、仙侠、王朝修仙和系统流网文的 Codex Skill。它覆盖从零规划、故事圣经、人物与力量体系、前三章、续写、重写、连续性审校和机械质量门禁。

市场展示名为 **玄章天工｜Xuanhuan Storyforge**；稳定的 Skill 技术 ID 仍为 `write-xuanhuan-web-fiction-zh`，以兼容现有调用。

## 目录

- `.agents/plugins/marketplace.json`：仓库级 Codex marketplace。
- `plugins/xuanhuan-storyforge/.codex-plugin/plugin.json`：skills-only Plugin 清单。
- `plugins/xuanhuan-storyforge/skills/write-xuanhuan-web-fiction-zh/`：Skill 本体。
- `submission/`：OpenAI 公开市场的文案、测试用例和人工提交清单。

## 版本与规则来源

- **v1/v2**：连续性工程与硬冲击章程（01–10 锁、九项留存硬锁、逐章净字数锁、审计脚本）。
- **v3（2026-08）**：蒸馏自 26 份创作技法研究报告（`rules/` 中 26 份 rule-XX.md 为逐份溯源底账，共 769 条硬规则；覆盖矩阵见 `rules/RULES-INDEX.md`），新增 6 份主题参考：
  - `references/climax-techniques.md`：八型高潮（C01-C08）、单元高潮（U01-U10）
  - `references/hooks-and-chains.md`：章末八型（K01-K14）、钩子链（L01-L12）、单元咬合（B01-B04）
  - `references/satisfaction-and-pacing.md`：12 种爽货（S01-S12）、四级爽点、铺压弹债（R01-R10）
  - `references/reversal-anguish-meme.md`：反转（F01-F14）、虐点（N01-N14）、热梗（M01-M10）
  - `references/opening-and-golden-finger.md`：硬冲突（C01-C12）、退婚替婚开局（T01-T14）、金手指隐藏层（L0-L5）
  - `references/memory-and-continuity.md`：四层记忆、上下文包、记忆回写协议
- 蒸馏规则以 SKILL.md §5.19 硬锁形式与 v1/v2 并列累积，多报告口径冲突已在 §5.19E 统一。
- **用户增补（2026-08-27 / 2026-08-28）**：
  - SKILL.md §5.20：情绪压爆点与情感张力合同（大纲预检三问、五感锚点扩写、情感张力门禁）
  - SKILL.md §5.21 + `references/reader-retention-36.md`：留存与付费 36 锁（留01–留36：爽感循环、抓人密度、打脸三层递进、情绪曲线、钩子链、名场面、付费转化等）
  - SKILL.md §5.22 + `references/alignment-protocol-16.md`：开局对齐协议 16 条（对01–对16：开书契约卡、卖点主权、金手指四拍循环、先满后亏、租约四件套、F00 开局流水线、P0–P5 优先级）
  - 五篇源文档逐字存档于 `sources/2026-08-28-user-supplement/`

## 本地验证

```bash
python3 -m unittest discover \
  -s plugins/xuanhuan-storyforge/skills/write-xuanhuan-web-fiction-zh/tests \
  -v
```

Codex 插件清单还应使用当前 Codex 安装自带的 `validate_plugin.py` 验证。公开市场的最终上线状态以 OpenAI 审核通过、开发者主动发布和公共详情页可安装为准。

## 安全与隐私

该插件不包含 MCP 服务，不发起网络请求，也不需要第三方凭据。正文审计脚本只读取指定正文与本地规则文件；使用 `--json-out` 时会另写 QA 报告，但默认不记录使用者的绝对文件路径。

## 许可

MIT License（见 [LICENSE](LICENSE)）。免费公开使用：可自由使用、修改与再分发，需保留版权声明。
