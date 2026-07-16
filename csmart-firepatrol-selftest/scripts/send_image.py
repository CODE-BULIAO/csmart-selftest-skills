#!/usr/bin/env python3
"""仅向巡火测试群发送现有图片；默认只检查。支持 --profile 参数。"""

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
    parser.add_argument("--image", type=Path, required=True)
    caption = parser.add_mutually_exclusive_group(required=True)
    caption.add_argument("--caption")
    caption.add_argument("--caption-file", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    profile = load_profile(args.profile)
    image = args.image.expanduser().resolve()
    try:
        require_test_group(args.to, args.bot_root, profile)
        if not image.is_file():
            raise RuntimeError(f"图片不存在：{image}")
        text = args.caption if args.caption is not None else args.caption_file.read_text(encoding="utf-8")
        if not text.strip():
            raise RuntimeError("caption 不能为空")
        env = load_env(args.root / ".env")
        secret = env.get("SEND_API_SECRET", "")
        if not secret:
            raise RuntimeError("缺少 SEND_API_SECRET")
    except (OSError, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2

    url = args.url or f"http://127.0.0.1:{env.get('SEND_API_PORT', '13081')}/send-image"
    payload = {"to": args.to, "imagePath": str(image), "imageName": image.name, "caption": text}
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
