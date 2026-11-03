#!/usr/bin/env python3
"""Validates what the agent CLIs load from this repo, which a syntax linter cannot see:
frontmatter keys, Codex agent TOML, example JSON, and ~/llmfiles paths named in prose."""

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = {"opus", "sonnet", "fable", "haiku", "inherit"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
SKILL_DESCRIPTION_LIMIT = 1024
FRONTMATTER_YAMLLINT = "{extends: default, rules: {line-length: disable, document-start: disable}}"

errors = []


def tracked(*patterns):
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--", *patterns],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [ROOT / p for p in out.splitlines() if (ROOT / p).exists()]


def fail(path, message):
    errors.append(f"{path.relative_to(ROOT)}: {message}")


def frontmatter(path):
    lines = path.read_text().splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        fail(path, "missing YAML frontmatter")
        return None
    text = "\n".join(lines[1 : lines.index("---", 1)]) + "\n"
    lint = subprocess.run(
        ["yamllint", "-f", "parsable", "-d", FRONTMATTER_YAMLLINT, "-"],
        input=text, capture_output=True, text=True, check=False,
    )
    for issue in lint.stdout.splitlines():
        fail(path, f"frontmatter {issue.removeprefix('stdin:')}")
    return top_level_keys(text)


def top_level_keys(text):
    keys, current = {}, None
    for line in text.splitlines():
        match = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if match:
            current = match.group(1)
            keys[current] = match.group(2).strip()
        elif current and line.startswith((" ", "\t")):
            keys[current] = (keys[current] + " " + line.strip()).strip()
    return {k: v.strip("'\"") for k, v in keys.items()}


def require(path, keys, *names):
    for name in names:
        if not keys.get(name):
            fail(path, f"frontmatter needs a non-empty `{name}`")


def check_skills():
    for path in tracked("skills/*/SKILL.md", "codex/skills/*/SKILL.md"):
        keys = frontmatter(path)
        if keys is None:
            continue
        require(path, keys, "name", "description")
        if keys.get("name") and keys["name"] != path.parent.name:
            fail(path, f"name `{keys['name']}` must match its directory `{path.parent.name}`")
        if len(keys.get("description", "")) > SKILL_DESCRIPTION_LIMIT:
            fail(path, f"description is over {SKILL_DESCRIPTION_LIMIT} characters")


def check_agents():
    for path in tracked("agents/*.md"):
        keys = frontmatter(path)
        if keys is None:
            continue
        require(path, keys, "name", "description", "model", "effort")
        if keys.get("name") and keys["name"] != path.stem:
            fail(path, f"name `{keys['name']}` must match the file name `{path.stem}`")
        if keys.get("model") and keys["model"] not in MODELS:
            fail(path, f"model `{keys['model']}` is not an alias: {sorted(MODELS)}")
        if keys.get("effort") and keys["effort"] not in EFFORTS:
            fail(path, f"effort `{keys['effort']}` is not one of {sorted(EFFORTS)}")


def check_commands():
    for path in tracked("commands/*.md"):
        keys = frontmatter(path)
        if keys is not None:
            require(path, keys, "description")


def check_codex_agents():
    for path in tracked("codex/agents/*.toml"):
        try:
            agent = tomllib.loads(path.read_text())
        except tomllib.TOMLDecodeError as error:
            fail(path, f"invalid TOML: {error}")
            continue
        for key in ("name", "description", "model", "model_reasoning_effort", "developer_instructions"):
            if not agent.get(key):
                fail(path, f"needs a non-empty `{key}`")
        if agent.get("name") and agent["name"] != path.stem:
            fail(path, f"name `{agent['name']}` must match the file name `{path.stem}`")


def check_json():
    for path in tracked("*.json"):
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError as error:
            fail(path, f"invalid JSON: {error}")


def check_references():
    for path in tracked("*.md", "*.toml", "*.yaml", "*.py", "*.sh", "hooks/*"):
        text = path.read_text()
        # The match stops at `<` and `*`, so placeholders and globs check their parent directory.
        for ref in set(re.findall(r"~/llmfiles/([\w./-]+)", text)):
            ref = ref.rstrip(".")
            if ref.split("/")[0] == "local":  # gitignored, absent from a fresh clone
                continue
            if not (ROOT / ref).exists():
                fail(path, f"names ~/llmfiles/{ref}, which does not exist")
        if path.suffix != ".md":
            continue
        for link in set(re.findall(r"\]\(([^)\s]+)\)", text)):
            target = link.split("#")[0]
            if not target or re.match(r"^[a-z]+:|^<|^url$", target):
                continue
            if not (path.parent / target).exists():
                fail(path, f"links to {target}, which does not exist")


if __name__ == "__main__":
    check_skills()
    check_agents()
    check_commands()
    check_codex_agents()
    check_json()
    check_references()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)
