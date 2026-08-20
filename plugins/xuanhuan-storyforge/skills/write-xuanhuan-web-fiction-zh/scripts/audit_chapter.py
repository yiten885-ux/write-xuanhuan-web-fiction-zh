#!/usr/bin/env python3
"""Deterministic, read-only audit for Chinese-fiction chapters.

The audit can require a non-placeholder H1 title before prose, measures prose
length, and reports literal repetition, watchlist hits, and sentence-rhythm
candidates. It makes no semantic claims about authorship, continuity, pacing,
character arcs, consent, or literary quality.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import statistics
import sys
import tempfile
import unicodedata
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "2.0"
DEFAULT_WATCHLIST = (
    Path(__file__).resolve().parent.parent / "references" / "zh-style-watchlist.json"
)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")
H1_TITLE_RE = re.compile(r"^\s{0,3}#(?!#)\s+(.+?)\s*$")
BATCH_TITLE_HEADING_RE = re.compile(
    r"^\s{0,3}##(?!#)\s+本批章节标题\s*#*\s*$"
)
ORDERED_TITLE_ITEM_RE = re.compile(r"^\s{0,3}(\d+)[.)、]\s+(.+?)\s*$")
CHAPTER_TITLE_PARTS_RE = re.compile(
    r"^(?:(第[零〇一二三四五六七八九十百千万两"
    r"壹贰叁肆伍陆柒捌玖拾佰仟\d]+章)"
    r"(?:[\s:：、.．·—-]*))?(.*?)$"
)
PLACEHOLDER_TITLE_RE = re.compile(
    r"^(?:待定(?:[（(]暂定[)）])?|tbd|tba|todo|xxx|未定|未命名|无标题|"
    r"标题(?:[一二三四五六七八九十\d]+)?|章节标题|待补(?:标题)?|待命名)$",
    re.IGNORECASE,
)
ONLY_CHAPTER_NUMBER_RE = re.compile(
    r"^第[零〇一二三四五六七八九十百千万两"
    r"壹贰叁肆伍陆柒捌玖拾佰仟\d]+章$"
)
LIST_PREFIX_RE = re.compile(r"^\s{0,3}(?:[-+*]|\d+[.)])\s+")
BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>\s?")
LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
REFERENCE_LINK_RE = re.compile(r"!?\[([^\]]*)\]\[[^\]]*\]")
HTML_TAG_RE = re.compile(r"<[^>]+>")
INLINE_CODE_RE = re.compile(r"`+[^`]*`+")
INDENTED_CODE_RE = re.compile(r"^(?:\t| {4})")
SENTENCE_END_RE = re.compile(r"(?:[。！？!?]+|…{2,}|\.{2,})(?:[”’」』】）》]*)")
EDITORIAL_RULE_ID_RE = re.compile(
    r"(?:HOOK-EMO-01|PLOT-MIND-02|SYS-COST-03|LOOT-DELAY-04|"
    r"END-HOOK-05|BOUND-QUANT-06|SMART-LIMIT-07|VILLAIN-LAYER-08|"
    r"EVENT-RULE-09|INFO-DELAY-10)",
    re.IGNORECASE,
)
EDITORIAL_RULE_NAME_RE = re.compile(
    r"(?:(?:情绪钩子前置|智斗三层套娃|金手指非线性代价|代价双通道|"
    r"战利品延迟释放|战利品双池|章末异常钩子|金手指量化边界|"
    r"主角智力上限显性化|反派层级具象化|核心事件规则预埋|"
    r"家族谜题信息延迟)(?:律|锁)|"
    r"(?:开篇情感锚定|主角差异性行为|爽点频率与间隔|"
    r"章尾动作与信息双钩子|章尾双钩子|章尾信息悬停|"
    r"世界观双向展示|节奏与副本周期|场景转移与副本周期|"
    r"设定稀缺性|情绪峰值(?:类型配比)?|情绪失控系数|"
    r"章尾安全区禁令)"
    r"(?:律|锁)?|(?:前三万字)?(?:六项|九项)留存硬锁)"
)
RETENTION_RULE_NAMES = (
    "开篇情感锚定",
    "主角差异性行为",
    "爽点频率与间隔",
    "章尾动作与信息双钩子",
    "章尾双钩子",
    "章尾信息悬停",
    "世界观双向展示",
    "节奏与副本周期",
    "场景转移与副本周期",
    "设定稀缺性",
    "情绪峰值类型配比",
    "情绪峰值",
    "情绪失控系数",
    "章尾安全区禁令",
    "章尾安全区",
    "六项留存硬锁",
    "前三万字六项留存硬锁",
    "九项留存硬锁",
    "前三万字九项留存硬锁",
)
SOFTBREAK_RETENTION_RULE_NAME_RE = re.compile(
    "|".join(
        r"[ \t\r\n]*".join(re.escape(char) for char in name)
        for name in RETENTION_RULE_NAMES
    )
)
RETENTION_AUDIT_TOKENS = (
    "开篇锚",
    "主角意外指数",
    "爽点密度",
    "章尾钩子强度",
    "世界观吸引力值",
    "节奏加速系数",
    "爆款留存率",
    "综合得分",
    "设定稀缺性评分",
    "情绪失控系数",
    "章尾焦虑值",
    "章尾安全区违规次数",
    "常规选择一",
    "常规选择二",
    "常规选择三",
    "常规选择1",
    "常规选择2",
    "常规选择3",
    "第四方案",
    "六项留存检查",
    "六项留存自检",
    "九项留存检查",
    "九项留存自检",
    "本章落袋微爽点",
    "滚动三章窗口",
    "改写前文因果判断的新事实",
    "滚动两章窗口",
    "第10章门槛状态",
    "核心外挂稀缺性",
    "内部相似度排除",
    "真实近三年Top100检索",
    "翻盘类型配比",
    "意外型翻盘",
    "算计型翻盘",
    "滚动6章窗口",
    "安全区禁令",
    "安全规则穿透证据",
    "QA报告",
    "QA结果",
)
SOFTBREAK_RETENTION_AUDIT_TOKEN_RE = re.compile(
    "|".join(
        r"[ \t\r\n]*".join(re.escape(char) for char in token)
        for token in sorted(RETENTION_AUDIT_TOKENS, key=len, reverse=True)
    ),
    re.IGNORECASE,
)
RETENTION_FORMULA_TOKENS = (
    "开篇锚",
    "主角意外指数",
    "爽点密度",
    "章尾钩子强度",
    "世界观吸引力值",
    "节奏加速系数",
    "爆款留存率",
    "综合得分",
    "设定稀缺性评分",
    "情绪失控系数",
    "章尾焦虑值",
    "章尾安全区违规次数",
)
SOFTBREAK_RETENTION_FORMULA_RE = re.compile(
    r"(" + "|".join(re.escape(token) for token in RETENTION_FORMULA_TOKENS)
    + r")[ \t]*\r?\n[ \t]*([=:：])"
)
OUTPUT_CHECK_MARKER_RE = re.compile(
    r"(?:\[\s*)?OUTPUT\s*CHECK(?:\s*\])?", re.IGNORECASE
)
SOFTBREAK_OUTPUT_CHECK_RE = re.compile(
    r"(?<![A-Za-z0-9])OUTPUT[ \t]*\r?\n[ \t]*CHECK(?![A-Za-z0-9])",
    re.IGNORECASE,
)
EDITORIAL_BLOCK_HEADING_RE = re.compile(
    r"^\s*#{1,6}\s*(?:"
    r"QA\s*(?:报告|结果|检查)?|质量检查|内部\s*QA|AI\s*自检|"
    r"自检(?:结果|报告|清单|表)?|审计(?:结果|报告|清单|表)|检查结果|"
    r"(?:输出|章节|正文|规则)(?:自检|校验|检查)(?:结果|报告|清单|表)?"
    r")(?:\s*[:：])?\s*#*\s*$|"
    r"^\s*(?:QA\s*(?:报告|结果)?|内部\s*QA|AI\s*自检|自检结果|"
    r"输出自检)(?:\s*[:：])?\s*$|"
    r"^\s*(?:#{1,6}\s*)?(?:即时池|延迟池)\s*(?:[:：]|项目|物品|未知物)",
    re.IGNORECASE,
)
EDITORIAL_STATUS_LINE_RE = re.compile(
    r"^\s*(?:[-+*]\s*)?(?:0?[1-9]|10)(?:[.)、:：\s-]+)"
    r"(?:PASS|FAIL|未触发)(?:\b|\s|[：:（(])",
    re.IGNORECASE,
)
EDITORIAL_META_RE = re.compile(
    r"(?:(?<![A-Za-z0-9])(?:PASS|FAIL)(?![A-Za-z0-9])|TRIGGER_REWRITE|"
    r"AI\s*自检|自检宏|约束\s*ID|"
    r"触发条件\s*[（(]?IF[)）]?|执行动作\s*[（(]?THEN[)）]?|"
    r"禁止动作\s*[（(]?ELSE[)）]?)",
    re.IGNORECASE,
)
LAYER_AUDIT_RE = re.compile(
    r"层\s*[一二三123]\s*[：:].*(?:计划|反制|反拆|破局|副作用)"
)
RETENTION_AUDIT_RE = re.compile(
    r"(?:开篇锚|主角意外指数|爽点密度|章尾钩子强度|"
    r"世界观吸引力值|节奏加速系数|爆款留存率|综合得分|"
    r"设定稀缺性评分|情绪失控系数|章尾焦虑值|"
    r"章尾安全区违规次数)\s*[=:：]|"
    r"^(?:[-+*]\s*)?(?:常规选择[一二三123]|第四方案|"
    r"(?:六项|九项)留存(?:检查|自检|锁)|不可逆程度内部评分|"
    r"本章落袋微爽点|滚动三章窗口|改写前文因果判断的新事实|"
    r"滚动两章窗口|第\s*10\s*章门槛状态|核心外挂稀缺性|"
    r"内部相似度排除|真实近三年\s*Top100\s*检索|翻盘类型配比|"
    r"意外型翻盘|算计型翻盘|滚动\s*6\s*章窗口|安全区禁令|"
    r"安全规则穿透证据)\s*(?:[:：]|$)"
)
RETENTION_AUDIT_COMPACT_RE = re.compile(
    r"(?:开篇锚|主角意外指数|爽点密度|章尾钩子强度|"
    r"世界观吸引力值|节奏加速系数|爆款留存率|综合得分|"
    r"设定稀缺性评分|情绪失控系数|章尾焦虑值|"
    r"章尾安全区违规次数)[=:：]|"
    r"(?:常规选择[一二三123]|第四方案|(?:六项|九项)留存(?:检查|自检|锁)|"
    r"不可逆程度内部评分|本章落袋微爽点|滚动三章窗口|"
    r"改写前文因果判断的新事实|滚动两章窗口|第10章门槛状态|"
    r"核心外挂稀缺性|内部相似度排除|真实近三年Top100检索|"
    r"翻盘类型配比|意外型翻盘|算计型翻盘|滚动6章窗口|"
    r"安全区禁令|安全规则穿透证据)[:：]"
)
CRAFT_CONTROL_NAMES = (
    "平台爽点模式",
    "平台爽点适配",
    "平台爽点与打脸四拍",
    "起点向硬规则",
    "番茄向硬规则",
    "起点爽点逻辑",
    "番茄爽点逻辑",
    "打脸四拍",
    "黄金三章公式",
    "爽点公式",
    "期待感公式",
    "章节钩子公式",
    "番茄快节奏开头模板",
    "起点升级文模板",
    "身份反差装逼打脸模板",
    "AI味硬规则",
    "去AI味系统指令",
    "AI味检测与改写层",
    "去AI味检测与改写",
    "去AI味自检",
    "AI味版本",
    "去AI味版本",
    "禁用词词库",
    "AI高频词清单",
    "正文去模板化审校",
    "平台长线期待与即时兑现账",
    "打脸四拍账",
    "正文风格卡",
    "去模板化复检账",
    "写作前风格注入层",
    "写作中硬规则约束层",
    "后处理去AI味检测与改写指令",
    "起点爽点关键词",
    "番茄爽点关键词",
)
CRAFT_CONTROL_NAME_RE = re.compile(
    "|".join(re.escape(name) for name in CRAFT_CONTROL_NAMES),
    re.IGNORECASE,
)
CRAFT_AUDIT_LINE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:[一二三四五六七八九十0-9]+[.、]\s*)?(?:"
    r"\[?角色设定\]?|\[?写作宪法(?:[-—–]+)?AI味硬规则\]?|"
    r"第一拍\s*[:：]\s*压|第二拍\s*[:：]\s*扬|"
    r"第三拍\s*[:：]\s*打|第四拍\s*[:：]\s*收|"
    r"对话占比(?:至少|目标)?\s*30\s*%|"
    r"环境描写(?:不超过|目标)?\s*15\s*%|"
    r"抽象词密度(?:低于|目标)?\s*5\s*%|"
    r"平均句长(?:不超过|目标)?\s*25\s*字?|"
    r"每\s*300\s*字内至少出现|每\s*500\s*字内至少出现|"
    r"连续心理独白不超过\s*3\s*句|"
    r"请检查以下小说片段[,，]找出AI味问题|改写要求|"
    r"写作前\s*[:：]?\s*风格注入层|"
    r"写作中\s*[:：]?\s*硬规则约束层|"
    r"后处理[‘’“”\"']*去AI味[‘’“”\"']*检测与改写指令|"
    r"(?:[一二三四五六七八九十0-9]+[.、]\s*)?(?:词汇|句式|内容|节奏|情感)层|"
    r"(?:[一二三四五六七八九十0-9]+[.、]\s*)?(?:场景|描写|对话|情绪|段落节奏|开头|结尾)公式|"
    r"起点\s*[:：]\s*付费订阅向(?:[,，][^\r\n]{0,120})?|"
    r"番茄\s*[:：]\s*免费广告向(?:[,，][^\r\n]{0,120})?|"
    r"起点[,，、/]番茄等平台的爽点逻辑分别是什么|"
    r"起点卖的是[^\r\n]{1,80}番茄卖的是[^\r\n]{1,80}|"
    r"起点重成长[,，]番茄重情绪[。.]*|"
    r"飞卢\s*[:：]\s*开局核爆[,，、]每章打脸[。.]*|"
    r"禁用或尽量少用以下AI高频词[^\r\n]{0,120}|"
    r"禁止连续使用排比句[^\r\n]{0,60}|禁止直接告诉读者情绪[^\r\n]{0,60}|"
    r"对话必须像人话[^\r\n]{0,60}|不要总结升华[^\r\n]{0,60}"
    r")\s*(?:[:：]|$)",
    re.IGNORECASE,
)
CRAFT_AUDIT_COMPACT_RE = re.compile(
    r"(?:压(?:→|➡|➜|⇒|->|[-—–/])+扬(?:→|➡|➜|⇒|->|[-—–/])+打(?:→|➡|➜|⇒|->|[-—–/])+收|"
    r"\|平台\|爽点逻辑\|特点\||"
    r"对话占比(?:至少|目标)?30%|环境描写(?:不超过|目标)?15%|"
    r"抽象词密度(?:低于|目标)?5%|平均句长(?:不超过|目标)?25字?|"
    r"每300字内至少出现|每500字内至少出现|"
    r"连续心理独白不超过3句|请检查以下小说片段[,，]找出AI味问题|"
    r"写作前[:：]?风格注入层|写作中[:：]?硬规则约束层|"
    r"后处理[‘’“”\"']*去AI味[‘’“”\"']*检测与改写指令|"
    r"起点[,，、/]番茄等平台的爽点逻辑分别是什么|"
    r"起点卖的是.{1,80}番茄卖的是.{1,80}|起点重成长[,，]番茄重情绪[。.]*|"
    r"飞卢[:：]开局核爆[,，、]每章打脸[。.]*|"
    r"禁用或尽量少用以下AI高频词.{0,120}|禁止连续使用排比句.{0,60}|"
    r"禁止直接告诉读者情绪.{0,60}|对话必须像人话.{0,60}|不要总结升华.{0,60})",
    re.IGNORECASE,
)
CONTINUITY_CONTROL_NAMES = (
    "正文前检查",
    "正文后状态更新",
    "设定库更新",
    "生成前复述",
    "章前状态卡",
    "章后状态增量",
    "连续性状态事务",
    "连续性状态更新",
    "人物状态机",
    "剧情阶段状态机",
    "逐角色知情账",
    "角色知情账",
    "时间线账本",
    "伏笔账本",
    "关键帧计划",
    "回溯校验",
    "章节自问自答",
    "锚点提醒",
    "纠偏指令",
    "对抗性自检",
    "全局一致性检查",
    "行为约束伪代码",
    "长篇连续性与防跳脱合同",
    "R1-R10执行清单",
    "新增设定",
)
CONTINUITY_CONTROL_NAME_RE = re.compile(
    "|".join(re.escape(name) for name in CONTINUITY_CONTROL_NAMES),
    re.IGNORECASE,
)
RULES_31_60_CONTROL_LABELS = (
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
RULES_31_60_CONTROL_LABEL_ALIASES = RULES_31_60_CONTROL_LABELS + (
    "滚动一千五百字新术语密度",
    "功能解释五百至八百字延迟",
    "概念父子链",
    "双危机或三千字冲突后泄压",
    "代价关系角色可见",
    "牺牲型策略非战斗截断",
    "普通线索N+3触碰",
    "章尾四型轮换",
    "对话L1/L2/L3单一主功能",
    "亲密表达反套话",
    "长期感官损失异质代偿",
    "滚动三章代价清点",
    "新场景环境三锚",
    "场景中段物件过渡",
    "重大冲突三波",
    "规则博弈前三百字显化",
    "红黄绿线配比",
    "红线新信息百字重估",
    "配角连续三章自利决策",
    "反派三行动私人压力泄漏",
    "紧密第三人称限知视角",
    "不可直知信息迹象推断",
    "角色动作签名",
    "动作观察判断执行",
    "物件跨章状态台账",
    "活跃物件三章触碰",
    "章内峰谷",
    "缓场实体展开",
    "三轮对话动作穿插",
    "纯动作三百字认知插针",
    "高压泄压钟摆",
    "中间物过渡",
    "推断句替代陈述句",
    "动作描写个人签名",
    "动作三步最小单元",
    "物件状态持续追踪",
    "活跃物件三章内触碰",
    "章内节奏波谷波峰",
    "对话三轮插动作",
    "纯动作三百字",
)
RULES_31_60_STRONG_CONTROL_NAMES = tuple(
    f"{label}协议" for label in RULES_31_60_CONTROL_LABEL_ALIASES
) + (
    "推断句替代陈述句",
    "动作三步最小单元",
    "物件状态表规则",
    "章内波谷波峰算法",
    "缓场两个必须",
    "纯动作300字上限",
    "纯动作三百字上限",
    "逐章节奏六十项硬锁",
    "六十项节奏锁",
    "规则三十一至六十",
)
RULES_31_60_LABEL_PATTERN = "|".join(
    re.escape(label)
    for label in sorted(RULES_31_60_CONTROL_LABEL_ALIASES, key=len, reverse=True)
)
RULES_31_60_SOFTBREAK_CONTROL_RE = re.compile(
    "|".join(
        r"[ \t]*\r?\n[ \t]*".join(re.escape(character) for character in label)
        for label in sorted(
            RULES_31_60_CONTROL_LABEL_ALIASES, key=len, reverse=True
        )
    ),
    re.IGNORECASE,
)
RULES_31_60_NUMBER_PATTERN = (
    r"(?:3[1-9]|[45]\d|60|三十一|三十二|三十三|三十四|三十五|三十六|"
    r"三十七|三十八|三十九|四十|四十一|四十二|四十三|四十四|四十五|"
    r"四十六|四十七|四十八|四十九|五十|五十一|五十二|五十三|五十四|"
    r"五十五|五十六|五十七|五十八|五十九|六十)"
)

CHAPTER_RHYTHM_CONTROL_NAMES = (
    "逐章节奏二十项硬锁",
    "二十项节奏锁",
    "逐章节奏三十项硬锁",
    "三十项节奏锁",
    "章节自检报告",
    "节奏控制协议",
    "主角能动性协议",
    "反派压迫感协议",
    "金手指差异化记忆点协议",
    "信息密度编码协议",
    "开篇钩子协议",
    "章节结尾断崖钩子协议",
    "结尾断崖钩子协议",
    "情绪收益打脸反差节奏协议",
    "情绪收益节奏协议",
    "对话信息冲突双载协议",
    "对话双载协议",
    "宏观信息三章释放定律协议",
    "三章释放定律协议",
    "打斗场景三幕式协议",
    "打斗三幕式",
    "配角功能标签变数协议",
    "配角功能标签",
    "战力边界锚定协议",
    "战力边界锚定",
    "环境五感触发协议",
    "五感触发协议",
    "心理行动外化协议",
    "心理行动外化",
    "修炼升级三不写协议",
    "修炼三不写",
    "支线三章回收挂起协议",
    "支线回收挂起",
    "悬念类型轮换协议",
    "章间前情微召回协议",
    "章间微召回",
    "世界观名词首次出现即锚定协议",
    "名词首次出现即锚定",
    "信息释放密度224协议",
    "信息释放密度“224”协议",
    "信息释放密度二二四协议",
    "伏笔三章挂起提醒协议",
    "伏笔“三章挂起提醒”协议",
    "代价数值前10章固定标注协议",
    "代价数值“前10章固定标注”协议",
    "代价数值前十章固定标注协议",
    "未知物品功能边界三章内暴露协议",
    "未知物品“功能边界三章内暴露”协议",
    "主角每章成长痕迹协议",
    "主角“每章成长痕迹”协议",
    "世界观底层规则一致性协议",
    "世界观“底层规则一致性”协议",
    "同类描写去重协议",
    "“同类描写去重”协议",
    "章节净字数±20%协议",
    "章节净字数“±20%”协议",
    "章节净字数+/-20%协议",
    "章节净字数正负20%协议",
    "AI生成后执行报告协议",
    "AI“生成后执行报告”协议",
    "规则二十一至三十",
) + RULES_31_60_STRONG_CONTROL_NAMES
CHAPTER_RHYTHM_CONTROL_NAME_RE = re.compile(
    "|".join(
        re.escape(name)
        for name in sorted(CHAPTER_RHYTHM_CONTROL_NAMES, key=len, reverse=True)
    ),
    re.IGNORECASE,
)
CHAPTER_RHYTHM_FORMULA_TOKENS = (
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
) + RULES_31_60_CONTROL_LABEL_ALIASES
CHAPTER_RHYTHM_FORMULA_RE = re.compile(
    r"(?:"
    + "|".join(re.escape(token) for token in CHAPTER_RHYTHM_FORMULA_TOKENS)
    + r")\s*(?:=|:|：|→)",
    re.IGNORECASE,
)
RULES_31_60_CONTROL_LINE_RE = re.compile(
    rf"(?:^\s*(?:#{{1,6}}\s*)?(?:[-+*]\s*)?"
    rf"(?:(?:规则\s*)?{RULES_31_60_NUMBER_PATTERN}\s*[.、:：·—-]+\s*)?"
    rf"(?:[\[【]\s*)?(?:{RULES_31_60_LABEL_PATTERN})(?:\s*[\]】])?"
    rf"(?:\s*(?:协议|规则|算法|上限|最小单元))?\s*(?:[:：]\s*)?$)|"
    rf"(?:(?:data[-_:]?(?:rule|formula|check|control)|aria-label|content)\s*=\s*"
    rf"[\"'][^\"']{{0,240}}(?:{RULES_31_60_LABEL_PATTERN})[^\"']*[\"'])|"
    rf"(?:[\"'](?:rule|formula|check|control|instruction|qa)[\"']\s*:\s*"
    rf"[\"'][^\"']{{0,240}}(?:{RULES_31_60_LABEL_PATTERN})[^\"']*[\"'])",
    re.IGNORECASE | re.MULTILINE,
)
RULES_31_60_QA_LINE_RE = re.compile(
    rf"^\s*(?:#{{1,6}}\s*)?(?:[-+*]\s*)?"
    rf"(?:(?:规则\s*)?{RULES_31_60_NUMBER_PATTERN}\s*[.、:：-]\s*)?"
    rf"(?:[\[【]\s*)?(?:{RULES_31_60_LABEL_PATTERN})(?:\s*[\]】])?"
    rf".{{0,180}}(?:是\s*/\s*否|通过\s*/\s*未通过|PASS|FAIL)",
    re.IGNORECASE,
)
RULES_31_60_CONTROL_COMPACT_RE = re.compile(
    rf"(?:(?:规则)?{RULES_31_60_NUMBER_PATTERN}[.、:：·—-]*"
    rf"(?:[\[【])?(?:{RULES_31_60_LABEL_PATTERN})(?:[\]】])?"
    rf"(?:协议|规则|算法|上限|最小单元)?)|"
    rf"(?:[\[【](?:{RULES_31_60_LABEL_PATTERN})[\]】])|"
    rf"(?:#{{1,6}}(?:{RULES_31_60_LABEL_PATTERN})(?:协议|规则|算法|上限|最小单元)?)|"
    rf"(?:(?:data[-_:]?(?:rule|formula|check|control)|aria-label|content)=[\"']"
    rf"[^\"']{{0,240}}(?:{RULES_31_60_LABEL_PATTERN})[^\"']*[\"'])|"
    rf"(?:[\"'](?:rule|formula|check|control|instruction|qa)[\"']:[\"']"
    rf"[^\"']{{0,240}}(?:{RULES_31_60_LABEL_PATTERN})[^\"']*[\"'])|"
    rf"(?:(?:规则)?{RULES_31_60_NUMBER_PATTERN}[.、:：-]?"
    rf"(?:[\[【])?(?:{RULES_31_60_LABEL_PATTERN})(?:[\]】])?.{{0,180}}"
    rf"(?:是/否|通过/未通过|PASS|FAIL))",
    re.IGNORECASE,
)
RULES_31_60_REPORT_RE = re.compile(
    r"(?:规则\s*)?(?:31\s*[-–—至]\s*60|三十一\s*至\s*六十)\s*"
    r"(?:执行报告|QA\s*(?:报告|结果)?|自检(?:报告|结果|清单|检查)?)|"
    r"自检\s*(?:31\s*[-–—至]\s*60|三十一\s*至\s*六十)",
    re.IGNORECASE,
)
RULES_31_60_REPORT_COMPACT_RE = re.compile(
    r"(?:规则)?(?:31[-–—至]60|三十一至六十)"
    r"(?:执行报告|QA(?:报告|结果)?|自检(?:报告|结果|清单|检查)?)|"
    r"自检(?:31[-–—至]60|三十一至六十)",
    re.IGNORECASE,
)
CHAPTER_RHYTHM_QA_LINE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:[-+*]\s*)?(?:\d{1,2}[.、:：]\s*)?"
    r"(?:[\[【])?(?:节奏|主角|反派|金手指|密度|开篇|结尾|爽感|对话|宏观|"
    r"打斗|配角|战力|环境|心理|修炼|支线|悬念|衔接|名词|信息密度|"
    r"名词锚定|伏笔提醒|数值标注|物品边界|成长痕迹|规则一致|去重|字数|执行报告)(?:[\]】])?"
    r".{0,180}(?:是\s*/\s*否|通过\s*/\s*未通过|PASS|FAIL)",
    re.IGNORECASE,
)
EXECUTION_REPORT_CONTROL_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:[\[【]\s*)?规则执行报告(?:\s*[\]】])?\s*(?:[:：]|$)|"
    r"^\s*(?:#{1,6}\s*)?(?:一[、.]\s*通过项|二[、.]\s*未通过项|"
    r"三[、.]\s*修正后文本)\s*(?:[:：]|$)|"
    r"(?:aria-label|data-[\w:-]+|content)\s*=\s*[\"'][^\"']*规则执行报告[^\"']*[\"']",
    re.IGNORECASE | re.MULTILINE,
)
EXECUTION_REPORT_COMPACT_RE = re.compile(
    r"(?:[\[【]规则执行报告[\]】]|#{1,6}规则执行报告|"
    r"一[、.]通过项|二[、.]未通过项|三[、.]修正后文本|"
    r"自检(?:21[-–—]30|二十一至三十))",
    re.IGNORECASE,
)
REWRITE_CONTROL_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:[-+*]\s*)?(?:[\[【])?"
    r"(?:重写|重写警告|拆分)(?:[\]】])?(?:\s*[:：]|\s*$)",
    re.IGNORECASE,
)
IF_THEN_CONTROL_RE = re.compile(
    r"(?:^\s*(?:#{1,6}\s*)?(?:[-+*]\s*)?I\s*F\b[\s\S]{0,300}?"
    r"\bT\s*H\s*E\s*N\b|"
    r"[\"']IF[\"']\s*:.{0,300}[\"']THEN[\"']\s*:|"
    r"(?:data[-_:]?control|aria-label|content)\s*=\s*[\"'][^\"']*"
    r"\bIF\b[^\"']{0,300}\bTHEN\b[^\"']*[\"']|"
    r"[\"'](?:control|instruction|rule)[\"']\s*:\s*[\"'][^\"']*"
    r"\bIF\b[^\"']{0,300}\bTHEN\b[^\"']*[\"'])",
    re.IGNORECASE | re.MULTILINE,
)
HTML_IF_THEN_ATTR_RE = re.compile(
    r"<(?=[^\r\n]{0,1200}\b(?:data[-_:])?if\s*=)"
    r"(?=[^\r\n]{0,1200}\b(?:data[-_:])?then\s*=)[^\r\n]*",
    re.IGNORECASE,
)
CHAPTER_RHYTHM_AUDIT_COMPACT_RE = re.compile(
    r"(?:章节自检报告|二十项节奏锁|逐章节奏二十项硬锁|"
    r"三十项节奏锁|逐章节奏三十项硬锁)|"
    r"(?:"
    + "|".join(re.escape(token) for token in CHAPTER_RHYTHM_FORMULA_TOKENS)
    + r")(?:=|:|：|→)|"
    r"[\[【](?:重写|重写警告)[\]】]|"
    r"(?:\d{1,2}[.、:：])?(?:节奏|主角|反派|金手指|密度|开篇|结尾|爽感|对话|宏观|"
    r"打斗|配角|战力|环境|心理|修炼|支线|悬念|衔接|名词|信息密度|"
    r"名词锚定|伏笔提醒|数值标注|物品边界|成长痕迹|规则一致|去重|字数|执行报告)"
    r".{0,180}(?:是/否|通过/未通过|PASS|FAIL)|"
    r"(?:[\[【]规则执行报告[\]】]|一[、.]通过项|二[、.]未通过项|"
    r"三[、.]修正后文本|[\[【]拆分[\]】]|自检(?:21[-–—]30|二十一至三十))",
    re.IGNORECASE,
)
CONTINUITY_AUDIT_LINE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:【|\[)?(?:铁律层|状态卡|本章关键帧|"
    r"正文前检查|正文后状态更新|设定库更新|生成前复述|"
    r"人物状态机|剧情阶段状态机|时间线账本|伏笔账本|"
    r"回溯校验|章节自问自答|自检流程|锚点提醒|纠偏指令|"
    r"对抗性自检|全局一致性检查|写作计划|行为约束伪代码)"
    r"(?:】|\])?\s*(?:[:：]|$)|"
    r"^\s*(?:#{1,6}\s*)?(?:[-+*]\s*)?R\s*(?:10|[1-9])\s*"
    r"(?:[.、:：-]+)\s*(?:事实锁|人物锁|世界锁|主线锁|因果禁区|"
    r"冲突仲裁(?:锁)?|视角锁|信息锁|时间锁|空间锁|PASS|FAIL|"
    r"检查|更新|事实|人物|世界|主线|视角|信息|时间|空间)",
    re.IGNORECASE,
)
R_LOCK_COMPACT_RE = re.compile(
    r"(?<![A-Za-z0-9])R(?:10|[1-9])(?:[.、:：-]+)?(?:"
    r"事实锁|人物锁|世界锁|主线锁|因果禁区|冲突仲裁锁?|"
    r"视角锁|信息锁|时间锁|空间锁|PASS|FAIL|检查|更新|"
    r"事实|人物|世界|主线|视角|信息|时间|空间)",
    re.IGNORECASE,
)
CONTROL_STATUS_COMPACT_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:PASS|FAIL)(?![A-Za-z0-9])",
    re.IGNORECASE,
)
STRUCTURED_STATE_LINE_RE = re.compile(
    r"^\s*(?:[-+*]\s*)?[{\[]?\s*(?:[\"']?(?:chapter_?state|characters|"
    r"facts|items|locations|knowledge|timeline|foreshadowing|plot_?states|"
    r"chapter_?transactions|unresolved_?conflicts|keyframes|text_?sha256|"
    r"scene|time|location|state|"
    r"人物|事实|物品|地点|知情|时间线|伏笔|剧情阶段|章节事务|未解决冲突)"
    r"[\"']?\s*[:=]|"
    r"(?:【|\[)(?:场景|时间|地点|人物状态|角色状态)(?:】|\])|"
    r"(?:场景|时间|地点|人物状态|角色状态|当前时间|当前地点|当前状态|"
    r"事实[_ ]?delta|人物[_ ]?delta|物品[_ ]?delta|地点[_ ]?delta|"
    r"knowledge[_ ]?delta|timeline[_ ]?delta|foreshadow[_ ]?delta)\s*[:=])|"
    r"^\s*\|?\s*(?:场景|scene)\s*\|\s*(?:时间|time)\s*\|\s*"
    r"(?:地点|location)\s*\|\s*(?:人物状态|角色状态|当前状态|状态|state)\s*\|?",
    re.IGNORECASE,
)
STRUCTURED_STATE_MULTIKEY_RE = re.compile(
    r"^(?=.*(?:场景|scene)\s*[:=])(?=.*(?:时间|time)\s*[:=])"
    r"(?=.*(?:地点|location)\s*[:=])(?=.*(?:状态|state)\s*[:=]).*$",
    re.IGNORECASE,
)
STRUCTURED_STATE_COMPACT_RE = re.compile(
    r"[\"']?(?:chapterstate|characters|facts|items|locations|knowledge|timeline|"
    r"foreshadowing|plotstates|chaptertransactions|unresolvedconflicts|keyframes|"
    r"textsha256)[\"']?[:=]",
    re.IGNORECASE,
)
STRUCTURED_STATE_FOUR_KEY_COMPACT_RE = re.compile(
    r"(?:"
    r"场景(?:[\"']?[:=|]|<).{0,120}"
    r"时间(?:[\"']?[:=|]|<).{0,120}"
    r"地点(?:[\"']?[:=|]|<).{0,120}"
    r"(?:人物状态|角色状态|当前状态|状态)(?:[\"']?[:=|]|<)?|"
    r"场景时间地点(?:人物状态|角色状态|当前状态|状态)|"
    r"scenetimelocation(?:characterstate|personstate|currentstate|state)"
    r")",
    re.IGNORECASE,
)
DOCUMENT_QA_HEADING_RE = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]*)?"
    r"Q[ \t\r\n]*A[ \t\r\n]*(?:报[ \t\r\n]*告|结[ \t\r\n]*果)"
    r"[ \t]*(?:[:：])?[ \t#]*$",
    re.IGNORECASE | re.MULTILINE,
)
DEFAULT_IGNORABLE_RANGES = (
    (0x034F, 0x034F),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180F),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFFA0, 0xFFA0),
    (0xFFF0, 0xFFF8),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
    (0xE0000, 0xE0FFF),
)
CONFUSABLE_ASCII_TRANSLATION = str.maketrans(
    {
        # Common Greek/Cyrillic homoglyphs used to disguise ASCII control IDs.
        "Α": "A",
        "А": "A",
        "α": "a",
        "а": "a",
        "Β": "B",
        "В": "B",
        "β": "b",
        "Ϲ": "C",
        "С": "C",
        "ϲ": "c",
        "с": "c",
        "Ε": "E",
        "Е": "E",
        "ε": "e",
        "е": "e",
        "Ϝ": "F",
        "Η": "H",
        "Н": "H",
        "η": "h",
        "Ι": "I",
        "І": "I",
        "ι": "i",
        "і": "i",
        "Κ": "K",
        "К": "K",
        "κ": "k",
        "к": "k",
        "Μ": "M",
        "М": "M",
        "μ": "m",
        "м": "m",
        "Ν": "N",
        "ν": "n",
        "Ο": "O",
        "О": "O",
        "ο": "o",
        "о": "o",
        "Ρ": "P",
        "Р": "P",
        "ρ": "p",
        "р": "p",
        "Ѕ": "S",
        "ѕ": "s",
        "Τ": "T",
        "Т": "T",
        "τ": "t",
        "т": "t",
        "Υ": "Y",
        "Ү": "Y",
        "υ": "y",
        "ү": "y",
        "Χ": "X",
        "Х": "X",
        "χ": "x",
        "х": "x",
    }
)
RENDER_DIRECTION_CONTROL_RE = re.compile(
    r"[\u202a-\u202e\u2066-\u2069]|<\s*bdo\b|"
    r"unicode-bidi\s*:|direction\s*:\s*rtl",
    re.IGNORECASE,
)
CHAPTER_NUMERAL_CHARS = (
    "零〇一二三四五六七八九十百千万两壹贰叁肆伍陆柒捌玖拾佰仟\d"
)
MARKDOWN_CHAPTER_HEADING_RE = re.compile(
    rf"^\s{{0,3}}(#{{1,6}})\s+(第[{CHAPTER_NUMERAL_CHARS}]+章)"
    r"(?:[\s:：、.．·—-]+(.*?))?\s*#*\s*$"
)
PLAIN_CHAPTER_HEADING_RE = re.compile(
    rf"^\s*(第[{CHAPTER_NUMERAL_CHARS}]+章)"
    r"(?:[\s:：、.．·—-]+(.*?))?\s*$"
)


class AuditError(Exception):
    """A user-facing input or configuration error."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit UTF-8 Chinese-fiction chapters without modifying them. "
            "Exit 1 means a requested content gate failed; "
            "exit 2 means the input or configuration was invalid."
        )
    )
    parser.add_argument("chapter", type=Path, help="UTF-8 Markdown or text chapter")
    parser.add_argument(
        "--require-title",
        action="store_true",
        help="require a batch title inventory first and matching non-placeholder H1 titles",
    )
    parser.add_argument(
        "--require-opening-three",
        action="store_true",
        help=(
            "require the first three H1 sections to be chapters 1, 2, and 3 "
            "and each to meet the configured opening range (default 2000..3200) "
            "with a final sentence of at most 15 effective characters; "
            "the seven-rule opening contract still requires separate semantic review"
        ),
    )
    parser.add_argument(
        "--opening-min-effective",
        type=int,
        default=2000,
        help="inclusive minimum for each of opening chapters 1..3 (default: 2000)",
    )
    parser.add_argument(
        "--opening-max-effective",
        type=int,
        default=3200,
        help="inclusive maximum for each of opening chapters 1..3 (default: 3200)",
    )
    parser.add_argument(
        "--min-effective",
        type=int,
        default=2000,
        help="inclusive minimum effective prose characters per chapter (default: 2000)",
    )
    parser.add_argument(
        "--max-effective",
        type=int,
        default=3200,
        help="inclusive maximum effective prose characters per chapter (default: 3200)",
    )
    parser.add_argument(
        "--target-effective",
        type=int,
        help=(
            "optional target effective prose characters per chapter; applies a "
            "+/-20 percent window intersected with --min-effective/--max-effective"
        ),
    )
    parser.add_argument(
        "--long-sentence",
        type=int,
        default=80,
        help="effective-character threshold for long-sentence candidates",
    )
    parser.add_argument(
        "--max-paragraph-sentence-average",
        type=float,
        help=(
            "optional inclusive maximum average effective sentence length for "
            "each non-empty prose source line/paragraph"
        ),
    )
    parser.add_argument(
        "--forbid-outside-dialogue",
        action="append",
        default=[],
        metavar="TEXT",
        help=(
            "literal term forbidden outside paired Chinese/straight quotation marks; "
            "repeatable or comma-separated"
        ),
    )
    parser.add_argument(
        "--json-out", type=Path, help="optional stable UTF-8 JSON report path"
    )
    parser.add_argument(
        "--watchlist",
        type=Path,
        default=DEFAULT_WATCHLIST,
        help="watchlist JSON (defaults to bundled file)",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="TEXT",
        help="literal exemption; repeatable or comma-separated",
    )
    return parser.parse_args(argv)


def resolved_length_window(args: argparse.Namespace) -> tuple[int, int, int | None, int | None]:
    """Return the absolute/target intersection used by the per-chapter gate."""

    if args.target_effective is None:
        return args.min_effective, args.max_effective, None, None
    target_minimum = (4 * args.target_effective + 4) // 5
    target_maximum = (6 * args.target_effective) // 5
    return (
        max(args.min_effective, target_minimum),
        min(args.max_effective, target_maximum),
        target_minimum,
        target_maximum,
    )


def validate_args(args: argparse.Namespace) -> None:
    if args.min_effective < 0:
        raise AuditError("--min-effective must be non-negative")
    if args.max_effective < args.min_effective:
        raise AuditError("--max-effective must be >= --min-effective")
    if args.target_effective is not None:
        if args.target_effective <= 0:
            raise AuditError("--target-effective must be a positive integer")
        effective_minimum, effective_maximum, _, _ = resolved_length_window(args)
        if effective_minimum > effective_maximum:
            raise AuditError(
                "--target-effective +/-20 percent window does not intersect "
                "the configured absolute length range"
            )
    if args.opening_min_effective < 0:
        raise AuditError("--opening-min-effective must be non-negative")
    if args.opening_max_effective < args.opening_min_effective:
        raise AuditError(
            "--opening-max-effective must be >= --opening-min-effective"
        )
    if args.long_sentence < 1:
        raise AuditError("--long-sentence must be positive")
    if (
        args.max_paragraph_sentence_average is not None
        and args.max_paragraph_sentence_average <= 0
    ):
        raise AuditError("--max-paragraph-sentence-average must be positive")
    if args.require_opening_three and not args.require_title:
        raise AuditError("--require-opening-three requires --require-title")
    if not args.chapter.is_file():
        raise AuditError(f"chapter not found: {args.chapter}")
    if not args.watchlist.is_file():
        raise AuditError(f"watchlist not found: {args.watchlist}")
    if args.json_out is not None:
        output_path = args.json_out.resolve()
        if output_path == args.chapter.resolve():
            raise AuditError("--json-out must not overwrite the source chapter")
        if output_path == args.watchlist.resolve():
            raise AuditError("--json-out must not overwrite the watchlist")


def read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError(f"not valid UTF-8: {path}") from exc
    except OSError as exc:
        raise AuditError(f"cannot read {path}: {exc}") from exc


def strip_frontmatter(lines: list[str]) -> list[str]:
    if not lines or lines[0].strip() != "---":
        return lines
    for index in range(1, min(len(lines), 200)):
        if lines[index].strip() == "---":
            return [""] * (index + 1) + lines[index + 1 :]
    return lines


def mask_fenced_lines(lines: list[str]) -> list[str]:
    """Preserve line numbers while hiding fenced-code contents from title scans."""

    masked: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for raw in lines:
        fence = FENCE_RE.match(raw)
        if fence:
            run = fence.group(1)
            if not in_fence:
                in_fence = True
                fence_char = run[0]
                fence_len = len(run)
            elif run[0] == fence_char and len(run) >= fence_len:
                in_fence = False
            masked.append("")
        elif in_fence:
            masked.append("")
        else:
            masked.append(raw)
    return masked


def strip_h1_markup(value: str) -> str:
    """Remove only Markdown closing-heading syntax, preserving literal title marks."""

    return re.sub(r"\s+#+\s*$", "", value).strip()


def parse_chapter_title(value: str) -> tuple[tuple[str | None, str] | None, str]:
    """Return a comparable (chapter label, title) pair and a failure reason."""

    plain = unicodedata.normalize("NFKC", strip_h1_markup(value))
    if not plain or effective_count(plain) == 0:
        return None, "empty title"
    match = CHAPTER_TITLE_PARTS_RE.fullmatch(plain)
    if not match:
        return None, "unparseable title"
    chapter_label, title = match.groups()
    title = title.strip()
    if title.startswith("《") and title.endswith("》"):
        title = title[1:-1].strip()
    if not title:
        return None, "chapter number without a title"
    if effective_count(title) == 0:
        return None, "title has no letters or numbers"
    if ONLY_CHAPTER_NUMBER_RE.fullmatch(title):
        return None, "title is only another chapter number"
    if PLACEHOLDER_TITLE_RE.fullmatch(title):
        return None, "placeholder title"
    return (chapter_label, title), "valid chapter title"


def title_gate(text: str, required: bool) -> dict[str, Any]:
    """Check title inventory/order and reject prose before chapter headings."""

    if not required:
        return {
            "required": False,
            "passed": None,
            "line": None,
            "text": None,
            "inventory_present": None,
            "inventory_count": None,
            "heading_count": None,
            "reason": "not required",
        }

    without_bom = text.lstrip("\ufeff")
    without_comments = HTML_COMMENT_RE.sub(
        lambda match: "\n" * match.group(0).count("\n"), without_bom
    )
    lines = mask_fenced_lines(strip_frontmatter(without_comments.splitlines()))

    first_visible: tuple[int, str] | None = None
    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        first_visible = (line_number, raw)
        break

    if first_visible is None:
        return {
            "required": True,
            "passed": False,
            "line": None,
            "text": None,
            "inventory_present": False,
            "inventory_count": 0,
            "heading_count": 0,
            "reason": "no visible chapter content",
        }

    first_line_number, first_line = first_visible
    inventory_present = bool(BATCH_TITLE_HEADING_RE.match(first_line))
    first_is_h1 = bool(H1_TITLE_RE.match(first_line))
    if not inventory_present and not first_is_h1:
        return {
            "required": True,
            "passed": False,
            "line": first_line_number,
            "text": None,
            "inventory_present": False,
            "inventory_count": 0,
            "heading_count": 0,
            "reason": "story content appears before the title inventory or H1 title",
        }

    inventory: list[tuple[str | None, str]] = []
    headings: list[tuple[int, str, tuple[str | None, str]]] = []
    scanning_inventory = inventory_present

    for line_number, raw in enumerate(lines[first_line_number - 1 :], start=first_line_number):
        stripped = raw.strip()
        if not stripped:
            continue
        if inventory_present and line_number == first_line_number:
            continue

        h1_match = H1_TITLE_RE.match(raw)
        if h1_match:
            parsed, reason = parse_chapter_title(h1_match.group(1))
            if parsed is None:
                return {
                    "required": True,
                    "passed": False,
                    "line": line_number,
                    "text": strip_h1_markup(h1_match.group(1)) or None,
                    "inventory_present": inventory_present,
                    "inventory_count": len(inventory),
                    "heading_count": len(headings) + 1,
                    "reason": reason,
                }
            headings.append((line_number, strip_h1_markup(h1_match.group(1)), parsed))
            scanning_inventory = False
            continue

        if scanning_inventory:
            item_match = ORDERED_TITLE_ITEM_RE.match(raw)
            if not item_match:
                return {
                    "required": True,
                    "passed": False,
                    "line": line_number,
                    "text": None,
                    "inventory_present": True,
                    "inventory_count": len(inventory),
                    "heading_count": 0,
                    "reason": "non-title content appears inside the batch title inventory",
                }
            item_number = int(item_match.group(1))
            if item_number != len(inventory) + 1:
                return {
                    "required": True,
                    "passed": False,
                    "line": line_number,
                    "text": item_match.group(2).strip() or None,
                    "inventory_present": True,
                    "inventory_count": len(inventory),
                    "heading_count": 0,
                    "reason": "batch title inventory numbering is not consecutive from 1",
                }
            parsed, reason = parse_chapter_title(item_match.group(2))
            if parsed is None:
                return {
                    "required": True,
                    "passed": False,
                    "line": line_number,
                    "text": item_match.group(2).strip() or None,
                    "inventory_present": True,
                    "inventory_count": len(inventory) + 1,
                    "heading_count": 0,
                    "reason": f"invalid batch title: {reason}",
                }
            inventory.append(parsed)
            continue

        if not headings:
            return {
                "required": True,
                "passed": False,
                "line": line_number,
                "text": None,
                "inventory_present": inventory_present,
                "inventory_count": len(inventory),
                "heading_count": 0,
                "reason": "story content appears before the first H1 chapter title",
            }

    if not headings:
        reason = "batch title inventory is not followed by an H1 chapter title" if inventory_present else "no H1 chapter title"
        return {
            "required": True,
            "passed": False,
            "line": first_line_number,
            "text": None,
            "inventory_present": inventory_present,
            "inventory_count": len(inventory),
            "heading_count": 0,
            "reason": reason,
        }

    heading_pairs = [item[2] for item in headings]
    if not inventory_present:
        return {
            "required": True,
            "passed": False,
            "line": first_line_number,
            "text": headings[0][1],
            "inventory_present": False,
            "inventory_count": 0,
            "heading_count": len(headings),
            "reason": "batch title inventory is required before every fiction delivery",
        }
    if inventory != heading_pairs:
        return {
            "required": True,
            "passed": False,
            "line": first_line_number,
            "text": headings[0][1],
            "inventory_present": True,
            "inventory_count": len(inventory),
            "heading_count": len(headings),
            "reason": "batch title inventory and H1 chapter titles differ in count, text, number, or order",
        }

    return {
        "required": True,
        "passed": True,
        "line": headings[0][0],
        "text": headings[0][1],
        "inventory_present": inventory_present,
        "inventory_count": len(inventory),
        "heading_count": len(headings),
        "reason": "valid batch title inventory and matching H1 title order",
    }


class _RenderedHTMLText(HTMLParser):
    """Extract browser-visible text while preserving structural line breaks."""

    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tr",
        "ul",
    }
    SKIP_CONTENT_TAGS = {
        "code",
        "head",
        "noscript",
        "pre",
        "script",
        "style",
        "template",
    }
    VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.tag_stack: list[tuple[str, bool]] = []
        self.suppressed_depth = 0
        self.suppressed_probe: list[str] = []

    def _line_break(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def _control_marker(self) -> None:
        self._line_break()
        self.parts.append("OUTPUT CHECK")
        self._line_break()

    def _attribute_control(self, attrs: list[tuple[str, str | None]]) -> bool:
        source = "<element " + " ".join(
            f'{name}="{value or ""}"' for name, value in attrs
        ) + ">"
        normalized = normalize_unicode_scan(source)
        return _editorial_kind_from_normalized(normalized) is not None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        attributes = {name.lower(): value for name, value in attrs}
        style = (attributes.get("style") or "").lower()
        own_hidden = (
            tag in self.SKIP_CONTENT_TAGS
            or "hidden" in attributes
            or (attributes.get("aria-hidden") or "").lower() == "true"
            or bool(re.search(r"display\s*:\s*none", style))
            or bool(re.search(r"visibility\s*:\s*hidden", style))
        )
        suppressed = self.suppressed_depth > 0 or own_hidden
        if self._attribute_control(attrs):
            self._control_marker()
        if tag not in self.VOID_TAGS:
            self.tag_stack.append((tag, suppressed))
            if suppressed:
                self.suppressed_depth += 1
        if not suppressed and tag in self.BLOCK_TAGS:
            self._line_break()

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = {name.lower(): value for name, value in attrs}
        style = (attributes.get("style") or "").lower()
        hidden = (
            self.suppressed_depth > 0
            or "hidden" in attributes
            or (attributes.get("aria-hidden") or "").lower() == "true"
            or bool(re.search(r"display\s*:\s*none", style))
            or bool(re.search(r"visibility\s*:\s*hidden", style))
        )
        if self._attribute_control(attrs):
            self._control_marker()
        if not hidden and tag.lower() in self.BLOCK_TAGS:
            self._line_break()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        was_suppressed = self.suppressed_depth > 0
        ended_visible = self.suppressed_depth == 0
        match_index: int | None = None
        for index in range(len(self.tag_stack) - 1, -1, -1):
            if self.tag_stack[index][0] == tag:
                match_index = index
                break
        if match_index is not None:
            popped = self.tag_stack[match_index:]
            del self.tag_stack[match_index:]
            self.suppressed_depth -= sum(1 for _, suppressed in popped if suppressed)
            self.suppressed_depth = max(self.suppressed_depth, 0)
            ended_visible = not any(suppressed for _, suppressed in popped)
        if was_suppressed and self.suppressed_depth == 0:
            hidden_text = "".join(self.suppressed_probe)
            self.suppressed_probe.clear()
            normalized = normalize_unicode_scan(hidden_text)
            if _editorial_kind_from_normalized(normalized) is not None:
                self._control_marker()
        if ended_visible and tag in self.BLOCK_TAGS:
            self._line_break()

    def handle_data(self, data: str) -> None:
        if self.suppressed_depth == 0:
            self.parts.append(data)
        else:
            self.suppressed_probe.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def html_text_content(value: str) -> str:
    """Return rendered HTML text using the standard-library parser."""

    parser = _RenderedHTMLText()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        # Purity scanning also retains the literal source view, so malformed
        # markup remains visible even if rendered extraction cannot finish.
        return value
    return parser.text()


def strip_default_ignorables(value: str) -> str:
    """Remove Unicode format/variation characters used to split visible tokens."""

    kept: list[str] = []
    for character in value:
        codepoint = ord(character)
        if unicodedata.category(character) == "Cf":
            continue
        if any(start <= codepoint <= end for start, end in DEFAULT_IGNORABLE_RANGES):
            continue
        kept.append(character)
    return "".join(kept)


def unwrap_markdown_links(value: str) -> str:
    """Keep Markdown labels and discard inline/reference destinations."""

    output: list[str] = []
    index = 0
    length = len(value)
    while index < length:
        image = value[index] == "!" and index + 1 < length and value[index + 1] == "["
        opening = index + 1 if image else index
        if value[opening] != "[":
            output.append(value[index])
            index += 1
            continue
        closing = value.find("]", opening + 1)
        if closing < 0:
            output.append(value[index])
            index += 1
            continue

        label = value[opening + 1 : closing]
        cursor = closing + 1
        if cursor < length and value[cursor] == "(":
            depth = 0
            destination_end: int | None = None
            probe = cursor
            while probe < length:
                if value[probe] == "\\" and probe + 1 < length:
                    probe += 2
                    continue
                if value[probe] == "(":
                    depth += 1
                elif value[probe] == ")":
                    depth -= 1
                    if depth == 0:
                        destination_end = probe
                        break
                probe += 1
            if destination_end is not None:
                output.append(label)
                index = destination_end + 1
                continue
        elif cursor < length and value[cursor] == "[":
            reference_end = value.find("]", cursor + 1)
            if reference_end >= 0:
                output.append(label)
                index = reference_end + 1
                continue

        # Shortcut references and ordinary bracketed labels render their label.
        output.append(label)
        index = closing + 1
    return "".join(output)


def normalize_unicode_scan(value: str) -> str:
    """Canonicalize Unicode/markup punctuation without discarding HTML source."""

    decoded = html.unescape(html.unescape(value))
    # Reader files must not be able to hide editorial labels behind JSON-style
    # Unicode escapes. Decode only explicit scalar escapes; malformed escapes
    # stay literal and remain available to the source scan.
    def decode_escape(match: re.Match[str]) -> str:
        codepoint = int(match.group(1) or match.group(2), 16)
        if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
            return match.group(0)
        return chr(codepoint)

    decoded = re.sub(
        r"\\U([0-9a-fA-F]{8})|\\u([0-9a-fA-F]{4})",
        decode_escape,
        decoded,
    )
    decomposed = unicodedata.normalize("NFKD", decoded)
    decomposed = "".join(
        character
        for character in decomposed
        if unicodedata.category(character)[0] != "M"
    )
    normalized = strip_default_ignorables(unicodedata.normalize("NFKC", decomposed))
    normalized = normalized.translate(CONFUSABLE_ASCII_TRANSLATION)
    normalized = "".join(
        "-"
        if unicodedata.category(character) == "Pd" or character == "−"
        else character
        for character in normalized
    )
    normalized = unwrap_markdown_links(normalized)
    normalized = re.sub(r"\\([^\s])", r"\1", normalized)
    normalized = re.sub(r"[*_~`]", "", normalized)
    return normalized


def normalize_editorial_scan(line: str, *, remove_comments: bool = False) -> str:
    """Flatten one source/rendering variant before leak detection."""

    if remove_comments:
        candidate = HTML_COMMENT_RE.sub("", line)
    else:
        # Keep hidden comment contents visible to the source-purity scan.
        candidate = line.replace("<!--", "").replace("-->", "")
    return normalize_unicode_scan(candidate)


def editorial_scan_variants(line: str) -> list[str]:
    """Return source-visible and rendered-without-comments scan variants."""

    source_visible = normalize_editorial_scan(line, remove_comments=False)
    source_rendered = normalize_unicode_scan(html_text_content(source_visible))
    comments_removed = normalize_editorial_scan(line, remove_comments=True)
    comments_removed_rendered = normalize_unicode_scan(
        html_text_content(comments_removed)
    )
    variants = [
        source_visible,
        source_rendered,
        comments_removed,
        comments_removed_rendered,
    ]
    return list(dict.fromkeys(variants))


def normalize_structure_line(line: str) -> str:
    """Flatten inline HTML/Markdown before recognizing a chapter boundary."""

    rendered = html_text_content(html.unescape(html.unescape(line)))
    return normalize_unicode_scan(rendered).strip()


def chapter_heading_value(line: str) -> tuple[str, int] | None:
    """Return an explicit chapter boundary and heading level (0 means plain)."""

    normalized = normalize_structure_line(line)
    normalized = re.sub(
        rf"(第[{CHAPTER_NUMERAL_CHARS}]+章)(?=[《【（(])", r"\1 ", normalized
    )
    markdown = MARKDOWN_CHAPTER_HEADING_RE.match(normalized)
    if markdown:
        label = markdown.group(2)
        subtitle = (markdown.group(3) or "").strip()
        value = strip_h1_markup(f"{label} {subtitle}".strip())
        return value, len(markdown.group(1))

    plain = PLAIN_CHAPTER_HEADING_RE.match(normalized)
    if plain:
        label = plain.group(1)
        subtitle = (plain.group(2) or "").strip()
        # Plain prose can begin with "第一章 ...". A sentence-final mark or an
        # implausibly long subtitle is narration, not an explicit heading.
        if subtitle and (
            re.search(r"[。；;]\s*$", subtitle)
            or effective_count(subtitle) > 40
        ):
            return None
        value = f"{label} {subtitle}".strip()
        return value, 0
    return None


def _editorial_kind_from_normalized(normalized: str) -> str | None:
    """Classify one already-normalized source/rendering view without recursion."""

    compact = re.sub(r"\s+", "", normalized)
    if OUTPUT_CHECK_MARKER_RE.search(normalized):
        return "output_check_marker"
    if EDITORIAL_RULE_ID_RE.search(compact):
        return "rule_constraint_id"
    if EDITORIAL_RULE_NAME_RE.search(compact):
        return "rule_constraint_name"
    if CRAFT_CONTROL_NAME_RE.search(compact):
        return "craft_control_name"
    if CONTINUITY_CONTROL_NAME_RE.search(compact):
        return "continuity_control_name"
    if CHAPTER_RHYTHM_CONTROL_NAME_RE.search(compact):
        return "chapter_rhythm_control_name"
    if RULES_31_60_SOFTBREAK_CONTROL_RE.search(normalized):
        return "chapter_rhythm_control_name"
    if RULES_31_60_CONTROL_LINE_RE.search(normalized):
        return "chapter_rhythm_control_name"
    if EXECUTION_REPORT_CONTROL_RE.search(normalized):
        return "chapter_rhythm_execution_report"
    if RULES_31_60_REPORT_RE.search(normalized):
        return "chapter_rhythm_execution_report"
    if EDITORIAL_BLOCK_HEADING_RE.search(normalized):
        return "audit_block_heading"
    if EDITORIAL_STATUS_LINE_RE.search(normalized):
        return "audit_status_line"
    if EDITORIAL_META_RE.search(normalized):
        return "audit_instruction"
    if LAYER_AUDIT_RE.search(normalized):
        return "layer_audit_label"
    if RETENTION_AUDIT_RE.search(normalized):
        return "retention_audit_label"
    if CRAFT_AUDIT_LINE_RE.search(normalized):
        return "craft_audit_label"
    if CRAFT_AUDIT_COMPACT_RE.search(compact):
        return "craft_audit_label"
    if CONTINUITY_AUDIT_LINE_RE.search(normalized):
        return "continuity_audit_label"
    if R_LOCK_COMPACT_RE.search(compact):
        return "continuity_rule_label"
    if CHAPTER_RHYTHM_FORMULA_RE.search(normalized):
        return "chapter_rhythm_formula"
    if CHAPTER_RHYTHM_QA_LINE_RE.search(normalized):
        return "chapter_rhythm_audit_label"
    if RULES_31_60_QA_LINE_RE.search(normalized):
        return "chapter_rhythm_audit_label"
    if REWRITE_CONTROL_RE.search(normalized):
        return "rewrite_control_marker"
    if IF_THEN_CONTROL_RE.search(normalized) or HTML_IF_THEN_ATTR_RE.search(normalized):
        return "if_then_control_instruction"
    if CHAPTER_RHYTHM_AUDIT_COMPACT_RE.search(compact):
        return "chapter_rhythm_audit_label"
    if STRUCTURED_STATE_LINE_RE.search(normalized):
        return "structured_state_block"
    if STRUCTURED_STATE_MULTIKEY_RE.search(normalized):
        return "structured_state_block"
    if STRUCTURED_STATE_COMPACT_RE.search(compact):
        return "structured_state_block"
    if STRUCTURED_STATE_FOUR_KEY_COMPACT_RE.search(compact):
        return "structured_state_block"
    return None


def editorial_meta_kind(line: str) -> str | None:
    """Classify internal audit language that must never count as fiction prose."""

    if RENDER_DIRECTION_CONTROL_RE.search(html.unescape(line)):
        return "render_direction_control"
    for normalized in editorial_scan_variants(line):
        kind = _editorial_kind_from_normalized(normalized)
        if kind is not None:
            return kind
    return None


def fiction_purity_gate(text: str) -> dict[str, Any]:
    """Reject editor/audit control language from a reader-facing fiction file."""

    # Scan the literal file before removing frontmatter, HTML comments, code
    # fences, or Markdown. Hidden/editor-only text still violates file purity.
    def scan_lines(candidate: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        in_editorial_block = False
        for line_number, raw in enumerate(candidate.splitlines(), start=1):
            heading = chapter_heading_value(raw)
            if in_editorial_block and heading is not None:
                in_editorial_block = False

            kind = editorial_meta_kind(raw)
            if kind is not None:
                in_editorial_block = True
                found.append(
                    {
                        "line": line_number,
                        "kind": kind,
                        "excerpt": raw.strip()[:160],
                    }
                )
                continue
            if in_editorial_block and raw.strip():
                found.append(
                    {
                        "line": line_number,
                        "kind": "audit_block_continuation",
                        "excerpt": raw.strip()[:160],
                    }
                )
        return found

    hits = scan_lines(text)
    # A comment can split a visible token (for example, A<!--x-->B). Scan the
    # browser-rendered equivalent as well. This second pass is needed even when
    # the source pass already found some other control text.
    rendered_without_comments = HTML_COMMENT_RE.sub("", text)
    if rendered_without_comments != text:
        rendered_hits = scan_lines(rendered_without_comments)
        existing = {(hit["kind"], hit["excerpt"]) for hit in hits}
        for hit in rendered_hits:
            key = (hit["kind"], hit["excerpt"])
            if key not in existing:
                hits.append(hit)
                existing.add(key)

    # Full-document rendered views catch control tokens split across a soft
    # line break or a multi-line HTML start tag. Only the unambiguous IDs and
    # OUTPUT CHECK marker are checked at document scope to avoid treating an
    # ordinary narrative sentence containing words like "审计报告" as a block.
    document_existing = {(hit["kind"], hit["excerpt"]) for hit in hits}
    if RENDER_DIRECTION_CONTROL_RE.search(html.unescape(text)):
        excerpt = re.sub(r"\s+", " ", text).strip()[:160]
        key = ("render_direction_control", excerpt)
        if key not in document_existing:
            hits.append(
                {"line": None, "kind": "render_direction_control", "excerpt": excerpt}
            )
            document_existing.add(key)
    for rendered in editorial_scan_variants(text):
        compact = re.sub(r"\s+", "", rendered)
        document_kind: str | None = None
        if EDITORIAL_RULE_ID_RE.search(compact):
            document_kind = "rule_constraint_id"
        elif EDITORIAL_RULE_NAME_RE.search(compact):
            document_kind = "rule_constraint_name"
        elif RETENTION_AUDIT_COMPACT_RE.search(compact):
            document_kind = "retention_audit_label"
        elif CRAFT_CONTROL_NAME_RE.search(compact):
            document_kind = "craft_control_name"
        elif CRAFT_AUDIT_COMPACT_RE.search(compact):
            document_kind = "craft_audit_label"
        elif CONTINUITY_CONTROL_NAME_RE.search(compact):
            document_kind = "continuity_control_name"
        elif CHAPTER_RHYTHM_CONTROL_NAME_RE.search(compact):
            document_kind = "chapter_rhythm_control_name"
        elif RULES_31_60_SOFTBREAK_CONTROL_RE.search(rendered):
            document_kind = "chapter_rhythm_control_name"
        elif RULES_31_60_CONTROL_COMPACT_RE.search(compact):
            document_kind = "chapter_rhythm_control_name"
        elif EXECUTION_REPORT_CONTROL_RE.search(rendered):
            document_kind = "chapter_rhythm_execution_report"
        elif EXECUTION_REPORT_COMPACT_RE.search(compact):
            document_kind = "chapter_rhythm_execution_report"
        elif RULES_31_60_REPORT_COMPACT_RE.search(compact):
            document_kind = "chapter_rhythm_execution_report"
        elif R_LOCK_COMPACT_RE.search(compact):
            document_kind = "continuity_rule_label"
        elif STRUCTURED_STATE_COMPACT_RE.search(compact):
            document_kind = "structured_state_block"
        elif STRUCTURED_STATE_FOUR_KEY_COMPACT_RE.search(compact):
            document_kind = "structured_state_block"
        elif CONTROL_STATUS_COMPACT_RE.search(compact):
            document_kind = "audit_instruction"
        elif IF_THEN_CONTROL_RE.search(rendered):
            document_kind = "if_then_control_instruction"
        elif CHAPTER_RHYTHM_AUDIT_COMPACT_RE.search(compact):
            document_kind = "chapter_rhythm_audit_label"
        elif DOCUMENT_QA_HEADING_RE.search(rendered):
            document_kind = "audit_block_heading"
        elif re.search(r"OUTPUTCHECK", compact, re.IGNORECASE):
            document_kind = "output_check_marker"
        if document_kind is None:
            continue
        excerpt = re.sub(r"\s+", " ", rendered).strip()[:160]
        key = (document_kind, excerpt)
        if key not in document_existing:
            hits.append({"line": None, "kind": document_kind, "excerpt": excerpt})
            document_existing.add(key)

    return {
        "required": True,
        "passed": not hits,
        "hits": hits[:100],
        "reason": (
            "reader-facing fiction contains no rule IDs or audit/control text"
            if not hits
            else "reader-facing fiction contains rule IDs or audit/control text"
        ),
    }


def clean_markdown(text: str) -> tuple[str, list[tuple[int, str]]]:
    """Return net fiction prose while excluding structure and audit metadata."""

    def clean_comment(match: re.Match[str]) -> str:
        # A complete control block hidden in a comment still starts an excluded
        # editorial block. Ordinary comments disappear while preserving line
        # count; comments used only to split a visible token are removed so the
        # rendered token can be reconstructed and detected below.
        replacement = ""
        if editorial_meta_kind(match.group(0)) is not None:
            replacement = "OUTPUT CHECK"
        return replacement + "\n" * match.group(0).count("\n")

    text = HTML_COMMENT_RE.sub(clean_comment, text.lstrip("\ufeff"))
    text = html_text_content(text)
    # HTML attributes are converted to OUTPUT CHECK by the rendered-text
    # parser; after rendering, preserve split plain-text/JSON IF...THEN blocks.
    text = IF_THEN_CONTROL_RE.sub("OUTPUT CHECK", text)
    text = RULES_31_60_SOFTBREAK_CONTROL_RE.sub("OUTPUT CHECK", text)
    text = SOFTBREAK_OUTPUT_CHECK_RE.sub("OUTPUT CHECK", text)
    text = SOFTBREAK_RETENTION_RULE_NAME_RE.sub(
        lambda match: re.sub(r"\s+", "", match.group(0)), text
    )
    text = SOFTBREAK_RETENTION_AUDIT_TOKEN_RE.sub(
        lambda match: re.sub(r"\s+", "", match.group(0)), text
    )
    text = SOFTBREAK_RETENTION_FORMULA_RE.sub(
        lambda match: match.group(1) + match.group(2), text
    )
    lines = strip_frontmatter(text.splitlines())
    # Map the whitespace-free rendered document back to source lines. This
    # catches a strong control label even when every character is separated by
    # arbitrary soft breaks or blank lines. Starting the block at the mapped
    # first character also prevents the split fragments from padding length.
    flattened_parts: list[str] = []
    flattened_line_map: list[int] = []
    for line_number, raw in enumerate(lines, start=1):
        normalized = normalize_unicode_scan(unwrap_markdown_links(raw))
        compact = re.sub(r"\s+", "", normalized)
        flattened_parts.append(compact)
        flattened_line_map.extend([line_number] * len(compact))
    flattened_document = "".join(flattened_parts)
    document_control_starts: set[int] = set()
    document_patterns = (
        EDITORIAL_RULE_ID_RE,
        EDITORIAL_RULE_NAME_RE,
        RETENTION_AUDIT_COMPACT_RE,
        CRAFT_CONTROL_NAME_RE,
        CRAFT_AUDIT_COMPACT_RE,
        CONTINUITY_CONTROL_NAME_RE,
        CHAPTER_RHYTHM_CONTROL_NAME_RE,
        RULES_31_60_CONTROL_COMPACT_RE,
        EXECUTION_REPORT_COMPACT_RE,
        RULES_31_60_REPORT_COMPACT_RE,
        R_LOCK_COMPACT_RE,
        CONTROL_STATUS_COMPACT_RE,
        CHAPTER_RHYTHM_AUDIT_COMPACT_RE,
        STRUCTURED_STATE_COMPACT_RE,
        STRUCTURED_STATE_FOUR_KEY_COMPACT_RE,
    )
    for pattern in document_patterns:
        for match in pattern.finditer(flattened_document):
            if match.start() < len(flattened_line_map):
                document_control_starts.add(flattened_line_map[match.start()])
    for match in re.finditer(r"OUTPUTCHECK", flattened_document, re.IGNORECASE):
        if match.start() < len(flattened_line_map):
            document_control_starts.add(flattened_line_map[match.start()])
    prose_lines: list[tuple[int, str]] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    in_title_inventory = False
    in_editorial_block = False

    for line_number, raw in enumerate(lines, start=1):
        fence = FENCE_RE.match(raw)
        if fence:
            run = fence.group(1)
            if not in_fence:
                in_fence = True
                fence_char = run[0]
                fence_len = len(run)
            elif run[0] == fence_char and len(run) >= fence_len:
                in_fence = False
            continue

        indented_code = bool(INDENTED_CODE_RE.match(raw))
        heading = (
            chapter_heading_value(raw)
            if not in_fence and not indented_code
            else None
        )
        if in_editorial_block and heading is not None:
            in_editorial_block = False
        if line_number in document_control_starts:
            in_editorial_block = True
            continue
        if editorial_meta_kind(raw) is not None:
            in_editorial_block = True
            continue
        if in_editorial_block:
            continue
        if in_fence:
            continue
        if indented_code:
            continue

        if BATCH_TITLE_HEADING_RE.match(raw):
            in_title_inventory = True
            continue
        if in_title_inventory:
            if heading is not None:
                in_title_inventory = False
            else:
                continue

        line = raw.strip()
        if not line or HEADING_RE.match(raw) or heading is not None:
            continue
        if re.match(r"^\s{0,3}(?:[-*_]\s*){3,}$", raw):
            continue
        if re.match(r"^\s{0,3}\[[^\]]+\]:\s+\S+", raw):
            continue

        line = BLOCKQUOTE_RE.sub("", line)
        line = LIST_PREFIX_RE.sub("", line)
        line = unwrap_markdown_links(line)
        line = INLINE_CODE_RE.sub("", line)
        line = re.sub(r"[*_~]", "", line).strip()
        if line:
            prose_lines.append((line_number, line))

    return "\n".join(line for _, line in prose_lines), prose_lines


def split_chapter_sections(text: str) -> list[dict[str, Any]]:
    """Split explicit H1..H6 or plain chapter headings for per-chapter gates."""

    without_bom = text.lstrip("\ufeff")
    source_lines = strip_frontmatter(without_bom.splitlines())
    comments_masked = HTML_COMMENT_RE.sub(
        lambda match: "\n" * match.group(0).count("\n"), without_bom
    )
    structure_lines = strip_frontmatter(comments_masked.splitlines())
    # Comment replacement preserves line count. If malformed input still
    # produces a mismatch, fail closed by padding the shorter structural view.
    if len(structure_lines) < len(source_lines):
        structure_lines.extend([""] * (len(source_lines) - len(structure_lines)))
    elif len(structure_lines) > len(source_lines):
        structure_lines = structure_lines[: len(source_lines)]
    scan_lines = mask_fenced_lines(structure_lines)
    sections: list[dict[str, Any]] = []
    current_line: int | None = None
    current_title: str | None = None
    current_heading_level: int | None = None
    current_lines: list[str] = []

    for line_number, (scan_raw, source_raw) in enumerate(
        zip(scan_lines, source_lines), start=1
    ):
        heading = (
            None
            if INDENTED_CODE_RE.match(source_raw)
            else chapter_heading_value(scan_raw)
        )
        if heading is not None:
            if current_line is not None:
                sections.append(
                    {
                        "line": current_line,
                        "title": current_title,
                        "heading_level": current_heading_level,
                        "text": "\n".join(current_lines),
                    }
                )
            current_line = line_number
            current_title, current_heading_level = heading
            current_lines = [source_raw]
        elif current_line is not None:
            current_lines.append(source_raw)

    if current_line is not None:
        sections.append(
            {
                "line": current_line,
                "title": current_title,
                "heading_level": current_heading_level,
                "text": "\n".join(current_lines),
            }
        )
    return sections


def is_effective(character: str) -> bool:
    return unicodedata.category(character)[0] in {"L", "N"}


def effective_count(text: str) -> int:
    return sum(1 for character in text if is_effective(character))


def final_sentence(text: str) -> str:
    """Return the last punctuation-delimited prose sentence for a chapter."""

    sentences = [part.strip() for part in SENTENCE_END_RE.split(text) if part.strip()]
    return sentences[-1] if sentences else ""


def chapter_number(label: str | None) -> int | None:
    """Parse only the explicit low chapter labels needed by the opening gate."""

    if label is None:
        return None
    normalized = unicodedata.normalize("NFKC", label)
    match = re.fullmatch(r"第(.+?)章", normalized)
    if not match:
        return None
    value = match.group(1)
    mapping = {"一": 1, "二": 2, "三": 3, "壹": 1, "贰": 2, "叁": 3}
    if value in mapping:
        return mapping[value]
    if value.isdigit():
        return int(value)
    return None


def opening_three_gate(
    sections: list[dict[str, Any]], required: bool, minimum: int, maximum: int
) -> dict[str, Any]:
    """Check only deterministic structure/length for the locked opening contract."""

    if not required:
        return {
            "required": False,
            "passed": None,
            "minimum": minimum,
            "maximum": maximum,
            "chapters": [],
            "reason": "not required",
        }

    if len(sections) < 3:
        return {
            "required": True,
            "passed": False,
            "minimum": minimum,
            "maximum": maximum,
            "chapters": [],
            "reason": "fewer than three explicit chapter sections",
        }

    checked: list[dict[str, Any]] = []
    expected_numbers = [1, 2, 3]
    for expected, section in zip(expected_numbers, sections[:3]):
        parsed, title_reason = parse_chapter_title(section["title"] or "")
        label = parsed[0] if parsed is not None else None
        number = chapter_number(label)
        section_prose, _ = clean_markdown(section["text"])
        count = effective_count(section_prose)
        ending = final_sentence(section_prose)
        ending_count = effective_count(ending)
        order_pass = number == expected
        length_pass = minimum <= count <= maximum
        ending_pass = 0 < ending_count <= 15
        checked.append(
            {
                "expected_chapter": expected,
                "observed_label": label,
                "title": section["title"],
                "line": section["line"],
                "effective_prose_chars": count,
                "final_sentence": ending,
                "final_sentence_effective_chars": ending_count,
                "order_passed": order_pass,
                "length_passed": length_pass,
                "final_sentence_passed": ending_pass,
                "passed": (
                    parsed is not None and order_pass and length_pass and ending_pass
                ),
                "title_reason": title_reason,
            }
        )

    passed = all(item["passed"] for item in checked)
    if passed:
        reason = (
            f"chapters 1..3 are ordered and each meets {minimum}..{maximum}"
        )
    elif any(not item["order_passed"] for item in checked):
        reason = "the first three H1 sections are not chapters 1, 2, and 3 in order"
    elif any(not item["final_sentence_passed"] for item in checked):
        reason = "one or more opening chapters end with over 15 effective characters or no prose sentence"
    else:
        reason = (
            "one or more opening chapters fall outside "
            f"{minimum}..{maximum} effective prose characters"
        )
    return {
        "required": True,
        "passed": passed,
        "minimum": minimum,
        "maximum": maximum,
        "chapters": checked,
        "reason": reason,
    }


def percentile(values: list[int], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def sentence_metrics(prose: str, threshold: int) -> dict[str, Any]:
    sentences = [part.strip() for part in SENTENCE_END_RE.split(prose) if part.strip()]
    lengths = [effective_count(sentence) for sentence in sentences]
    candidates = [
        {"index": index, "effective_chars": length, "excerpt": sentence[:120]}
        for index, (sentence, length) in enumerate(zip(sentences, lengths), start=1)
        if length >= threshold
    ]
    return {
        "count": len(sentences),
        "min": min(lengths, default=0),
        "median": statistics.median(lengths) if lengths else 0,
        "p90": round(percentile(lengths, 0.9), 2),
        "max": max(lengths, default=0),
        "long_candidates": candidates[:20],
    }


def paragraph_sentence_average_gate(
    prose_lines: list[tuple[int, str]], maximum: float | None
) -> dict[str, Any]:
    """Check average effective sentence length for each prose source line.

    This is a deterministic formatting proxy. Wrapped Markdown lines and semantic
    paragraphs still require review.
    """

    if maximum is None:
        return {
            "required": False,
            "maximum": None,
            "passed": None,
            "paragraphs_checked": 0,
            "violations": [],
        }

    violations: list[dict[str, Any]] = []
    for line_number, paragraph in prose_lines:
        sentences = [
            part.strip() for part in SENTENCE_END_RE.split(paragraph) if part.strip()
        ]
        lengths = [effective_count(sentence) for sentence in sentences]
        if not lengths:
            continue
        average = sum(lengths) / len(lengths)
        if average > maximum:
            violations.append(
                {
                    "line": line_number,
                    "sentence_count": len(lengths),
                    "average_effective_chars": round(average, 2),
                    "excerpt": paragraph[:160],
                }
            )
    return {
        "required": True,
        "maximum": maximum,
        "passed": not violations,
        "paragraphs_checked": len(prose_lines),
        "violations": violations[:50],
    }


QUOTE_PAIRS = {"“": "”", "‘": "’", "「": "」", "『": "』", '"': '"'}


def prose_outside_quotation_marks(
    prose_lines: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    """Return text outside paired quote marks while preserving source lines."""

    outside_lines: list[tuple[int, str]] = []
    closing_quote: str | None = None
    for line_number, line in prose_lines:
        outside: list[str] = []
        for character in line:
            if closing_quote is not None:
                if character == closing_quote:
                    closing_quote = None
                continue
            if character in QUOTE_PAIRS:
                closing_quote = QUOTE_PAIRS[character]
                continue
            outside.append(character)
        outside_lines.append((line_number, "".join(outside)))
    return outside_lines


def forbidden_outside_dialogue_gate(
    prose_lines: list[tuple[int, str]], terms: set[str], allowed: set[str]
) -> dict[str, Any]:
    """Find literal forbidden terms outside paired quotation marks."""

    active_terms = sorted(term for term in terms if term and term not in allowed)
    if not active_terms:
        return {
            "required": False,
            "terms": [],
            "passed": None,
            "hits": [],
        }

    hits: list[dict[str, Any]] = []
    for term in active_terms:
        for line_number, outside in prose_outside_quotation_marks(prose_lines):
            count = outside.count(term)
            if count:
                hits.append(
                    {
                        "term": term,
                        "line": line_number,
                        "count": count,
                        "excerpt": outside[:160],
                    }
                )
    return {
        "required": True,
        "terms": active_terms,
        "passed": not hits,
        "hits": hits[:100],
    }


def parse_allow(values: list[str]) -> set[str]:
    result: set[str] = set()
    for value in values:
        result.update(part.strip() for part in value.split(",") if part.strip())
    return result


def repeated_paragraphs(
    prose_lines: list[tuple[int, str]], allowed: set[str]
) -> list[dict[str, Any]]:
    normalized: dict[str, list[int]] = {}
    display: dict[str, str] = {}
    for line_number, line in prose_lines:
        key = re.sub(r"\s+", "", line)
        if effective_count(key) < 8 or key in allowed:
            continue
        normalized.setdefault(key, []).append(line_number)
        display[key] = line
    return [
        {"text": display[key][:160], "count": len(lines), "lines": lines}
        for key, lines in normalized.items()
        if len(lines) >= 2
    ][:20]


def repeated_phrases(prose: str, allowed: set[str]) -> list[dict[str, Any]]:
    compact = "".join(character for character in prose if is_effective(character))
    candidates: list[tuple[int, int, str]] = []
    for size in (12, 10, 8, 6, 4):
        if len(compact) < size:
            continue
        counts = Counter(compact[index : index + size] for index in range(len(compact) - size + 1))
        for phrase, count in counts.items():
            if count >= 3 and phrase not in allowed:
                candidates.append((size * count, count, phrase))

    candidates.sort(key=lambda item: (-item[0], -len(item[2]), item[2]))
    selected: list[tuple[int, int, str]] = []
    for score, count, phrase in candidates:
        if any(phrase in existing or existing in phrase for _, _, existing in selected):
            continue
        selected.append((score, count, phrase))
        if len(selected) == 20:
            break
    return [
        {"text": phrase, "count": count, "score": score}
        for score, count, phrase in selected
    ]


def load_watchlist(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(read_utf8(path))
    except json.JSONDecodeError as exc:
        raise AuditError(f"invalid watchlist JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("categories"), list):
        raise AuditError("watchlist must contain a categories array")
    return data["categories"]


def watchlist_hits(
    prose_lines: list[tuple[int, str]], categories: list[dict[str, Any]], allowed: set[str]
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for category in categories:
        category_id = str(category.get("id", "unknown"))
        label = str(category.get("label", category_id))
        terms = category.get("terms", [])
        if not isinstance(terms, list):
            raise AuditError(f"watchlist category {category_id} terms must be an array")
        for term_value in terms:
            term = str(term_value)
            if not term or term in allowed:
                continue
            locations: list[dict[str, Any]] = []
            total = 0
            for line_number, line in prose_lines:
                count = line.count(term)
                if count:
                    total += count
                    locations.append({"line": line_number, "count": count, "excerpt": line[:160]})
            if total:
                hits.append(
                    {
                        "category": category_id,
                        "label": label,
                        "term": term,
                        "count": total,
                        "locations": locations[:10],
                    }
                )
    return hits


def write_json_atomic(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            handle.write(payload)
            temporary = Path(handle.name)
        temporary.replace(path)
    except OSError as exc:
        raise AuditError(f"cannot write JSON report {path}: {exc}") from exc


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    raw = read_utf8(args.chapter)
    prose, prose_lines = clean_markdown(raw)
    fiction_purity = fiction_purity_gate(raw)
    title = title_gate(raw, args.require_title)
    allowed = parse_allow(args.allow)
    forbidden_terms = parse_allow(args.forbid_outside_dialogue)
    effective = effective_count(prose)
    non_whitespace = sum(1 for character in prose if not character.isspace())
    sections = split_chapter_sections(raw)
    opening_three = opening_three_gate(
        sections,
        args.require_opening_three,
        args.opening_min_effective,
        args.opening_max_effective,
    )
    length_minimum, length_maximum, target_minimum, target_maximum = (
        resolved_length_window(args)
    )
    chapter_lengths: list[dict[str, Any]] = []
    if sections:
        for index, section in enumerate(sections, start=1):
            section_prose, _ = clean_markdown(section["text"])
            section_effective = effective_count(section_prose)
            chapter_lengths.append(
                {
                    "index": index,
                    "line": section["line"],
                    "title": section["title"],
                    "effective_prose_chars": section_effective,
                    "passed": length_minimum <= section_effective <= length_maximum,
                }
            )
    else:
        chapter_lengths.append(
            {
                "index": 1,
                "line": None,
                "title": None,
                "effective_prose_chars": effective,
                "passed": length_minimum <= effective <= length_maximum,
            }
        )
    length_pass = all(item["passed"] for item in chapter_lengths)
    paragraph_average = paragraph_sentence_average_gate(
        prose_lines, args.max_paragraph_sentence_average
    )
    forbidden_outside_dialogue = forbidden_outside_dialogue_gate(
        prose_lines, forbidden_terms, allowed
    )
    style_gates_passed = all(
        gate["passed"] is not False
        for gate in (paragraph_average, forbidden_outside_dialogue)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            # Reports are commonly shared for review. Keep host-specific directory
            # names out of the sidecar by default; the content hash remains the
            # stable identifier for the audited source.
            "name": args.chapter.name,
            "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        },
        "title_gate": title,
        "fiction_purity_gate": fiction_purity,
        "opening_three_gate": opening_three,
        "counts": {
            "effective_prose_chars": effective,
            "non_whitespace_chars": non_whitespace,
            "prose_lines": len(prose_lines),
        },
        "length_gate": {
            "minimum": length_minimum,
            "maximum": length_maximum,
            "absolute_minimum": args.min_effective,
            "absolute_maximum": args.max_effective,
            "target_effective": args.target_effective,
            "target_tolerance_percent": 20 if args.target_effective is not None else None,
            "target_minimum": target_minimum,
            "target_maximum": target_maximum,
            "scope": "per_chapter",
            "chapters": chapter_lengths,
            "passed": length_pass,
        },
        "sentence_rhythm": sentence_metrics(prose, args.long_sentence),
        "style_gates": {
            "paragraph_sentence_average": paragraph_average,
            "forbidden_outside_dialogue": forbidden_outside_dialogue,
            "passed": style_gates_passed,
        },
        "repetition_candidates": {
            "paragraphs": repeated_paragraphs(prose_lines, allowed),
            "phrases": repeated_phrases(prose, allowed),
        },
        "watchlist_hits": watchlist_hits(
            prose_lines, load_watchlist(args.watchlist), allowed
        ),
        "limitations": [
            "The title gate verifies final Markdown order, placeholders, and inventory/H1 agreement, not hidden drafting chronology or title quality.",
            "Length gates are evaluated independently for every explicit H1..H6 or plain-text chapter heading; aggregate length cannot compensate for a short or long chapter.",
            "When --target-effective is supplied, the per-chapter range is the intersection of the configured absolute range and the integer target +/-20 percent range; an empty intersection is a configuration error.",
            "The audit cannot verify whether titles were locked before drafting, copied exactly from a user prompt, or assigned non-invented chapter numbers.",
            "The opening-three gate checks chapter order, its configured per-chapter net-fiction range (default 2000..3200), and whether each final sentence has 1..15 effective characters; it cannot verify the seven-rule opening contract, including the early crisis, background cost, ability effect/cost/boundary, protagonist setup, antagonist precedent, banked stage victory, and prior visibility of key settings.",
            "The audit cannot verify the nine retention semantics: irreversible stakes, a fair but unexpected fourth choice, micro/major payoff meaning, causal reinterpretation at chapter endings, positive worldbuilding value, completed scene-transfer/dungeon loop, setting scarcity, surprise/calculation payoff ratio, or unsafe chapter-ending anxiety; those require separate evidence review and do not establish reader retention or market performance.",
            "The audit cannot verify the thirty chapter-rhythm semantics, including beat quality, active decisions, antagonist pressure, ability distinctiveness, information carriers, hook meaning, payoff meaning, combat tactics, power scaling, sensory immersion, information-load meaning, character growth, world-rule consistency, or term anchoring; those require separate evidence review.",
            "Rule IDs, OUTPUT CHECK blocks, and audit/control language are rejected by the fiction-purity gate and excluded from net-fiction counts; a separate sidecar report must carry audit details.",
            "The paragraph-average gate treats each non-empty prose source line as a paragraph and uses effective letters/numbers; manual review is required for wrapped Markdown, abbreviations, and semantic paragraph boundaries.",
            "The outside-dialogue gate excludes text inside paired quotation marks; quotation marks do not prove that the quoted span is character dialogue, and malformed or nested quotes require manual review.",
            "Candidates require contextual human or model review.",
            "This report does not establish authorship, pacing, continuity, consent, or quality.",
        ],
    }


def print_summary(report: dict[str, Any]) -> None:
    counts = report["counts"]
    gate = report["length_gate"]
    rhythm = report["sentence_rhythm"]
    repetition = report["repetition_candidates"]
    title = report["title_gate"]
    fiction_purity = report["fiction_purity_gate"]
    opening = report["opening_three_gate"]
    style_gates = report["style_gates"]
    if title["required"]:
        print(
            "title_gate="
            + ("PASS" if title["passed"] else "FAIL")
            + f" line={title['line']} reason={title['reason']}"
        )
    else:
        print("title_gate=SKIP")
    print(
        "fiction_purity_gate="
        + ("PASS" if fiction_purity["passed"] else "FAIL")
        + f" hits={len(fiction_purity['hits'])} reason={fiction_purity['reason']}"
    )
    if opening["required"]:
        print(
            "opening_three_gate="
            + ("PASS" if opening["passed"] else "FAIL")
            + f" reason={opening['reason']}"
        )
        for chapter in opening["chapters"]:
            print(
                f"opening_chapter[{chapter['expected_chapter']}]="
                + ("PASS" if chapter["passed"] else "FAIL")
                + f" effective={chapter['effective_prose_chars']} "
                + f"ending_effective={chapter['final_sentence_effective_chars']} "
                + f" label={chapter['observed_label']!r}"
            )
    else:
        print("opening_three_gate=SKIP")
    print(f"effective_prose_chars={counts['effective_prose_chars']}")
    print(f"non_whitespace_chars={counts['non_whitespace_chars']}")
    print(
        "length_gate="
        + ("PASS" if gate["passed"] else "FAIL")
        + f" range={gate['minimum']}..{gate['maximum']}"
        + f" target={gate['target_effective']!r}"
    )
    for chapter in gate["chapters"]:
        print(
            f"chapter_length[{chapter['index']}]="
            + ("PASS" if chapter["passed"] else "FAIL")
            + f" effective={chapter['effective_prose_chars']} title={chapter['title']!r}"
        )
    print(
        f"sentences={rhythm['count']} median={rhythm['median']} "
        f"p90={rhythm['p90']} max={rhythm['max']}"
    )
    paragraph_average = style_gates["paragraph_sentence_average"]
    forbidden = style_gates["forbidden_outside_dialogue"]
    print(
        "paragraph_sentence_average_gate="
        + (
            "SKIP"
            if not paragraph_average["required"]
            else ("PASS" if paragraph_average["passed"] else "FAIL")
        )
    )
    print(
        "forbidden_outside_dialogue_gate="
        + (
            "SKIP"
            if not forbidden["required"]
            else ("PASS" if forbidden["passed"] else "FAIL")
        )
    )
    print(
        f"repeated_paragraphs={len(repetition['paragraphs'])} "
        f"repeated_phrases={len(repetition['phrases'])} "
        f"watchlist_hits={len(report['watchlist_hits'])}"
    )


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        validate_args(args)
        report = build_report(args)
        print_summary(report)
        if args.json_out:
            write_json_atomic(args.json_out, report)
        title_pass = (
            not report["title_gate"]["required"] or report["title_gate"]["passed"]
        )
        opening_pass = (
            not report["opening_three_gate"]["required"]
            or report["opening_three_gate"]["passed"]
        )
        return (
            0
            if report["length_gate"]["passed"]
            and report["fiction_purity_gate"]["passed"]
            and title_pass
            and opening_pass
            and report["style_gates"]["passed"]
            else 1
        )
    except AuditError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
