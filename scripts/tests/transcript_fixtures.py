"""Small made-up transcripts in the layout Claude Code writes under ~/.claude/projects."""

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc).timestamp()


def load_script(filename):
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_")[:-3], SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iso(minutes_ago):
    return datetime.fromtimestamp(NOW - minutes_ago * 60, timezone.utc).isoformat().replace("+00:00", "Z")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    os.utime(path, (NOW, NOW))


def user(text, minutes_ago, **extra):
    return {"type": "user", "timestamp": iso(minutes_ago), "message": {"role": "user", "content": text}, **extra}


def assistant(msg_id, minutes_ago, model="claude-opus-5-5", out=100, inp=10, cache_read=0, cache_write=0, content=None):
    return {
        "type": "assistant", "timestamp": iso(minutes_ago),
        "message": {
            "id": msg_id, "model": model, "role": "assistant", "content": content or [],
            "usage": {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cache_read,
                      "cache_creation_input_tokens": cache_write},
        },
    }


def tool_use(tool_id, name, **inp):
    return {"type": "tool_use", "id": tool_id, "name": name, "input": inp}


def tool_result(tool_id, text, minutes_ago, is_error=False):
    block = {"type": "tool_result", "tool_use_id": tool_id, "content": text, "is_error": is_error}
    return {"type": "user", "timestamp": iso(minutes_ago), "message": {"role": "user", "content": [block]}}


def slash(name, minutes_ago):
    return user(f"<command-name>/{name}</command-name>\n<command-args></command-args>", minutes_ago)


def subagent(root, project, session, agent_id, agent_type, rows, description="task"):
    base = root / project / session / "subagents" / f"agent-{agent_id}"
    write_jsonl(base.with_suffix(".jsonl"), rows)
    base.with_suffix(".meta.json").write_text(json.dumps({"agentType": agent_type, "description": description}))
