from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LeanSkillContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_required_files_exist(self) -> None:
        required = {
            "SKILL.md",
            "agents/openai.yaml",
            "assets/chapter-card-template.md",
            "assets/story-bible-template.md",
            "references/story-design.md",
            "references/character-emotion.md",
            "references/revision-continuity.md",
            "references/opening-retention-six-locks.md",
            "references/zh-style-watchlist.json",
            # v3：26 份研究报告蒸馏新增（创作技法层）
            "references/climax-techniques.md",
            "references/hooks-and-chains.md",
            "references/satisfaction-and-pacing.md",
            "references/reversal-anguish-meme.md",
            "references/memory-and-continuity.md",
            "references/opening-and-golden-finger.md",
            "rules/RULES-INDEX.md",
            "rules/rule-00.md",
            "rules/rule-01.md",
            "rules/rule-02.md",
            "rules/rule-03.md",
            "rules/rule-04.md",
            "rules/rule-05.md",
            "rules/rule-06.md",
            "rules/rule-07.md",
            "rules/rule-08.md",
            "rules/rule-09.md",
            "rules/rule-10.md",
            "rules/rule-11.md",
            "rules/rule-12.md",
            "rules/rule-13.md",
            "rules/rule-14.md",
            "rules/rule-15.md",
            "rules/rule-16.md",
            "rules/rule-17.md",
            "rules/rule-18.md",
            "rules/rule-19.md",
            "rules/rule-20.md",
            "rules/rule-21.md",
            "rules/rule-22.md",
            "rules/rule-23.md",
            "rules/rule-24.md",
            "rules/rule-25.md",
            "scripts/audit_chapter.py",
            "tests/test_audit_chapter.py",
            "tests/test_skill_contract.py",
        }
        actual = {
            str(path.relative_to(ROOT))
            for path in ROOT.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual(required, actual)

    def test_markdown_inventory_stays_lean(self) -> None:
        # v3 契约：SKILL.md 保持精简，参考文档按主题按需加载，rules/ 为溯源底账（不进运行时上下文）。
        markdown = list(ROOT.rglob("*.md"))
        text_files = list(ROOT.rglob("*.txt"))
        self.assertLessEqual(len(markdown), 45)
        self.assertEqual([], text_files)
        self.assertLess(sum(path.stat().st_size for path in markdown), 800_000)
        # v1 与 v2、v3 必须并存；上限只防无关膨胀，不能倒逼删除任一合同。
        self.assertLess((ROOT / "SKILL.md").stat().st_size, 60_000)
        self.assertLessEqual(len(list((ROOT / "references").glob("*.md"))), 12)
        self.assertLessEqual(len(list((ROOT / "rules").glob("*.md"))), 30)

    def test_frontmatter_is_minimal_and_valid(self) -> None:
        skill = self.read("SKILL.md")
        self.assertTrue(skill.startswith("---\nname: write-xuanhuan-web-fiction-zh\n"))
        frontmatter = skill.split("---", 2)[1]
        self.assertIn("\ndescription:", frontmatter)
        self.assertEqual(2, len([line for line in frontmatter.splitlines() if ":" in line]))

    def test_all_local_markdown_links_resolve(self) -> None:
        for source in ROOT.rglob("*.md"):
            text = source.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (source.parent / target).resolve()
                with self.subTest(source=source.name, target=target):
                    self.assertTrue(resolved.exists())
                    self.assertTrue(resolved.is_relative_to(ROOT.resolve()))

    def test_examples_are_isolated_from_runtime_routing(self) -> None:
        runtime = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                ROOT / "SKILL.md",
                ROOT / "agents/openai.yaml",
                ROOT / "assets/chapter-card-template.md",
                ROOT / "assets/story-bible-template.md",
                ROOT / "references/story-design.md",
                ROOT / "references/character-emotion.md",
                ROOT / "references/revision-continuity.md",
                ROOT / "references/opening-retention-six-locks.md",
            ]
        )
        self.assertNotIn("project-lock-", runtime)
        self.assertNotIn("/Users/", runtime)
        self.assertNotIn("outputs/", runtime)
        self.assertIn("默认只是帮助理解规则的素材", runtime)
        self.assertIn("不得把它们写入 Skill 描述、触发路由、门禁、模板、测试或通用参考", runtime)

    def test_seven_opening_rules_are_generic_and_present(self) -> None:
        skill = self.read("SKILL.md")
        markers = (
            "第一章前 1000 个有效正文字符出现命运危机",
            "背景信息通过当前代价进入",
            "效果、代价、边界",
            "主角前三章至少一次主动设局",
            "主要压迫者用一件完整前科立威",
            "三章内完成一次阶段胜利",
            "先看见，再暗示，后揭示或使用",
        )
        for marker in markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_user_allowed_devices_are_not_globally_banned(self) -> None:
        skill = self.read("SKILL.md")
        character = self.read("references/character-emotion.md")
        self.assertIn("不自动判禁写", skill)
        self.assertIn("检查不是擅自禁写", character)
        self.assertIn("回忆可以在后期新揭遗言、功劳、秘密或隐情", character)
        self.assertIn("不要求每个情绪都兑换战力", character)

    def test_templates_preserve_canon_and_evidence(self) -> None:
        card = self.read("assets/chapter-card-template.md")
        bible = self.read("assets/story-bible-template.md")
        for marker in (
            "主角主动选择",
            "场景后不可逆变化",
            "三章阶段胜利及落袋状态",
        ):
            self.assertIn(marker, card)
        for marker in (
            "已确认正史",
            "草稿事实",
            "后续计划",
            "用户明确启用的特殊规则",
        ):
            self.assertIn(marker, bible)

    def test_agent_metadata_is_concise(self) -> None:
        metadata = self.read("agents/openai.yaml")
        self.assertLess(len(metadata), 600)
        self.assertIn('display_name: "玄章天工｜Xuanhuan Storyforge"', metadata)
        description_match = re.search(
            r'^\s*short_description:\s*"([^"]+)"\s*$', metadata, re.MULTILINE
        )
        self.assertIsNotNone(description_match)
        description = description_match.group(1)
        self.assertGreaterEqual(len(description), 25)
        self.assertLessEqual(len(description), 64)
        self.assertIn("$write-xuanhuan-web-fiction-zh", metadata)
        self.assertIn("示例不进入通用门禁", metadata)
        self.assertIn("逐章净正文2000–3000字符", metadata)
        self.assertIn("约束ID和自检只写独立QA侧车", metadata)

    def test_retention_reference_is_mandatory_and_cumulative(self) -> None:
        skill = self.read("SKILL.md")
        retention = self.read("references/opening-retention-six-locks.md")
        self.assertIn(
            "必须完整读取并执行 [references/opening-retention-six-locks.md]",
            skill,
        )
        self.assertIn("九项留存硬锁是默认硬锁，不是可选建议", skill)
        self.assertIn(
            "九项与七条前三章合同、v1、既有 v2、01–10、正文隔离锁及逐章净字数锁并列累积",
            skill,
        )
        self.assertIn(
            "本文件九项硬锁与 `SKILL.md` 中的七条前三章合同、v1、既有 v2、01–10、正文隔离锁和逐章净字数锁并列累积",
            retention,
        )
        self.assertIn("不得替换、放宽或择一执行", retention)

    def test_retention_six_atomic_rules_are_welded(self) -> None:
        skill = self.read("SKILL.md")
        retention = self.read("references/opening-retention-six-locks.md")
        for marker in (
            "前 300 个读者可见正文字符内",
            "普通人最可能选择的 3 个方案",
            "不属于前三项的“第四方案”",
            "每章至少落袋 1 个微爽点",
            "任意连续 3 章内至少落袋 1 个主爽点",
            "每章最后 3 句必须同时具备",
            "改写一个既有事实的来源、归属、意图、时间、身份或规则边界",
            "任意连续 2 章内，至少出现 1 次",
            "比例不得低于 1:3",
            "第 3 章结束前",
            "第 10 章结束前",
            "核心外挂的 3 个本质功能",
            "至少一项必须是作者能一句话说明的根本偏移",
            "情绪失控系数 = 意外型翻盘次数",
            "意外型翻盘与算计型翻盘的数量比必须落在 2:1 至 3:1",
            "每章结尾时，主角不得同时满足三项",
            "章尾焦虑值 = 未解决威胁数 × 2",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, retention)
        for marker in (
            "前 300 个含标点的读者可见正文字符内",
            "任意滚动 3 章内至少一次“第四方案”",
            "每章至少一个落袋微爽点",
            "每章最后 3 句同时包含动作压力",
            "任意滚动 2 章至少一次",
            "第 10 章结束前完成",
            "核心外挂在“做什么、怎么做、代价是什么”三项中",
            "任意滚动 6 章内",
            "每章结尾不得同时处于安全区",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_retention_counting_windows_do_not_override_length_lock(self) -> None:
        skill = self.read("SKILL.md")
        retention = self.read("references/opening-retention-six-locks.md")
        for marker in (
            "按滚动窗口计算",
            "不得据此把现有单章最低字数从 2000 提高到 2500",
            "同一状态变化只能按其最高等级计 1 次",
            "爽点密度 =（微爽点数 × 0.4 + 主爽点数 × 1.0）÷ 实际净正文万字符数",
            "情感锚定强度 = 不可逆损失或威胁数 ÷ 总困境数",
            "主角意外行为频次 = 合格第四方案数 ÷ 主角关键决策总数",
            "章尾信息熵增量 = 改写因果的新信息数 ÷ 当前钩子所调用的已埋伏笔或相关前提数",
            "场景滞留惯性`按连续 3 章未完成主要场景转移的滚动窗口数计入扣分",
            "设定稀缺性评分`按内部相似度排除计算",
            "情绪失控系数 = 意外型翻盘次数 ÷ 全部翻盘次数",
            "章尾安全区违规次数`按每章结尾三项同时成立次数计入扣分",
            "五项逐章检查",
            "四项跨章/设定周期检查",
            "不是经市场验证的预测模型",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, retention)
        self.assertIn("每章必须独立达到 2000–3000 个净正文有效字符", skill)

    def test_retention_future_gate_cannot_be_prematurely_passed(self) -> None:
        skill = self.read("SKILL.md")
        retention = self.read("references/opening-retention-six-locks.md")
        self.assertIn("第 3 章场景转移必须已经在正文落地", retention)
        self.assertIn("第 10 章门槛记为“尚未到期，已规划”", retention)
        self.assertIn("不得提前登记通过", retention)
        self.assertIn("不足 6 章的交付只登记已规划峰值，不得提前写通过", retention)
        self.assertIn("未满 6 章时规划账不得写成已通过", skill)

    def test_retention_templates_require_semantic_evidence(self) -> None:
        card = self.read("assets/chapter-card-template.md")
        bible = self.read("assets/story-bible-template.md")
        for marker in (
            "不可逆锚定的目标主体 / 剩余时限 / 永久后果",
            "主角实际采用的第四方案",
            "本章落袋微爽点（必须 ≥ 1）",
            "改写前文因果判断的新事实",
            "本章正面用途 / 惊奇 / 美感 / 便利 / 公共价值场景",
            "第 3 章结束前实际离开的动作与正文证据",
            "第 10 章门槛状态（尚未到期 / 已到期）",
            "核心外挂的 3 个本质功能",
            "情绪失控系数（目标 ≥ 0.6）",
            "章尾焦虑值（目标 ≥ 4）",
            "九项留存锁 QA 侧车记录",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, card)
        for marker in (
            "开篇不可逆锚定账",
            "三章差异性行为与主爽账",
            "逐章爽点与前三万字密度账",
            "章尾动作与信息双钩子账",
            "世界观双向展示账",
            "场景转移与首个副本闭环账",
            "设定稀缺性账",
            "情绪峰值类型配比账",
            "章尾安全区账",
            "九项留存锁状态账",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, bible)

    def test_agent_metadata_mentions_new_six_without_replacing_old_contracts(self) -> None:
        metadata = self.read("agents/openai.yaml")
        self.assertLess(len(metadata), 600)
        self.assertIn("既有五锁、06–10及前三万字九项留存锁", metadata)
        self.assertIn("逐章净正文2000–3000字符", metadata)
        self.assertIn("约束ID和自检只写独立QA侧车", metadata)
        self.assertIn("示例不进入通用门禁", metadata)

    def test_hard_impact_contract_is_default_and_conjunctive(self) -> None:
        skill = self.read("SKILL.md")
        self.assertIn("本节是默认强制的合取合同", skill)
        self.assertIn("所有适用项都必须满足", skill)
        for marker in (
            "3:1 可视偿债",
            "300/800 截断",
            "三向利益与反向记忆",
            "反派先拆牌",
            "世界观砸脸",
            "先动身体，再动脑",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_payoff_and_hook_formulas_are_welded(self) -> None:
        skill = self.read("SKILL.md")
        for marker in (
            "同一场景内至少落袋 3 个彼此可区分的收益单位",
            "打脸、夺宝、收人或升阶",
            "反派出现生理性或社会性反噬",
            "付出 → 回报显现 → 溢出碾压",
            "前 300 字内出现一种异常感知",
            "任意相邻两次信息差截断之间最多约 800 个有效正文字符",
            "至少经过下一次钩子后再解释来源",
            "异常感知 → 即时行动 → 结果半露 → 留白逼问",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_character_antagonist_and_world_rules_are_welded(self) -> None:
        skill = self.read("SKILL.md")
        for marker in (
            "对主角的立场",
            "对反派或对立方的立场",
            "独立利益",
            "公共身份 + 私人欲望 + 当下恐惧 = 行动依据",
            "反派先拆牌",
            "同一轮冲突同时威胁至少两个",
            "主角真正的 C 计划",
            "层三触发源等于层二的必然副作用",
            "感官异常 → 环境变形 → 旧权力失灵 → 一句话重新定义局面",
            "不超过 15 个有效字符",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_emotion_and_first_chapter_rules_are_welded(self) -> None:
        skill = self.read("SKILL.md")
        for marker in (
            "第一段直接写主角正在完成的反常或高风险动作",
            "第二段必须出现该动作的即时物理或社会结果",
            "前 1000 字内让主角原有预期彻底落空",
            "反常动作 → 即时结果 → 倒逼信息",
            "第一反应必须是情绪驱动",
            "主角先确认对方状态",
            "不超过 7 个有效字符",
            "外部刺激 → 本能动作 → 身体代价 → 环境静默 → 一句短台",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_chapter_card_requires_evidence_for_every_hard_module(self) -> None:
        card = self.read("assets/chapter-card-template.md")
        bible = self.read("assets/story-bible-template.md")
        for marker in (
            "同场景 3 个可视收益单位",
            "信息差截断位置与相邻有效字数",
            "三向利益",
            "B 为成立必须支付的隐藏代价 / 副作用",
            "C 计划如何只利用该代价触发",
            "当前最强势力失效",
            "不超过 7 个有效字符且无感叹号的短台",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, card)
        self.assertIn("反派先手账", bible)
        self.assertIn("层级亮相账", bible)
        self.assertIn("Skill 默认硬合同", bible)

    def test_five_opening_validation_locks_are_welded(self) -> None:
        skill = self.read("SKILL.md")
        for marker in (
            "HOOK-EMO-01｜情绪钩子前置锁",
            "PLOT-MIND-02｜智斗三层套娃锁",
            "SYS-COST-03｜非线性代价锁",
            "LOOT-DELAY-04｜战利品双池锁",
            "END-HOOK-05｜章末认知错位锁",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_hook_and_mind_locks_preserve_atomic_conditions(self) -> None:
        skill = self.read("SKILL.md")
        for marker in (
            "共情锚点值 = 感官压迫词数 × 1 + 压迫者直接台词次数 × 2 + 时间死限或生理威胁次数 × 3",
            "第一章前 150 个有效正文字符必须依次出现",
            "至少 2 个生理感官压迫词",
            "一句带引号且由压迫者本人说出的直接台词",
            "锚点值达到 6 后，才允许首次超凡动作",
            "首次超凡动作必须晚于第 3 个自然段",
            "智斗深度 = 明面计划数 1 + 反拆动作数 1 + 反拆副作用利用数 1 = 3",
            "层三触发源等于层二的必然副作用",
            "明面 A 计划 → 反派 B 反制 → A 破产 → 主角利用 B 的必然副作用执行 C 计划",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_cost_loot_and_end_hook_conditions_are_atomic(self) -> None:
        skill = self.read("SKILL.md")
        for marker in (
            "代价完整性 = 显性代价 1 + 隐性抽象损耗 1 = 2",
            "每次生效都必须同时植入一种不可逆且本章无法解释的抽象异常",
            "感知异常",
            "物件异常",
            "情感的麻木或错位",
            "转化逻辑不是伤害数值 × 系数",
            "同场景线性以伤换强 ≤ 1 次",
            "即时展示项 ≤ 3 且本章全部实际使用",
            "未知物件 ≥ 1",
            "未知物件本章解释次数 = 0",
            "第三章或任意阶段性卷末的最后 200 个有效正文字符",
            "必须二选一：金手指对新威胁",
            "已死者、令牌、遗物或延迟池物件发生复苏",
            "最后一句的语法主语必须是异常现象",
            "本章未解释该异常",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_existing_v2_validation_lock_is_preserved_before_ten_lock(self) -> None:
        skill = self.read("SKILL.md")
        footer = """```markdown
[MANDATORY] 玄幻开篇五条硬规则（违反任一则输出无效，必须回滚重写）：

1. 情绪钩子前置律（HOOK）：第一章前150字内，必须按“感官词→反派台词→死限”顺序输出，锚点值≥6后方可触发主角首次超凡动作。
2. 智斗三层套娃律（MIND）：任何交锋场景必须包含：明面计划(层1)→反派拆解(层2)→主角利用拆解副作用翻盘(层3)，缺一不可。
3. 代价双通道律（COST）：每次金手指生效必须输出“显性生理代价”和“隐性抽象损耗（不解释）”双通道。
4. 战利品双池律（LOOT）：胜利后战利品分“即时池(≤3项，立即可用)”和“延迟池(≥1项，功能锁仓不解释)”。
5. 章末异常钩子律（END）：章节最后200字禁止主角喊口号，必须输出“金手指异动”或“死物复苏”类客观异常现象。

[OUTPUT CHECK] 每生成一卷/章末尾，必须在独立 QA 侧车附上五条规则的自检结果（PASS/FAIL），FAIL项须附修订版本；严禁写入小说正文。
```"""
        self.assertIn(footer, skill)
        self.assertLess(skill.index(footer), skill.index("[MANDATORY] 玄幻开篇十条硬规则"))

    def test_templates_require_evidence_and_state_ledgers(self) -> None:
        card = self.read("assets/chapter-card-template.md")
        bible = self.read("assets/story-bible-template.md")
        for marker in (
            "前 150 字共情基准范围",
            "共情锚点值（必须 ≥ 6）",
            "首次超凡动作所在自然段（必须 > 3）",
            "B 为成立必须支付的隐藏代价 / 副作用",
            "智斗深度（必须 = 3）",
            "本次抽象异常类别（感知 / 物件 / 人格漂移）",
            "代价完整性（必须 = 2）",
            "即时池项目（必须 ≤ 3）",
            "各即时项在本章内的实际使用证据",
            "最后一句的异常现象主语",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, card)
        self.assertIn("金手指非线性代价账", bible)
        self.assertIn("战利品双池与延迟回收账", bible)
        self.assertIn("输出自检账", bible)
        self.assertIn("承诺回收章位 / 状态", bible)

    def test_output_check_is_mandatory_but_isolated_in_sidecar(self) -> None:
        skill = self.read("SKILL.md")
        card = self.read("assets/chapter-card-template.md")
        for marker in (
            "独立 QA 侧车",
            "逐项登记 01–10",
            "01–05 仍分别登记 `v1 PASS/FAIL｜既有 v2 PASS/FAIL`",
            "未触发项写 `PASS（未触发：原因）`",
            "FAIL 只回滚其触发范围",
            "最终交付前必须十项全部 PASS",
            "旧合同中“附上自检”的含义统一解释为“附独立 QA 文件或内部审计记录”",
            "黑匣子模式仍须完成十项内部自检",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)
        for marker in ("内部 QA 侧车记录", "禁止进入正文", "v1 PASS / FAIL", "既有 v2 PASS / FAIL", "BOUND-QUANT-06", "INFO-DELAY-10", "FAIL 修订版本与复检"):
            self.assertIn(marker, card)

    def test_reader_output_firewall_and_net_length_lock_are_welded(self) -> None:
        skill = self.read("SKILL.md")
        card = self.read("assets/chapter-card-template.md")
        bible = self.read("assets/story-bible-template.md")
        for marker in (
            "读者正文与编辑控制层永久隔离",
            "规则名、约束 ID、自检宏、PASS/FAIL、公式拆解和审计表",
            "每章必须独立达到 2000–3000 个净正文有效字符",
            "三章总和、平均数或其他长章不能补偿任一短章",
            "不统计批次标题清单、H1/H2 标题、标点、空白、Markdown 标记、HTML 注释、代码块、链接地址、编辑说明、规则 ID、自检表或 QA 内容",
            "生成纯正文 → 移除控制层污染 → 逐章净计数",
            "正文纯净门禁发现一个约束 ID",
            "QA 与正文必须分文件交付",
            "第 4、5 节已经标为默认硬锁的阈值与章位不受本句豁免",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)
        for marker in (
            "本章净正文有效字符",
            "扫描结果（必须 0 命中）",
            "QA 侧车路径（不得与正文合并）",
        ):
            self.assertIn(marker, card)
        self.assertIn("正文纯净与长度账", bible)
        self.assertIn("控制层污染命中数", bible)

    def test_v1_and_v2_are_cumulative_not_replacements(self) -> None:
        skill = self.read("SKILL.md")
        bible = self.read("assets/story-bible-template.md")
        for marker in (
            "v1 与 v2 是并行累积合同",
            "v2 只能新增阈值、顺序和复检，不能删除、替换或放宽 v1",
            "v1 要求至少 2 处明确计划陈述",
            "v1 要求最迟在首次至第 3 次使用间建立不可逆抽象损耗",
            "接下来 3 章内立即使用的消耗品",
            "v1 要求以认知错位或金手指被动异变形成客观异常",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)
        self.assertIn("v1、既有 v2 与新增 06–10 是并行累积合同，不得互相替换", bible)

    def test_v1_footer_is_restored_before_v2_footer(self) -> None:
        skill = self.read("SKILL.md")
        v1 = """**【硬规则模式：玄幻开篇生成校验锁】**
生成前三章正文时，所有输出必须逐条满足以下5项原子规则（违反任一规则则自动回滚重写）：
1. HOOK-EMO-01：第一章前150字强制包含“感官压迫+压迫者台词/死限”，超凡动作延后。
2. PLOT-MIND-02：交锋场景强制套娃三层（明面计划→反派反制→主角利用反制副作用破局）。
3. SYS-COST-03：每次金手指生效必须带“显性生理代价”和“不可解释的抽象损耗伏笔”，禁止线性数值兑换。
4. LOOT-DELAY-04：战利品分“即时池（≤3项）”与“延迟池（≥1项未知物）”，本章内禁止解释延迟池。
5. END-HOOK-05：章末禁止主角喊口号，强制采用“客观异变现象（金手指失控/死物复苏）”制造认知错位。"""
        self.assertIn(v1, skill)
        self.assertLess(skill.index(v1), skill.index("[MANDATORY] 玄幻开篇五条硬规则"))

    def test_new_five_locks_are_welded_and_atomic(self) -> None:
        skill = self.read("SKILL.md")
        for marker in (
            "BOUND-QUANT-06｜金手指量化边界锁",
            "本章存在总量参照",
            "本章存在单次变化尺度",
            "本章存在恢复路径暗示",
            "SMART-LIMIT-07｜智谋失算锁",
            "第三次智谋翻盘之前安排至少一次预判失效或设局失败",
            "失败原因是反派具体布置",
            "VILLAIN-LAYER-08｜反派层级锁",
            "当前反派独特手段 ≥ 1",
            "终极反派侧面描写 ≥ 2 且角度不同",
            "EVENT-RULE-09｜考核规则预埋锁",
            "比什么具体动作",
            "按何种时间、精度、消耗或结果判定胜负",
            "第一处预埋提前 ≥ 200 字",
            "开场前约 200 字内有回扣",
            "INFO-DELAY-10｜家族谜题延迟锁",
            "单场新事实 ≤ 3",
            "前三章核心真相公开比例 ≤ 50% 且事实点 ≤ 3",
            "本次产生新谜题 ≥ 1",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_mind_mode_and_cooldown_are_welded_without_weakening_mind_lock(self) -> None:
        skill = self.read("SKILL.md")
        for marker in (
            "主流玄幻模式",
            "70%–80% 武力、升级与结果兑现",
            "20%–30% 智斗布局",
            "智斗/权谋模式规划 50%–90% 智斗",
            "至少安排 3 章",
            "一旦写成智谋翻盘，仍执行 `PLOT-MIND-02`",
            "阶段与核心反派的非纯武力交锋必须执行完整三层智斗",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_new_lock_templates_and_ledgers_require_evidence(self) -> None:
        card = self.read("assets/chapter-card-template.md")
        bible = self.read("assets/story-bible-template.md")
        for marker in (
            "本章总量或当前余量的明确数值参照",
            "第二胜后、第三胜前的针对性失败",
            "当前压迫反派的独特可复现手段",
            "第一处预埋距正式开始的有效字数",
            "核心事实清单总数 / 当前公开比例",
            "后续至少 3 章冷却安排",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, card)
        for marker in (
            "金手指量化边界账",
            "智谋胜负与冷却账",
            "反派层级证据账",
            "核心事件规则账",
            "家族谜题信息账",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, bible)

    def test_ten_rule_footer_is_exact_and_precedes_isolation_lock(self) -> None:
        skill = self.read("SKILL.md").rstrip()
        footer = """```markdown
[MANDATORY] 玄幻开篇十条硬规则（违反任一则输出无效，必须回滚重写）：

01-情绪钩子前置律：第一章前150字内，感官词+反派台词+死限，锚点≥6后方可触发超凡动作。
02-智斗三层套娃律：交锋场景必须含“明面计划→反派拆解→主角利用拆解副作用翻盘”三层。
03-代价双通道律：每次金手指生效必须输出“显性生理代价”和“隐性抽象损耗（不解释）”。
04-战利品双池律：胜利后战利品分“即时池(≤3项，立即可用)”和“延迟池(≥1项，功能锁仓)”。
05-章末异常钩子律：最后200字禁止主角喊口号，必须输出“金手指异动”或“死物复苏”类客观异常。
06-金手指量化边界律：首次金手指展示时必须给出绝对度量参照（如总长度）和恢复路径暗示。
07-主角智力上限显性化律：主角连续智谋成功后，必须安排一次“预判被反派绕过”的失败。
08-反派层级具象化律：当前反派须有独特压迫手段；终极反派实体出场前须有至少两次侧面描写。
09-核心事件规则预埋律：任何考核/试炼开始前，必须提前交代“比什么、怎么分胜负、对手优势”。
10-家族谜题信息延迟律：每次揭秘最多3条新事实，且必须附带新的未解之谜。

[OUTPUT CHECK] 每生成一章末尾，必须在独立 QA 侧车附上十条规则的自检结果（PASS/FAIL），FAIL项须附修订版本；严禁写入小说正文。
```"""
        self.assertIn(footer, skill)
        self.assertLess(skill.index("[MANDATORY] 玄幻开篇五条硬规则"), skill.index(footer))
        isolation = "[MANDATORY] 读者正文隔离与逐章净字数锁"
        self.assertIn(isolation, skill)
        self.assertLess(skill.index(footer), skill.index(isolation))
        self.assertTrue(skill.endswith("```"))

    def test_loot_sentence_skeleton_is_generic(self) -> None:
        skill = self.read("SKILL.md")
        self.assertIn("{主角名}从未见过的", skill)
        self.assertIn("仿佛有什么东西在辨认他/她", skill)
        self.assertIn("占位符必须替换", skill)

    def test_audit_is_described_as_deterministic_not_market_proof(self) -> None:
        skill = self.read("SKILL.md")
        self.assertIn("审计脚本只检查可机械识别的候选", skill)
        self.assertIn("不把“通过门禁”写成“已是爆款”", skill)
        self.assertIn("--require-opening-three", skill)
        self.assertIn("--min-effective 2000", skill)
        self.assertIn("--max-effective 3000", skill)
        self.assertIn("审计控制文字判为正文污染", skill)


if __name__ == "__main__":
    unittest.main()
