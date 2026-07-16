#!/usr/bin/env python3
"""把 JSONL 测试结果生成简洁 Markdown 报告。"""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def read_results(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def cell(value: object) -> str:
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    return str(value or "-").replace("|", "\\|").replace("\n", "<br>")


def usage_lines(usage: dict) -> list[str]:
    try:
        started = datetime.fromisoformat(str(usage["started_at"]))
        finished = datetime.fromisoformat(str(usage["finished_at"]))
    except (KeyError, ValueError) as exc:
        raise RuntimeError("usage.json 缺少有效的开始或结束时间") from exc
    seconds = (finished - started).total_seconds()
    if seconds < 0:
        raise RuntimeError("结束时间不能早于开始时间")
    minutes, remain = divmod(int(seconds), 60)
    token = lambda key: "不可获取" if usage.get(key) is None else f"{int(usage[key]):,}"
    return [
        f"- 开始时间：{usage['started_at']}",
        f"- 结束时间：{usage['finished_at']}",
        f"- 运行耗时：{minutes} 分 {remain} 秒",
        f"- 输入 Token：{token('input_tokens')}",
        f"- 输出 Token：{token('output_tokens')}",
        f"- 总 Token：{token('total_tokens')}",
        f"- 统计来源：{usage.get('source') or '未说明'}",
    ]


def render(rows: list[dict], run_id: str, requirements: str, environment: str, scope: str, usage: dict) -> str:
    statuses = Counter(str(row.get("status", "")) for row in rows)
    invalid = sorted({status for status in statuses if status not in {"PASS", "FAIL", "BLOCKED"}})
    if invalid:
        raise RuntimeError("非法状态：" + "、".join(invalid))
    lines = [
        "# 巡火测试报告",
        "",
        f"- Run ID：`{run_id}`",
        f"- 需求来源：{requirements}",
        f"- 测试环境：{environment}",
        f"- 测试范围：{scope}",
        f"- 结果：PASS {statuses['PASS']} / FAIL {statuses['FAIL']} / BLOCKED {statuses['BLOCKED']}",
        "",
        "## 运行消耗",
        "",
        *usage_lines(usage),
        "",
        "## 测试结果",
        "",
        "| 用例 | 状态 | 实际结果 | 证据 | 缺陷/阻塞 |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(cell(row.get(key)) for key in ("id", "status", "actual", "evidence", "defect")) + " |")
    lines += ["", "## 结论", "", "存在 FAIL 时不通过；存在 BLOCKED 时列明未覆盖范围并安排补测。", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--requirements", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--usage", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        usage = json.loads(args.usage.read_text(encoding="utf-8"))
        report = render(read_results(args.results), args.run_id, args.requirements, args.environment, args.scope, usage)
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(json.dumps({"status": "READY", "out": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
