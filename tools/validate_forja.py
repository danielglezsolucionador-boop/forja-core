from __future__ import annotations

from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "phases/phase_1_forja_foundation",
    "phases/phase_2_reusable_module_system",
    "phases/phase_3_app_factory_engine",
    "phases/phase_4_ecosystem_integration",
    "phases/phase_5_operational_automation",
    "apps/backend/app/main.py",
    "apps/backend/app/core/config.py",
    "apps/frontend/package.json",
    "packages/contracts/forja.openapi.notes.md",
]


def main() -> int:
    checks = [{"path": path, "exists": (ROOT / path).exists()} for path in REQUIRED_PATHS]
    result = {
        "status": "ok" if all(item["exists"] for item in checks) else "failed",
        "checks": checks,
        "rules": {
            "local_only": True,
            "no_cloud": True,
            "no_push_required": True,
            "zero_write_policy": True,
            "human_in_the_loop": True,
        },
    }
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
