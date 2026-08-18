from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
AUDIT = SKILL_ROOT / "scripts" / "audit_chapter.py"


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


class OpeningThreeGateTests(unittest.TestCase):
    def run_audit(
        self,
        text: str,
        *,
        opening: bool = True,
        require_title: bool = True,
        minimum: int = 2000,
        maximum: int = 3000,
        opening_minimum: int | None = None,
        opening_maximum: int | None = None,
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
            [1999, 2600, 3001],
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

    def test_default_opening_and_general_range_is_2000_to_3000(self) -> None:
        text = make_batch(
            [("第一章", "门前异响"), ("第二章", "旧约落印"), ("第三章", "阶上留痕")],
            [2000, 2500, 3000],
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
        self.assertEqual(report["length_gate"]["maximum"], 3000)
        self.assertEqual(report["opening_three_gate"]["minimum"], 2000)
        self.assertEqual(report["opening_three_gate"]["maximum"], 3000)

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


if __name__ == "__main__":
    unittest.main()
