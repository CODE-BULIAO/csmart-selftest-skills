#!/usr/bin/env python3
"""从通用契约模板和项目配置动态生成测试计划。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def load_contracts(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_profile(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_points(zones: dict[str, list[str]]) -> list[str]:
    points: list[str] = []
    for zone_points in zones.values():
        points.extend(zone_points)
    return points


def find_special_points(zones: dict[str, list[str]]) -> list[str]:
    return [p for p in flatten_points(zones) if not re.match(r"^[A-Z]\d+$", p)]


def find_invalid_point(zones: dict[str, list[str]]) -> str:
    all_points = set(flatten_points(zones))
    candidate = "Z999"
    while candidate in all_points:
        candidate = f"X{candidate[1:]}" if candidate.startswith("Z") else f"Z{int(candidate[1:]) + 1}"
    return candidate


def get_zone_values(zones: dict[str, list[str]]) -> tuple[str, list[str]]:
    first_zone_name = next(iter(zones))
    return first_zone_name, zones[first_zone_name]


def build_substitutions(profile: dict) -> dict[str, str | list[str]]:
    reqs = profile.get("requirements", {})
    zones = reqs.get("zones", {})
    trigger_words = reqs.get("trigger_words", [])
    first_zone_name, first_zone_points = get_zone_values(zones)
    all_points = flatten_points(zones)
    subs: dict[str, str | list[str]] = {
        "FIRST_POINT": first_zone_points[0] if first_zone_points else "",
        "MID_POINT": first_zone_points[len(first_zone_points) // 2] if first_zone_points else "",
        "LAST_POINT": all_points[-1] if all_points else "",
        "INVALID_POINT": find_invalid_point(zones),
        "SPECIAL_POINTS": find_special_points(zones),
        "TRIGGER_WORD": trigger_words[0] if trigger_words else "",
        "ALL_TRIGGERS": trigger_words,
        "SEPARATORS": reqs.get("separators", []),
    }
    return subs


def substitute(value: object, subs: dict[str, str | list[str]]) -> object:
    if isinstance(value, str):
        for key, sub in subs.items():
            placeholder = f"${{{key}}}"
            if isinstance(sub, list):
                if placeholder == value:
                    return sub
                value = value.replace(placeholder, ", ".join(sub))
            else:
                value = value.replace(placeholder, str(sub))
        return value
    if isinstance(value, list):
        return [substitute(item, subs) for item in value]
    if isinstance(value, dict):
        return {k: substitute(v, subs) for k, v in value.items()}
    return value


def generate_expanded_cases(contract: dict, subs: dict[str, str | list[str]]) -> list[dict]:
    contract_id = contract["id"]
    params = contract.get("params", [])
    special_points = subs.get("SPECIAL_POINTS", [])

    if contract_id == "GEN-008":
        if not special_points:
            return [{
                "id": contract_id,
                "priority": contract["priority"],
                "requirement": contract["requirement"],
                "input": "",
                "expected": "",
                "evidence": [],
                "reason": contract.get("reason", ""),
                "tags": contract.get("tags", []),
                "status": "NOT_APPLICABLE",
                "not_applicable_reason": "项目无非数字特殊点位，跳过此用例",
            }]
        cases = []
        for point in special_points[:5]:
            cases.append({
                "id": f"{contract_id}-{point}",
                "priority": contract["priority"],
                "requirement": contract["requirement"],
                "input": f"{subs['TRIGGER_WORD']} {point}",
                "expected": f"{point} 标记为已上报且归属正确区域",
                "evidence": contract.get("evidence", []),
                "reason": contract.get("reason", ""),
                "tags": contract.get("tags", []),
            })
        return cases

    if not params:
        case = dict(contract)
        case["input"] = substitute(contract.get("input", ""), subs)
        case["expected"] = substitute(contract.get("expected", ""), subs)
        case.pop("params", None)
        return [case]

    triggers = subs.get("ALL_TRIGGERS", [])

    if contract_id == "GEN-003":
        cases = []
        for word in triggers:
            cases.append({
                "id": f"{contract_id}-{word}",
                "priority": contract["priority"],
                "requirement": contract["requirement"],
                "input": f"{word} {subs['FIRST_POINT']}",
                "expected": contract.get("expected", ""),
                "evidence": contract.get("evidence", []),
                "reason": contract.get("reason", ""),
                "tags": contract.get("tags", []),
            })
        return cases

    case = dict(contract)
    case["input"] = substitute(contract.get("input", ""), subs)
    case["expected"] = substitute(contract.get("expected", ""), subs)
    case.pop("params", None)
    return [case]


def matches_include(case: dict, include_tags: set[str]) -> bool:
    if not include_tags:
        return True
    case_tags = set(case.get("tags", []))
    return bool(case_tags & include_tags)


def generate(contracts_path: Path, profile_path: Path, include_tags: set[str] | None = None) -> list[dict]:
    contracts = load_contracts(contracts_path)
    profile = load_profile(profile_path)
    subs = build_substitutions(profile)
    tags = include_tags or set()
    plan: list[dict] = []
    seen_ids: set[str] = set()
    for contract in contracts:
        expanded = generate_expanded_cases(contract, subs)
        for case in expanded:
            case_id = str(case.get("id", ""))
            if case_id in seen_ids:
                continue
            seen_ids.add(case_id)
            if matches_include(case, tags):
                plan.append(case)
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--include", type=str, default="", help="逗号分隔的标签，只生成匹配的用例")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    try:
        include_tags = set(t.strip() for t in args.include.split(",") if t.strip()) if args.include else None
        plan = generate(args.contracts, args.profile, include_tags)
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in plan), encoding="utf-8")
    print(json.dumps({"status": "READY", "cases": len(plan), "out": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
