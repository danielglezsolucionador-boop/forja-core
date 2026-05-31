from __future__ import annotations

import faulthandler
import os
import sys
import traceback


faulthandler.enable(all_threads=True)


def log(message: str) -> None:
    print(message, flush=True)


def main() -> int:
    log("BOOTSTRAP_STAGE_0_BEGIN")
    log(f"BOOTSTRAP_PYTHON={sys.version}")
    log(f"BOOTSTRAP_CWD={os.getcwd()}")
    log(f"BOOTSTRAP_SYS_PATH={sys.path}")
    log(f"BOOTSTRAP_PORT={os.getenv('PORT', '8100')}")
    log(f"BOOTSTRAP_APP_ENV={os.getenv('FORJA_APP_ENV', 'unset')}")
    log(f"BOOTSTRAP_DB_AUTO_MIGRATE={os.getenv('FORJA_DB_AUTO_MIGRATE', 'unset')}")
    log(f"BOOTSTRAP_DATABASE_URL_CONFIGURED={bool(os.getenv('FORJA_DATABASE_URL'))}")

    try:
        log("BOOTSTRAP_STAGE_1_IMPORT_UVICORN_BEGIN")
        import uvicorn

        log(f"BOOTSTRAP_STAGE_1_IMPORT_UVICORN_OK version={getattr(uvicorn, '__version__', 'unknown')}")

        log("BOOTSTRAP_STAGE_2_IMPORT_APP_MAIN_BEGIN")
        import app.main as main_module

        log(f"BOOTSTRAP_STAGE_2_IMPORT_APP_MAIN_OK app={type(main_module.app).__name__}")

        log("BOOTSTRAP_STAGE_3_OPENAPI_CHECK_BEGIN")
        routes_count = len(main_module.app.routes)
        log(f"BOOTSTRAP_STAGE_3_OPENAPI_CHECK_OK routes={routes_count}")

        port = int(os.getenv("PORT", "8100"))
        log("BOOTSTRAP_STAGE_4_UVICORN_RUN_BEGIN")
        uvicorn.run(
            main_module.app,
            host="0.0.0.0",
            port=port,
            log_level="debug",
            access_log=True,
        )
        log("BOOTSTRAP_STAGE_5_UVICORN_RUN_RETURNED")
        return 0
    except SystemExit as exc:
        log(f"BOOTSTRAP_SYSTEM_EXIT code={exc.code}")
        log(traceback.format_exc())
        raise
    except BaseException as exc:
        log(f"BOOTSTRAP_FATAL {exc.__class__.__name__}: {exc}")
        log(traceback.format_exc())
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
