from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = [
    json.loads(line)
    for line in (ROOT / "evals/generic-contracts.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]


def test_contracts_have_required_fields() -> None:
    required = {"id", "priority", "requirement", "expected", "evidence", "reason", "tags"}
    for row in CONTRACTS:
        assert required <= row.keys(), f"用例 {row.get('id')} 缺少字段"


def test_contract_ids_are_unique() -> None:
    ids = [row["id"] for row in CONTRACTS]
    assert len(set(ids)) == len(ids)


def test_all_ids_start_with_gen() -> None:
    for row in CONTRACTS:
        assert row["id"].startswith("GEN-"), f"用例 ID {row['id']} 不以 GEN- 开头"


def test_core_tag_coverage() -> None:
    tags = {tag for row in CONTRACTS for tag in row["tags"]}
    required_tags = {
        "routing",
        "dictionary",
        "trigger",
        "forward",
        "reverse",
        "separator",
        "special-point",
        "invalid",
        "summary",
        "scheduler",
        "manual-summary",
        "business-date",
        "daily-frequency",
    }
    assert required_tags <= tags


def test_no_hardcoded_project_data() -> None:
    text = (ROOT / "evals/generic-contracts.jsonl").read_text(encoding="utf-8")
    assert "BLY" not in text
    assert "GROUP_FIREPATROL_BLY" not in text
    assert "cron 0 18-23,0" not in text
    assert "A16" not in text or "${FIRST_POINT}" in text or "A16" not in text
    for row in CONTRACTS:
        for field in ("input", "expected"):
            value = str(row.get(field, ""))
            assert "65" not in value or "project-profile" in value, f"用例 {row['id']} 包含硬编码的 65 点字典"


def test_contracts_use_params_or_profile_references() -> None:
    for row in CONTRACTS:
        has_params = bool(row.get("params"))
        text = json.dumps(row, ensure_ascii=False)
        has_profile_ref = "project-profile" in text or "requirements." in text
        if row["id"] in ("GEN-001", "GEN-010", "GEN-011", "GEN-014"):
            continue
        assert has_params or has_profile_ref, f"用例 {row['id']} 既无 params 也无 profile 引用"
