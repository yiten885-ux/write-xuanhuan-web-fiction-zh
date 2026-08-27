# Report 04 规则蒸馏

## 报告主题
写作流水线的落地骨架：五张状态空卡（00_state 外置记忆）+ 一张「写一章」消息壳——每章新开一次请求，写完用【记忆回写】覆盖文件，不要在同一条聊天里续到第 200 章。

## 硬规则
- R04-01 每章新开一次请求，写完用【记忆回写】覆盖文件，禁止在同一条聊天里续写到第 200 章。
- R04-02 五张空卡必须存在并逐章维护：00_state/novel_state.md（热状态，每章整份替换，≤1500 字）；00_state/hook_chain.md（主链 3-5 环+暗链+本章钩卡）；00_state/foreshadow.md（埋伏总表，一条一行）；00_state/debt_ledger.md（物的持有+讨债票+后悔药）；00_state/golden_finger.md（四件套+L0-L5+本章许可）；用法说明放 00_state/README.md。
- R04-03 写一章消息壳（prompts/write_chapter_user_shell.md）的用法必须固定：System=xuanhuan_system_prompt.txt；User=消息壳里「用户消息」整段，把 {} 换成五张卡+冲突卡+上章正文。
- R04-04 输出顺序锁死：约束列表→章纲→正文→自检→记忆回写。
- R04-05 自检有 N：模型应重写正文，不要自己圆。
- R04-06 用记忆回写覆盖五张卡后，才允许写 N+1。
- R04-07 想直接开写第 1 章：退婚开局的样例已填好在 00_state（examples 目录[OCR存疑：「examplesichLtuinhun filld nd」原文残缺，疑为「examples/退婚开局已填好样例」]），把各块抄进空卡、冲突卡贴进消息壳、上章填「无」，即可写 Ch1。
- R04-08 流水线就这一句：System 管嘴，00_state 管记得住，消息壳管这一章看见什么。

## 公式与结构模板
- 空模板文件表：
  | 文件 | 作用 |
  |---|---|
  | 00_state/novel_state.md | 热状态，每章整份替换，≤1500 字 |
  | 00_state/hook_chain.md | 主链 3-5 环+暗链+本章钩卡 |
  | 00_state/foreshadow.md | 埋伏总表，一条一行 |
  | 00_state/debt_ledger.md | 物的持有+讨债票+后悔药 |
  | 00_state/golden_finger.md | 四件套+L0-L5+本章许可 |
  | 00_state/README.md | 用法说明 |
  | prompts/write_chapter_user_shell.md | 写一章消息壳 |
- 写一章消息壳 5 步（发给模型时）：1. System=xuanhuan_system_prompt.txt；2. User=消息壳「用户消息」整段，把 {} 换成五张卡+冲突卡+上章正文；3. 输出顺序锁死：约束列表→章纲→正文→自检→记忆回写；4. 自检有 N：模型应重写正文，你不要自己圆；5. 用记忆回写覆盖五张卡后，才允许写 N+1。

## 禁忌与反例
- 禁止在同一条聊天里续写到第 200 章（每章新开请求）。
- 禁止自检出 N 时自己圆（必须让模型重写正文）。
- 禁止未用记忆回写覆盖五张卡就写 N+1。

## 来源
grok_report (4).pdf，共 2 页：
- P1：五张空卡+写一章消息壳（空模板表、消息壳 5 步）
- P2：直接开写第 1 章的方法、流水线一句话总结
