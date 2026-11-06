"""数据装载层：科室、分诊规则、急症规则、知识库、医生出诊表。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import DATA_DIR


def _load_json(name: str, default: Any) -> Any:
    path: Path = DATA_DIR / name
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # 数据文件写坏了也不能让服务起不来
        print(f"[store] 解析 {name} 失败: {exc}")
        return default


@dataclass
class HospitalData:
    hospital: dict = field(default_factory=dict)
    departments: list[dict] = field(default_factory=list)
    triage_rules: list[dict] = field(default_factory=list)
    populations: list[dict] = field(default_factory=list)
    clarify: dict = field(default_factory=dict)
    emergency: dict = field(default_factory=dict)
    knowledge: list[dict] = field(default_factory=list)
    doctors: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.dept_by_name: dict[str, dict] = {d["name"]: d for d in self.departments}

    def dept(self, name: str) -> dict | None:
        return self.dept_by_name.get(name)

    def doctors_of(self, dept_name: str) -> list[dict]:
        return [d for d in self.doctors if d.get("dept") == dept_name]


def _build() -> HospitalData:
    dept_doc = _load_json("departments.json", {})
    triage_doc = _load_json("triage_rules.json", {})
    emergency_doc = _load_json("emergency_rules.json", {})
    kb_doc = _load_json("knowledge.json", {"items": []})
    doctor_doc = _load_json("doctors.json", {"doctors": []})

    return HospitalData(
        hospital=dept_doc.get("hospital", {}),
        departments=dept_doc.get("departments", []),
        triage_rules=triage_doc.get("rules", []),
        populations=triage_doc.get("populations", []),
        clarify=triage_doc.get("clarify", {}),
        emergency=emergency_doc,
        knowledge=kb_doc.get("items", []),
        doctors=doctor_doc.get("doctors", []),
    )


_data: HospitalData | None = None


def get_data() -> HospitalData:
    global _data
    if _data is None:
        _data = _build()
    return _data


def reload_data() -> HospitalData:
    global _data
    _data = _build()
    return _data
