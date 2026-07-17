from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_report  # noqa: E402
import filter_evidence  # noqa: E402
import generate_cases  # noqa: E402
import merge_cases  # noqa: E402
import runtime  # noqa: E402
import send_image  # noqa: E402
import send_text  # noqa: E402


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


def test_extract_profile_block_scopes_to_zone_var() -> None:
    source = "\nconst KAI_ZONES = { A: ['A1'] };\nconst kaiSched = { schedule: ['0 18 * * *'] };\n\nconst BLY_ZONES = { B: ['B1'] };\nconst blySched = { schedule: ['0 22 * * *'] };\n"
    kai_block = runtime.extract_profile_block(source, "KAI_ZONES")
    bly_block = runtime.extract_profile_block(source, "BLY_ZONES")
    assert "KAI_ZONES" in kai_block
    assert "BLY_ZONES" not in kai_block
    assert "BLY_ZONES" in bly_block
    assert "KAI_ZONES" not in bly_block


def test_extract_schedules_scoped_to_profile() -> None:
    source = "\nconst KAI_FIRE_PATROL_ZONES = { A: ['A1'] };\nconst kaiConf = { schedule: ['0 18 * * *', '0 21 * * *'] };\n\nconst BLY_FIRE_PATROL_ZONES = { B: ['B1'] };\nconst blyConf = { schedule: ['0 22 * * *', '0 0 * * *'] };\n"
    assert runtime.extract_schedules(source, "KAI_FIRE_PATROL_ZONES") == ["'0 18 * * *', '0 21 * * *'"]
    assert runtime.extract_schedules(source, "BLY_FIRE_PATROL_ZONES") == ["'0 22 * * *', '0 0 * * *'"]
    assert len(runtime.extract_schedules(source, "")) == 2


def test_extract_schedules_falls_back_when_zone_not_found() -> None:
    source = "const ZONES = { A: ['A1'] };\nconst conf = { schedule: ['0 18 * * *'] };"
    assert runtime.extract_schedules(source, "NONEXISTENT_ZONES") == ["'0 18 * * *'"]


def test_sender_defaults_to_ready() -> None:
    assert send_image.execution_status(False) == "READY"
    assert send_image.execution_status(True) == "EXECUTE"


def test_send_text_execution_status() -> None:
    assert send_text.execution_status(False) == "READY"
    assert send_text.execution_status(True) == "EXECUTE"


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


def test_generate_cases_site_b_gen008_not_applicable() -> None:
    plan = generate_cases.generate(CONTRACTS_PATH, FIXTURES / "site-b-10-points.json")
    gen008_cases = [row for row in plan if row["id"] == "GEN-008"]
    assert len(gen008_cases) == 1
    assert gen008_cases[0]["status"] == "NOT_APPLICABLE"
    assert "特殊点位" in gen008_cases[0]["not_applicable_reason"]


def test_generate_cases_site_a_gen008_expanded() -> None:
    plan = generate_cases.generate(CONTRACTS_PATH, FIXTURES / "site-a-65-points.json")
    gen008_cases = [row for row in plan if row["id"].startswith("GEN-008-")]
    assert len(gen008_cases) > 0
    for case in gen008_cases:
        assert case.get("status") != "NOT_APPLICABLE"


def test_generate_cases_include_filters_by_tag() -> None:
    plan_all = generate_cases.generate(CONTRACTS_PATH, FIXTURES / "site-a-65-points.json")
    plan_routing = generate_cases.generate(CONTRACTS_PATH, FIXTURES / "site-a-65-points.json", {"routing"})
    assert len(plan_routing) < len(plan_all)
    assert len(plan_routing) > 0
    for case in plan_routing:
        assert "routing" in case.get("tags", [])


def test_generate_cases_include_multiple_tags() -> None:
    plan = generate_cases.generate(CONTRACTS_PATH, FIXTURES / "site-a-65-points.json", {"routing", "invalid"})
    for case in plan:
        tags = set(case.get("tags", []))
        assert tags & {"routing", "invalid"}


def test_generate_cases_include_empty_returns_all() -> None:
    plan_default = generate_cases.generate(CONTRACTS_PATH, FIXTURES / "site-a-65-points.json")
    plan_none = generate_cases.generate(CONTRACTS_PATH, FIXTURES / "site-a-65-points.json", None)
    assert len(plan_default) == len(plan_none)


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


def test_filter_evidence_removes_base64_body(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    fake_base64 = "/9j/" + "A" * 500
    entry = {"type": "image", "body": fake_base64, "caption": "安全相", "filePath": "/tmp/img.jpg", "size": 12345}
    log.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    results = filter_evidence.filter_file(log)
    assert len(results) == 1
    assert results[0]["type"] == "image"
    assert results[0]["caption"] == "安全相"
    assert results[0]["filePath"] == "/tmp/img.jpg"
    assert "[Base64 removed" in results[0]["body"]


def test_filter_evidence_keeps_metadata_fields(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    entry = {"type": "text", "text": "巡夜安全相已記錄", "files": [], "savedFiles": [], "status": "ok"}
    log.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    results = filter_evidence.filter_file(log)
    assert len(results) == 1
    assert results[0]["type"] == "text"
    assert results[0]["text"] == "巡夜安全相已記錄"
    assert results[0]["files"] == []


def test_filter_evidence_handles_text_lines(tmp_path: Path) -> None:
    log = tmp_path / "log.txt"
    log.write_text("INFO: bot started\nINFO: message received\n", encoding="utf-8")
    results = filter_evidence.filter_file(log)
    assert len(results) == 2
    assert "bot started" in results[0]["line"]


def test_filter_evidence_is_base64_detection() -> None:
    assert filter_evidence.is_base64("/9j/" + "A" * 300)
    assert filter_evidence.is_base64("iVBOR" + "A" * 300)
    assert not filter_evidence.is_base64("short text")
    assert not filter_evidence.is_base64("安全相 B1")


def test_filter_evidence_inline_base64_replacement() -> None:
    line = "data:image/jpeg;base64," + "/9j/" + "A" * 300
    filtered = filter_evidence.filter_text_line(line)
    assert "[Base64 removed" in filtered
    assert "/9j/" not in filtered


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
    assert "NOT_APPLICABLE 0" in report
    assert "测试环境：测试群" in report
    assert "运行耗时：2 分 5 秒" in report
    assert "总 Token：1,500" in report
    assert "范围解析失败" in report


def test_report_rejects_invalid_status() -> None:
    usage = {"started_at": "2026-07-15T10:00:00+08:00", "finished_at": "2026-07-15T10:01:00+08:00"}
    with pytest.raises(RuntimeError, match="非法状态"):
        build_report.render([{"id": "X", "status": "SKIP"}], "run-1", "需求", "环境", "范围", usage)


def test_report_accepts_not_applicable_status() -> None:
    rows = [
        {"id": "GEN-008", "status": "NOT_APPLICABLE", "actual": "", "evidence": [], "defect": "无非数字特殊点位"},
    ]
    usage = {
        "started_at": "2026-07-15T10:00:00+08:00",
        "finished_at": "2026-07-15T10:01:00+08:00",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "source": "runtime",
    }
    report = build_report.render(rows, "run-1", "需求", "环境", "范围", usage)
    assert "NOT_APPLICABLE 1" in report
    assert "无非数字特殊点位" in report


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
