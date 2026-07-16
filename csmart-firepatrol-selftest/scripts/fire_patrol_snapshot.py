#!/usr/bin/env python3
"""只读输出指定业务日和群组的巡火状态。"""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("/root/whatsapp-bot/data/fire_patrol.json"))
    parser.add_argument("--date", required=True)
    parser.add_argument("--group-id", required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.data.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(data.get(args.date, {}).get(args.group_id, {}), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
