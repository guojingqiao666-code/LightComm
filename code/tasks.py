# -*- coding: utf-8 -*-
"""
tasks.py — 三个任务族的轻量 benchmark（内置数据，无需外部下载）。

每个任务提供：
  - name / description / input / system_prompt
  - make_workflow(data) -> Workflow   （子问题并行 + 大模型综合/验证的结构）
  - verify(output, gt) -> (bool, detail)  确定性规则验证（不依赖 LLM 二次判断）

任务族：
  1. MultiHopQA   —— 多跳问答：子问题并行检索/作答（small），综合推理（large）
  2. BugTriage    —— 软件缺陷分诊：严重度+根因并行判定（small），复核（large）
  3. DocEdit      —— 协作文档编辑：多修改点并行执行（small），质量验证（large）
"""
from __future__ import annotations

import json
import re
from typing import Callable, Dict, List, Tuple

from lightcomm import Workflow, WorkflowStep


# ============================================================
# 通用工具
# ============================================================

_FULL_TO_HALF = {ord(f): ord(h) for f, h in zip(
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ：，。；！？（）",
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:,.;!?()")}


def normalize(text: str) -> str:
    """归一化：小写、全角转半角、去空白、常见同义替换。"""
    t = (text or "").lower().translate(_FULL_TO_HALF)
    t = re.sub(r"\s+", "", t)
    t = t.replace("空指针", "nullpointer").replace("npe", "nullpointer")
    t = t.replace("达·芬奇", "达芬奇")
    return t


def contains_groups(output: str, groups: List[List[str]]) -> Tuple[bool, List[str]]:
    """验证：外层列表为 AND（每组必须满足），组内为 OR（任一同义候选命中即可）。

    groups 示例：[["高"], ["崩溃", "crash", "宕机"], ["nullpointer", "空指针", "npe"]]
    """
    text = normalize(output)
    missing = [g for g in groups if not any(normalize(k) in text for k in g)]
    return (len(missing) == 0), missing


def contains_all(output: str, keywords: List[str]) -> Tuple[bool, List[str]]:
    """兼容旧调用：把平铺关键词视为同义组（组内任一命中即算该组满足）。"""
    return contains_groups(output, [[k] for k in keywords])


def step_prompt(template: str) -> Callable[[dict], str]:
    return lambda view: template


# ============================================================
# 任务 1：MultiHopQA（12 例，每题 2-3 个子问题）
# ============================================================

MULTIHOP_QA = [
    {
        "id": "qa1",
        "input": "长江流经的省份中，哪个省的省会是杭州？",
        "sub_queries": [
            "长江流经哪些省份？列出名称。",
            "这些省份中，哪个省的省会是杭州？",
        ],
        "gt_keywords": [["浙江"]],
    },
    {
        "id": "qa2",
        "input": "《蒙娜丽莎》的作者出生在哪座城市？",
        "sub_queries": [
            "《蒙娜丽莎》的作者是谁？",
            "该作者出生在哪座城市？",
        ],
        "gt_keywords": [["芬奇", "列奥纳多", "达芬奇"]],
    },
    {
        "id": "qa3",
        "input": "中国第一颗人造卫星的发射年份是哪一年？这一年中国发生了什么标志性事件？",
        "sub_queries": [
            "中国第一颗人造卫星叫什么、哪一年发射？",
            "1970 年中国有哪些标志性历史事件？",
        ],
        "gt_keywords": [["1970"]],
    },
    {
        "id": "qa4",
        "input": "获得 2024 年诺贝尔生理学或医学奖的两位科学家中，哪位是美国人？",
        "sub_queries": [
            "2024 年诺贝尔生理学或医学奖授予了谁？",
            "其中哪位的国籍是美国？",
        ],
        "gt_keywords": [["安布罗斯", "维克托", "ruvkun"]],
    },
    {
        "id": "qa5",
        "input": "Python 语言之父出生在哪个国家？该国首都是哪里？",
        "sub_queries": [
            "Python 语言之父是谁？",
            "他出生在哪个国家？",
            "该国的首都是哪里？",
        ],
        "gt_keywords": [["荷兰"], ["阿姆斯特丹"]],
    },
    {
        "id": "qa6",
        "input": "珠穆朗玛峰所在的山脉横跨哪两个国家？其中人均 GDP 较低的是哪个？",
        "sub_queries": [
            "珠穆朗玛峰位于哪座山脉、横跨哪两个国家？",
            "这两个国家 2023 年人均 GDP 哪个更低？",
        ],
        "gt_keywords": [["尼泊尔"], ["中国"]],
    },
    {
        "id": "qa7",
        "input": "《三国演义》的作者是哪个朝代的作家？该朝代之前是哪个朝代？",
        "sub_queries": [
            "《三国演义》的作者是谁、哪个朝代？",
            "该朝代之前的朝代是什么？",
        ],
        "gt_keywords": [["明"], ["元"]],
    },
    {
        "id": "qa8",
        "input": "国际空间站主要合作机构 NASA 属于哪个国家？该国现任总统上任年份是？",
        "sub_queries": [
            "NASA 属于哪个国家？",
            "该国现任总统哪一年上任？",
        ],
        "gt_keywords": [["美国"], ["2025"]],
    },
    {
        "id": "qa9",
        "input": "已知\"阿波罗计划\"首次载人登月任务编号是 11。那么该任务指令长是谁？他乘坐的登月舱名字是？",
        "sub_queries": [
            "阿波罗 11 号任务的指令长是谁？",
            "阿波罗 11 号的登月舱叫什么名字？",
        ],
        "gt_keywords": [["阿姆斯特朗"], ["鹰", "鹰号", "eagle"]],
    },
    {
        "id": "qa10",
        "input": "DeepMind 开发的围棋 AI AlphaGo 战胜李世石是哪一年？那年 AlphaGo 的胜场是 4 比多少？",
        "sub_queries": [
            "AlphaGo 与李世石的比赛是哪一年？",
            "那次比赛最终比分是多少？",
        ],
        "gt_keywords": [["2016"], ["1", "4比1", "4-1"]],
    },
    {
        "id": "qa11",
        "input": "《红楼梦》的作者曹雪芹是哪个朝代人？该朝代的开国皇帝是谁？",
        "sub_queries": [
            "曹雪芹是哪个朝代的人？",
            "该朝代的开国皇帝是谁？",
        ],
        "gt_keywords": [["清"], ["努尔哈赤", "皇太极", "顺治"]],
    },
    {
        "id": "qa12",
        "input": "欧洲联盟的总部设在哪个城市？该城市属于哪个国家？",
        "sub_queries": [
            "欧盟总部设在哪个城市？",
            "该城市属于哪个国家？",
        ],
        "gt_keywords": [["布鲁塞尔"], ["比利时"]],
    },
]


def multihop_workflow(data: dict) -> Workflow:
    subs = data["sub_queries"]
    steps = []
    for i, q in enumerate(subs):
        steps.append(WorkflowStep(
            id=f"sub{i}",
            kind="retrieve",
            prompt=step_prompt(
                f"回答下面的子问题。只输出直接答案，一两句话，不要多余内容。\n\n子问题：{q}"
            ),
            max_tokens=300,
            temperature=0.0,
        ))
    sub_ids = [f"sub{i}" for i in range(len(subs))]
    steps.append(WorkflowStep(
        id="syn",
        kind="synthesize",
        depends_on=sub_ids,
        prompt=step_prompt(
            "综合上面各子问题的答案，回答原始问题。给出完整、准确的最终答案。\n\n原始问题：" + data["input"]
        ),
        max_tokens=600,
        temperature=0.0,
    ))
    return Workflow(steps)


def multihop_verify(output: str, data: dict) -> Tuple[bool, dict]:
    ok, missing = contains_groups(output, data["gt_keywords"])
    return ok, {"missing": missing, "keywords": data["gt_keywords"]}


# ============================================================
# 任务 2：BugTriage（10 例）
# ============================================================

BUG_TRIAGE = [
    {
        "id": "bug1",
        "input": "用户反馈：'应用在点击导出按钮后直接崩溃，日志显示 NullPointerException at line 143 of ExportService.java，影响所有使用导出功能的用户。'",
        "gt": {"severity": "高", "category": "崩溃",
               "keywords": [["高"], ["崩溃", "crash", "宕机"], ["nullpointer", "空指针", "npe"]]},
    },
    {
        "id": "bug2",
        "input": "用户反馈：'个人中心头像无法更新，点击上传后一直转圈，不影响其他功能。'",
        "gt": {"severity": "中", "category": "功能异常",
               "keywords": [["中"], ["上传", "头像", "功能异常"]]},
    },
    {
        "id": "bug3",
        "input": "用户反馈：'订单支付成功后页面仍显示待支付，金额已扣款，涉及金额约 5 万元，多个用户反馈。'",
        "gt": {"severity": "高", "category": "支付",
               "keywords": [["高"], ["支付", "扣款"]]},
    },
    {
        "id": "bug4",
        "input": "用户反馈：'搜索结果中英文标点显示为乱码，仅中文环境出现，功能可用。'",
        "gt": {"severity": "低", "category": "显示",
               "keywords": [["低"], ["乱码", "编码", "显示"]]},
    },
    {
        "id": "bug5",
        "input": "用户反馈：'注册页点击发送验证码没有任何反应，控制台报 500 错误，新用户无法注册。'",
        "gt": {"severity": "高", "category": "注册",
               "keywords": [["高"], ["注册", "验证码"]]},
    },
    {
        "id": "bug6",
        "input": "用户反馈：'夜间模式下部分按钮文字看不清，对比度太低，不影响操作。'",
        "gt": {"severity": "低", "category": "界面",
               "keywords": [["低"], ["对比度", "夜间"]]},
    },
    {
        "id": "bug7",
        "input": "用户反馈：'购物车添加商品后偶发数量翻倍，刷新后恢复，一天出现几次。'",
        "gt": {"severity": "中", "category": "数据一致性",
               "keywords": [["中"], ["数量", "翻倍", "一致性", "并发"]]},
    },
    {
        "id": "bug8",
        "input": "用户反馈：'报表导出功能对超过 1 万行的数据导出后 Excel 打不开，文件损坏。'",
        "gt": {"severity": "中", "category": "导出",
               "keywords": [["中"], ["导出", "损坏", "大文件"]]},
    },
    {
        "id": "bug9",
        "input": "用户反馈：'所有用户登录后都收到重复的通知推送，量非常大，疑似线上事故。'",
        "gt": {"severity": "高", "category": "推送",
               "keywords": [["高"], ["推送", "重复"]]},
    },
    {
        "id": "bug10",
        "input": "用户反馈：'帮助中心页面打开慢，加载需 10 秒以上，页面最终能显示。'",
        "gt": {"severity": "中", "category": "性能",
               "keywords": [["中"], ["性能", "慢", "加载"]]},
    },
]


def bugtriage_workflow(data: dict) -> Workflow:
    return Workflow([
        WorkflowStep(
            id="sev", kind="classify",
            prompt=step_prompt(
                "根据缺陷报告判断严重级别（高/中/低），只输出一个词：高 或 中 或 低。\n\n缺陷报告：" + data["input"]
            ),
            max_tokens=50, temperature=0.0,
        ),
        WorkflowStep(
            id="cat", kind="classify",
            prompt=step_prompt(
                "根据缺陷报告判断问题类别（崩溃/功能异常/界面/性能/数据一致性/支付/注册/导出/推送等），只输出类别词。\n\n缺陷报告：" + data["input"]
            ),
            max_tokens=50, temperature=0.0,
        ),
        WorkflowStep(
            id="fin", kind="final", depends_on=["sev", "cat"],
            prompt=step_prompt(
                "综合严重级别和类别判断，输出一行诊断结论，格式：严重级别：X；问题类别：Y；建议：一句话。"
            ),
            max_tokens=200, temperature=0.0,
        ),
    ])


def bugtriage_verify(output: str, data: dict) -> Tuple[bool, dict]:
    gt = data["gt"]
    ok, missing = contains_groups(output, gt["keywords"])
    return ok, {"missing": missing, "expected": gt}


# ============================================================
# 任务 3：DocEdit（8 例）
# ============================================================

DOC_EDIT = [
    {
        "id": "doc1",
        "input": "修改以下产品说明文档：1) 把标题改为\"新一代智能水杯\"；2) 在功能列表末尾增加\"支持 30 天待机\"；3) 删除所有提到\"旧版\"的句子。\n\n文档：\n# 智能水杯 2.0\n功能列表：\n- 保温 12 小时\n- 温度显示\n- 旧版产品不支持触控\n本产品为旧版升级版。",
        "gt_keywords": [["新一代智能水杯"], ["30天待机", "30天", "待机"]],
        "gt_absent": ["旧版"],
        "sections": ["标题", "功能列表", "全文"],
    },
    {
        "id": "doc2",
        "input": "修改这份会议纪要：1) 会议日期改为 2026-10-08；2) 把\"预算 10 万\"改为\"预算 15 万\"；3) 补充决议项\"下周五前完成原型\"。\n\n文档：\n会议纪要\n日期：2026-09-20\n讨论内容：预算 10 万，计划 3 个月内上线。",
        "gt_keywords": [["2026-10-08", "2026年10月8日", "10月8日"], ["15万", "150000"], ["原型"]],
        "gt_absent": [],
        "sections": ["日期", "预算", "决议"],
    },
    {
        "id": "doc3",
        "input": "编辑请假邮件草稿：1) 称呼改为\"李经理\"；2) 请假时长改为 5 天；3) 结尾增加\"祝好\"。\n\n草稿：\n王经理：\n因家中有事，申请请假 3 天，请批准。",
        "gt_keywords": [["李经理"], ["5天", "五天"], ["祝好"]],
        "gt_absent": ["3天", "三天"],
        "sections": ["称呼", "时长", "结尾"],
    },
    {
        "id": "doc4",
        "input": "修改周报模板：1) 标题改为\"产品组周报\"；2) 增加\"风险\"章节；3) 删除\"附：报销说明\"一行。\n\n模板：\n# 周报\n本周完成：开发登录页。\n附：报销说明见财务流程。",
        "gt_keywords": [["产品组周报"], ["风险"]],
        "gt_absent": ["报销"],
        "sections": ["标题", "章节", "全文"],
    },
    {
        "id": "doc5",
        "input": "编辑服务协议：1) 试用期从 14 天改为 30 天；2) 违约金比例从 5% 改为 10%；3) 增加条款\"本协议解释权归甲方\"。\n\n协议：\n试用期 14 天。违约需支付合同金额 5% 的违约金。",
        "gt_keywords": [["30天", "三十天"], ["10%", "百分之十"], ["甲方"]],
        "gt_absent": ["14天", "十四天", "5%"],
        "sections": ["试用期", "违约金", "条款"],
    },
    {
        "id": "doc6",
        "input": "修改活动通知：1) 时间改为本周六 14:00；2) 地点改为 3 楼会议室；3) 增加\"请提前 10 分钟到场\"。\n\n通知：\n活动时间：本周日 09:00。地点：2 楼大厅。",
        "gt_keywords": [["本周六", "周六"], ["14:00", "14点", "1400"], ["3楼会议室", "3楼"], ["提前10分钟", "提前10分"]],
        "gt_absent": ["本周日", "周日", "2楼大厅", "2楼"],
        "sections": ["时间", "地点", "提醒"],
    },
    {
        "id": "doc7",
        "input": "编辑实验说明：1) 样本量改为 200；2) 温度条件改为 37°C；3) 删除\"初步\"一词。",
        "input_doc": "实验说明：初步采用 100 个样本，在 25°C 下培养。",
        "gt_keywords": [["200", "两百"], ["37", "37度", "37°c"]],
        "gt_absent": ["100", "25", "初步"],
        "sections": ["样本量", "温度", "全文"],
    },
    {
        "id": "doc8",
        "input": "修改 API 文档：1) 接口名从 /v1/old 改为 /v2/new；2) 超时时间改为 30s；3) 增加返回字段 error_code。",
        "input_doc": "接口 /v1/old，超时 10s，返回 {data}。",
        "gt_keywords": [["/v2/new", "v2"], ["30s", "30秒"], ["error_code", "错误码"]],
        "gt_absent": ["/v1/old", "10s"],
        "sections": ["接口名", "超时", "返回字段"],
    },
]


def docedit_workflow(data: dict) -> Workflow:
    doc = data.get("input_doc", data["input"])
    n = len(data["sections"])
    steps = []
    for i, sec in enumerate(data["sections"]):
        steps.append(WorkflowStep(
            id=f"edit{i}", kind="edit",
            prompt=step_prompt(
                f"你负责文档中与「{sec}」相关的修改。根据指令修改对应部分，只输出修改后的对应段落内容。\n\n原始文档：\n{doc[:1500]}"
            ),
            max_tokens=400, temperature=0.0,
        ))
    edit_ids = [f"edit{i}" for i in range(n)]
    steps.append(WorkflowStep(
        id="fin", kind="final", depends_on=edit_ids,
        prompt=step_prompt(
            "把上面各部分的修改合并成完整的新文档输出。确保所有指令都已执行。"
        ),
        max_tokens=800, temperature=0.0,
    ))
    return Workflow(steps)


def docedit_verify(output: str, data: dict) -> Tuple[bool, dict]:
    ok, missing = contains_groups(output, data["gt_keywords"])
    absent_ok = True
    present = []
    out_norm = normalize(output)
    for word in data.get("gt_absent", []):
        if normalize(word) in out_norm:
            absent_ok = False
            present.append(word)
    return (ok and absent_ok), {"missing": missing, "should_not_contain": present}


# ============================================================
# 注册表
# ============================================================

TASKS = {
    "multihop": {
        "kind": "multihop",
        "description": "多跳问答（子问题并行 + 综合）",
        "data": MULTIHOP_QA,
        "make_workflow": multihop_workflow,
        "verify": multihop_verify,
        "system_prompt": "你是一个严谨的多跳问答助手，基于给定信息回答问题，答案要准确完整。",
    },
    "bug_triage": {
        "kind": "bug_triage",
        "description": "软件缺陷分诊（并行判定 + 复核）",
        "data": BUG_TRIAGE,
        "make_workflow": bugtriage_workflow,
        "verify": bugtriage_verify,
        "system_prompt": "你是软件缺陷分诊助手，输出要简洁、直接、包含关键判断。",
    },
    "doc_edit": {
        "kind": "doc_edit",
        "description": "协作文档编辑（多修改点并行 + 合并）",
        "data": DOC_EDIT,
        "make_workflow": docedit_workflow,
        "verify": docedit_verify,
        "system_prompt": "你是文档编辑助手，严格按指令修改，保留未要求改动的内容。",
    },
}
