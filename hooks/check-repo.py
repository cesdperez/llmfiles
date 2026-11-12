#!/usr/bin/env python3
"""Validates what the agent CLIs load from this repo, which a syntax linter cannot see:
frontmatter keys, Codex agent TOML, opencode agents and config, example JSON, and ~/llmfiles
paths named in prose."""

import fnmatch
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = {"opus", "sonnet", "fable", "haiku", "inherit"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
OPENCODE_MODEL = re.compile(rf"^[\w-]+/[\w.-]+(#({'|'.join(sorted(EFFORTS | {'none'}))}))?$")
OPENCODE_MODES = {"subagent", "primary", "all"}
OPENCODE_ONLY_AGENTS = {"conductor", "ab-judge"}
# Only the conductor allows these again, so build, plan and general never pick one.
CONDUCTOR_ONLY_SUBAGENTS = ("builder-*", "ab-judge")
BUILDER_CONTRACT = "~/llmfiles/opencode/builder-contract.md"
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


def check_opencode_agents():
    claude_agents = {path.stem.lower() for path in tracked("agents/*.md")}
    for path in tracked("opencode/agents/*.md"):
        keys = frontmatter(path)
        if keys is None:
            continue
        require(path, keys, "description", "mode", "model")
        # Commands name agents by their Claude name, so each wrapper needs a Claude counterpart.
        if path.stem.lower() not in claude_agents and not opencode_only(path.stem):
            fail(path, f"has no Claude agent `agents/{path.stem}.md` of the same name")
        if keys.get("mode") and keys["mode"] not in OPENCODE_MODES:
            fail(path, f"mode `{keys['mode']}` is not one of {sorted(OPENCODE_MODES)}")
        if keys.get("model") and not OPENCODE_MODEL.match(keys["model"]):
            fail(path, f"model `{keys['model']}` is not provider/model#variant")


def opencode_only(name):
    return name in OPENCODE_ONLY_AGENTS or name.startswith("builder-")


def check_builders():
    builders = {path.stem: path for path in tracked("opencode/agents/builder-*.md")}
    for path in builders.values():
        if BUILDER_CONTRACT not in path.read_text():
            fail(path, f"must tell the builder to read {BUILDER_CONTRACT}")
    routing = ROOT / "opencode" / "builders.md"
    text = "".join(path.read_text() for path in tracked("opencode/builders.md"))
    routed = set(re.findall(r"`(builder-[\w-]+)`", text))
    for name in sorted(builders.keys() - routed):
        fail(routing, f"does not route to `{name}`")
    agents = {path.stem for path in tracked("opencode/agents/*.md")}
    escalation = text.split("## Escalation", 1)[1].split("\n## ", 1)[0] if "## Escalation" in text else ""
    named = routed | set(re.findall(r"`([a-z][a-z-]*)`", escalation))
    for name in sorted(named - agents):
        fail(routing, f"names `{name}`, which has no opencode/agents/{name}.md")


def check_conductor_subagents():
    path = ROOT / "opencode" / "agents" / "conductor.md"
    if not tracked("opencode/agents/conductor.md"):
        return
    agents = {agent.stem for agent in tracked("opencode/agents/*.md")}
    allowed = re.findall(
        r"action: subagent\s+resource: \"?([\w*-]+)\"?\s+effect: allow", path.read_text(),
    )
    for pattern in allowed:
        if not fnmatch.filter(agents, pattern):
            fail(path, f"allows subagent `{pattern}`, which matches no opencode/agents/*.md")


def check_opencode_config():
    path = ROOT / "opencode" / "opencode.json"
    try:
        config = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(path, f"unreadable: {error}")
        return
    if not isinstance(config, dict):
        fail(path, "must be a JSON object")
        return
    model = config.get("model")
    if not isinstance(model, str) or not OPENCODE_MODEL.match(model):
        fail(path, "needs a `model` in provider/model#variant form")
    instructions = config.get("instructions")
    if not isinstance(instructions, list) or not all(isinstance(i, str) for i in instructions):
        fail(path, "`instructions` must be a list of paths")
    check_adapter_skill_denies(path, config.get("permissions"))
    check_builder_deny(path, config.get("permissions"))


def check_adapter_skill_denies(path, permissions):
    # The Codex adapters in ~/.agents/skills would shadow the linked commands in opencode.
    rules = permissions if isinstance(permissions, list) else []
    denied = {
        rule.get("resource") for rule in rules
        if isinstance(rule, dict) and rule.get("action") == "skill" and rule.get("effect") == "deny"
    }
    adapters = {skill.parent.name for skill in tracked("codex/skills/*/SKILL.md")}
    for name in sorted(adapters - denied):
        fail(path, f"needs a `skill` deny rule for the Codex adapter `{name}`")
    for name in sorted(denied - adapters):
        fail(path, f"denies skill `{name}`, which is not a Codex adapter in codex/skills/")


def check_builder_deny(path, permissions):
    for resource in CONDUCTOR_ONLY_SUBAGENTS:
        rule = {"action": "subagent", "resource": resource, "effect": "deny"}
        if not isinstance(permissions, list) or rule not in permissions:
            fail(path, f"needs the global rule {json.dumps(rule)}")


def check_json():
    for path in tracked("*.json"):
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError as error:
            fail(path, f"invalid JSON: {error}")


def check_references():
    for path in tracked("*.md", "*.toml", "*.yaml", "*.json", "*.py", "*.sh", "hooks/*"):
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
    check_opencode_agents()
    check_builders()
    check_conductor_subagents()
    check_opencode_config()
    check_json()
    check_references()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)
