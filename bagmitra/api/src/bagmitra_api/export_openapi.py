"""Write the OpenAPI schema (source of truth for the Dart client).

Usage: python -m bagmitra_api.export_openapi [output-path]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from bagmitra_api.core.settings import Settings
from bagmitra_api.main import create_app


def render_openapi(settings: Settings) -> str:
    spec = create_app(settings).openapi()
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else Path("../docs/api/openapi.json")
    out.write_text(render_openapi(Settings(environment="test")), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv)
