#!/usr/bin/env python3
"""发现巡火运行配置并执行无副作用检查。支持 --profile 参数实现通用化。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"\'')
    return values


def load_profile(profile_path: Path | None) -> dict | None:
    if profile_path is None:
        return None
    return json.loads(profile_path.read_text(encoding="utf-8"))


def source_default(source: str, name: str) -> str:
    match = re.search(
        rf"const\s+{re.escape(name)}\s*=\s*process\.env\.{re.escape(name)}\s*(?:\|\||\?\?)\s*(['\"])(.*?)\1",
        source,
    )
    return match.group(2) if match else ""


def extract_points(source: str, zone_var_name: str = "") -> list[str]:
    if zone_var_name:
        pattern = rf"const\s+{re.escape(zone_var_name)}\s*=\s*[\[\{{](.*?)[\]\}}];"
    else:
        pattern = r"const\s+\w*(?:ZONES|FIRE_PATROL_ZONES)\s*=\s*[\[\{](.*?)[\]\}];"
    match = re.search(pattern, source, re.S)
    if not match:
        return []
    points: list[str] = []
    for point in re.findall(r"['\"]([A-Z][A-Z0-9]{0,3})['\"]", match.group(1), re.I):
        point = point.upper()
        if point not in points:
            points.append(point)
    return points


def discover(bot_root: Path, profile: dict | None = None) -> dict[str, object]:
    constants_path = bot_root / "group_constants.js"
    profile_path = bot_root / "group_process/fire_patrol_process.js"
    missing = [str(path) for path in (constants_path, profile_path) if not path.is_file()]
    if missing:
        raise RuntimeError("缺少运行文件：" + "、".join(missing))

    constants = constants_path.read_text(encoding="utf-8")
    fire_profile = profile_path.read_text(encoding="utf-8")
    env = load_env(bot_root / ".env")

    impl = (profile or {}).get("implementation", {})
    env_vars = impl.get("runtime_env_vars", {})
    prod_env_name = env_vars.get("production_group", "GROUP_FIREPATROL_BLY")
    test_env_name = env_vars.get("test_group", "GROUP_FIREPATROL_BLY_TEST")
    zone_var = env_vars.get("zone_variable", "")

    production = env.get(prod_env_name, source_default(constants, prod_env_name))
    test = env.get(test_env_name, source_default(constants, test_env_name))
    start = re.search(r"operationalStartHour\s*:\s*(\d+)", fire_profile)
    return {
        "production_group": production,
        "test_group": test,
        "test_group_safe": bool(test) and test.endswith("@g.us") and test != production,
        "operational_start_hour": int(start.group(1)) if start else None,
        "valid_points": extract_points(fire_profile, zone_var),
        "schedules": [item.strip() for item in re.findall(r"schedule\s*:\s*\[([^\]]+)\]", fire_profile)],
        "data_file": str(bot_root / "data/fire_patrol.json"),
    }


def require_test_group(target: str, bot_root: Path, profile: dict | None = None) -> None:
    row = discover(bot_root, profile)
    if not row["test_group_safe"] or target != row["test_group"]:
        raise RuntimeError(f"拒绝非巡火测试群：{target}")
    if profile:
        production_groups = profile.get("routing", {}).get("production_groups", [])
        if target in production_groups:
            raise RuntimeError(f"拒绝生产群：{target}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bot-root", type=Path, default=Path("/root/whatsapp-bot"))
    parser.add_argument("--sender-root", type=Path, default=Path("/home/claw/self-testing-bot-run"))
    parser.add_argument("--profile", type=Path, default=None, help="项目配置文件路径")
    parser.add_argument("--target")
    args = parser.parse_args()

    profile = load_profile(args.profile)

    try:
        row = discover(args.bot_root, profile)
    except (OSError, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2

    env_path = args.sender_root / ".env"
    env = load_env(env_path)
    checks = {
        "test_group_safe": row["test_group_safe"],
        "target_allowed": not args.target or args.target == row["test_group"],
        "operational_start_hour": row["operational_start_hour"] is not None,
        "valid_points": bool(row["valid_points"]),
        "data_file": Path(str(row["data_file"])).is_file(),
        "sender_env": env_path.is_file(),
        "send_api_secret": bool(env.get("SEND_API_SECRET")),
    }
    ready = all(checks.values())
    print(json.dumps({"status": "READY" if ready else "BLOCKED", "checks": checks, "runtime": row}, ensure_ascii=False, indent=2))
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
