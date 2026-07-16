#!/usr/bin/env python3
"""合并生成计划与增量 JSONL 用例，并拒绝重复 ID。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise RuntimeError(f"用例文件不存在：{path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def merge(plan: Path, new: Path | None = None) -> list[dict]:
    rows = read_jsonl(plan) + (read_jsonl(new) if new else [])
    required = {"id", "priority", "requirement", "input", "expected", "evidence", "reason", "tags"}
    invalid = [str(row.get("id", "<missing>")) for row in rows if not required <= row.keys()]
    if invalid:
        raise RuntimeError("用例字段不完整：" + "、".join(invalid))
    ids = [str(row.get("id", "")) for row in rows]
    if any(not case_id for case_id in ids):
        raise RuntimeError("每条用例必须包含 id")
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise RuntimeError("重复用例 ID：" + "、".join(duplicates))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True, help="生成的测试计划文件")
    parser.add_argument("--new", type=Path, help="增量用例文件")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        rows = merge(args.plan, args.new)
    except (RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"status": "READY", "cases": len(rows), "out": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
