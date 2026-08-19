# 玄章天工｜Xuanhuan Storyforge

`write-xuanhuan-web-fiction-zh` 是面向中文玄幻、仙侠、王朝修仙和系统流网文的 Codex Skill。它覆盖从零规划、故事圣经、人物与力量体系、前三章、续写、重写、长篇状态事务、连续性审校和机械质量门禁。

市场展示名为 **玄章天工｜Xuanhuan Storyforge**；稳定的 Skill 技术 ID 仍为 `write-xuanhuan-web-fiction-zh`，以兼容现有调用。

## 目录

- `.agents/plugins/marketplace.json`：仓库级 Codex marketplace。
- `plugins/xuanhuan-storyforge/.codex-plugin/plugin.json`：skills-only Plugin 清单。
- `plugins/xuanhuan-storyforge/skills/write-xuanhuan-web-fiction-zh/`：Skill 本体。
- `submission/`：OpenAI 公开市场的文案、测试用例和人工提交清单。

## 本地验证

```bash
python3 -m unittest discover \
  -s plugins/xuanhuan-storyforge/skills/write-xuanhuan-web-fiction-zh/tests \
  -v
```

对有已提交事件的长篇状态文件，可额外校验最终正文哈希、来源锚、关键帧和相邻版本链：

```bash
python3 plugins/xuanhuan-storyforge/skills/write-xuanhuan-web-fiction-zh/scripts/validate_story_state.py \
  current.state.json \
  --prose final.md \
  --previous previous.state.json \
  --json-out current.qa.json
```

正文、`.state.json` 状态和 `.qa.json` 审计必须保持三文件隔离；状态或审计文字不得进入读者正文或补足章节字数。

Codex 插件清单还应使用当前 Codex 安装自带的 `validate_plugin.py` 验证。公开市场的最终上线状态以 OpenAI 审核通过、开发者主动发布和公共详情页可安装为准。

## 安全与隐私

该插件不包含 MCP 服务，不发起网络请求，也不需要第三方凭据。正文审计脚本只读取指定正文与本地规则文件；使用 `--json-out` 时会另写 QA 报告，但默认不记录使用者的绝对文件路径。

## 许可

本仓库未授予开源许可。除非权利人另行书面授权，保留全部权利。
