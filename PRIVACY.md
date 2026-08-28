# 隐私政策（Privacy Policy）— 玄章天工｜Xuanhuan Storyforge

**生效日期：2026-08-27**

玄章天工（Xuanhuan Storyforge）是一个 skills-only 的 Codex Plugin。本插件：

- 不包含远程 MCP 服务；
- 不自行建立用户账户；
- 不要求第三方 API Key；
- 不向开发者的服务器发送用户的正文、设定或任何会话内容。

插件在 Codex 会话中处理用户主动提供的文本；相关数据处理同时受用户所使用的 OpenAI 产品条款与隐私政策约束（见 [OpenAI Privacy Policy](https://openai.com/policies/privacy-policy/)）。

## 本地审计工具

插件内的正文审计脚本只读取用户指定的正文文件和随插件提供的规则文件。只有当用户显式传入 `--json-out` 参数时，它才会另写一个本地 QA 报告；报告记录源文件名和内容 SHA-256，不记录绝对路径，不进行任何网络传输。

## 数据收集与共享

- 本插件不收集、不存储、不共享任何用户个人数据。
- 插件不包含遥测、统计或追踪代码。

## 政策更新

本政策如有更新，将随本仓库提交记录发布并更新生效日期。

## 联系方式

安全或隐私问题请通过 [Issues](https://github.com/yiten885-ux/write-xuanhuan-web-fiction-zh/issues) 提交，或参阅 [SECURITY.md](SECURITY.md)。
