---
name: skillbuilder
description: Build an llmfiles knowledge skill or a Codex-specific workflow skill when explicitly requested.
---

Read `~/llmfiles/codex/compatibility.md`, then `~/llmfiles/commands/skillbuilder.md`. Execute the command body with the following Codex replacements taking precedence. Use the user's text after `$skillbuilder` as its arguments.

- Build shared knowledge skills under `~/llmfiles/skills/`. Put Codex-specific procedures and command adapters under `~/llmfiles/codex/skills/`.
- Include `name` and `description` in `SKILL.md`. For Codex, explicit-only invocation is configured by `policy.allow_implicit_invocation: false` in `agents/openai.yaml`, not Claude's `disable-model-invocation` field. Keep ordinary shared knowledge skills automatically discoverable.
- For a shared skill, preserve any requested Claude invocation metadata and configure Codex's invocation policy separately. Treat tool names as workflow guidance rather than permission settings.
- Replace Claude's `Skill` tool calls with explicit reads of the dependency's `SKILL.md` when that dependency is needed. A Codex skill may load an explicit-only dependency as part of an explicitly invoked workflow.
- Validate with the installed skill-creator validator when available, and check that any referenced files and executable helpers exist. Report which installation loop in the README registers the created skill.
