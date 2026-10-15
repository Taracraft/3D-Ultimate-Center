"""Command-line entry point for the standalone Studio HTTP API server."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from aiohttp import web

from core.bootstrap import build_runtime
from core.paths import StudioPaths
from core.version import STUDIO_VERSION

from .http_server import create_http_application


def _default_runtime_root() -> Path:
    configured = os.environ.get("PCC_STUDIO_RUNTIME_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[1] / ".runtime" / "3D-Studio"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ultimate 3D Printing Studio standalone HTTP API",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("PCC_STUDIO_HTTP_HOST", "127.0.0.1"),
        help="HTTP bind address",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PCC_STUDIO_HTTP_PORT", "8768")),
        help="HTTP listen port",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_default_runtime_root(),
        help="Studio runtime root; production target is /srv/3D-Studio",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("PCC_STUDIO_LOG_LEVEL", "INFO"),
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Python log level",
    )
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    runtime_root = arguments.root.expanduser().resolve()

    logging.basicConfig(
        level=getattr(logging, arguments.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )

    print()
    print("=" * 72)
    print("Ultimate 3D Printing Studio - Standalone API")
    print("=" * 72)
    print(f"Version:      {STUDIO_VERSION}")
    print(f"Runtime root: {runtime_root}")
    print(f"HTTP:         http://{arguments.host}:{arguments.port}")
    print("API base:     /api/ultimate_3d_studio/v1")
    print()

    runtime = build_runtime(StudioPaths(runtime_root))
    application = create_http_application(runtime, close_runtime=True)

    web.run_app(
        application,
        host=arguments.host,
        port=arguments.port,
        print=None,
        access_log=logging.getLogger("aiohttp.access"),
    )

    print()
    print("API-Server wurde beendet.")
    print("Terminal bleibt offen.")


if __name__ == "__main__":
    main()
