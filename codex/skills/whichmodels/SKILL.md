---
name: whichmodels
description: Review Codex model and effort choices for llmfiles agents and propose evidence-backed changes when explicitly requested.
---

Read `~/llmfiles/codex/compatibility.md`, then `~/llmfiles/commands/whichmodels.md`. Use the source's inventory, research, proposal, adversarial review, and output process with these replacements. Use the user's text after `$whichmodels` as its focus.

- Scope the inventory to `~/llmfiles/codex/agents/*.toml`, the active Codex home (`CODEX_HOME` or `~/.codex`), its `config.toml` and selected profile, and the README's Codex model rationale. Inspect only model, effort, and agent settings; do not expose credentials.
- Replace Anthropic model research with OpenAI models available to this Codex account. Use official OpenAI documentation for supported model IDs, effort levels, pricing, and defaults, plus independent benchmarks and practitioner reports for workload evidence. Load the installed `openai-docs` skill when available.
- Compare explicit Codex model IDs rather than Claude aliases. The effort labels across providers are not equivalent. Keep the source's three research mandates and two adversarial mandates, batching within available slots.
- Report the strongest evidence for and against each proposed change. Propose only; apply changes after the user asks. Claude configuration remains outside this skill's default scope.
