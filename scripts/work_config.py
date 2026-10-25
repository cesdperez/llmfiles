"""Org-specific settings, kept out of the public repo in an untracked file.

Copy local.example/work.json to local/work.json and fill it in, or point
LLMFILES_WORK_CONFIG at another path.
"""

import json
import os
import sys
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "local" / "work.json"


def load(*required):
    path = Path(os.environ.get("LLMFILES_WORK_CONFIG", DEFAULT_PATH)).expanduser()
    try:
        config = json.loads(path.read_text())
    except FileNotFoundError:
        sys.exit(f"missing {path}. Copy local.example/work.json there and fill it in.")
    missing = [key for key in required if not config.get(key)]
    if missing:
        sys.exit(f"{path} lacks: {', '.join(missing)}")
    return config
