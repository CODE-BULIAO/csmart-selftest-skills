#!/usr/bin/env python3
"""过滤日志证据，移除 Base64 图片数据，只保留元数据字段。"""

from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path

BASE64_PREFIXES = ("/9j/", "iVBOR", "R0lGOD", "UklGR", "AAABAA", "DAIK")
BASE64_MIN_LENGTH = 200
KEEP_FIELDS = {
    "type", "id", "timestamp", "date", "time",
    "caption", "text", "message", "reply", "body_text",
    "filePath", "path", "file", "imagePath", "imageName",
    "size", "fileSize", "length",
    "files", "savedFiles",
    "status", "state", "changes",
    "from", "to", "group", "groupId",
    "senderName", "pushName",
    "error", "reason",
}
BASE64_INLINE_RE = re.compile(
    r"(?:data:image/[^;]+;base64,)?([A-Za-z0-9+/]{200,}={0,2})"
)


def is_base64(value: str) -> bool:
    if len(value) < BASE64_MIN_LENGTH:
        return False
    for prefix in BASE64_PREFIXES:
        if value.startswith(prefix):
            return True
    if len(value) > 500 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", value):
        return True
    return False


def summarize_base64(value: str) -> str:
    size = len(value)
    return f"[Base64 removed, {size} chars]"


def filter_value(key: str, value: object) -> object:
    if isinstance(value, str):
        if is_base64(value):
            return summarize_base64(value)
        inline = BASE64_INLINE_RE.sub(
            lambda m: summarize_base64(m.group(1)), value
        )
        return inline
    if isinstance(value, list):
        return [filter_value(key, item) for item in value]
    if isinstance(value, dict):
        return filter_entry(value)
    return value


def filter_entry(entry: dict) -> dict:
    result: dict = {}
    for key, value in entry.items():
        filtered = filter_value(key, value)
        if isinstance(filtered, str) and filtered.startswith("[Base64 removed"):
            result[key] = filtered
        else:
            result[key] = filtered
    return result


def filter_text_line(line: str) -> str:
    return BASE64_INLINE_RE.sub(
        lambda m: summarize_base64(m.group(1)), line
    )


def filter_file(input_path: Path) -> list[dict]:
    content = input_path.read_text(encoding="utf-8", errors="replace")
    results: list[dict] = []

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entry = json.loads(stripped)
            if isinstance(entry, dict):
                results.append(filter_entry(entry))
            elif isinstance(entry, list):
                for item in entry:
                    if isinstance(item, dict):
                        results.append(filter_entry(item))
            else:
                results.append({"line": filter_text_line(stripped)})
        except json.JSONDecodeError:
            filtered = filter_text_line(stripped)
            if filtered.strip():
                results.append({"line": filtered})

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="输入日志文件")
    parser.add_argument("--out", type=Path, required=True, help="输出过滤后的 JSONL")
    args = parser.parse_args()

    if not args.input.is_file():
        print(json.dumps({"status": "BLOCKED", "reason": f"文件不存在：{args.input}"}, ensure_ascii=False))
        return 2

    entries = filter_file(args.input)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries),
        encoding="utf-8",
    )

    original_size = args.input.stat().st_size
    filtered_size = args.out.stat().st_size
    reduction = (1 - filtered_size / original_size) * 100 if original_size > 0 else 0
    print(json.dumps({
        "status": "READY",
        "entries": len(entries),
        "original_bytes": original_size,
        "filtered_bytes": filtered_size,
        "reduction_pct": round(reduction, 1),
        "out": str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
