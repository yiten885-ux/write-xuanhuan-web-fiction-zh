# Report 26 规则蒸馏

## 报告主题
「96 套路（T001-T096）爽文套路系统」规范：做成可执行 skill，模型先选 ID 再只加载该号的 HARD/FORMULA，禁止一次吞 96 条；每号统一字段 WHEN/HARD/FORMULA(PRESS→PAYOFF→HOOK→VISIBLE)/BAN/STACK；一章最多 PRIMARY_T+SUB_T 两个；撞 BAN 或全局 S/F/V 废章重写。

## 硬规则

### 一、系统形态与加载约束
- R26-01 必须把 96 套路（T001-T096）系统做成可执行 skill：模型先选 ID，再只加载该号的 HARD/FORMULA；禁止一次吞 96 条。
- R26-02 必须按固定目录布局组织套路库：SKILL.md 负责路由、套路卡、配额；references/global-contract.md 管全局废章条件；references/tropes-index.md 管一行一名、选型；references/tropes-001-050.md 存 T001-T050 全文；references/tropes-051-096.md 存 T051-T096 全文；references/stack-recipes.md 管配方与 NOSTACK。
- R26-03 每个套路号必须使用统一字段（模型能解析）：WHEN / HARD / FORMULA（PRESS→PAYOFF→HOOK→VISIBLE）/ BAN / STACK。

### 二、T001 铁律
- R26-04 T001（救美）必须锁死为辅线：救美可以发生，兑现只作证人物证；禁止当主糖、禁止性过程。

### 三、模型运行工作流（5 步）
- R26-05 必须按 5 步跑套路：①读 SKILL.md + global-contract.md；②用 tropes-index 选出 PRIMARY_T + 可选 SUB_T（一章最多两个）；③只打开这两个 ID 的条目；④先填套路卡再写正文；⑤撞 BAN 或全局 S/F/V=废章重写。
- R26-06 一章最多只能选两个套路：PRIMARY_T + 可选 SUB_T；禁止一章超过两个。
- R26-07 只能加载所选两个 ID 的条目；禁止加载其余 94 条全文。
- R26-08 必须先填套路卡再写正文；禁止跳过套路卡直接写正文。

### 四、全局废章与组合
- R26-09 撞 BAN 或全局 S/F/V 必须废章重写，禁止带病续写。（S/F/V 的确切含义原文未给出，待补）
- R26-10 退婚开局必须最小加载 T002+T072；套餐必须用 T089；真香必须用 T051（且禁止与 T002 同章）。
- R26-11 必须把整个 shuangwen-tropes/ 文件夹拷入目标环境（如 Cursor，Claude skills 即可用）；与现有 xuanhuan_system_prompt.txt、00_state/ 的接口必须按 SKILL 第 2 节对接。
- R26-12 试跑时必须按固定协议输出：丢一句开局（如「退婚灭门赘婿」），按 skill 协议输出 PRIMARY_T、FORBIDDEN、套路卡、第 1 章五个 200 字检查点。

## 公式与结构模板

### 套路字段（每号统一，模型能解析）
| 字段 | 定义（原文给出部分） |
|---|---|
| WHEN | 触发条件/何时用。原文仅给字段名，语义未展开。 |
| HARD | 硬约束。原文仅给字段名，语义未展开；工作流要求「只加载该号的 HARD/FORMULA」。 |
| FORMULA | 展开为 PRESS→PAYOFF→HOOK→VISIBLE（施压→兑现→钩子→可视化）；四阶段内部细则原文未给出。 |
| BAN | 禁用项。原文仅给字段名；撞 BAN=废章重写。 |
| STACK | 组合规则。原文仅给字段名；配方由 references/stack-recipes.md 管（配方与 NOSTACK）。 |
| FORBIDDEN | 试跑协议输出项中出现一次；与 BAN 的关系原文未说明。 |

### 模型工作流（5 步模板）
1. 读 SKILL.md + global-contract.md。
2. 用 tropes-index 选出 PRIMARY_T + 可选 SUB_T（一章最多两个）。
3. 只打开这两个 ID 的条目。
4. 先填套路卡再写正文。
5. 撞 BAN 或全局 S/F/V=废章重写。

### 试跑输出协议
丢一句开局（如「退婚灭门赘婿」）→ 按 skill 协议输出：PRIMARY_T、FORBIDDEN、套路卡、第 1 章五个 200 字检查点。

## 禁忌与反例
- 禁止一次吞 96 条：必须先选 ID，再只加载该号的 HARD/FORMULA。
- 撞 BAN 或全局 S/F/V 必须废章重写，禁止带病续写。
- T001（救美）禁止当主糖、禁止性过程。
- T051（真香）禁止与 T002（退婚）同章。
- 一章禁止超过两个套路（PRIMARY_T + 可选 SUB_T）。
- 反例演示（由已披露规则推导）：开局用 T002 退婚 + 同章用 T051 真香 → 撞 BAN → 废章重写；正确做法是退婚开局最小加载 T002+T072，套餐用 T089，真香留给后续章节。
- 一句话：套路库是「先选号、只加载、按卡写、撞禁即废」的最小加载系统，不是一次性背完 96 条的百科全书。

## 来源
PDF 页 1-2（combined-26.txt；OCR 文本共 2 页）
