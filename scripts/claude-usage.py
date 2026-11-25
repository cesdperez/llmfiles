#!/usr/bin/env python3
"""Spend, context, cache, tool and parallelism figures from Claude Code transcripts.

Usage: claude-usage.py [--days 14] [--root ~/.claude/projects]

Emits JSON on stdout. Dollar figures are list-price equivalents from PRICES, not what a
subscription bills. A session belongs to its first slash command, and its subagents' spend
counts toward it. `headline` holds the flat metrics /tunesetup compares run to run.
"""

import argparse
import bisect
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcripts as tr  # noqa: E402

PRICES_CHECKED = "2026-11-25"
# $/MTok: input, output, cache read, 5m cache write, 1h cache write.
PRICES = {
    "claude-fable-5-2": (8.0, 40.0, 0.20, 10.0, 16.0),
    "claude-fable-5-1": (10.0, 50.0, 0.25, 12.5, 20.0),
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0, 8.0),
    "claude-opus-5": (5.0, 25.0, 0.50, 6.25, 10.0),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10, 2.5, 4.0),
    "claude-sonnet-5": (2.0, 10.0, 0.20, 2.5, 4.0),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125, 0.20),
}
HAIKU_LONG = (0.50, 2.50, 0.05, 0.625, 1.0)  # Haiku 5.5 prompts over 100K tokens
FAST_MULTIPLIER = 2.0
MEDIA_TOKENS = 1600  # estimate per image or PDF page; the real count depends on pixel size
CACHE_MISS_MIN_TOKENS = 2000
IDLE_GAP_BUCKETS = ("<5m", "5m-1h", ">1h")
SKIP_TYPES = {"queue-operation", "atis-latch", "tools-used", "ai-title", "last-prompt", "pr-link", "mode",
              "api-request-blob", "api-request-shape"}
NOTIFICATION_ID_RE = re.compile(r"<tool-use-id>([^<]+)</tool-use-id>")
HANDBACK_RE = re.compile(r'<agent-message from="([^"]+)">')


def price_for(model, ctx):
    if model == "claude-haiku-5-5" and ctx > 100_000:
        return HAIKU_LONG
    return PRICES.get(model)


def cost_of(req):
    p = price_for(req["model"], req["ctx"])
    if not p:
        return None
    mult = FAST_MULTIPLIER if req.get("speed") == "fast" else 1.0
    pin, pout, pread, p5, p1 = p
    return mult * (req["inp"] * pin + req["out"] * pout + req["cr"] * pread + req["cw5"] * p5 + req["cw1"] * p1) / 1e6


def tool_key(name, inp):
    if not isinstance(inp, dict):
        return name
    if name == "Bash":
        return "Bash: " + tr.bash_head(inp.get("command", ""))
    if name == "Skill":
        return "Skill: " + str(inp.get("skill"))
    if name in tr.AGENT_TOOLS:
        return "Agent: " + str(inp.get("subagent_type") or "general-purpose")
    return name


def result_size(content):
    """Text bytes of a tool result, and its image or document blocks, which bill by size, not bytes."""
    if isinstance(content, str):
        return len(content.encode()), 0
    size, media = 0, 0
    for b in content if isinstance(content, list) else []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            size += len(b.get("text", "").encode())
        elif b.get("type") in ("image", "document"):
            media += 1
        else:
            size += len(json.dumps(b))
    return size, media


def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))]


def med(xs):
    return statistics.median(xs) if xs else None


def merged(intervals):
    out = []
    for a, b in sorted(i for i in intervals if i[1] > i[0]):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def union_len(intervals):
    return sum(b - a for a, b in merged(intervals))


def uncovered_len(intervals, cover):
    """Length of the union of intervals that no cover interval overlaps."""
    total = 0.0
    cover = merged(cover)
    for a, b in merged(intervals):
        cur = a
        for ca, cb in cover:
            if cb <= cur or ca >= b:
                continue
            total += max(0, ca - cur)
            cur = max(cur, cb)
            if cur >= b:
                break
        total += max(0, b - cur)
    return total


def usage_record(d, message, ts, path):
    u = message["usage"]
    cc = u.get("cache_creation") or {}
    cw = u.get("cache_creation_input_tokens") or 0
    cw1 = cc.get("ephemeral_1h_input_tokens") or 0
    cw5 = cc.get("ephemeral_5m_input_tokens") or 0
    if cw and not (cw1 or cw5):
        cw5 = cw
    rec = {
        "id": message["id"], "model": message.get("model"), "ts": ts, "ref": d.get("requestRef"),
        "inp": u.get("input_tokens") or 0, "cr": u.get("cache_read_input_tokens") or 0, "cw5": cw5, "cw1": cw1,
        "out": u.get("output_tokens") or 0,
        "think": (u.get("output_tokens_details") or {}).get("thinking_tokens") or 0,
        "speed": u.get("speed"), "effort": d.get("effort"), "pte": d.get("perTurnEffort"),
        "skill": d.get("attributionSkill"), "path": path,
    }
    rec["ctx"] = rec["inp"] + rec["cr"] + rec["cw5"] + rec["cw1"]
    return rec


def new_transcript(path, kind, root):
    project, session = tr.session_of(path, root)
    t = {
        "path": path, "project": project, "kind": kind, "session": session,
        "agent_type": None, "meta": {}, "first_ts": None, "last_ts": None, "commands": [], "first_user": None,
        "tool_uses": {}, "tool_results": [], "compactions": 0, "req_start": {}, "api_params": [],
        "notif": {}, "handback": {}, "cost_state": None, "entry": None, "dispatched": False,
        "file_first_ts": None, "last_usage_pos": -1,
    }
    if kind == "sub":
        t["meta"] = tr.subagent_meta(path)
        t["agent_type"] = tr.subagent_type(path, t["meta"])
    return t


def note_max(store, key, value):
    store[key] = max(store.get(key, 0), value)


def scan(path, kind, root, cutoff, msgs, known):
    """Stream one transcript, appending each usage record to msgs[message id]."""
    t = new_transcript(path, kind, root)
    for pos, d in enumerate(tr.records(path)):
        typ = d.get("type")
        if typ == "attachment":
            at = d.get("attachment") or {}
            prompt = at.get("prompt") if at.get("type") == "queued_command" else None
            if isinstance(prompt, str) and "<task-notification>" in prompt and "<result>" in prompt:
                m = NOTIFICATION_ID_RE.search(prompt)
                if m:
                    note_max(t["notif"], m.group(1), len(prompt.encode()))
            continue
        if typ == "cost-state":
            t["cost_state"] = {"cost": d.get("totalCostUSD"), "start": (d.get("startTime") or 0) / 1000, "pos": pos}
            continue
        if typ in SKIP_TYPES:
            continue
        ts = tr.parse_ts(d.get("timestamp"))
        if ts is not None and t["file_first_ts"] is None:
            t["file_first_ts"] = ts
        if typ == "assistant" and (d.get("message") or {}).get("usage"):
            t["last_usage_pos"] = pos
        if ts is None or ts < cutoff:
            continue
        t["first_ts"] = ts if t["first_ts"] is None else min(t["first_ts"], ts)
        t["last_ts"] = ts if t["last_ts"] is None else max(t["last_ts"], ts)
        t["entry"] = t["entry"] or d.get("entrypoint")
        if kind == "main":
            t["commands"] += [(ts, c) for c in tr.commands_in(d, known)]
        if typ == "api-request":
            scan_api_request(t, d, ts)
        elif typ == "system" and d.get("subtype") == "compact_boundary":
            t["compactions"] += 1
        elif typ == "assistant":
            scan_assistant(t, d, ts, msgs)
        elif typ == "user":
            scan_user(t, d, ts)
    return t


def scan_api_request(t, d, ts):
    t["req_start"][d.get("id")] = ts
    p = d.get("params") or {}
    ttls = [c.get("value", {}).get("ttl", "5m") for c in d.get("cacheControl") or []]
    t["api_params"].append({
        "model": p.get("model"), "effort": (p.get("output_config") or {}).get("effort"),
        "thinking": (p.get("thinking") or {}).get("type"), "ttl": ",".join(sorted(set(ttls))),
    })


def scan_assistant(t, d, ts, msgs):
    m = d.get("message") or {}
    if m.get("usage") and m.get("id") and m.get("model") != "<synthetic>":
        msgs[m["id"]].append(usage_record(d, m, ts, t["path"]))
    for b in m.get("content") or []:
        if not (isinstance(b, dict) and b.get("type") == "tool_use"):
            continue
        inp = b.get("input") if isinstance(b.get("input"), dict) else {}
        name = b.get("name")
        detail = inp.get("command") or inp.get("file_path") or inp.get("pattern") or inp.get("url") or ""
        t["tool_uses"][b.get("id")] = {
            "name": name, "key": tool_key(name, inp), "ts": ts, "detail": str(detail)[:200],
            "file": inp.get("file_path"), "full_cmd": inp.get("command") if name == "Bash" else None,
        }


def scan_user(t, d, ts):
    content = (d.get("message") or {}).get("content")
    txt = tr.text_of(content)
    if "<task-notification>" in txt[:200] and "<result>" in txt:
        m = NOTIFICATION_ID_RE.search(txt)
        if m:
            note_max(t["notif"], m.group(1), len(txt.encode()))
    if tr.is_dispatched(txt):
        t["dispatched"] = True
    if "<agent-message from=" in txt[:300]:
        for m in HANDBACK_RE.finditer(txt):
            note_max(t["handback"], m.group(1), len(txt.encode()))
    if txt and not d.get("isMeta") and t["first_user"] is None and "tool_result" not in str(content)[:50]:
        t["first_user"] = txt[:3000]
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                size, media = result_size(b.get("content"))
                t["tool_results"].append((b.get("tool_use_id"), size, media, ts))


def dedupe(msgs, T):
    """One request per message id: streaming repeats an id within a file, and a resumed or forked
    session copies earlier messages into a new file, which the earliest file keeps."""
    reqs = defaultdict(list)
    cross_file = 0
    for recs in msgs.values():
        paths = {r["path"] for r in recs}
        if len(paths) > 1:
            cross_file += 1
            owner = min(paths, key=lambda p: (T[p]["first_ts"] or float("inf"), p))
        else:
            owner = recs[0]["path"]
        final = dict(max((r for r in recs if r["path"] == owner), key=lambda r: (r["out"], r["ts"])))
        final["cost"] = cost_of(final)
        final["start"] = T[owner]["req_start"].get(final["ref"])
        reqs[owner].append(final)
    for rs in reqs.values():
        rs.sort(key=lambda r: r["start"] or r["ts"])
    return reqs, cross_file


def analyze(root, days, now=None, known=None):
    known = tr.repo_commands() if known is None else known
    cutoff = tr.cutoff_for(days, now)
    msgs = defaultdict(list)
    T = {path: scan(path, kind, root, cutoff, msgs, known) for path, kind in tr.transcript_files(root, cutoff)}
    reqs, cross_file = dedupe(msgs, T)
    subs_of, orphans = defaultdict(list), 0
    for p, t in T.items():
        if t["kind"] == "sub":
            mp = tr.main_path_of(p, root)
            if mp in T:
                subs_of[mp].append(p)
            else:
                orphans += 1
    ctx = {"T": T, "reqs": reqs, "subs_of": subs_of, "cutoff": cutoff, "known": known}
    unpriced = Counter(r["model"] for rs in reqs.values() for r in rs if r["cost"] is None)
    out = {
        "generated": datetime.now(timezone.utc).isoformat(), "days": days, "files": len(T),
        "prices_checked": PRICES_CHECKED, "unpriced_requests": dict(unpriced),
        "cross_file_duplicate_message_ids": cross_file, "orphan_subagent_files": orphans,
    }
    out.update(totals(ctx))
    out.update(agents(ctx))
    sessions = session_rows(ctx)
    out.update(commands_section(ctx, sessions))
    out.update(cache_section(ctx, sessions))
    out["context"] = context_section(ctx, sessions)
    out.update(effort_section(ctx))
    out["tools"] = tools_section(ctx)
    out["parallelism"] = parallelism_section(ctx, sessions)
    out["headline"] = headline(out)
    return out


def tcost(ctx, path):
    return sum(r["cost"] or 0 for r in ctx["reqs"].get(path, []))


def totals(ctx):
    T, reqs = ctx["T"], ctx["reqs"]
    by_model = defaultdict(Counter)
    for rs in reqs.values():
        for r in rs:
            c = by_model[r["model"]]
            c["requests"] += 1
            for k in ("inp", "cw5", "cw1", "cr", "out", "think"):
                c[k] += r[k]
            c["cost"] += r["cost"] or 0
    category = Counter()
    for m, c in by_model.items():
        p = PRICES.get(m)
        if p:
            for i, name in enumerate(("inp", "out", "cr", "cw5", "cw1")):
                category[("input", "output", "cache_read", "cache_write_5m", "cache_write_1h")[i]] += c[name] * p[i] / 1e6
    by_ctx = defaultdict(Counter)
    for p, rs in reqs.items():
        k = T[p]["agent_type"] or "main"
        for r in rs:
            by_ctx[k]["all"] += r["cost"] or 0
            by_ctx[k]["over100k"] += (r["cost"] or 0) if r["ctx"] > 100_000 else 0
            by_ctx[k]["over200k"] += (r["cost"] or 0) if r["ctx"] > 200_000 else 0
    out_tokens = sum(c["out"] for c in by_model.values())
    think = sum(c["think"] for c in by_model.values())
    return {
        "total_cost": sum(c["cost"] for c in by_model.values()),
        "main_cost": sum(tcost(ctx, p) for p, t in T.items() if t["kind"] == "main"),
        "sub_cost": sum(tcost(ctx, p) for p, t in T.items() if t["kind"] == "sub"),
        "by_model": {m: dict(c) for m, c in by_model.items()},
        "cost_by_category": dict(category),
        "cost_by_ctx_and_type": {k: dict(v) for k, v in by_ctx.items()},
        "thinking": {"output": out_tokens, "thinking": think, "share": think / max(1, out_tokens)},
    }


def report_sizes(ctx):
    """Bytes of each subagent's report, from its Agent result, task notification or handback."""
    by_tool_use, by_agent = {}, {}
    for t in ctx["T"].values():
        tu = t["tool_uses"]
        for tid, size, _, _ in t["tool_results"]:
            if tid in tu and tu[tid]["name"] in tr.AGENT_TOOLS:
                note_max(by_tool_use, tid, size)
        for tid, size in t["notif"].items():
            if tid in tu and tu[tid]["name"] in tr.AGENT_TOOLS:
                note_max(by_tool_use, tid, size)
        for aid, size in t["handback"].items():
            note_max(by_agent, aid, size)
    return by_tool_use, by_agent


def agents(ctx):
    T, reqs = ctx["T"], ctx["reqs"]
    by_tool_use, by_agent = report_sizes(ctx)
    stats = defaultdict(lambda: defaultdict(list))
    runs = []
    for p, t in T.items():
        rs = reqs.get(p)
        if t["kind"] != "sub" or not rs:
            continue
        aid = os.path.basename(p)[:-len(".jsonl")].replace("agent-", "")
        sizes = [x for x in (by_tool_use.get(t["meta"].get("toolUseId")), by_agent.get(aid)) if x is not None]
        run = {
            "type": t["agent_type"], "requests": len(rs), "cost": tcost(ctx, p),
            "dur": (t["last_ts"] - t["first_ts"]) if t["first_ts"] else 0,
            "tokens": sum(r["ctx"] + r["out"] for r in rs), "first_cost": rs[0]["cost"] or 0,
            "end_ctx": rs[-1]["ctx"], "cold_write": rs[0]["cw5"] + rs[0]["cw1"],
            "report_bytes": max(sizes) if sizes else None, "desc": t["meta"].get("description"),
            "models": Counter(r["model"] for r in rs),
        }
        runs.append(run)
        s = stats[run["type"]]
        for k in ("tokens", "cost", "end_ctx", "requests", "dur", "cold_write"):
            s[k].append(run[k])
        if run["report_bytes"] is not None:
            s["report_bytes"].append(run["report_bytes"])
        s["models"].append(run["models"])
    out = {}
    for k, s in stats.items():
        reports = s["report_bytes"]
        out[k] = {
            "runs": len(s["cost"]), "cost": sum(s["cost"]), "median_tokens": med(s["tokens"]),
            "p90_tokens": pct(s["tokens"], .9), "median_end_ctx": med(s["end_ctx"]),
            "median_requests": med(s["requests"]), "median_dur_min": (med(s["dur"]) or 0) / 60,
            "median_cold_write": med(s["cold_write"]), "median_report_bytes": med(reports),
            "p90_report_bytes": pct(reports, .9), "max_report_bytes": max(reports) if reports else None,
            "models": dict(sum(s["models"], Counter())),
        }
    tiny = [r for r in runs if r["requests"] <= 3]
    biggest = sorted((r for r in runs if r["report_bytes"]), key=lambda r: -r["report_bytes"])[:10]
    return {
        "agents": out,
        "tiny_subagent_runs": {"count": len(tiny), "cost": sum(r["cost"] for r in tiny),
                               "by_type": dict(Counter(r["type"] for r in tiny))},
        "cold_start_cost": sum(r["first_cost"] for r in runs),
        "largest_subagent_reports": [{k: r[k] for k in ("type", "report_bytes", "desc", "cost")} for r in biggest],
    }


def final_cost_state(t, cutoff):
    """Claude Code's own total for a session, when it covers exactly what this script counted.

    A continued or resumed file carries the earlier session's spend, and some files keep one early
    record that is never updated, so only a record started in the period, before the file's first
    record, with no usage after it, is comparable."""
    cs = t["cost_state"]
    if not cs or cs["cost"] is None or t["file_first_ts"] is None:
        return None
    if cs["start"] < cutoff or cs["start"] > t["file_first_ts"] or t["last_usage_pos"] > cs["pos"]:
        return None
    return cs["cost"]


def session_rows(ctx):
    T, reqs, subs_of = ctx["T"], ctx["reqs"], ctx["subs_of"]
    rows = []
    for p, t in T.items():
        if t["kind"] != "main" or not t["first_ts"]:
            continue
        subs = subs_of.get(p, [])
        cost = tcost(ctx, p) + sum(tcost(ctx, s) for s in subs)
        if cost == 0 and not reqs.get(p):
            continue
        cmds = [c for _, c in sorted(t["commands"])]
        primary = cmds[0] if cmds else "(none)"
        if t["dispatched"]:
            primary += "[fleet-worker]"
        rs = reqs.get(p, [])
        all_rs = rs + [r for s in subs for r in reqs.get(s, [])]
        last = max([t["last_ts"]] + [T[s]["last_ts"] for s in subs if T[s]["last_ts"]])
        rows.append({
            "path": p, "project": tr.project_label(t["project"]), "session": t["session"], "commands": cmds,
            "primary": primary, "cost": cost, "main_cost": tcost(ctx, p), "sub_cost": cost - tcost(ctx, p),
            "n_subs": len(subs), "dur_min": (last - t["first_ts"]) / 60,
            "peak_ctx": max((r["ctx"] for r in rs), default=0), "compactions": t["compactions"],
            "cr": sum(r["cr"] for r in all_rs), "cw": sum(r["cw5"] + r["cw1"] for r in all_rs),
            "first_user": (t["first_user"] or "")[:160], "entry": t["entry"],
            "cost_state": final_cost_state(t, ctx["cutoff"]),
            "first_ts": t["first_ts"], "requests": len(rs),
            "cost_over_200k": sum(r["cost"] or 0 for r in rs if r["ctx"] > 200_000),
        })
    rows.sort(key=lambda s: -s["cost"])
    return rows


def commands_section(ctx, sessions):
    by_cmd = defaultdict(list)
    for s in sessions:
        by_cmd[s["primary"]].append(s)
    invocations = Counter(c for s in sessions for c in s["commands"])
    commands = {}
    for k, ss in sorted(by_cmd.items(), key=lambda kv: -sum(s["cost"] for s in kv[1])):
        cost = sum(s["cost"] for s in ss)
        commands[k] = {
            "sessions": len(ss), "total_cost": cost, "median_cost": med([s["cost"] for s in ss]),
            "p90_cost": pct([s["cost"] for s in ss], .9), "median_dur_min": med([s["dur_min"] for s in ss]),
            "cache_read_per_write": sum(s["cr"] for s in ss) / max(1, sum(s["cw"] for s in ss)),
            "sub_share": sum(s["sub_cost"] for s in ss) / max(1e-9, cost),
        }
    full = [s for s in sessions if s["cost_state"] is not None]
    none = [s for s in sessions if s["primary"] == "(none)"]
    skill_cost = Counter()
    for rs in ctx["reqs"].values():
        for r in rs:
            skill_cost[r["skill"] or "(none)"] += r["cost"] or 0
    keys = ("project", "session", "primary", "commands", "cost", "main_cost", "sub_cost", "n_subs", "dur_min",
            "peak_ctx", "compactions", "requests")
    return {
        "n_main_sessions": len(sessions),
        "commands": commands,
        "command_invocations_all": dict(invocations),
        "top_sessions": [{k: s[k] for k in keys} for s in sessions[:15]],
        "cost_by_attribution_skill": dict(skill_cost.most_common(25)),
        "cost_state_check": {"sessions": len(full), "computed": sum(s["cost"] for s in full),
                             "claude_code": sum(s["cost_state"] for s in full)},
        "no_command_sessions": {
            "by_entry": dict(Counter(s["entry"] for s in none)),
            "under_1usd": sum(1 for s in none if s["cost"] < 1),
            "top": [{k: s[k] for k in ("project", "cost", "dur_min", "n_subs", "first_user")} for s in none[:12]],
        },
    }


def cache_section(ctx, sessions):
    T, reqs = ctx["T"], ctx["reqs"]
    all_rs = [r for rs in reqs.values() for r in rs]
    read = sum(r["cr"] for r in all_rs)
    write = sum(r["cw5"] + r["cw1"] for r in all_rs)
    miss, miss_by_kind = defaultdict(Counter), defaultdict(Counter)
    for p, rs in reqs.items():
        prev = {}
        for r in rs:
            before, prev[r["model"]] = prev.get(r["model"]), r
            pp = price_for(r["model"], r["ctx"])
            if not pp:
                continue
            if not before:
                miss["first_request"]["n"] += 1
                miss["first_request"]["tokens"] += r["cw5"] + r["cw1"]
                miss["first_request"]["cost"] += (r["cw5"] * pp[3] + r["cw1"] * pp[4]) / 1e6
                continue
            gap = (r["start"] or r["ts"]) - (before["start"] or before["ts"])
            if r["cw1"] and 300 < gap <= 3600 and r["cr"] > CACHE_MISS_MIN_TOKENS:
                miss["saved_by_1h_ttl"]["n"] += 1
                miss["saved_by_1h_ttl"]["cost"] += r["cr"] * (pp[3] - pp[2]) / 1e6
            cacheable = before["cr"] + before["cw5"] + before["cw1"]
            missed = max(0, min(cacheable, r["ctx"]) - r["cr"])
            if missed < CACHE_MISS_MIN_TOKENS:
                continue
            w = r["cw5"] + r["cw1"]
            write_rate = ((r["cw5"] * pp[3] + r["cw1"] * pp[4]) / w) if w else pp[3]
            extra = missed * (write_rate - pp[2]) / 1e6
            bucket = ">1h" if gap > 3600 else ("5m-1h" if gap > 300 else "<5m")
            miss[bucket]["n"] += 1
            miss[bucket]["tokens"] += missed
            miss[bucket]["cost"] += extra
            miss_by_kind[T[p]["kind"]][bucket] += extra
    heavy = [s for s in sessions if s["cost"] > 1 and s["cw"] > 0.15 * max(1, s["cr"])]
    return {
        "cache": {"read": read, "write": write, "read_per_write": read / max(1, write),
                  "write_5m": sum(r["cw5"] for r in all_rs), "write_1h": sum(r["cw1"] for r in all_rs)},
        "cache_misses": {k: dict(v) for k, v in miss.items()},
        "cache_misses_by_kind": {k: dict(v) for k, v in miss_by_kind.items()},
        "ttl_1h_premium_paid": sum(r["cw1"] * (PRICES[r["model"]][4] - PRICES[r["model"]][3]) / 1e6
                                   for r in all_rs if r["model"] in PRICES),
        "write_heavy_sessions": [{k: s[k] for k in ("project", "primary", "cost", "cr", "cw", "dur_min")}
                                 for s in heavy[:10]],
    }


def context_section(ctx, sessions):
    T, reqs = ctx["T"], ctx["reqs"]
    peaks = [s["peak_ctx"] for s in sessions]
    all_rs = [r for rs in reqs.values() for r in rs]
    buckets = Counter()
    for p, t in T.items():
        if t["kind"] != "main":
            continue
        for r in reqs.get(p, []):
            n = r["ctx"]
            buckets["<100k" if n < 100_000 else "100-200k" if n < 200_000 else "200-500k" if n < 500_000 else ">500k"] += r["cost"] or 0
    return {
        "peak_p50": med(peaks), "peak_p90": pct(peaks, .9), "peak_max": max(peaks, default=0),
        "sessions_over_200k": sum(1 for x in peaks if x > 200_000),
        "sessions_over_500k": sum(1 for x in peaks if x > 500_000),
        "compactions_main": sum(s["compactions"] for s in sessions),
        "compactions_all": sum(t["compactions"] for t in T.values()),
        "sessions_with_compaction": sum(1 for s in sessions if s["compactions"]),
        "cost_over_200k_main": sum(s["cost_over_200k"] for s in sessions),
        "cost_over_200k_all": sum(r["cost"] or 0 for r in all_rs if r["ctx"] > 200_000),
        "cost_over_500k_all": sum(r["cost"] or 0 for r in all_rs if r["ctx"] > 500_000),
        "main_cost_buckets": dict(buckets),
    }


def effort_section(ctx):
    T, reqs = ctx["T"], ctx["reqs"]
    effort = defaultdict(Counter)
    for p, rs in reqs.items():
        for r in rs:
            key = f"{r['model']}|effort={r['effort']}|perTurn={r['pte']}"
            effort[T[p]["kind"]][key + "|n"] += 1
            effort[T[p]["kind"]][key + "|cost"] += r["cost"] or 0
    params = Counter(
        f"{t['kind']}|{a['model']}|effort={a['effort']}|thinking={a['thinking']}|ttl={a['ttl']}"
        for t in T.values() for a in t["api_params"]
    )
    return {"effort": {k: dict(v) for k, v in effort.items()}, "api_request_params": dict(params.most_common(30))}


def tools_section(ctx):
    T, reqs = ctx["T"], ctx["reqs"]
    calls, size_by, carry, media, kind_bytes, reads, bash_runs = (Counter() for _ in range(7))
    largest = []
    for p, t in T.items():
        tu = t["tool_uses"]
        rs = reqs.get(p, [])
        starts = [r["start"] or r["ts"] for r in rs]
        read_price = price_for(rs[0]["model"], 0) if rs else None
        for u in tu.values():
            calls[u["key"]] += 1
            calls["__name__" + u["name"]] += 1
            if u["name"] == "Read" and u["file"]:
                reads[(p, u["file"])] += 1
            if u["full_cmd"]:
                bash_runs[(p, u["full_cmd"])] += 1
        for tid, size, img, ts in t["tool_results"]:
            u = tu.get(tid, {"name": "?", "key": "?", "detail": ""})
            size_by[u["key"]] += size
            size_by["__name__" + u["name"]] += size
            later = len(starts) - bisect.bisect_right(starts, ts)
            if read_price:
                carry[u["key"]] += (size / 4 + img * MEDIA_TOKENS) * later * read_price[2] / 1e6
            media[u["key"]] += img
            kind_bytes[(t["kind"], u["key"])] += size
            largest.append((size, u["key"], u["detail"], tr.project_label(t["project"]), t["kind"], t["agent_type"], later))
    largest.sort(key=lambda x: -x[0])

    def by_name(counter):
        return {k[8:]: v for k, v in counter.most_common() if k.startswith("__name__")}

    def by_key(counter, n):
        return dict(Counter({k: v for k, v in counter.items() if not k.startswith("__name__")}).most_common(n))

    n_requests = sum(len(v) for v in reqs.values())
    return {
        "calls_per_request": sum(len(t["tool_uses"]) for t in T.values()) / max(1, n_requests),
        "calls_by_name": by_name(calls), "bytes_by_name": by_name(size_by),
        "calls_by_key": by_key(calls, 40), "bytes_by_key": by_key(size_by, 40),
        "carry_cost_by_key_est": dict(carry.most_common(25)),
        "largest_results": [{"bytes": n, "key": k, "detail": d, "project": pr, "kind": kd, "agent": ag,
                             "later_requests": lt} for n, k, d, pr, kd, ag, lt in largest[:25]],
        "media_blocks_by_key": dict(media.most_common(10)),
        "bytes_by_kind_key": {f"{k}|{kk}": v for (k, kk), v in kind_bytes.most_common(30)},
        "calls_main_vs_sub": dict(Counter(t["kind"] for t in T.values() for _ in t["tool_uses"])),
        "total_result_bytes": sum(by_name(size_by).values()),
        "duplicate_reads": {"files_read_more_than_once": sum(1 for v in reads.values() if v > 1),
                            "extra_reads": sum(v - 1 for v in reads.values() if v > 1),
                            "total_reads": sum(reads.values())},
        "repeated_bash": {"distinct_repeated": sum(1 for v in bash_runs.values() if v > 1),
                          "extra_runs": sum(v - 1 for v in bash_runs.values() if v > 1),
                          "total_bash": sum(bash_runs.values()),
                          "top": [{"cmd": c[:150], "times": v} for (_, c), v in bash_runs.most_common(15) if v > 1]},
    }


def parallelism_section(ctx, sessions):
    T, reqs = ctx["T"], ctx["reqs"]
    primary = {s["path"]: s["primary"] for s in sessions}
    rows = []
    for p, t in T.items():
        subs = [s for s in ctx["subs_of"].get(p, []) if T[s]["first_ts"]]
        if t["kind"] != "main" or not subs or not t["first_ts"]:
            continue
        spans = [(T[s]["first_ts"], T[s]["last_ts"]) for s in subs]
        cur = peak = 0
        for _, step in sorted([(a, 1) for a, _ in spans] + [(b, -1) for _, b in spans]):
            cur += step
            peak = max(peak, cur)
        busy = [(r["start"] or r["ts"], r["ts"]) for r in reqs.get(p, [])]
        for tid, _, _, ts in t["tool_results"]:
            u = t["tool_uses"].get(tid)
            if u and u["name"] not in tr.AGENT_TOOLS:
                busy.append((u["ts"], ts))
        fg = [T[s] for s in subs if T[s]["meta"].get("requestShape") == "foreground"]
        rows.append({
            "project": tr.project_label(t["project"]), "primary": primary.get(p), "n_subs": len(subs),
            "peak": peak, "sub_union_min": union_len(spans) / 60, "main_idle_min": uncovered_len(spans, busy) / 60,
            "fg_subs": len(fg), "fg_min": sum(x["last_ts"] - x["first_ts"] for x in fg) / 60,
            "session_min": (t["last_ts"] - t["first_ts"]) / 60,
        })
    return {
        "sessions": len(rows), "peak_p50": med([r["peak"] for r in rows]),
        "peak_p90": pct([r["peak"] for r in rows], .9), "peak_max": max((r["peak"] for r in rows), default=0),
        "sum_session_min": sum(r["session_min"] for r in rows),
        "sum_sub_union_min": sum(r["sub_union_min"] for r in rows),
        "sum_main_idle_min": sum(r["main_idle_min"] for r in rows),
        "fg_runs": sum(r["fg_subs"] for r in rows), "fg_min": sum(r["fg_min"] for r in rows),
        "top": sorted(rows, key=lambda r: -r["main_idle_min"])[:10],
    }


def headline(out):
    h = {
        "total_cost": out["total_cost"], "main_cost": out["main_cost"], "sub_cost": out["sub_cost"],
        "main_sessions": out["n_main_sessions"], "cache_read_per_write": out["cache"]["read_per_write"],
        "cache_miss_cost": sum(out["cache_misses"].get(k, {}).get("cost", 0) for k in IDLE_GAP_BUCKETS),
        "sessions_over_200k": out["context"]["sessions_over_200k"],
        "compactions_main": out["context"]["compactions_main"],
        "main_idle_min": out["parallelism"]["sum_main_idle_min"],
        "tool_result_bytes": out["tools"]["total_result_bytes"],
    }
    for name, c in out["commands"].items():
        for k in ("sessions", "total_cost", "median_cost", "median_dur_min"):
            h[f"commands.{name}.{k}"] = c[k]
    for name, a in out["agents"].items():
        for k in ("runs", "cost", "median_report_bytes"):
            h[f"agents.{name}.{k}"] = a[k]
    return h


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=float, default=14)
    ap.add_argument("--root", default=tr.DEFAULT_ROOT)
    a = ap.parse_args()
    json.dump(analyze(a.root, a.days), sys.stdout, indent=1, default=str)
    print()


if __name__ == "__main__":
    main()
