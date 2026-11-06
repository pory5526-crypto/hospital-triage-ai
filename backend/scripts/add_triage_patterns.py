"""一次性脚本：给分诊规则批量补充正则模式，覆盖患者的口语说法。

跑完即可删除，规则结果已写回 data/triage_rules.json。
"""

from __future__ import annotations

import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "triage_rules.json"

PATTERNS: dict[str, list[str]] = {
    "r-throat": ["(咽|喉咙|嗓子).{0,6}(疼|痛|干|痒|异物|发炎)"],
    "r-ear": ["(耳朵|耳内|耳道).{0,6}(响|嗡|闷|堵|疼|痛|流脓)", "(听力|听声音).{0,4}(下降|变差|不清)"],
    "r-skin": ["(起|长|出).{0,4}(疹|红点|疙瘩)", "痒"],
    "r-acne": ["痘"],
    "r-eye": ["(看东西|视力).{0,4}(模糊|下降|变差|不清)", "眼.{0,4}(红|疼|痛|干|痒)"],
    "r-dental": ["牙.{0,6}(出血|流血|松动|疼|痛)", "(嘴里|口腔|嘴巴).{0,6}溃疡"],
    "r-urinary": ["小便.{0,8}(刺痛|疼|痛|灼|泡)", "尿.{0,2}(频|急|痛|血)"],
    "r-joint": ["膝盖.{0,6}(疼|痛|酸)", "关节.{0,4}(肿|疼|痛|响)"],
    "r-varicose": ["血管.{0,4}(鼓|凸|突|粗)", "(腿|下肢).{0,6}(肿|胀|发凉)"],
    "r-gyn": ["(例假|月经).{0,6}(没来|不来|推迟|错后|乱)", "(没来|不来|推迟|错后).{0,4}(例假|月经)", "白带"],
    "r-thyroid": ["脖子.{0,4}(粗|肿|大)", "手.{0,3}(抖|颤)"],
    "r-fatigue": ["没力气", "浑身.{0,3}无力", "脸色.{0,4}(白|苍白)"],
    "r-cough": ["(走|爬|上楼|活动).{0,8}喘", "喘.{0,4}(不过气|不上)"],
    "r-general_surgery": ["(脖子|颈部|腋下|腹股沟).{0,8}(包|肿块|淋巴结|疙瘩)"],
    "r-breast": ["乳房.{0,8}(硬块|肿块|疙瘩|包|疼|痛)"],
    "r-anemia": ["脸色.{0,4}(白|苍白)"],
    "r-snore": ["打呼噜"],
    "r-mental": ["睡不着", "睡不好", "情绪"],
    "r-diabetes": ["血糖"],
    "r-tcm": ["中药", "调理"],
    "r-pain": ["疼得厉害.{0,10}(好久|几个月|几年)"],
}

NEW_RULES = [
    {
        "id": "r-kidney",
        "keywords": ["泡沫尿", "肌酐高", "尿蛋白", "眼睑水肿"],
        "patterns": ["(小便|尿).{0,6}泡沫", "(眼睑|眼睛|脸|下肢|双脚).{0,4}(水肿|肿起来|浮肿)"],
        "scores": {"肾内科": 1.0},
        "note": "泡沫尿、水肿需查尿常规与肾功能，归肾内科",
    },
    {
        "id": "r-lump",
        "keywords": ["体表肿块", "淋巴结肿大", "皮下肿块", "颈部包块"],
        "patterns": [
            "(脖子|颈部|腋下|腹股沟|锁骨).{0,8}(包|肿块|结节|疙瘩)",
            "(摸到|长了个|长了一).{0,4}(包|硬块|疙瘩)"
        ],
        "scores": {"普通外科": 1.0},
        "note": "体表包块先到普通外科，必要时加做超声",
    },
    {
        "id": "r-growth",
        "keywords": ["个子矮", "长得慢", "发育迟缓", "身高不达标"],
        "patterns": ["(个子|身高).{0,6}(矮|偏矮|不长|不达标|低)", "(比同龄|比同学).{0,4}(矮|小|瘦)"],
        "scores": {"儿童保健科": 1.2},
        "note": "生长发育评估归儿童保健科，14 岁以下也可先到儿科",
    },
]


def main() -> None:
    doc = json.loads(PATH.read_text(encoding="utf-8"))
    rules = doc["rules"]
    by_id = {r["id"]: r for r in rules}

    updated = 0
    for rid, pats in PATTERNS.items():
        rule = by_id.get(rid)
        if not rule:
            print(f"⚠ 找不到规则 {rid}")
            continue
        existing = rule.get("patterns", [])
        merged = existing + [p for p in pats if p not in existing]
        rule["patterns"] = merged
        updated += 1

    existing_ids = {r["id"] for r in rules}
    added = 0
    for rule in NEW_RULES:
        if rule["id"] not in existing_ids:
            rules.append(rule)
            existing_ids.add(rule["id"])
            added += 1

    PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {updated} 条规则，新增 {added} 条，共 {len(rules)} 条")


if __name__ == "__main__":
    main()
