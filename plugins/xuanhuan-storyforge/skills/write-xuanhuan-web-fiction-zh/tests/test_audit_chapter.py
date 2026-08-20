from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
AUDIT = SKILL_ROOT / "scripts" / "audit_chapter.py"
AUDIT_SPEC = importlib.util.spec_from_file_location("xuanhuan_audit_chapter", AUDIT)
assert AUDIT_SPEC is not None and AUDIT_SPEC.loader is not None
AUDIT_MODULE = importlib.util.module_from_spec(AUDIT_SPEC)
sys.modules[AUDIT_SPEC.name] = AUDIT_MODULE
AUDIT_SPEC.loader.exec_module(AUDIT_MODULE)


def make_batch(labels: list[tuple[str, str]], lengths: list[int]) -> str:
    inventory = ["## 本批章节标题", ""]
    chapters: list[str] = []
    for index, ((label, title), length) in enumerate(zip(labels, lengths), start=1):
        inventory.append(f"{index}. {label}《{title}》")
        ending = "门开了"
        chapters.extend(
            ["", f"# {label} {title}", "", "甲" * (length - len(ending)) + "。", ending + "。"]
        )
    return "\n".join(inventory + chapters) + "\n"


RULES_31_TO_60_LABELS = (
    "术语密度上限",
    "延迟解释",
    "概念捆绑",
    "高压-泄压钟摆",
    "代价被看见",
    "情感逆转",
    "最小反馈闭环",
    "钩子类型轮换",
    "对话三级负载",
    "不说破亲密",
    "感官代偿",
    "跨章代价清点",
    "环境锚定",
    "中间物",
    "三波冲突",
    "前置条件显化",
    "悬念红黄绿",
    "认知回落",
    "配角主动决策",
    "反派失衡",
    "视角刚性锁定",
    "推断句替代",
    "动作个人签名",
    "动作三步",
    "物件状态表",
    "活跃物件三章触碰",
    "章内波谷波峰",
    "缓场两个必须",
    "三轮对话插动作",
    "纯动作300字",
)

RULES_31_TO_60_EXACT_NAMES = (
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


class OpeningThreeGateTests(unittest.TestCase):
    def direct_purity_and_counts(self, text: str) -> tuple[dict, list[int]]:
        purity = AUDIT_MODULE.fiction_purity_gate(text)
        sections = AUDIT_MODULE.split_chapter_sections(text)
        if not sections:
            sections = [{"text": text}]
        counts: list[int] = []
        for section in sections:
            cleaned, _ = AUDIT_MODULE.clean_markdown(section["text"])
            counts.append(AUDIT_MODULE.effective_count(cleaned))
        return purity, counts

    def run_audit(
        self,
        text: str,
        *,
        opening: bool = True,
        require_title: bool = True,
        minimum: int = 2000,
        maximum: int = 3200,
        opening_minimum: int | None = None,
        opening_maximum: int | None = None,
        target_effective: int | None = None,
        max_paragraph_sentence_average: float | None = None,
        forbid_outside_dialogue: list[str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chapter = root / "opening.md"
            report = root / "report.json"
            chapter.write_text(text, encoding="utf-8")
            command = [
                sys.executable,
                str(AUDIT),
                str(chapter),
                "--min-effective",
                str(minimum),
                "--max-effective",
                str(maximum),
                "--json-out",
                str(report),
            ]
            if require_title:
                command.append("--require-title")
            if opening:
                command.append("--require-opening-three")
            if opening_minimum is not None:
                command.extend(["--opening-min-effective", str(opening_minimum)])
            if opening_maximum is not None:
                command.extend(["--opening-max-effective", str(opening_maximum)])
            if target_effective is not None:
                command.extend(["--target-effective", str(target_effective)])
            if max_paragraph_sentence_average is not None:
                command.extend(
                    [
                        "--max-paragraph-sentence-average",
                        str(max_paragraph_sentence_average),
                    ]
                )
            for term in forbid_outside_dialogue or []:
                command.extend(["--forbid-outside-dialogue", term])
            result = subprocess.run(command, text=True, capture_output=True, check=False)
            payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
            return result, payload

    def test_valid_opening_three_passes(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
            [2000, 2500, 3000],
        )
        result, report = self.run_audit(text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(report["opening_three_gate"]["passed"])
        self.assertEqual(
            [item["effective_prose_chars"] for item in report["opening_three_gate"]["chapters"]],
            [2000, 2500, 3000],
        )

    def test_two_chapters_fail(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印")],
            [2600, 2600],
        )
        result, report = self.run_audit(text)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["opening_three_gate"]["passed"])
        self.assertIn("fewer than three", report["opening_three_gate"]["reason"])

    def test_wrong_order_fails_even_when_inventory_matches(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第三章", "阶上留痕"), ("第二章", "旧约落印")],
            [2600, 2600, 2600],
        )
        result, report = self.run_audit(text)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(report["title_gate"]["passed"])
        self.assertFalse(report["opening_three_gate"]["passed"])

    def test_opening_range_is_fixed_even_if_general_range_is_broader(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
            [1999, 2600, 3201],
        )
        result, report = self.run_audit(text, minimum=0, maximum=4000)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(report["length_gate"]["passed"])
        self.assertFalse(report["opening_three_gate"]["passed"])
        self.assertFalse(report["opening_three_gate"]["chapters"][0]["length_passed"])
        self.assertFalse(report["opening_three_gate"]["chapters"][2]["length_passed"])

    def test_arabic_low_chapter_numbers_are_accepted(self) -> None:
        text = make_batch(
            [("第1章", "门前异响"), ("第2章", "旧约落印"), ("第3章", "阶上留痕")],
            [2600, 2600, 2600],
        )
        result, report = self.run_audit(text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(report["opening_three_gate"]["passed"])

    def test_explicit_opening_range_override_is_honored(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
            [1800, 1850, 1900],
        )
        result, report = self.run_audit(
            text,
            minimum=0,
            maximum=4000,
            opening_minimum=1800,
            opening_maximum=1900,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(report["opening_three_gate"]["passed"])
        self.assertEqual(report["opening_three_gate"]["minimum"], 1800)
        self.assertEqual(report["opening_three_gate"]["maximum"], 1900)

    def test_default_opening_and_general_range_is_2000_to_3200(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
            [2000, 2500, 3200],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chapter = root / "opening.md"
            report_path = root / "report.json"
            chapter.write_text(text, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(AUDIT),
                    str(chapter),
                    "--require-title",
                    "--require-opening-three",
                    "--json-out",
                    str(report_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(report["length_gate"]["minimum"], 2000)
        self.assertEqual(report["length_gate"]["maximum"], 3200)
        self.assertEqual(report["opening_three_gate"]["minimum"], 2000)
        self.assertEqual(report["opening_three_gate"]["maximum"], 3200)

    def test_punctuation_or_emoji_only_titles_fail(self) -> None:
        for bad_title in ("——", "！！！", "🔥"):
            with self.subTest(title=bad_title):
                text = make_batch(
                    [("第一章", bad_title), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
                    [2600, 2600, 2600],
                )
                result, report = self.run_audit(text)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["title_gate"]["passed"])

    def test_title_disguised_as_another_chapter_number_fails(self) -> None:
        for bad_title in ("第1章", "第二章", "第一百章"):
            with self.subTest(title=bad_title):
                text = make_batch(
                    [("第一章", bad_title), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
                    [2600, 2600, 2600],
                )
                result, report = self.run_audit(text)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["title_gate"]["passed"])

    def test_fourth_chapter_does_not_change_first_three_contract(self) -> None:
        text = make_batch(
            [
                ("第一章", "门前异响"),
                ("第二章", "旧约落印"),
                ("第三章", "阶上留痕"),
                ("第四章", "入谷"),
            ],
            [2600, 2600, 2600, 2600],
        )
        result, report = self.run_audit(text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(report["opening_three_gate"]["passed"])
        self.assertEqual(len(report["opening_three_gate"]["chapters"]), 3)

    def test_old_mode_remains_available(self) -> None:
        text = make_batch([("第一章", "旧稿")], [2100])
        result, report = self.run_audit(
            text, opening=False, minimum=2000, maximum=4000
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIsNone(report["opening_three_gate"]["passed"])

    def test_opening_flag_requires_title_protocol(self) -> None:
        text = make_batch(
            [("第一章", "一"), ("第二章", "二"), ("第三章", "三")],
            [2600, 2600, 2600],
        )
        result, report = self.run_audit(text, require_title=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report, {})
        self.assertIn("requires --require-title", result.stderr)

    def test_report_explicitly_disclaims_semantic_and_market_proof(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
            [2600, 2600, 2600],
        )
        result, report = self.run_audit(text)
        self.assertEqual(result.returncode, 0)
        limitations = " ".join(report["limitations"])
        self.assertIn("cannot verify the seven-rule opening contract", limitations)
        self.assertIn("protagonist setup", limitations)
        self.assertIn("retention semantics", limitations)
        self.assertIn("irreversible stakes", limitations)
        self.assertIn("unexpected fourth choice", limitations)
        self.assertIn("scene-transfer/dungeon loop", limitations)
        self.assertIn("reader retention", limitations)
        self.assertIn("market performance", limitations)

    def test_rule_id_in_prose_fails_purity_and_cannot_pad_length(self) -> None:
        text = make_batch([("第一章", "净稿")], [1990])
        polluted = text.replace(
            "\n门开了。\n",
            "\n**SYS-COST-03**：" + "审计填充" * 100 + "\n门开了。\n",
        )
        result, report = self.run_audit(
            polluted, opening=False, minimum=2000, maximum=3000
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["fiction_purity_gate"]["passed"])
        self.assertEqual(
            report["fiction_purity_gate"]["hits"][0]["kind"],
            "rule_constraint_id",
        )
        self.assertLessEqual(
            report["length_gate"]["chapters"][0]["effective_prose_chars"],
            1990,
        )
        self.assertFalse(report["length_gate"]["passed"])

    def test_output_check_block_fails_purity_and_is_excluded_from_length(self) -> None:
        text = make_batch([("第一章", "净稿")], [1900])
        text += (
            "\n## [OUTPUT CHECK]\n\n"
            "全部规则 PASS/FAIL：" + "审计填充" * 100 + "\n"
        )
        result, report = self.run_audit(
            text, opening=False, minimum=2000, maximum=3000
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["fiction_purity_gate"]["passed"])
        self.assertEqual(
            report["length_gate"]["chapters"][0]["effective_prose_chars"],
            1900,
        )
        self.assertFalse(report["length_gate"]["passed"])

    def test_fenced_rule_id_still_fails_reader_facing_purity(self) -> None:
        text = make_batch([("第一章", "净稿")], [2000])
        text += "\n```markdown\nPLOT-MIND-02：层1计划，层2反制，层3破局。\n```\n"
        result, report = self.run_audit(
            text, opening=False, minimum=2000, maximum=3000
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["fiction_purity_gate"]["passed"])
        self.assertTrue(
            any(
                hit["kind"] == "rule_constraint_id"
                for hit in report["fiction_purity_gate"]["hits"]
            )
        )
        self.assertEqual(
            report["length_gate"]["chapters"][0]["effective_prose_chars"],
            2000,
        )

    def test_visually_obfuscated_rule_ids_fail_and_cannot_pad(self) -> None:
        variants = (
            "规则SYS-COST-03通过",
            "SYS-**COST**-03",
            "SYS-<span>COST</span>-03",
            "SYS-CO\u200bST-03",
            "SYS-CO\u00adST-03",
            "SYS-CO\u034fST-03",
            "SYS-CO\u061cST-03",
            "SYS-CO\u180eST-03",
            "SYS-CO\ufe00ST-03",
            "SYS-CO\ufe0fST-03",
            "SYS-CO\U000e0100ST-03",
            "SYS‐COST‐03",
            "ＳＹＳ－ＣＯＳＴ－０３",
            "SYS-[COST](https://example.invalid)-03",
            "SYS-[COST][internal]-03",
            r"SYS\-COST\-03",
            "SYS&#45;COST&#45;03",
            "SYS-<!--hidden-->COST-03",
            "SYS-<span title=\">\">COST</span>-03",
            "情绪钩子前置锁",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                text = make_batch([("第一章", "净稿")], [1990])
                text = text.replace(
                    "\n门开了。\n",
                    f"\n{variant}：" + "审计填充" * 100 + "\n门开了。\n",
                )
                result, report = self.run_audit(
                    text, opening=False, minimum=2000, maximum=3000
                )
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["fiction_purity_gate"]["passed"])
                self.assertLessEqual(
                    report["length_gate"]["chapters"][0]["effective_prose_chars"],
                    1990,
                )

    def test_markdown_link_output_check_fails_and_cannot_pad(self) -> None:
        text = make_batch([("第一章", "净稿")], [1900])
        text += (
            "\n## [OUTPUT](https://example.invalid) CHECK\n"
            + "审计填充" * 100
            + "\n"
        )
        result, report = self.run_audit(
            text, opening=False, minimum=2000, maximum=3000
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["fiction_purity_gate"]["passed"])
        self.assertEqual(
            report["length_gate"]["chapters"][0]["effective_prose_chars"],
            1900,
        )

    def test_shortcut_and_softbreak_control_markers_fail(self) -> None:
        variants = (
            "SYS-[COST]-03\n\n[COST]: https://example.invalid",
            "SYS-[COST](https://example.invalid/a_(b))-03",
            "## [OUTPUT] CHECK\n" + "审计填充" * 100,
            "OUTPUT\nCHECK\n" + "审计填充" * 100,
        )
        for variant in variants:
            with self.subTest(first_line=variant.splitlines()[0]):
                text = make_batch([("第一章", "净稿")], [1900])
                text += "\n" + variant + "\n"
                result, report = self.run_audit(
                    text, opening=False, minimum=2000, maximum=3000
                )
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["fiction_purity_gate"]["passed"])
                if variant.startswith("OUTPUT\nCHECK"):
                    self.assertEqual(
                        report["length_gate"]["chapters"][0][
                            "effective_prose_chars"
                        ],
                        1900,
                    )

    def test_multiline_comment_cannot_split_a_rule_id(self) -> None:
        text = make_batch([("第一章", "净稿")], [2000])
        text += "\nSYS-<!--\nhidden\n-->COST-03\n"
        result, report = self.run_audit(
            text, opening=False, minimum=2000, maximum=3000
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["fiction_purity_gate"]["passed"])

    def test_multiline_html_cannot_split_a_rule_id(self) -> None:
        text = make_batch([("第一章", "净稿")], [1900])
        text += "\nSYS-<span\n title=\">\">COST</span>-03\n" + "审计填充" * 100
        result, report = self.run_audit(
            text, opening=False, minimum=2000, maximum=3000
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["fiction_purity_gate"]["passed"])

    def test_control_ids_in_html_attributes_fail_purity(self) -> None:
        clean = make_batch([("第一章", "净稿")], [2000])
        for attribute in ("SYS-COST-03", "[OUTPUT CHECK]"):
            with self.subTest(attribute=attribute):
                text = clean + f'\n<input value="{attribute}">\n'
                result, report = self.run_audit(
                    text, opening=False, minimum=2000, maximum=3000
                )
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["fiction_purity_gate"]["passed"])

    def test_hidden_html_and_code_cannot_pad_net_fiction_length(self) -> None:
        filler = "审计填充" * 25
        variants = (
            f"<div hidden>{filler}</div>",
            f'<div style="display:none">{filler}</div>',
            f"<script>{filler}</script>",
            f"<style>{filler}</style>",
            f"<template>{filler}</template>",
            f"<pre><code>{filler}</code></pre>",
            "    " + filler,
            "\t" + filler,
        )
        for variant in variants:
            with self.subTest(prefix=variant[:20]):
                text = make_batch([("第一章", "净稿")], [1900]) + "\n" + variant
                result, report = self.run_audit(
                    text, opening=False, minimum=2000, maximum=3000
                )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(
                    report["length_gate"]["chapters"][0][
                        "effective_prose_chars"
                    ],
                    1900,
                )
                self.assertFalse(report["length_gate"]["passed"])

    def test_hidden_html_cannot_visually_rejoin_a_rule_id(self) -> None:
        clean = make_batch([("第一章", "净稿")], [2000])
        variants = (
            "SYS-<span hidden>x</span>COST-03",
            'SYS-<span style="display:none">x</span>COST-03',
            "SYS-<script>x</script>COST-03",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                result, report = self.run_audit(
                    clean + "\n" + variant,
                    opening=False,
                    minimum=2000,
                    maximum=3000,
                )
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["fiction_purity_gate"]["passed"])

    def test_bidi_and_homoglyph_rule_ids_fail_purity(self) -> None:
        clean = make_batch([("第一章", "净稿")], [2000])
        variants = (
            "SYS-\u202eTSOC\u202c-03",
            'SYS-<bdo dir="rtl">TSOC</bdo>-03',
            'SYS-<span style="unicode-bidi:bidi-override;direction:rtl">TSOC</span>-03',
            "ЅҮЅ-СОЅТ-03",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                result, report = self.run_audit(
                    clean + "\n" + variant,
                    opening=False,
                    minimum=2000,
                    maximum=3000,
                )
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["fiction_purity_gate"]["passed"])

    def test_retention_rule_names_fail_purity_and_cannot_pad_length(self) -> None:
        variants = (
            "开篇情感锚定",
            "主角差异性行为律",
            "爽点频率与间隔",
            "章尾动作与信息双钩子",
            "章尾信息悬停锁",
            "世界观双向展示",
            "节奏与副本周期",
            "场景转移与副本周期锁",
            "前三万字六项留存硬锁",
            "前三万字九项留存硬锁",
            "设定稀缺性",
            "情绪峰值类型配比",
            "情绪失控系数",
            "章尾安全区禁令",
            "开篇**情感**锚定",
            "章尾<span>动作与信息</span>双钩子",
            "世界观双\u200b向展示",
            "[节奏与副本周期](https://example.invalid)",
            "六项留存<!--hidden-->硬锁",
            "九项留存<!--hidden-->硬锁",
            "世界观双向\n展示",
            "设定稀缺\n性",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                text = make_batch([("第一章", "净稿")], [1900])
                text += "\n" + variant + "\n" + "审计填充" * 100 + "\n"
                result, report = self.run_audit(
                    text,
                    opening=False,
                    minimum=2000,
                    maximum=3000,
                )
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["fiction_purity_gate"]["passed"])
                self.assertEqual(
                    report["length_gate"]["chapters"][0]["effective_prose_chars"],
                    1900,
                )
                self.assertFalse(report["length_gate"]["passed"])

    def test_retention_formula_and_choice_labels_fail_purity(self) -> None:
        variants = (
            "爽点密度 = 2.5",
            "主角意外指数：0.7",
            "爆款留存率 = 8.1",
            "设定稀缺性评分 = 6.0",
            "情绪失控系数：0.66",
            "章尾焦虑值：4",
            "常规选择一：求饶",
            "第四方案：反向设局",
            "六项留存检查：",
            "九项留存检查：",
            "核心外挂稀缺性：已排除",
            "意外型翻盘：2",
            "算计型翻盘：1",
            "滚动6章窗口：",
            "安全区禁令：通过",
            "本章落袋微爽点：已完成",
            "改写前文因果判断的新事实：身份有误",
            "第10章门槛状态：尚未到期",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                clean = make_batch([("第一章", "净稿")], [2000])
                result, report = self.run_audit(
                    clean + "\n" + variant,
                    opening=False,
                    minimum=2000,
                    maximum=3000,
                )
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["fiction_purity_gate"]["passed"])

    def test_natural_world_and_payoff_prose_is_not_mistaken_for_control_text(self) -> None:
        text = make_batch([("第一章", "净稿")], [2000])
        text += "\n这世界很奇，他终于拿到了应得的回报。\n"
        result, report = self.run_audit(
            text,
            opening=False,
            minimum=2000,
            maximum=3000,
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report["fiction_purity_gate"]["passed"])

    def test_embedded_qa_report_phrase_in_narration_is_not_a_control_heading(self) -> None:
        text = make_batch([("第一章", "净稿")], [2000])
        text += "\n账房递来的QA报告写着药材短缺，纸角还沾着雨。\n"
        result, report = self.run_audit(
            text,
            opening=False,
            minimum=2000,
            maximum=3000,
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report["fiction_purity_gate"]["passed"])

    def test_softbreak_retention_audit_labels_fail_and_cannot_pad(self) -> None:
        variants = (
            "爽点密度\n=2.5",
            "爽点密度<br>=2.5",
            "第四\n方案：反向设局",
            "第四<br>方案：反向设局",
            "设定稀缺性<br>评分：6",
            "情绪失控<br>系数：0.66",
            "章尾安全区<br>禁令：通过",
            "Q\nA报告\n纯净：通过",
            "Q<br>A报告\n纯净：通过",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                text = make_batch([("第一章", "净稿")], [1900])
                text += "\n" + variant + "\n" + "审计填充" * 100 + "\n"
                result, report = self.run_audit(
                    text,
                    opening=False,
                    minimum=2000,
                    maximum=3000,
                )
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["fiction_purity_gate"]["passed"])
                self.assertEqual(
                    report["length_gate"]["chapters"][0]["effective_prose_chars"],
                    1900,
                )
                self.assertFalse(report["length_gate"]["passed"])

    def test_platform_and_four_beat_control_blocks_fail_and_cannot_pad(self) -> None:
        variants = (
            "## 平台爽点适配",
            "## 起点向硬规则",
            "番茄爽点逻辑：即时情绪+翻页率",
            "| 平台 | 爽点逻辑 | 特点 |",
            "打脸四拍：压—扬—打—收",
            "第一拍：压\n第二拍：扬\n第三拍：打\n第四拍：收",
            "黄金三章公式：",
            "爽点公式 = （压抑×期待）÷释放时间",
            "期待感公式 = 目标清晰+阻力强大",
            "章节钩子公式 = 新危机",
            "番茄快节奏开头模板",
            "起点升级文模板",
            "身份反差装逼打脸模板",
            "起点卖的是‘成长期待+长期追读’，番茄卖的是‘即时情绪+翻页率’。",
            "起点、番茄等平台的爽点逻辑分别是什么？",
            "起点爽点关键词：期待、成长、升级",
            "番茄爽点关键词：即时打脸、身份反差",
            "### 1. 起点：付费订阅向",
            "### 1. 起点：付费订阅向，核心是‘期待感+成长线’",
            "### 2. 番茄：免费广告向，核心是‘即时情绪+高刺激’",
            "起点重成长，番茄重情绪。",
            "飞卢：开局核爆、每章打脸。",
            "压->扬->打->收",
            "压➡扬➡打➡收",
            "压/扬/打/收",
        )
        for variant in variants:
            with self.subTest(variant=variant.splitlines()[0]):
                text = make_batch([("第一章", "净稿")], [1900])
                text += "\n" + variant + "\n" + "审计填充" * 100 + "\n"
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_deai_control_blocks_fail_purity_and_cannot_pad(self) -> None:
        variants = (
            "[角色设定]",
            "[写作宪法——AI味硬规则]",
            "去AI味系统指令",
            "AI味检测与改写层",
            "去AI味检测与改写：",
            "AI味版本：",
            "去AI味版本：",
            "禁用词词库：仿佛、似乎、然而",
            "AI高频词清单：仿佛、似乎、然而",
            "对话占比至少30%",
            "环境描写不超过15%",
            "抽象词密度低于5%",
            "平均句长不超过25字",
            "每300字内至少出现一个具体感官细节",
            "每500字内至少出现一个具体动作",
            "连续心理独白不超过3句",
            "请检查以下小说片段，找出AI味问题",
            "改写要求：",
            "## 写作前：风格注入层",
            "## 写作中：硬规则约束层",
            "### 1. 词汇层",
            "### 2. 句式层",
            "### 3. 内容层",
            "### 4. 节奏层",
            "### 5. 情感层",
            "### 1. 场景公式",
            "### 2. 描写公式",
            "### 3. 对话公式",
            "### 4. 情绪公式",
            "### 5. 段落节奏公式",
            "### 6. 开头公式",
            "### 7. 结尾公式",
            "## 四、后处理‘去AI味’检测与改写指令",
            "禁用或尽量少用以下AI高频词：仿佛、似乎",
            "禁止连续使用排比句。",
            "禁止直接告诉读者情绪。",
            "对话必须像人话。",
            "不要总结升华。",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                text = make_batch([("第一章", "净稿")], [1900])
                text += "\n" + variant + "\n" + "审计填充" * 100 + "\n"
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_new_craft_control_markers_obfuscated_fail_and_cannot_pad(self) -> None:
        variants = (
            "打脸**四拍**：压—扬—打—收",
            "[打脸四拍](https://example.invalid)：压—扬—打—收",
            "打脸<span>四拍</span>：压—扬—打—收",
            "打脸<!--hidden-->四拍：压—扬—打—收",
            "打脸\u200b四拍：压—扬—打—收",
            "打脸<br>四拍：压—扬—打—收",
            "打脸**\n**四拍：压—扬—打—收",
            "打[脸](https://example.invalid)\n四拍：压—扬—打—收",
            "去**AI**味自检：",
            "去AI<br>味自检：",
            "去AI\n味自检：",
            "起点向<br>硬规则",
            "起点向\n硬规则",
            "打\n脸\n四\n拍：压—扬—打—收",
            "打脸\n\n\n四拍：压—扬—打—收",
            "去\nAI\n味\n自检：",
            "起\n点\n向\n硬\n规\n则",
        )
        for variant in variants:
            with self.subTest(variant=variant.splitlines()[0]):
                text = make_batch([("第一章", "净稿")], [1900])
                text += "\n" + variant + "\n" + "审计填充" * 100 + "\n"
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_craft_control_block_resets_at_next_chapter_boundary(self) -> None:
        text = make_batch(
            [("第一章", "短章"), ("第二章", "正常章")],
            [1900, 2000],
        )
        text = text.replace(
            "\n# 第二章 正常章\n",
            "\n## 去AI味检测与改写\n"
            + "审计填充" * 100
            + "\n# 第二章 正常章\n",
        )
        purity, counts = self.direct_purity_and_counts(text)
        self.assertFalse(purity["passed"])
        self.assertEqual(counts, [1900, 2000])

    def test_craft_near_neighbor_prose_is_not_misclassified(self) -> None:
        variants = (
            "起点在北门外，番茄摊挨着药铺。",
            "七只猫从晋江渡口窜过。",
            "他压住刀背，扬腕打飞铁钉，收刀时没看身后。",
            "少年抬手打了自己一耳光，又在门上拍了四下。",
            "器灵自称AI，却尝不出酒里的铁锈味。",
            "他从供词上划掉‘仿佛’二字，墨还没干。",
            "掌柜把禁用的药名写进词库，免得伙计抓错药。",
            "三十人里至少来了九个，院中只占三成。",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                text = make_batch([("第一章", "净稿")], [2000]) + "\n" + variant
                purity, counts = self.direct_purity_and_counts(text)
                self.assertTrue(purity["passed"])
                self.assertGreaterEqual(counts[0], 2000)
                self.assertLessEqual(counts[0], 3000)

    def test_watchlist_hit_is_candidate_not_a_failing_style_gate(self) -> None:
        text = make_batch([("第一章", "净稿")], [2000])
        text += "\n他仿佛听见井底有人敲了两下。\n"
        result, report = self.run_audit(
            text, opening=False, minimum=2000, maximum=3000
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(report["style_gates"]["passed"])
        self.assertTrue(
            any(hit["term"] == "仿佛" for hit in report["watchlist_hits"])
        )

    def test_craft_control_cli_smoke_fails_and_cannot_pad(self) -> None:
        text = make_batch([("第一章", "净稿")], [1900])
        text += "\n## 去AI味检测与改写\n" + "审计填充" * 100 + "\n"
        result, report = self.run_audit(
            text, opening=False, minimum=2000, maximum=3000
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["fiction_purity_gate"]["passed"])
        self.assertEqual(
            report["length_gate"]["chapters"][0]["effective_prose_chars"],
            1900,
        )

    def test_standalone_status_and_generic_selfcheck_blocks_are_excluded(self) -> None:
        variants = (
            "01 PASS\n" + "审计填充" * 100,
            "02 FAIL\n" + "审计填充" * 100,
            "## 自检结果\n" + "审计填充" * 100,
            "## 输出自检\n" + "审计填充" * 100,
            "AI 自检：\n" + "审计填充" * 100,
            "## QA\n01 通过\n" + "审计填充" * 100,
            "## 检查结果\n01 通过\n" + "审计填充" * 100,
            "## QA 报告\n纯净：通过\n" + "审计填充" * 100,
            "## QA结果\n纯净：通过\n" + "审计填充" * 100,
            "## 质量检查\n纯净：通过\n" + "审计填充" * 100,
            "PLOT-MIND-02：层1计划\n" + "无标签续行" * 100,
        )
        for variant in variants:
            with self.subTest(first_line=variant.splitlines()[0]):
                text = make_batch([("第一章", "净稿")], [1900])
                text = text.replace("\n门开了。\n", f"\n{variant}\n门开了。\n")
                result, report = self.run_audit(
                    text, opening=False, minimum=2000, maximum=3000
                )
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["fiction_purity_gate"]["passed"])
                self.assertLessEqual(
                    report["length_gate"]["chapters"][0]["effective_prose_chars"],
                    1900,
                )
                self.assertFalse(report["length_gate"]["passed"])

    def test_generic_selfcheck_in_code_fence_still_fails_purity(self) -> None:
        text = make_batch([("第一章", "净稿")], [2000])
        text += "\n```markdown\n自检结果\n01 PASS\n02 FAIL\n```\n"
        result, report = self.run_audit(
            text, opening=False, minimum=2000, maximum=3000
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["fiction_purity_gate"]["passed"])
        self.assertEqual(
            report["length_gate"]["chapters"][0]["effective_prose_chars"],
            2000,
        )

    def test_hidden_comment_and_frontmatter_control_text_fail_purity(self) -> None:
        clean = make_batch([("第一章", "净稿")], [2000])
        variants = (
            clean + "\n<!-- HOOK-EMO-01 PASS -->\n",
            "---\ninternal: HOOK-EMO-01 PASS\n---\n" + clean,
        )
        for text in variants:
            with self.subTest(prefix=text[:20]):
                result, report = self.run_audit(
                    text, opening=False, minimum=2000, maximum=3000
                )
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["fiction_purity_gate"]["passed"])
                self.assertEqual(
                    report["length_gate"]["chapters"][0]["effective_prose_chars"],
                    2000,
                )

    def test_fullwidth_output_check_starts_excluded_audit_block(self) -> None:
        text = make_batch([("第一章", "净稿")], [1900])
        text += "\n## ［ＯＵＴＰＵＴ ＣＨＥＣＫ］\n" + "审计填充" * 100 + "\n"
        result, report = self.run_audit(
            text, opening=False, minimum=2000, maximum=3000
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["fiction_purity_gate"]["passed"])
        self.assertEqual(
            report["length_gate"]["chapters"][0]["effective_prose_chars"],
            1900,
        )

    def test_h2_chapters_are_counted_independently_not_as_one_document(self) -> None:
        text = (
            "## 第一章 短章一\n\n"
            + "甲" * 997
            + "。\n门开了。\n\n"
            + "## 第二章 短章二\n\n"
            + "乙" * 997
            + "。\n灯灭了。\n"
        )
        result, report = self.run_audit(
            text,
            opening=False,
            require_title=False,
            minimum=2000,
            maximum=3000,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(report["length_gate"]["chapters"]), 2)
        self.assertEqual(
            [
                item["effective_prose_chars"]
                for item in report["length_gate"]["chapters"]
            ],
            [1000, 1000],
        )
        self.assertFalse(report["length_gate"]["passed"])

    def test_plain_text_chapters_are_counted_independently(self) -> None:
        text = (
            "第一章 短章一\n\n"
            + "甲" * 997
            + "。\n门开了。\n\n"
            + "第二章 短章二\n\n"
            + "乙" * 997
            + "。\n灯灭了。\n"
        )
        result, report = self.run_audit(
            text,
            opening=False,
            require_title=False,
            minimum=2000,
            maximum=3000,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(report["length_gate"]["chapters"]), 2)
        self.assertEqual(
            [
                item["effective_prose_chars"]
                for item in report["length_gate"]["chapters"]
            ],
            [1000, 1000],
        )

    def test_bare_chapter_numbers_still_create_independent_sections(self) -> None:
        variants = (
            (
                "## 第一章\n\n"
                + "甲" * 997
                + "。\n门开了。\n\n"
                + "## 第二章\n\n"
                + "乙" * 997
                + "。\n灯灭了。\n"
            ),
            (
                "第一章\n\n"
                + "甲" * 997
                + "。\n门开了。\n\n"
                + "第二章\n\n"
                + "乙" * 997
                + "。\n灯灭了。\n"
            ),
        )
        for text in variants:
            with self.subTest(first_line=text.splitlines()[0]):
                result, report = self.run_audit(
                    text,
                    opening=False,
                    require_title=False,
                    minimum=2000,
                    maximum=3000,
                )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(len(report["length_gate"]["chapters"]), 2)
                self.assertEqual(
                    [
                        item["effective_prose_chars"]
                        for item in report["length_gate"]["chapters"]
                    ],
                    [1000, 1000],
                )
                self.assertFalse(report["length_gate"]["passed"])

    def test_rendered_chapter_headings_cannot_aggregate_short_chapters(self) -> None:
        variants = (
            (
                "# **第一章 短章一**\n\n"
                + "甲" * 1000
                + "\n# **第二章 短章二**\n\n"
                + "乙" * 1000
            ),
            (
                "# [第一章 短章一](https://example.invalid)\n\n"
                + "甲" * 1000
                + "\n# [第二章 短章二](https://example.invalid)\n\n"
                + "乙" * 1000
            ),
            (
                "# <span>第一章 短章一</span>\n\n"
                + "甲" * 1000
                + "\n# <span>第二章 短章二</span>\n\n"
                + "乙" * 1000
            ),
            (
                "<h1>第一章 短章一</h1>\n"
                + "甲" * 1000
                + "\n<h1>第二章 短章二</h1>\n"
                + "乙" * 1000
            ),
            (
                "## 第\u200b壹章\n"
                + "甲" * 1000
                + "\n## 第贰章\n"
                + "乙" * 1000
            ),
            (
                "第一章 我重生了！\n"
                + "甲" * 1000
                + "\n第二章 杀出山门！\n"
                + "乙" * 1000
            ),
            (
                "# 第一章《短章一》\n"
                + "甲" * 1000
                + "\n# 第二章《短章二》\n"
                + "乙" * 1000
            ),
        )
        for text in variants:
            with self.subTest(first_line=text.splitlines()[0]):
                result, report = self.run_audit(
                    text,
                    opening=False,
                    require_title=False,
                    minimum=2000,
                    maximum=3000,
                )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(
                    [
                        item["effective_prose_chars"]
                        for item in report["length_gate"]["chapters"]
                    ],
                    [1000, 1000],
                )

    def test_narrative_audit_words_and_ordinal_sentence_are_not_metadata(self) -> None:
        text = (
            "# 第一章 净稿\n\n"
            + "甲" * 995
            + "。\n户部的审计报告昨夜失窃。\n"
            + "第一章 只是序幕。\n"
            + "乙" * 984
            + "。\n门开了。\n"
        )
        result, report = self.run_audit(
            text,
            opening=False,
            require_title=False,
            minimum=2000,
            maximum=3000,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(report["fiction_purity_gate"]["passed"])
        self.assertEqual(len(report["length_gate"]["chapters"]), 1)
        self.assertEqual(
            report["length_gate"]["chapters"][0]["effective_prose_chars"],
            2000,
        )

    def test_document_headings_and_numbered_prose_are_not_audit_metadata(self) -> None:
        variants = ("检查结果", "审计报告", "1. 通过，生。")
        for line in variants:
            with self.subTest(line=line):
                text = (
                    "# 第一章 净稿\n\n"
                    + "甲" * 1000
                    + "。\n"
                    + line
                    + "\n"
                    + "乙" * 1000
                    + "。\n"
                )
                result, report = self.run_audit(
                    text,
                    opening=False,
                    require_title=False,
                    minimum=2000,
                    maximum=3000,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(report["fiction_purity_gate"]["passed"])

    def test_opening_final_sentence_over_fifteen_effective_chars_fails(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
            [2600, 2600, 2600],
        )
        text = text.rsplit("门开了。", 1)[0] + "那扇沉重的青铜门终于在众人眼前缓慢打开了。\n"
        result, report = self.run_audit(text)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["opening_three_gate"]["passed"])
        third = report["opening_three_gate"]["chapters"][2]
        self.assertGreater(third["final_sentence_effective_chars"], 15)
        self.assertFalse(third["final_sentence_passed"])

    def test_opening_final_sentence_at_fifteen_effective_chars_passes(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
            [2600, 2600, 2600],
        )
        text = text.rsplit("门开了。", 1)[0] + "青铜大门终于就在众人眼前打开了。\n"
        result, report = self.run_audit(text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        third = report["opening_three_gate"]["chapters"][2]
        self.assertEqual(third["final_sentence_effective_chars"], 15)
        self.assertTrue(third["final_sentence_passed"])

    def test_json_output_cannot_overwrite_source(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
            [2600, 2600, 2600],
        )
        with tempfile.TemporaryDirectory() as directory:
            chapter = Path(directory) / "opening.md"
            chapter.write_text(text, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(AUDIT),
                    str(chapter),
                    "--require-title",
                    "--require-opening-three",
                    "--json-out",
                    str(chapter),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("must not overwrite the source chapter", result.stderr)
            self.assertEqual(chapter.read_text(encoding="utf-8"), text)

    def test_json_report_does_not_expose_absolute_source_path(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
            [2600, 2600, 2600],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private_directory = root / "private-author-workspace"
            private_directory.mkdir()
            chapter = private_directory / "opening.md"
            report_path = root / "report.json"
            chapter.write_text(text, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(AUDIT),
                    str(chapter),
                    "--require-title",
                    "--require-opening-three",
                    "--json-out",
                    str(report_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(report["source"]["name"], "opening.md")
        self.assertNotIn("path", report["source"])
        self.assertNotIn("private-author-workspace", json.dumps(report, ensure_ascii=False))

    def test_json_output_cannot_overwrite_watchlist(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
            [2600, 2600, 2600],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chapter = root / "opening.md"
            watchlist = root / "watchlist.json"
            chapter.write_text(text, encoding="utf-8")
            watchlist_payload = '{"categories": []}\n'
            watchlist.write_text(watchlist_payload, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(AUDIT),
                    str(chapter),
                    "--require-title",
                    "--require-opening-three",
                    "--watchlist",
                    str(watchlist),
                    "--json-out",
                    str(watchlist),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("must not overwrite the watchlist", result.stderr)
            self.assertEqual(watchlist.read_text(encoding="utf-8"), watchlist_payload)

    def test_forbidden_term_outside_dialogue_fails_but_dialogue_exception_passes(self) -> None:
        outside = make_batch([("第一章", "旧稿")], [2100]).replace("甲甲", "仿佛", 1)
        result, report = self.run_audit(
            outside,
            opening=False,
            minimum=2000,
            maximum=4000,
            forbid_outside_dialogue=["仿佛,似乎"],
        )
        self.assertEqual(result.returncode, 1)
        gate = report["style_gates"]["forbidden_outside_dialogue"]
        self.assertFalse(gate["passed"])
        self.assertEqual(gate["hits"][0]["term"], "仿佛")

        quoted = make_batch([("第一章", "旧稿")], [2100]).replace(
            "甲甲甲", "“仿佛。”", 1
        )
        result, report = self.run_audit(
            quoted,
            opening=False,
            minimum=2000,
            maximum=4000,
            forbid_outside_dialogue=["仿佛,似乎"],
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(report["style_gates"]["forbidden_outside_dialogue"]["passed"])

    def test_paragraph_average_sentence_length_gate_is_per_source_paragraph(self) -> None:
        inventory = "## 本批章节标题\n\n1. 第一章《短句》\n\n# 第一章 短句\n\n"
        passing = inventory + ("甲" * 18 + "。\n\n") * 3
        result, report = self.run_audit(
            passing,
            opening=False,
            minimum=0,
            maximum=4000,
            max_paragraph_sentence_average=18,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(report["style_gates"]["paragraph_sentence_average"]["passed"])

        failing = inventory + "甲" * 19 + "。\n\n乙。\n"
        result, report = self.run_audit(
            failing,
            opening=False,
            minimum=0,
            maximum=4000,
            max_paragraph_sentence_average=18,
        )
        self.assertEqual(result.returncode, 1)
        gate = report["style_gates"]["paragraph_sentence_average"]
        self.assertFalse(gate["passed"])
        self.assertEqual(gate["violations"][0]["average_effective_chars"], 19)

    def test_continuity_control_blocks_fail_purity_and_cannot_pad_length(self) -> None:
        markers = (
            "【正文前检查】",
            "## 正文后状态更新",
            "【设定库更新】",
            "[新增设定]",
            "【生成前复述】",
            "【章前状态卡】",
            "【章后状态增量】",
            "【人物状态机】",
            "【剧情阶段状态机】",
            "【时间线账本】",
            "【伏笔账本】",
            "【关键帧计划】",
            "【回溯校验】",
            "【章节自问自答】",
            "【锚点提醒】",
            "【纠偏指令】",
            "【对抗性自检】",
            "【全局一致性检查】",
            "【行为约束伪代码】",
        )
        for marker in markers:
            with self.subTest(marker=marker):
                text = "# 第一章 净稿\n" + "甲" * 1900 + "\n" + marker + "\n" + "审计填充" * 100
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_r_locks_status_and_obfuscated_controls_cannot_pad_length(self) -> None:
        markers = (
            "R1：事实锁",
            "R2：人物锁",
            "R7：视角锁",
            "R10：空间锁",
            "R**1**：PASS",
            "R<span>1</span>：FAIL",
            "R<!--x-->1：PASS",
            "R\u200b1：检查",
            "Ｒ１：ＰＡＳＳ",
            "R<br>1：PASS",
            "R\n1：PASS",
            "P\nA\nS\nS",
            "F<br>A<br>I<br>L",
            "正\n文\n前\n检\n查",
            "正<br>文<br>后<br>状<br>态<br>更<br>新",
            "设\u200b定<!--x-->库<span>更</span>新",
            "[新**增**设定](https://example.invalid)",
        )
        for marker in markers:
            with self.subTest(marker=marker):
                text = "# 第一章 净稿\n" + "甲" * 1900 + "\n" + marker + "\n" + "审计填充" * 100
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_structured_state_json_yaml_and_tables_cannot_pad_length(self) -> None:
        markers = (
            "场景：客栈\n时间：黄昏\n地点：城南\n人物状态：受伤",
            "【场景】客栈 【时间】黄昏 【地点】城南 【人物状态】受伤",
            "场景=客栈；时间=黄昏；地点=城南；状态=受伤",
            "| 场景 | 时间 | 地点 | 人物状态 |\n|---|---|---|---|",
            "| 场景 | 时间 | 地点 | 状态 |\n|---|---|---|---|",
            "| **场景** | **时间** | **地点** | **角色状态** |\n|---|---|---|---|",
            "｜场景｜时间｜地点｜当前状态｜",
            '{"场景":"青石巷","时间":"子时","地点":"南门","状态":"重伤"}',
            "<table><tr><th>场景</th><th>时间</th><th>地点</th><th>状态</th></tr></table>",
            "<table><tr><th>scene</th><th>time</th><th>location</th><th>state</th></tr></table>",
            '{"characters": [], "timeline": [], "knowledge": []}',
            "characters:\n  - character_id: c1\nscene: inn\ntime: dusk\nlocation: south\nstate: hurt",
            "```json\n{\"facts\": [], \"characters\": []}\n审计填充审计填充\n```",
            "<!-- {\"chapter_transactions\": [], \"keyframes\": []} -->",
        )
        for marker in markers:
            with self.subTest(marker=marker):
                text = "# 第一章 净稿\n" + "甲" * 1900 + "\n" + marker + "\n" + "审计填充" * 100
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_continuity_controls_reset_at_next_chapter_and_nearby_prose_passes(self) -> None:
        text = (
            "# 第一章 净稿\n"
            + "甲" * 1900
            + "\n【正文后状态更新】\n"
            + "审计填充" * 100
            + "\n# 第二章 正文\n"
            + "乙" * 2000
        )
        purity, counts = self.direct_purity_and_counts(text)
        self.assertFalse(purity["passed"])
        self.assertEqual(counts, [1900, 2000])

        normal_lines = (
            "这个事实他早就知道。",
            "他的状态很差，仍提刀往前。",
            "时间不多了。",
            "地点在城南。",
            "眼前场景让他想起旧宅。",
            "正文前，他检查了一遍落款。",
            "正文后，状态更新得很慢。",
            "R1号傀儡撞破木门。",
            "他失败了三次，第四次才通过山门。",
            "账簿第三页写着地点和时间，墨迹还没干。",
        )
        for line in normal_lines:
            with self.subTest(line=line):
                normal = "# 第一章 净稿\n" + "甲" * 2000 + "\n" + line
                self.assertTrue(AUDIT_MODULE.fiction_purity_gate(normal)["passed"])

    def test_twenty_rhythm_rule_names_cannot_pad_length(self) -> None:
        markers = (
            "规则一 · 节奏控制协议",
            "规则二 · 主角能动性协议",
            "规则三 · 反派压迫感协议",
            "规则四 · 金手指差异化记忆点协议",
            "规则五 · 信息密度编码协议",
            "规则六 · 开篇钩子协议",
            "规则七 · 章节结尾断崖钩子协议",
            "规则八 · 情绪收益打脸反差节奏协议",
            "规则九 · 对话信息冲突双载协议",
            "规则十 · 宏观信息三章释放定律协议",
            "规则十一 · 打斗场景三幕式协议",
            "规则十二 · 配角功能标签变数协议",
            "规则十三 · 战力边界锚定协议",
            "规则十四 · 环境五感触发协议",
            "规则十五 · 心理行动外化协议",
            "规则十六 · 修炼升级三不写协议",
            "规则十七 · 支线三章回收挂起协议",
            "规则十八 · 悬念类型轮换协议",
            "规则十九 · 章间前情微召回协议",
            "规则二十 · 世界观名词首次出现即锚定协议",
            "| 规则十一 | 打斗三幕式 | 战斗层次 |",
            "| 规则十六 | 修炼三不写 | 突破验证 |",
        )
        for marker in markers:
            with self.subTest(marker=marker):
                text = "# 第一章 净稿\n" + "甲" * 1900 + "\n" + marker + "\n" + "审计填充" * 100
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_twenty_rhythm_formulas_selfcheck_and_rewrite_markers_cannot_pad(self) -> None:
        formula_tokens = (
            "章节结构",
            "场景结局",
            "反派压迫值",
            "金手指描写",
            "有效信息传递",
            "开篇钩子",
            "结尾钩子",
            "情绪收益",
            "有效对话",
            "谜题释放节奏",
            "有效打斗",
            "配角魅力",
            "越阶合理性",
            "场景沉浸",
            "心理描写",
            "有效突破",
            "支线管理",
            "结尾悬念类型",
            "章间衔接",
            "名词可记性",
        )
        markers = tuple(f"{token} = 内部计算" for token in formula_tokens) + (
            "【章节自检报告】",
            "1. [节奏] 过渡段≤800字？(是/否)",
            "11. [打斗] 战斗是否分三幕？(是/否)",
            "【重写】",
            "[重写警告]：修正该段",
            "IF 章节进入过渡场景 THEN 插入有效节拍",
            '{"IF":"进入过渡场景","THEN":"插入有效节拍"}',
            '{"status":"\\u3010\\u91cd\\u5199\\u3011"}',
        )
        for marker in markers:
            with self.subTest(marker=marker):
                text = "# 第一章 净稿\n" + "甲" * 1900 + "\n" + marker + "\n" + "审计填充" * 100
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_twenty_rhythm_controls_survive_markup_unicode_and_softbreaks(self) -> None:
        markers = (
            "节奏**控制**协议",
            "[节奏控制协议](https://example.invalid)",
            "节奏<span>控制</span>协议",
            "节奏<!--x-->控制协议",
            "节奏\u200b控制协议",
            "节奏<br>控制协议",
            "节\n奏\n控\n制\n协\n议",
            "&#x8282;&#x594f;控制协议",
            "打斗**场景三幕式**协议",
            "打斗<span>场景</span>三幕式协议",
            "【重<br>写<br>警<br>告】",
            "I\nF 进入过渡场景 T\nH\nE\nN 插入节拍",
        )
        for marker in markers:
            with self.subTest(marker=marker):
                text = "# 第一章 净稿\n" + "甲" * 1900 + "\n" + marker + "\n" + "审计填充" * 100
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_twenty_rhythm_controls_hidden_in_html_cannot_pad_length(self) -> None:
        markers = (
            '<div data-rule="节奏控制协议"></div>',
            '<div data-formula="有效打斗 = 内部计算"></div>',
            '<div aria-label="章节自检报告"></div>',
            '<meta content="【重写警告】">',
            '<div hidden>节奏控制协议</div>',
            '<div hidden>有效打斗 = 内部计算</div>',
            '<script>节奏控制协议</script>',
            '<rule IF="进入过渡" THEN="插入节拍"></rule>',
            '<rule data-then="插入节拍" data-if="进入过渡"></rule>',
            '<div hidden>节奏<span>控制</span>协议</div>',
        )
        for marker in markers:
            with self.subTest(marker=marker):
                text = "# 第一章 净稿\n" + "甲" * 1900 + "\n" + marker + "\n" + "审计填充" * 100
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_twenty_rhythm_control_block_resets_and_nearby_fiction_passes(self) -> None:
        polluted = (
            "# 第一章 净稿\n"
            + "甲" * 1900
            + "\n【章节自检报告】\n"
            + "审计填充" * 100
            + "\n# 第二章 正文\n"
            + "乙" * 2000
        )
        purity, counts = self.direct_purity_and_counts(polluted)
        self.assertFalse(purity["passed"])
        self.assertEqual(counts, [1900, 2000])

        normal_lines = (
            "更夫的鼓点忽快忽慢，他只得控制脚下节奏。",
            "戏分三幕，第二幕有一场打斗。",
            "药瓶上贴着标签，背面多了一行小字。",
            "边界碑钉在峡谷口，锚定铁索已经断了。",
            "师父有三不写：不写假账，不写欠条，不写遗书。",
            "旧案挂起三个月，县衙今日才回收卷宗。",
            "族老重写门规，把旧纸扔进火盆。",
            "他未通过山门试炼，转身时没有回头。",
            "“是，还是否？”铁算盘问。",
            "石壁上写着：一枚火钱等于三斤米。",
            "城门规则只有一条：日落后不放人。",
            "两宗协议昨夜作废。",
        )
        for line in normal_lines:
            with self.subTest(line=line):
                normal = "# 第一章 净稿\n" + "甲" * 2000 + "\n" + line
                self.assertTrue(AUDIT_MODULE.fiction_purity_gate(normal)["passed"])

    def test_default_length_boundaries_are_2000_and_3200_without_cross_compensation(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
            [1999, 2500, 3201],
        )
        result, report = self.run_audit(text, opening=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["length_gate"]["minimum"], 2000)
        self.assertEqual(report["length_gate"]["maximum"], 3200)
        self.assertEqual(
            [item["effective_prose_chars"] for item in report["length_gate"]["chapters"]],
            [1999, 2500, 3201],
        )
        self.assertEqual(
            [item["passed"] for item in report["length_gate"]["chapters"]],
            [False, True, False],
        )

    def test_rules_21_to_30_control_names_formulas_and_report_cannot_pad(self) -> None:
        markers = (
            "规则二十一：名词首次出现即锚定协议（强化版）",
            "规则二十二：信息释放密度“224”协议",
            "规则二十三：伏笔“三章挂起提醒”协议",
            "规则二十四：代价数值“前10章固定标注”协议",
            "规则二十五：未知物品“功能边界三章内暴露”协议",
            "规则二十六：主角“每章成长痕迹”协议",
            "规则二十七：世界观“底层规则一致性”协议",
            "规则二十八：“同类描写去重”协议",
            "规则二十九：章节净字数“±20%”协议",
            "规则三十：AI“生成后执行报告”协议",
            "信息释放密度二二四协议",
            "代价数值前十章固定标注协议",
            "章节净字数+/-20%协议",
            "章节净字数正负20%协议",
        )
        formula_tokens = (
            "名词记忆成本",
            "章节信息载荷",
            "伏笔记忆留存率",
            "标注覆盖率",
            "物品可信度",
            "成长痕迹",
            "规则可信度",
            "重复风险",
            "章节健康度",
            "生成流程",
        )
        report_markers = (
            "【规则执行报告】",
            "一、通过项：",
            "二、未通过项：",
            "三、修正后文本：",
            "【拆分】",
            "自检21-30：",
            "自检二十一至三十：",
            "21. [名词锚定] 是否在同段完成？(是/否)",
            "30. [执行报告] 是否仅写QA？(是/否)",
        )
        for marker in markers + tuple(f"{token} = 内部计算" for token in formula_tokens) + report_markers:
            with self.subTest(marker=marker):
                text = "# 第一章 净稿\n" + "甲" * 1900 + "\n" + marker + "\n" + "审计填充" * 100
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_rules_21_to_30_controls_survive_markup_hidden_html_and_softbreaks(self) -> None:
        markers = (
            "信息释放密度**224**协议",
            "[伏笔三章挂起提醒协议](https://example.invalid)",
            "代价数值<span>前十章固定标注</span>协议",
            "未知物品<!--x-->功能边界三章内暴露协议",
            "主角\u200b每章成长痕迹协议",
            "世界观<br>底层规则一致性协议",
            "同\n类\n描\n写\n去\n重\n协\n议",
            '<div hidden>章节净字数“±20%”协议</div>',
            '<script>AI“生成后执行报告”协议</script>',
            '<meta content="【规则执行报告】">',
            '<div data-rule="章节信息载荷 = 内部计算"></div>',
            '<div aria-label="规则执行报告"></div>',
            "【规\n则\n执\n行\n报\n告】",
            "[\u89c4\u5219\u6267\u884c\u62a5\u544a]",
        )
        for marker in markers:
            with self.subTest(marker=marker[:40]):
                text = "# 第一章 净稿\n" + "甲" * 1900 + "\n" + marker + "\n" + "审计填充" * 100
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_if_then_controls_in_structured_or_split_text_cannot_pad(self) -> None:
        markers = (
            '<div data-control="IF condition THEN action"></div>',
            "I\nF condition T\nH\nE\nN action",
            '{"control":"IF condition THEN action"}',
            '{"control":"\\u0049\\u0046 condition \\u0054\\u0048\\u0045\\u004e action"}',
        )
        for marker in markers:
            with self.subTest(marker=marker[:40]):
                text = (
                    "# 第一章 净稿\n"
                    + "甲" * 1900
                    + "\n"
                    + marker
                    + "\n"
                    + "审计填充" * 100
                )
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

        natural = (
            "# 第一章 净稿\n"
            + "甲" * 2000
            + "\n铁匠把‘IF’刻在左牌，把‘THEN’刻在右牌。"
        )
        purity, counts = self.direct_purity_and_counts(natural)
        self.assertTrue(purity["passed"])
        self.assertGreaterEqual(counts[0], 2000)

    def test_rules_21_to_30_control_block_resets_and_nearby_fiction_passes(self) -> None:
        polluted = (
            "# 第一章 净稿\n"
            + "甲" * 1900
            + "\n【规则执行报告】\n"
            + "审计填充" * 100
            + "\n# 第二章 正文\n"
            + "乙" * 2000
        )
        purity, counts = self.direct_purity_and_counts(polluted)
        self.assertFalse(purity["passed"])
        self.assertEqual(counts, [1900, 2000])

        normal_lines = (
            "巡检司的规则执行报告被雨泡烂了。",
            "族老修正后的文本少了三行。",
            "他把灵石拆分成两份。",
            "机关自检一遍，发出咔声。",
            "牢房21-30号全部熄灯。",
            "成长痕迹很浅，风一吹就没了。",
            "重复风险不大，掌柜仍换了路。",
            "底层石板遵循同一条规则。",
            "二二四号牢房昨夜换了守卫。",
            "前十章账册都标了价。",
            "章节健康度刻在铜牌背面。",
            "生成流程被匠人画成一条水线。",
            "【代价：气血 100 → 70】",
            "【恢复：气血 70 → 90】",
        )
        for line in normal_lines:
            with self.subTest(line=line):
                normal = "# 第一章 净稿\n" + "甲" * 2000 + "\n" + line
                self.assertTrue(AUDIT_MODULE.fiction_purity_gate(normal)["passed"])

    def test_rules_31_to_60_control_titles_and_formulas_cannot_pad(self) -> None:
        markers = tuple(
            f"### 规则{number}：{label}协议"
            for number, label in enumerate(RULES_31_TO_60_LABELS, start=31)
        ) + tuple(f"{label} = 内部计算" for label in RULES_31_TO_60_LABELS)
        for marker in markers:
            with self.subTest(marker=marker):
                text = (
                    "# 第一章 净稿\n"
                    + "甲" * 1900
                    + "\n"
                    + marker
                    + "\n"
                    + "审计填充" * 100
                )
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

        self.assertEqual(30, len(RULES_31_TO_60_EXACT_NAMES))
        for number, name in enumerate(RULES_31_TO_60_EXACT_NAMES, start=31):
            with self.subTest(exact_name=name):
                marker = f"### 规则{number}：{name}"
                self.assertIsNotNone(
                    AUDIT_MODULE._editorial_kind_from_normalized(marker)
                )

        for name in (
            RULES_31_TO_60_EXACT_NAMES[0],
            RULES_31_TO_60_EXACT_NAMES[14],
            RULES_31_TO_60_EXACT_NAMES[-1],
        ):
            with self.subTest(exact_padding=name):
                text = "# 第一章 净稿\n" + "甲" * 1900 + "\n【" + name + "】\n" + "审计填充" * 100
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

    def test_rules_31_to_60_selfcheck_reports_and_encodings_cannot_pad(self) -> None:
        selfcheck_indexes = (31, 34, 38, 42, 46, 50, 52, 55, 58, 60)
        selfchecks = tuple(
            f"{index}. [{RULES_31_TO_60_LABELS[index - 31]}] 是否通过？(是/否)"
            for index in selfcheck_indexes
        )
        reports = (
            "【规则31-60执行报告】",
            "规则三十一至六十QA报告",
            "自检31-60：",
            "自检三十一至六十",
            "【规则三十一至六十执行报告】",
            "【31-60 QA】",
        )
        encoded = (
            "**术语密度上限**",
            "[延迟解释](https://example.invalid)",
            '<div data-rule="概念捆绑"></div>',
            "<div hidden>高压-泄压钟摆</div>",
            "<script>代价被看见</script>",
            "情感<!--split-->逆转",
            "最小\u200b反馈闭环",
            "\n".join("钩子类型轮换"),
            "\n".join("环境锚定"),
            json.dumps({"rule": "对话三级负载"}, ensure_ascii=False),
            '{"rule":"\\u4e0d\\u8bf4\\u7834\\u4eb2\\u5bc6"}',
            "".join(f"&#x{ord(char):x};" for char in "感官代偿"),
            "【跨章代价清点】",
        )
        if_then = (
            "IF 术语密度上限超限 THEN 延迟解释",
            '<div data-control="IF 环境锚定缺失 THEN 强制重写"></div>',
            '{"IF":"三波冲突缺失","THEN":"重写"}',
            "I\nF 纯动作超限 T\nH\nE\nN 插入对话",
        )
        for marker in selfchecks + reports + encoded + if_then:
            with self.subTest(marker=marker[:60]):
                text = (
                    "# 第一章 净稿\n"
                    + "甲" * 1900
                    + "\n"
                    + marker
                    + "\n"
                    + "审计填充" * 100
                )
                purity, counts = self.direct_purity_and_counts(text)
                self.assertFalse(purity["passed"])
                self.assertEqual(counts, [1900])

        reset_at_chapter = (
            "# 第一章 净稿\n"
            + "甲" * 1900
            + "\n【术语密度上限】\n"
            + "审计填充" * 100
            + "\n# 第二章 正文\n"
            + "乙" * 2000
        )
        purity, counts = self.direct_purity_and_counts(reset_at_chapter)
        self.assertFalse(purity["passed"])
        self.assertEqual(counts, [1900, 2000])

    def test_rules_31_to_60_nearby_fiction_is_not_blocked(self) -> None:
        normal_lines = (
            "药铺的术语密度上限太低，讲不完这套阵法。",
            "他故意延迟解释，先把门闩上。",
            "学宫把两个概念捆绑在一起讲。",
            "铜炉上的高压泄压钟摆又响了一次。",
            "直到血浸透袖口，那份代价才被看见。",
            "戏班最擅长情感逆转，台下人哭完又笑。",
            "傀儡师把最小反馈闭环刻进铜脑。",
            "渔行规定钩子的类型每夜轮换。",
            "传音阵只能承受三级对话负载。",
            "老人把不说破的亲密藏进一碗面。",
            "失明后，他靠感官代偿辨出脚步。",
            "账房跨过两章账册，才清点出真正代价。",
            "船夫靠环境锚定方位。",
            "木匣只是两家交割的中间物。",
            "三波冲突先后撞在西门。",
            "阵纹让前置条件显化在石壁上。",
            "红黄绿三盏悬灯一盏接一盏熄灭。",
            "药效退去后，他的认知回落到七岁。",
            "那个不起眼的配角也主动做了决定。",
            "那人脚下一失衡，撞上了墙。",
            "观星镜的视角被机关刚性锁定。",
            "他用推断代替陈述，没有把话说死。",
            "每名刺客的动作都带着个人签名。",
            "这套擒拿动作分三步。",
            "库房门后钉着一张物件状态表。",
            "活跃的器灵每过三章钟声便碰一次墙。",
            "章纹内刻着一道波谷和一道波峰。",
            "先缓一缓，这两件事必须办完。",
            "三轮对话之后，他插了一句题外话。",
            "他用三百字记下那套纯粹动作。",
        )
        for line in normal_lines:
            with self.subTest(line=line):
                text = "# 第一章 净稿\n" + "甲" * 2000 + "\n" + line
                self.assertTrue(AUDIT_MODULE.fiction_purity_gate(text)["passed"])

    def test_target_effective_intersects_absolute_window(self) -> None:
        cases = (
            (3000, 2399, False, 2400, 3200),
            (3000, 2400, True, 2400, 3200),
            (3000, 3200, True, 2400, 3200),
            (3000, 3201, False, 2400, 3200),
            (2500, 2000, True, 2000, 3000),
            (2500, 3001, False, 2000, 3000),
            (2501, 2000, False, 2001, 3001),
            (2501, 2001, True, 2001, 3001),
            (2501, 3001, True, 2001, 3001),
            (2501, 3002, False, 2001, 3001),
            (1667, 2000, True, 2000, 2000),
            (4000, 3200, True, 3200, 3200),
        )
        for target, length, expected, minimum, maximum in cases:
            with self.subTest(target=target, length=length):
                text = make_batch([("第一章", "净稿")], [length])
                result, report = self.run_audit(
                    text,
                    opening=False,
                    target_effective=target,
                )
                self.assertEqual(result.returncode == 0, expected, result.stdout + result.stderr)
                self.assertEqual(report["length_gate"]["minimum"], minimum)
                self.assertEqual(report["length_gate"]["maximum"], maximum)
                self.assertEqual(report["length_gate"]["target_effective"], target)

    def test_target_effective_rejects_invalid_or_empty_intersection(self) -> None:
        text = make_batch([("第一章", "净稿")], [2000])
        for target in (0, -1, 1666, 4001):
            with self.subTest(target=target):
                result, report = self.run_audit(
                    text,
                    opening=False,
                    target_effective=target,
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(report, {})


if __name__ == "__main__":
    unittest.main()
