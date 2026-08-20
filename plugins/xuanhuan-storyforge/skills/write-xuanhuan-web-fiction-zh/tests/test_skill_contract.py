from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CORE_CONTRACT = "references/core-contracts.md"
LEGACY_REFERENCE_PATHS = (
    "references/story-design.md",
    "references/character-emotion.md",
    "references/revision-continuity.md",
    "references/opening-retention-six-locks.md",
    "references/chapter-rhythm-twenty-locks.md",
    "references/chapter-rhythm-rules-21-30.md",
    "references/chapter-rhythm-rules-31-60.md",
    "references/prose-style.md",
)


class LeanSkillContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def core_contract(self) -> str:
        """Return the single human-readable source for the migrated core rules."""

        return self.read(CORE_CONTRACT)

    def test_required_files_exist(self) -> None:
        required = {
            "SKILL.md",
            "agents/openai.yaml",
            "assets/chapter-card-template.md",
            "assets/story-bible-template.md",
            "assets/story-state-template.json",
            CORE_CONTRACT,
            "references/story-design.md",
            "references/character-emotion.md",
            "references/revision-continuity.md",
            "references/opening-retention-six-locks.md",
            "references/chapter-rhythm-twenty-locks.md",
            "references/chapter-rhythm-rules-21-30.md",
            "references/chapter-rhythm-rules-31-60.md",
            "references/prose-style.md",
            "references/rule-registry.json",
            "references/zh-style-watchlist.json",
            "scripts/audit_chapter.py",
            "scripts/validate_rule_registry.py",
            "scripts/validate_story_state.py",
            "tests/test_audit_chapter.py",
            "tests/test_rule_registry.py",
            "tests/test_skill_contract.py",
            "tests/test_story_state.py",
        }
        actual = {
            str(path.relative_to(ROOT))
            for path in ROOT.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual(required, actual)

    def test_markdown_inventory_stays_lean(self) -> None:
        markdown = list(ROOT.rglob("*.md"))
        text_files = list(ROOT.rglob("*.txt"))
        self.assertLessEqual(len(markdown), 12)
        self.assertEqual([], text_files)
        # 连续性引擎是独立的高密度参考；上限仍只防无关材料膨胀。
        self.assertLess(sum(path.stat().st_size for path in markdown), 240_000)
        # v1 与 v2 必须并存；上限只防无关膨胀，不能倒逼删除任一合同。
        self.assertLessEqual((ROOT / "SKILL.md").stat().st_size, 24_000)
        self.assertLessEqual(
            len((ROOT / "SKILL.md").read_text(encoding="utf-8").splitlines()),
            250,
        )
        reference_markdown = list((ROOT / "references").glob("*.md"))
        self.assertLessEqual(len(reference_markdown), 9)
        self.assertLess(sum(path.stat().st_size for path in reference_markdown), 200_000)

    def test_frontmatter_is_minimal_and_valid(self) -> None:
        skill = self.read("SKILL.md")
        self.assertTrue(skill.startswith("---\nname: write-xuanhuan-web-fiction-zh\n"))
        frontmatter = skill.split("---", 2)[1]
        self.assertIn("\ndescription:", frontmatter)
        self.assertEqual(2, len([line for line in frontmatter.splitlines() if ":" in line]))

    def test_entry_directly_routes_core_and_preserves_legacy_references(self) -> None:
        skill = self.read("SKILL.md")
        core = self.core_contract()
        registry = json.loads(self.read("references/rule-registry.json"))
        self.assertIn(
            "生成、续写、重写或审校任何小说正文：必须完整读取并执行 "
            "[references/core-contracts.md](references/core-contracts.md)。",
            skill,
        )
        for relative in (CORE_CONTRACT, *LEGACY_REFERENCE_PATHS):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())
                self.assertIn(f"[{relative}]({relative})", skill)
        for relative in {rule["source"] for rule in registry["rules"]}:
            with self.subTest(registry_source=relative):
                self.assertIn(f"[{relative}]({relative})", skill)
        self.assertIn(
            "[references/rule-registry.json](references/rule-registry.json)",
            skill,
        )
        self.assertIn(
            "[scripts/validate_rule_registry.py](scripts/validate_rule_registry.py)",
            skill,
        )
        self.assertIn("它是人类可读的合同真源；入口只负责路由", core)
        self.assertNotIn("## 4. 黄金前三章通用合同", skill)
        self.assertNotIn("[MANDATORY]", skill)
        for rule_id in (
            "HOOK-EMO-01",
            "PLOT-MIND-02",
            "SYS-COST-03",
            "LOOT-DELAY-04",
            "END-HOOK-05",
        ):
            self.assertNotIn(rule_id, skill)

    def test_entry_preserves_non_rule_behavioral_boundaries(self) -> None:
        skill = self.read("SKILL.md")
        for marker in (
            "用户显式启用或覆盖的公式、数值与特殊写法",
            "除此之外的数字只有用户明确启用后才生效",
            "连续多章时维护滚动三章状态表",
            "每项增量都绑定触发事件与正文来源",
            "直接说明阻塞项、已完成项和下一步",
            "正文交付前不展示大纲、公式、章卡或套路分析",
            "人物通过压力下的选择立住，不靠旁白宣布性格",
            "理解不等于免责，其行为仍须承担后果",
            "悲伤不按性别限制停留时间",
            "不得抹掉弱势角色的主体性",
            "不得用无来源的新事实临时修补漏洞",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

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
                ROOT / CORE_CONTRACT,
                ROOT / "references/story-design.md",
                ROOT / "references/character-emotion.md",
                ROOT / "references/revision-continuity.md",
                ROOT / "references/opening-retention-six-locks.md",
                ROOT / "references/chapter-rhythm-twenty-locks.md",
                ROOT / "references/chapter-rhythm-rules-21-30.md",
                ROOT / "references/chapter-rhythm-rules-31-60.md",
                ROOT / "references/prose-style.md",
            ]
        )
        self.assertNotIn("project-lock-", runtime)
        self.assertNotIn("/Users/", runtime)
        self.assertNotIn("attachments/", runtime)
        self.assertNotIn("outputs/", runtime)
        self.assertIsNone(
            re.search(
                r"任务(?:引用|涉及)[^\n]{0,120}(?:正文核心实体|这组前三章时)",
                runtime,
            )
        )
        self.assertIn("默认只是理解规则的素材", runtime)
        self.assertIn("不得写入 Skill 描述、触发路由、门禁、模板、测试或通用参考", runtime)

    def test_seven_opening_rules_are_generic_and_present(self) -> None:
        core = self.core_contract()
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
                self.assertIn(marker, core)

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
        self.assertIn("逐章净正文2000–3200字符", metadata)
        self.assertIn("约束ID和自检只写独立QA侧车", metadata)

    def test_retention_reference_is_mandatory_and_cumulative(self) -> None:
        skill = self.read("SKILL.md")
        core = self.core_contract()
        retention = self.read("references/opening-retention-six-locks.md")
        self.assertIn(
            "完整读取并执行 [references/opening-retention-six-locks.md]",
            skill,
        )
        self.assertIn("其中九项留存硬锁默认强制并累积", skill)
        self.assertIn(
            "九项与七条前三章合同、v1、既有 v2、01–10、正文隔离锁及逐章净字数锁并列累积",
            core,
        )
        self.assertIn(
            "本文件九项硬锁与 `SKILL.md` 中的七条前三章合同、v1、既有 v2、01–10、正文隔离锁和逐章净字数锁并列累积",
            retention,
        )
        self.assertIn("不得替换、放宽或择一执行", retention)

    def test_retention_six_atomic_rules_are_welded(self) -> None:
        core = self.core_contract()
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
                self.assertIn(marker, core)

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
        self.assertIn("每章必须独立达到 2000–3200 个净正文有效字符", skill)

    def test_retention_future_gate_cannot_be_prematurely_passed(self) -> None:
        core = self.core_contract()
        retention = self.read("references/opening-retention-six-locks.md")
        self.assertIn("第 3 章场景转移必须已经在正文落地", retention)
        self.assertIn("第 10 章门槛记为“尚未到期，已规划”", retention)
        self.assertIn("不得提前登记通过", retention)
        self.assertIn("不足 6 章的交付只登记已规划峰值，不得提前写通过", retention)
        self.assertIn("未满 6 章时规划账不得写成已通过", core)

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
        self.assertIn("逐章净正文2000–3200字符", metadata)
        self.assertIn("约束ID和自检只写独立QA侧车", metadata)
        self.assertIn("示例不进入通用门禁", metadata)

    def test_hard_impact_contract_is_default_and_conjunctive(self) -> None:
        core = self.core_contract()
        self.assertIn("本节是默认强制的合取合同", core)
        self.assertIn("所有适用项都必须满足", core)
        for marker in (
            "3:1 可视偿债",
            "300/800 截断",
            "三向利益与反向记忆",
            "反派先拆牌",
            "世界观砸脸",
            "先动身体，再动脑",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, core)

    def test_payoff_and_hook_formulas_are_welded(self) -> None:
        core = self.core_contract()
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
                self.assertIn(marker, core)

    def test_character_antagonist_and_world_rules_are_welded(self) -> None:
        core = self.core_contract()
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
                self.assertIn(marker, core)

    def test_emotion_and_first_chapter_rules_are_welded(self) -> None:
        core = self.core_contract()
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
                self.assertIn(marker, core)

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
        core = self.core_contract()
        for marker in (
            "HOOK-EMO-01｜情绪钩子前置锁",
            "PLOT-MIND-02｜智斗三层套娃锁",
            "SYS-COST-03｜非线性代价锁",
            "LOOT-DELAY-04｜战利品双池锁",
            "END-HOOK-05｜章末认知错位锁",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, core)

    def test_hook_and_mind_locks_preserve_atomic_conditions(self) -> None:
        core = self.core_contract()
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
                self.assertIn(marker, core)

    def test_cost_loot_and_end_hook_conditions_are_atomic(self) -> None:
        core = self.core_contract()
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
                self.assertIn(marker, core)

    def test_existing_v2_validation_lock_is_preserved_before_ten_lock(self) -> None:
        core = self.core_contract()
        legacy_five = (
            "HOOK-EMO-01",
            "PLOT-MIND-02",
            "SYS-COST-03",
            "LOOT-DELAY-04",
            "END-HOOK-05",
        )
        positions = [core.index(marker) for marker in legacy_five]
        self.assertEqual(sorted(positions), positions)
        self.assertIn("旧“五条硬规则”分别以 5.2、5.4、5.7、5.8、5.9 为唯一规范正文", core)
        self.assertIn("旧“十条硬规则”在上述五条之上累加 5.10–5.14", core)
        self.assertLess(core.index("旧“五条硬规则”"), core.index("旧“十条硬规则”"))

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
        core = self.core_contract()
        card = self.read("assets/chapter-card-template.md")
        for marker in (
            "独立 QA 侧车",
            "逐项登记 01–10",
            "01–05 仍分别登记 `v1 PASS/FAIL｜既有 v2 PASS/FAIL`",
            "未触发项只能写 `未触发：具体原因`，不得登记 PASS",
            "FAIL 只回滚其触发范围",
            "最终交付前必须十项全部 PASS",
            "旧合同中“附上自检”的含义统一解释为“附独立 QA 文件或内部审计记录”",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, core)
        self.assertIn(
            "用户要求“直接生成”“不要解释过程”或“黑匣子模式”时，内部仍执行任务卡、因果骨架、状态事务和审计",
            skill,
        )
        for marker in ("内部 QA 侧车记录", "禁止进入正文", "v1 PASS / FAIL", "既有 v2 PASS / FAIL", "BOUND-QUANT-06", "INFO-DELAY-10", "FAIL 修订版本与复检"):
            self.assertIn(marker, card)

    def test_reader_output_firewall_and_net_length_lock_are_welded(self) -> None:
        skill = self.read("SKILL.md")
        core = self.core_contract()
        card = self.read("assets/chapter-card-template.md")
        bible = self.read("assets/story-bible-template.md")
        for marker in (
            "读者正文与编辑控制层永久隔离",
            "规则名、约束 ID、自检宏、PASS/FAIL、公式拆解和审计表",
            "每章必须独立达到 2000–3200 个净正文有效字符",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)
        for marker in (
            "三章总和、平均数或其他长章不能补偿任一短章",
            "不统计批次标题清单、H1/H2 标题、标点、空白、Markdown 标记、HTML 注释、代码块、链接地址、编辑说明、规则 ID、自检表或 QA 内容",
            "生成纯正文 → 移除控制层污染 → 逐章净计数",
            "正文纯净门禁发现一个约束 ID",
            "正文文件只保存标题清单、章标题和小说正文",
            "QA 默认另存为同目录同名 `.qa.json`",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, core)
        for marker in (
            "本章净正文有效字符",
            "扫描结果（必须 0 命中）",
            "QA 侧车路径（不得与正文合并）",
        ):
            self.assertIn(marker, card)
        self.assertIn("正文纯净与长度账", bible)
        self.assertIn("控制层污染命中数", bible)

    def test_v1_and_v2_are_cumulative_not_replacements(self) -> None:
        core = self.core_contract()
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
                self.assertIn(marker, core)
        self.assertIn("v1、既有 v2 与新增 06–10 是并行累积合同，不得互相替换", bible)

    def test_v1_lock_sequence_is_preserved_in_core_contract(self) -> None:
        core = self.core_contract()
        headings = (
            "### 5.2 钩子前置：300/800 截断",
            "### 5.4 反派先拆牌：三层智斗与主角能动性并存",
            "### 5.7 金手指非线性代价",
            "### 5.8 战利品延迟释放",
            "### 5.9 章末异常钩子",
        )
        positions = [core.index(heading) for heading in headings]
        self.assertEqual(sorted(positions), positions)
        self.assertIn("归并只消除重复，不删除、替换或放宽任何规则", core)

    def test_new_five_locks_are_welded_and_atomic(self) -> None:
        core = self.core_contract()
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
                self.assertIn(marker, core)

    def test_mind_mode_and_cooldown_are_welded_without_weakening_mind_lock(self) -> None:
        core = self.core_contract()
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
                self.assertIn(marker, core)

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

    def test_ten_rule_sequence_and_isolation_contract_are_preserved(self) -> None:
        core = self.core_contract()
        rule_ids = (
            "HOOK-EMO-01",
            "PLOT-MIND-02",
            "SYS-COST-03",
            "LOOT-DELAY-04",
            "END-HOOK-05",
            "BOUND-QUANT-06",
            "SMART-LIMIT-07",
            "VILLAIN-LAYER-08",
            "EVENT-RULE-09",
            "INFO-DELAY-10",
        )
        positions = [core.index(rule_id) for rule_id in rule_ids]
        self.assertEqual(sorted(positions), positions)
        self.assertLess(
            core.index("### 6.1 五条与十条开篇硬锁"),
            core.index("### 6.2 正文隔离、净字数与留存合同"),
        )
        self.assertIn("违反任一已触发硬锁时，输出无效", core)
        self.assertIn("正文中出现规则名、约束 ID、PASS/FAIL、自检宏或层级拆解即为污染", core)

    def test_loot_sentence_skeleton_is_generic(self) -> None:
        core = self.core_contract()
        self.assertIn("{主角名}从未见过的", core)
        self.assertIn("仿佛有什么东西在辨认他/她", core)
        self.assertIn("占位符必须替换", core)

    def test_audit_is_described_as_deterministic_not_market_proof(self) -> None:
        skill = self.read("SKILL.md")
        core = self.core_contract()
        self.assertIn("审计脚本只检查可机械识别的候选", skill)
        self.assertIn("不把“通过门禁”写成“已是爆款”", skill)
        self.assertIn("--require-opening-three", skill)
        self.assertIn("--min-effective 2000", skill)
        self.assertIn("--max-effective 3200", skill)
        self.assertIn("审计控制词，即判定整份正文 FAIL", core)

    def test_platform_modes_and_four_beat_are_cumulative_not_replacements(self) -> None:
        skill = self.read("SKILL.md")
        core = self.core_contract()
        design = self.read("references/story-design.md")
        self.assertIn(
            "规划全书、世界、力量、金手指、地图、秘境、高潮、命名、平台爽点模式或打脸四拍",
            skill,
        )
        for marker in (
            "订阅成长向",
            "免费滑读向",
            "超快脑洞向",
            "情感关系向",
            "通用平衡",
            "平台名称在本 Skill 中只代表用户选择的编辑模式",
            "不代表官方算法、当前推荐政策或市场保证",
            "压 → 扬 → 打 → 收",
            "四拍不能替代反派拆解及其副作用",
            "章末新危机只能在更高层继续施压",
            "黄金三章的平台适配",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, design)
        self.assertIn("### 6.3 平台爽点与去模板化合同", core)
        self.assertIn(
            "核心合同、开篇留存合同、六十项章节节奏锁、平台模式、风格合同和连续性合同并列累积",
            skill,
        )

    def test_prose_style_reference_is_mandatory_and_three_layered(self) -> None:
        skill = self.read("SKILL.md")
        style = self.read("references/prose-style.md")
        self.assertIn(
            "生成、续写、重写或审校任何小说正文：完整读取并执行 [references/prose-style.md]",
            skill,
        )
        self.assertIn("正文风格默认目标", skill)
        self.assertIn("风格目标可由风格卡按具体语境覆盖", skill)
        for marker in (
            "写前风格注入",
            "写中约束",
            "写后检测与改写",
            "重新验收",
            "候选命中不是错误，更不是作者身份判断",
            "具体物件 + 动态动词 + 一项感官 + 人物主观滤镜",
            "触发事件 → 生理反应 → 行为冲动 → 抑制或爆发 → 环境或关系反馈",
            "风格白名单",
            "平均有效句长目标不超过 25 个字符",
            "对话目标占读者可见正文约 30% 以上",
            "环境描写目标不超过约 15%",
            "抽象词候选密度目标低于约 5%",
            "不能说“检测证明不是 AI 写的”",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, style)

    def test_platform_and_style_evidence_stay_in_sidecar_templates(self) -> None:
        card = self.read("assets/chapter-card-template.md")
        bible = self.read("assets/story-bible-template.md")
        for marker in (
            "目标平台 / 爽点模式",
            "去模板化强度（标准 / 强约束 / 自定义）与风格白名单",
            "平台爽点与打脸四拍",
            "正文去模板化审校",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, card)
        for marker in (
            "平台长线期待与即时兑现账",
            "打脸四拍账",
            "正文风格卡",
            "去模板化复检账",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, bible)

    def test_style_watchlist_is_candidate_only_and_extensible(self) -> None:
        watchlist = self.read("references/zh-style-watchlist.json")
        for marker in (
            '"schema_version": "1.1"',
            '"abstract_uplift"',
            '"cliche_simile"',
            '"summary_ending"',
            "候选",
            "不能据此判断作者身份",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, watchlist)

    def test_agent_metadata_routes_platform_and_style_without_exposing_controls(self) -> None:
        metadata = self.read("agents/openai.yaml")
        self.assertLess(len(metadata), 600)
        self.assertIn("按目标平台选择爽点模式", metadata)
        self.assertIn("完成去模板化审校", metadata)
        self.assertIn("约束ID和自检只写独立QA侧车", metadata)
        self.assertIn("四拍拆解也须隔离", metadata)

    def test_longform_continuity_contract_is_cumulative_and_internal_only(self) -> None:
        skill = self.read("SKILL.md")
        core = self.core_contract()
        continuity = self.read("references/revision-continuity.md")
        card = self.read("assets/chapter-card-template.md")
        bible = self.read("assets/story-bible-template.md")
        metadata = self.read("agents/openai.yaml")
        self.assertIn(
            "完整读取并执行 [references/revision-continuity.md]",
            skill,
        )
        self.assertIn("### 6.4 长篇连续性与防跳脱合同", core)
        self.assertIn(
            "核心合同、开篇留存合同、六十项章节节奏锁、平台模式、风格合同和连续性合同并列累积",
            skill,
        )
        for marker in (
            "### R1 事实锁",
            "### R2 人物锁",
            "### R3 世界锁",
            "### R4 主线锁",
            "### R5 因果禁区",
            "### R6 冲突仲裁锁",
            "### R7 视角锁",
            "### R8 信息锁",
            "### R9 时间锁",
            "### R10 空间锁",
            "载入状态 N → 章前预检 → 场景生成 → 章后增量",
            "正向回放",
            "逆向举证",
            "正文文件：只含标题和小说正文",
            "状态文件：保存结构化状态",
            "QA 侧车：保存规则证据",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, continuity)
        for marker in (
            "场景 POV / 可感知边界",
            "人物当前状态 → 允许状态 / 所需触发事件",
            "章后状态增量与回溯",
            "最终正文哈希 / 输出状态版本",
        ):
            self.assertIn(marker, card)
        for marker in (
            "事实版本账",
            "人物状态机",
            "逐角色知情账",
            "统一时间线",
            "人物位置与移动账",
            "唯一物品持有与转移账",
            "未解决连续性冲突",
        ):
            self.assertIn(marker, bible)
        self.assertIn("连续性状态事务", metadata)
        self.assertIn("正文、state、QA三分离", metadata)

    def test_story_state_validator_and_template_are_routed_without_quality_overclaim(self) -> None:
        skill = self.read("SKILL.md")
        continuity = self.read("references/revision-continuity.md")
        validator = self.read("scripts/validate_story_state.py")
        state_template = self.read("assets/story-state-template.json")
        self.assertIn("scripts/validate_story_state.py <当前.state.json>", skill)
        self.assertIn("非初始状态必须提供 --previous", skill)
        self.assertIn("--prose <最终正文.md>", skill)
        self.assertIn("story-state-template.json", continuity)
        for marker in (
            '"text_sha256"',
            '"keyframes"',
            '"chapter_transactions"',
            '"unresolved_conflicts"',
        ):
            self.assertIn(marker, state_template)
        for marker in (
            "previous_state_required",
            "unresolved_hard_conflict",
            "current_keyframe_binding_invalid",
            "ownership_model",
            ".qa.json",
        ):
            self.assertIn(marker, validator)
        self.assertIn("它不证明数量守恒", continuity)
        self.assertIn("它不证明数量守恒、自由文本时间先后、人物动机", continuity)

    def test_twenty_chapter_rhythm_locks_are_mandatory_and_cumulative(self) -> None:
        skill = self.read("SKILL.md")
        core = self.core_contract()
        rhythm = self.read("references/chapter-rhythm-twenty-locks.md")
        metadata = self.read("agents/openai.yaml")
        self.assertIn(
            "完整读取并合取执行 [references/chapter-rhythm-twenty-locks.md]",
            skill,
        )
        self.assertIn("核心合同、开篇留存合同、六十项章节节奏锁", skill)
        self.assertIn("在 QA 侧车写“未触发：具体原因”", skill)
        self.assertIn("未触发项只能写 `未触发：具体原因`，不得登记 PASS", core)
        self.assertIn(
            "全部已触发、已到期六十项节奏锁也必须全部 PASS",
            core,
        )
        self.assertIn(
            "与 `SKILL.md` 的七条前三章合同、v1、既有 v2、01–10、九项留存锁",
            rhythm,
        )
        self.assertIn("逐章节奏六十项硬锁", metadata)
        self.assertIn("逐章净正文2000–3200字符", metadata)
        self.assertIn("显式目标另取正负20%交集", metadata)
        rule_names = (
            "节奏控制协议",
            "主角能动性协议",
            "反派压迫感协议",
            "金手指差异化记忆点协议",
            "信息密度编码协议",
            "开篇钩子协议",
            "章节结尾断崖钩子协议",
            "情绪收益打脸反差节奏协议",
            "对话信息冲突双载协议",
            "宏观信息三章释放定律协议",
            "打斗场景三幕式协议",
            "配角功能标签变数协议",
            "战力边界锚定协议",
            "环境五感触发协议",
            "心理行动外化协议",
            "修炼升级三不写协议",
            "支线三章回收挂起协议",
            "悬念类型轮换协议",
            "章间前情微召回协议",
            "世界观名词首次出现即锚定协议",
        )
        for name in rule_names:
            with self.subTest(name=name):
                self.assertIn(name, rhythm)

    def test_twenty_locks_preserve_pov_causality_and_ability_scarcity(self) -> None:
        rhythm = self.read("references/chapter-rhythm-twenty-locks.md")
        for marker in (
            "规则名、公式、IF/THEN",
            "最终读者正文必须只含章标题与小说正文",
            "每章独立 **2000–3200 个净正文有效字符**",
            "禁止为了达标临时插入无铺垫袭击、异象、救兵或机械降神",
            "旁观者反应必须是当前 POV 能观察到的两份独立反应",
            "三项基础功能必须是本故事中本质不同的用途",
            "首次有效使用仍须当场说明可操作的效果、代价、边界",
            "配角功能、钩子类型、节拍类型、爽点等级和三幕结构只写内部账",
            "问题可以由事实缺口表达，不强制出现问号或感叹号",
            "沉睡伏笔不等于活跃支线",
            "普通人名、称谓、既知简称和无需记忆的背景名不计",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, rhythm)

    def test_twenty_lock_evidence_is_routed_to_sidecar_templates(self) -> None:
        card = self.read("assets/chapter-card-template.md")
        bible = self.read("assets/story-bible-template.md")
        for marker in (
            "逐章节奏六十项 QA 侧车记录",
            "有效节拍位置与最大间隔",
            "核心能力 3 项本质功能 + 1 项",
            "宏观谜题 T1、T2、T3",
            "活跃支线三章期限",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, card)
        for marker in (
            "逐章节奏与主角能动性滚动账",
            "反派、能力与宏观谜题账",
            "战斗、战力、配角与修炼账",
            "支线、悬念、章间衔接与名词账",
            "六十项节奏锁触发与复检账",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, bible)

    def test_rules_21_to_30_are_additive_strict_and_isolated(self) -> None:
        skill = self.read("SKILL.md")
        extra = self.read("references/chapter-rhythm-rules-21-30.md")
        continuity = self.read("references/revision-continuity.md")
        metadata = self.read("agents/openai.yaml")
        self.assertIn(
            "[references/chapter-rhythm-rules-21-30.md]",
            skill,
        )
        self.assertIn("只新增规则二十一至三十，不替换、不删减、不放宽前二十项", extra)
        rule_names = (
            "名词首次出现即锚定协议（强化版）",
            "信息释放密度 224 协议",
            "伏笔三章挂起提醒协议",
            "代价数值前十章固定标注协议",
            "未知物品功能边界三章内暴露协议",
            "主角每章成长痕迹协议",
            "世界观底层规则一致性协议",
            "同类描写去重协议",
            "章节目标净字数正负百分之二十协议",
            "生成后执行报告协议",
        )
        for name in rule_names:
            with self.subTest(name=name):
                self.assertIn(name, extra)
        for marker in (
            "同一段落、本句或下一句",
            "关键新专名最多四个",
            "结果不得超过 5.0",
            "N+1 与 N+3",
            "前十章的标注覆盖率至少 90%",
            "每章至少出现一次当前绝对状态参照",
            "N+3 结束前披露至少一项真实边界",
            "章首旧状态、触发事件、章末新状态",
            "已接受正文中出现可核对的来源锚与摘录哈希",
            "禁止使用同义词轮换器",
            "最终下界为 `max(2000, ceil(0.8T))`",
            "交集为空时属于配置冲突",
            "报告不得追加到小说正文",
            "同轮未通过项达到三项，执行二轮修正",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, extra)
        self.assertNotIn("即使没有状态变化，也记录空增量", continuity)
        self.assertIn("规则二十六让主角", continuity)
        self.assertIn("逐章节奏六十项硬锁", metadata)

    def test_rules_21_to_30_evidence_is_in_sidecars_and_ledgers(self) -> None:
        card = self.read("assets/chapter-card-template.md")
        bible = self.read("assets/story-bible-template.md")
        for marker in (
            "单章目标净字数 / 当前绝对窗口 / 目标正负20%交集窗口",
            "数值界面（开启 / 关闭 / 自定义）",
            "规则 21 同段本句或下一句锚定位置",
            "信息载荷 `L = 0.3N + 1.2T + 0.8I`",
            "重大伏笔首现 N / N+1 与 N+3 回响到期",
            "主角章首旧状态 / 触发事件 / 章末新状态",
            "规则 30：QA 报告路径",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, card)
        for marker in (
            "规则二十一至三十滚动账",
            "名词锚定与信息 224 账",
            "重大伏笔与未知物品期限账",
            "前十章状态结算与主角成长账",
            "底层规则、描写去重与目标字数账",
            "规则执行报告与二轮修订账",
            "同一段落、本句或下一句锚定",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, bible)

    def test_rules_31_to_60_are_additive_exact_and_isolated(self) -> None:
        skill = self.read("SKILL.md")
        first_twenty = self.read("references/chapter-rhythm-twenty-locks.md")
        rules_21_to_30 = self.read("references/chapter-rhythm-rules-21-30.md")
        rules_31_to_60 = self.read("references/chapter-rhythm-rules-31-60.md")
        metadata = self.read("agents/openai.yaml")

        self.assertIn(
            "[references/chapter-rhythm-rules-31-60.md](references/chapter-rhythm-rules-31-60.md)",
            skill,
        )
        self.assertIn("核心合同、开篇留存合同、六十项章节节奏锁", skill)
        self.assertIn("逐章节奏六十项硬锁", metadata)
        self.assertIn(
            "只新增规则三十一至六十，不替换、不删减、不放宽前二十项和规则二十一至三十",
            rules_31_to_60,
        )
        self.assertIn("chapter-rhythm-twenty-locks.md", rules_31_to_60)
        self.assertIn("chapter-rhythm-rules-21-30.md", rules_31_to_60)

        rule_names = (
            "滚动一千五百字新术语密度协议",
            "功能解释五百至八百字延迟协议",
            "概念父子链协议",
            "双危机或三千字冲突后泄压协议",
            "代价关系角色可见协议",
            "牺牲型策略非战斗截断协议",
            "普通线索N+3触碰协议",
            "章尾四型轮换协议",
            "对话L1/L2/L3单一主功能协议",
            "亲密表达反套话协议",
            "长期感官损失异质代偿协议",
            "滚动三章代价清点协议",
            "新场景环境三锚协议",
            "场景中段物件过渡协议",
            "重大冲突三波协议",
            "规则博弈前三百字显化协议",
            "红黄绿线配比协议",
            "红线新信息百字重估协议",
            "配角连续三章自利决策协议",
            "反派三行动私人压力泄漏协议",
            "紧密第三人称限知视角协议",
            "不可直知信息迹象推断协议",
            "角色动作签名协议",
            "动作观察判断执行协议",
            "物件跨章状态台账协议",
            "活跃物件三章触碰协议",
            "章内峰谷协议",
            "缓场实体展开协议",
            "三轮对话动作穿插协议",
            "纯动作三百字认知插针协议",
        )
        self.assertEqual(30, len(rule_names))
        self.assertEqual(30, len(set(rule_names)))
        positions = []
        for name in rule_names:
            with self.subTest(name=name):
                self.assertIn(name, rules_31_to_60)
                positions.append(rules_31_to_60.index(name))
        self.assertEqual(sorted(positions), positions)

        # 新增层不能靠删除旧层换取空间；旧二十项与 21–30 的精确合同仍在。
        self.assertIn("节奏控制协议", first_twenty)
        self.assertIn("世界观名词首次出现即锚定协议", first_twenty)
        self.assertIn("名词首次出现即锚定协议（强化版）", rules_21_to_30)
        self.assertIn("生成后执行报告协议", rules_21_to_30)

    def test_rules_31_to_60_arbitrate_existing_locks_without_relaxing_them(self) -> None:
        rules = self.read("references/chapter-rhythm-rules-31-60.md")
        for marker in (
            "任意滚动 1500 个净正文有效字符内，新术语最多 2 个",
            "首次锚定、可操作边界与安全限制不得延迟",
            "完整功能解释延迟到首次效果展示后的 500–800 个有效字符",
            "父概念 → 子概念 → 实例",
            "连续 2 次危机升级",
            "冲突累计达到 3000 个净正文有效字符",
            "关系角色可在当前 POV 中观察到的动作",
            "不得切换 POV",
            "普通线索首现章记为 N",
            "N+3 章结束前",
            "事件、认知、情感、感官",
            "L1、L2、L3 中只能有一个主功能",
            "异质代偿",
            "任意滚动 3 章",
            "不超过 80 个净正文有效字符",
            "温度、声场、气味或触感",
            "中段过渡物",
            "三波",
            "前 300 个净正文有效字符内",
            "1–2 条可操作规则",
            "红线约 60%",
            "黄线 20%–30%",
            "绿线不超过 10%",
            "红线新信息出现后 100 个净正文有效字符内",
            "任意连续 3 章",
            "自利主动决策",
            "同章出现至少 3 个独立行动",
            "私人压力",
            "紧密第三人称限知",
            "可见迹象 + 明示推断",
            "动作签名",
            "观察 → 判断 → 执行",
            "物件跨章状态台账",
            "活跃物件",
            "3 章内至少触碰一次",
            "峰段最长不得超过 800 个净正文有效字符",
            "谷段至少 150 个净正文有效字符",
            "身体状态或环境的二次展开",
            "每 3 轮对话",
            "连续纯动作达到 300 个净正文有效字符前",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, rules)

        for arbitration in (
            "规则二十、二十一、二十二合取后取更严的单章关键新专名最多 4 个",
            "规则三十二不延迟规则二十、二十一要求的首次同段锚定",
            "规则三十七不替代重大伏笔的 N+1 / N+3 双提醒",
            "规则四十三只使用当前 POV 仍可用的感官",
            "规则五十一禁止用规则三十六制造真实视角切换",
            "规则五十五的台账只进入状态文件或 QA 侧车",
        ):
            with self.subTest(arbitration=arbitration):
                self.assertIn(arbitration, rules)

    def test_rules_31_to_60_evidence_is_in_sidecars_and_continuity_ledgers(self) -> None:
        card = self.read("assets/chapter-card-template.md")
        bible = self.read("assets/story-bible-template.md")
        continuity = self.read("references/revision-continuity.md")
        metadata = self.read("agents/openai.yaml")

        for marker in (
            "规则 31–60 QA 侧车证据",
            "滚动1500字新术语窗口",
            "功能解释首次效果位置 / 500–800字到期",
            "父概念 / 子概念 / 实例",
            "危机次数 / 冲突累计字数 / 泄压证据",
            "代价关系见证动作",
            "普通线索首现 N / N+3 触碰",
            "章尾钩子主型",
            "对话 L1/L2/L3 主功能",
            "长期感官损失 / 异质代偿 / 危机判断",
            "红黄绿线占比",
            "当前 POV / 可见迹象 / 明示推断",
            "角色动作签名",
            "关键动作观察 / 判断 / 执行",
            "活跃物件三章触碰",
            "峰段 / 谷段",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, card)

        for marker in (
            "规则三十一至六十滚动账",
            "术语、概念链与功能解释账",
            "危机泄压、代价见证与牺牲截断账",
            "线索、钩子、对话与亲密表达账",
            "感官损失代偿与代价清点账",
            "场景锚点、过渡物与冲突三波账",
            "红黄绿线、配角与反派压力账",
            "POV、信息迹象与动作签名账",
            "物件状态、活跃期限与章内峰谷账",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, bible)

        for marker in (
            "紧密第三人称限知",
            "不可直知信息",
            "当前 POV 可见迹象",
            "角色动作签名",
            "物件跨章状态",
            "已接受正文来源锚",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, continuity)
        self.assertIn("逐章节奏六十项硬锁", metadata)
        self.assertIn("正文、state、QA三分离", metadata)

    def test_rules_31_to_60_reports_and_internal_labels_never_pollute_prose(self) -> None:
        skill = self.read("SKILL.md")
        rules = self.read("references/chapter-rhythm-rules-31-60.md")
        card = self.read("assets/chapter-card-template.md")
        for marker in (
            "规则名、编号、阈值、证据坐标、PASS/FAIL 与滚动账只写独立 QA 侧车",
            "最终读者正文只含章标题与小说正文",
            "不得在小说正文中输出规则三十一至六十的名称、编号或自检报告",
            "证据只能来自已接受正文、已验证 state 或用户明确确认的事实",
            "不得为通过门禁伪造证据位置、动作、节拍、物件状态或关系变化",
            "计划中的证据不得登记为 PASS",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, rules)
        self.assertIn("规则 31–60 QA 侧车证据", card)
        self.assertIn("约束ID和自检只写独立QA侧车", self.read("agents/openai.yaml"))
        self.assertIn("## 8. 正文、状态与 QA 隔离", skill)
        self.assertIn("正文标题、段落或文件不得出现约束 ID、规则名、PASS/FAIL", skill)


if __name__ == "__main__":
    unittest.main()
