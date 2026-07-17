#!/usr/bin/env python3
"""仅向巡火测试群发送文本消息；默认只检查。支持 --profile 参数。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from runtime import load_env, load_profile, require_test_group


def execution_status(execute: bool) -> str:
    return "EXECUTE" if execute else "READY"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/home/claw/self-testing-bot-run"))
    parser.add_argument("--bot-root", type=Path, default=Path("/root/whatsapp-bot"))
    parser.add_argument("--profile", type=Path, default=None, help="项目配置文件路径")
    parser.add_argument("--to", required=True)
    parser.add_argument("--message", required=True, help="要发送的文本内容")
    parser.add_argument("--url")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    profile = load_profile(args.profile)
    try:
        require_test_group(args.to, args.bot_root, profile)
        if not args.message.strip():
            raise RuntimeError("message 不能为空")
        env = load_env(args.root / ".env")
        secret = env.get("SEND_API_SECRET", "")
        if not secret:
            raise RuntimeError("缺少 SEND_API_SECRET")
    except (OSError, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2

    url = args.url or f"http://127.0.0.1:{env.get('SEND_API_PORT', '13081')}/send-text"
    payload = {"to": args.to, "text": args.message}
    if not args.execute:
        print(json.dumps({"status": "READY", "payload": payload}, ensure_ascii=False, indent=2))
        return 0

    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "x-send-api-secret": secret},
        method="POST",
    )
    try:
        with urlopen(request, timeout=args.timeout) as response:
            body, status = response.read().decode(errors="replace"), response.status
    except HTTPError as exc:
        body, status = exc.read().decode(errors="replace"), exc.code
    except URLError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 3
    print(json.dumps({"status": status, "response": body}, ensure_ascii=False, indent=2))
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
