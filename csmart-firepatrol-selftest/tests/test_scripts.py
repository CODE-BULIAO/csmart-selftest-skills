from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_report  # noqa: E402
import generate_cases  # noqa: E402
import merge_cases  # noqa: E402
import runtime  # noqa: E402
import send_image  # noqa: E402


FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
CONTRACTS_PATH = Path(__file__).resolve().parents[1] / "evals" / "generic-contracts.jsonl"


def test_extract_points_with_specific_zone_variable() -> None:
    source = """const KAI_FIRE_PATROL_ZONES = {
      A: ['A16', 'A1', 'AM', 'AG', 'A0'],
      B: ['B18', 'B1', 'BM', 'BG', 'B0']
    };"""
    assert runtime.extract_points(source, "KAI_FIRE_PATROL_ZONES") == [
        "A16", "A1", "AM", "AG", "A0", "B18", "B1", "BM", "BG", "B0",
    ]


def test_extract_points_with_generic_pattern() -> None:
    source = """const BLY_FIRE_PATROL_ZONES = {
      A: ['A16', 'A1', 'AM'],
      basement: ['BM1', 'BM2']
    };"""
    assert runtime.extract_points(source) == ["A16", "A1", "AM", "BM1", "BM2"]


def test_extract_points_with_different_project_name() -> None:
    source = """const HOSPITAL_ZONES = {
      floor1: ['F1', 'F2', 'F3']
    };"""
    assert runtime.extract_points(source) == ["F1", "F2", "F3"]


def test_source_default_reads_double_quoted_value() -> None:
    source = 'const GROUP_FIREPATROL_BLY = process.env.GROUP_FIREPATROL_BLY || "prod@g.us";'
    assert runtime.source_default(source, "GROUP_FIREPATROL_BLY") == "prod@g.us"


def test_require_test_group_rejects_non_test_group(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "discover", lambda _root, _profile=None: {"test_group_safe": True, "test_group": "patrol@g.us"})
    runtime.require_test_group("patrol@g.us", Path("/runtime"))
    with pytest.raises(RuntimeError, match="拒绝非巡火测试群"):
        runtime.require_test_group("permit@g.us", Path("/runtime"))


def test_require_test_group_rejects_production_group_from_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "discover", lambda _root, _profile=None: {"test_group_safe": True, "test_group": "test@g.us"})
    profile = {"routing": {"production_groups": ["prod@g.us"]}}
    with pytest.raises(RuntimeError, match="拒绝"):
        runtime.require_test_group("prod@g.us", Path("/runtime"), profile)


def test_sender_defaults_to_ready() -> None:
    assert send_image.execution_status(False) == "READY"
    assert send_image.execution_status(True) == "EXECUTE"


def test_merge_keeps_plan_and_new_cases(tmp_path: Path) -> None:
    plan = tmp_path / "plan.jsonl"
    new = tmp_path / "new.jsonl"
    template = {"priority": "P1", "requirement": "规则", "input": "输入", "expected": "结果", "evidence": [], "reason": "原因", "tags": []}
    plan.write_text(json.dumps({"id": "GEN-1", **template}, ensure_ascii=False) + "\n", encoding="utf-8")
    new.write_text(json.dumps({"id": "NEW-1", **template}, ensure_ascii=False) + "\n", encoding="utf-8")
    assert [row["id"] for row in merge_cases.merge(plan, new)] == ["GEN-1", "NEW-1"]


def test_merge_rejects_duplicate_ids(tmp_path: Path) -> None:
    plan = tmp_path / "plan.jsonl"
    plan.write_text('{"id":"CASE-1","priority":"P1","requirement":"规则","input":"输入","expected":"结果","evidence":[],"reason":"原因","tags":[]}\n', encoding="utf-8")
    new = tmp_path / "new.jsonl"
    new.write_text('{"id":"CASE-1","priority":"P1","requirement":"规则","input":"输入","expected":"结果","evidence":[],"reason":"原因","tags":[]}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="重复用例"):
        merge_cases.merge(plan, new)


def test_merge_rejects_incomplete_fields(tmp_path: Path) -> None:
    plan = tmp_path / "plan.jsonl"
    plan.write_text('{"id":"TRIGGER-1","prompt":"巡火测试"}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="字段不完整"):
        merge_cases.merge(plan)


def test_generate_cases_with_site_a_fixture() -> None:
    plan = generate_cases.generate(CONTRACTS_PATH, FIXTURES / "site-a-65-points.json")
    assert len(plan) > 15
    ids = [row["id"] for row in plan]
    assert "GEN-001" in ids
    assert any(i.startswith("GEN-003-") for i in ids)
    assert any(i.startswith("GEN-008-") for i in ids)
    for row in plan:
        assert {"id", "priority", "requirement", "input", "expected", "evidence", "reason", "tags"} <= row.keys()


def test_generate_cases_with_site_b_fixture() -> None:
    plan = generate_cases.generate(CONTRACTS_PATH, FIXTURES / "site-b-10-points.json")
    assert len(plan) > 10
    ids = [row["id"] for row in plan]
    assert "GEN-001" in ids
    assert any(i.startswith("GEN-003-") for i in ids)
    for row in plan:
        assert {"id", "priority", "requirement", "input", "expected", "evidence", "reason", "tags"} <= row.keys()


def test_generate_cases_no_unresolved_placeholders() -> None:
    plan = generate_cases.generate(CONTRACTS_PATH, FIXTURES / "site-a-65-points.json")
    for row in plan:
        text = json.dumps(row, ensure_ascii=False)
        assert "${" not in text, f"用例 {row['id']} 包含未解析的占位符"


def test_generate_cases_site_a_and_site_b_differ() -> None:
    plan_a = generate_cases.generate(CONTRACTS_PATH, FIXTURES / "site-a-65-points.json")
    plan_b = generate_cases.generate(CONTRACTS_PATH, FIXTURES / "site-b-10-points.json")
    inputs_a = {row["id"]: str(row["input"]) for row in plan_a}
    inputs_b = {row["id"]: str(row["input"]) for row in plan_b}
    common_ids = set(inputs_a) & set(inputs_b)
    differing = [cid for cid in common_ids if inputs_a[cid] != inputs_b[cid]]
    assert len(differing) > 0, "两个 fixture 生成的用例应该有不同输入"


def test_report_counts_and_lists_results() -> None:
    rows = [
        {"id": "GEN-1", "status": "PASS", "actual": "正确", "evidence": ["log"]},
        {"id": "NEW-1", "status": "FAIL", "actual": "错误", "defect": "范围解析失败"},
    ]
    usage = {
        "started_at": "2026-07-15T10:00:00+08:00",
        "finished_at": "2026-07-15T10:02:05+08:00",
        "input_tokens": 1200,
        "output_tokens": 300,
        "total_tokens": 1500,
        "source": "runtime",
    }
    report = build_report.render(rows, "run-1", "需求文档", "测试群", "通用契约+增量", usage)
    assert "PASS 1 / FAIL 1 / BLOCKED 0" in report
    assert "测试环境：测试群" in report
    assert "运行耗时：2 分 5 秒" in report
    assert "总 Token：1,500" in report
    assert "范围解析失败" in report


def test_report_rejects_invalid_status() -> None:
    usage = {"started_at": "2026-07-15T10:00:00+08:00", "finished_at": "2026-07-15T10:01:00+08:00"}
    with pytest.raises(RuntimeError, match="非法状态"):
        build_report.render([{"id": "X", "status": "SKIP"}], "run-1", "需求", "环境", "范围", usage)


def test_report_marks_unavailable_tokens() -> None:
    usage = {
        "started_at": "2026-07-15T10:00:00+08:00",
        "finished_at": "2026-07-15T10:00:30+08:00",
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "source": "当前运行环境未提供Token统计",
    }
    report = build_report.render([], "run-1", "需求", "环境", "范围", usage)
    assert "总 Token：不可获取" in report
    assert "当前运行环境未提供Token统计" in report
