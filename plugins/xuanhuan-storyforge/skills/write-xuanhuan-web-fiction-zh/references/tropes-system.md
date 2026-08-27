# 爽文套路系统（96 套路库 · 最小加载）

主题参考文档。蒸馏自 Report 26（OCR 文本 combined-26.txt，PDF 页 1-2）。本档是把「96 套路（T001-T096）系统」的架构、字段、工作流与已披露套路并入本 skill 的接口层；96 条全文不在本档，见下方架构与「待补」标注。

## 适用范围

- 什么时候读：开书/开卷选套路时；每章开工前选 PRIMARY_T/SUB_T 时；撞 BAN 或全局 S/F/V 判定废章时；退婚开局等已知组合落地时。
- 三句总纲：先选 ID，再只加载该号的 HARD/FORMULA，禁止一次吞 96 条（R26-01）；一章最多 PRIMARY_T+SUB_T 两个（R26-05/R26-06）；撞 BAN 或全局 S/F/V=废章重写（R26-09）。
- 与 SKILL.md §6.2 套路层管理的关系：§6.2 要求把套路当作因果模块而非装饰标签，每个套路记录功能/证据/限制/主线交叉/删除条件/状态六项；本系统的 WHEN/HARD/FORMULA/BAN/STACK 是这六项的可执行化（WHEN≈触发场景、HARD≈硬约束、BAN≈删除条件、STACK≈组合限制）。本系统与 §6.2 一样，只在用户明确启用时生效；默认仍优先保证因果、代价、人物选择和落袋回报。

## 架构（skill 目录布局，原文目录表）

| 文件 | 职责 |
|---|---|
| `SKILL.md` | 路由、套路卡、配额 |
| `references/global-contract.md` | 全局废章条件 |
| `references/tropes-index.md` | 一行一名，选型 |
| `references/tropes-001-050.md` | T001-T050 全文 |
| `references/tropes-051-096.md` | T051-T096 全文 |
| `references/stack-recipes.md` | 配方与 NOSTACK |

- 本 skill 对应落地：将上表目录并入 `write-xuanhuan-web-fiction-zh/references/`（或以 `shuangwen-tropes/` 子目录整体挂载），SKILL.md 增加路由入口（读 global-contract → tropes-index 选型 → 按 ID 开文件 → 套路卡配额）。
- 原文要求：把整个 shuangwen-tropes/ 文件夹拷进目标环境（如 Cursor，Claude skills 即可用）（R26-11）。

## 套路字段（每号统一，模型能解析）

- `WHEN`：触发条件。原文仅给字段名，语义未展开。
- `HARD`：硬约束；工作流要求「只加载该号的 HARD/FORMULA」（R26-01）。
- `FORMULA`：`PRESS→PAYOFF→HOOK→VISIBLE`（施压→兑现→钩子→可视化）。四阶段内部细则原文未给出。
- `BAN`：禁用项；撞 BAN=废章重写（R26-09）。字段内具体禁用清单原文未给出。
- `STACK`：组合规则；配方由 `references/stack-recipes.md` 管（配方与 NOSTACK）。具体配方内容原文未给出。
- `FORBIDDEN`：试跑协议输出项中出现一次（PRIMARY_T、FORBIDDEN、套路卡、检查点）；与 BAN 的关系原文未说明，待补。
- 各字段的完整语义定义原文未展开；上表为依字段名与上下文的最小解读，待原文补全确认。

## 模型工作流（5 步）

1. 读 SKILL.md + global-contract.md（先背全局废章合同）。
2. 用 tropes-index 选出 PRIMARY_T + 可选 SUB_T（一章最多两个）。
3. 只打开这两个 ID 的条目（禁止加载其余 94 条全文）。
4. 先填套路卡再写正文。
5. 撞 BAN 或全局 S/F/V=废章重写。

试跑协议（原文）：丢一句开局（如「退婚灭门赘婿」），按 skill 协议输出 PRIMARY_T、FORBIDDEN、套路卡、第 1 章五个 200 字检查点（R26-12）。

## 已披露套路

| 编号 | 名称 | 内容 |
|---|---|---|
| T001 | 救美 | 锁死为辅线：救美可以发生，兑现只作证人物证；禁止当主糖、禁止性过程（R26-04）。 |
| T002 | 退婚开局 | 见组合规则（R26-10）。 |
| T051 | 真香 | 禁止与 T002 同章（R26-10）。 |
| T072 | （与 T002 组合） | 退婚开局最小加载组成件（R26-10）。 |
| T089 | 套餐 | 退婚开局套餐用 T089（R26-10）。 |
| 其余 91 条 | — | 原文未披露全文：tropes-001-050.md / tropes-051-096.md 原文只给出文件名，条目内容全文待补。 |

## 组合规则

- 退婚开局最小加载：T002 + T072（R26-10）。
- 退婚开局套餐：用 T089（R26-10）。
- 真香：用 T051，禁止与 T002 同章（R26-10）。
- STACK 与 NOSTACK 配方原则：配方与 NOSTACK 由 references/stack-recipes.md 统一管理；原文未给出任何具体配方或 NOSTACK 清单，待补。启用本系统后，组合必须走 stack-recipes 查配方，禁止凭印象自组未登记组合。
- 一章最多两个套路（PRIMARY_T + 可选 SUB_T），超出即违规（R26-06）。

## 与既有系统的接口

- 原文声明：与现有 `xuanhuan_system_prompt.txt`、`00_state/` 的接口已写在 shuangwen-tropes 的 SKILL 第 2 节（R26-11）；具体字段映射原文未给出，待补。
- 本 skill 的对应物：
  - `xuanhuan_system_prompt.txt` → 本 skill 的 SKILL.md（含 §6.2 套路层管理六项记录：功能/证据/限制/主线交叉/删除条件/状态）。
  - `00_state/` → 本 skill 的状态目录与连续性工程（memory-and-continuity.md：每章记忆回写、正文/记忆/QA 三分文件、hook_chain.md 咬合回写）。
  - 套路卡字段（WHEN/HARD/FORMULA/BAN/STACK）可对齐到章节状态表与任务卡；确切映射方案原文未给出，落地时按「套路卡 → 章卡 → 记忆回写」串接，并标注来源 R26 编号。
- 全局废章合同（global-contract.md）对应本 skill 的全局硬锁（第 4、5 节默认硬锁阈值与章位）；S/F/V 的确切含义原文未给出，待补——它被用作全局废章触发条件之一（R26-09）。

## 禁忌

- 禁止一次吞 96 条：必须先选 ID，再只加载该号的 HARD/FORMULA（R26-01）。
- 禁止一章超过两个套路（PRIMARY_T + 可选 SUB_T）（R26-06）。
- 禁止只打开未选 ID 的条目（R26-07）。
- 禁止跳过套路卡直接写正文（R26-08）。
- 撞 BAN 或全局 S/F/V 必须废章重写，禁止带病续写（R26-09）。
- T001（救美）禁止当主糖、禁止性过程（R26-04）。
- T051（真香）禁止与 T002（退婚）同章（R26-10）。

## 来源

Report 26 规则蒸馏（rule-26.md）；OCR 文本 combined-26.txt，PDF 页 1-2。
