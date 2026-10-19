# Tools, skills, and MCPs

Choose tools to meet a concrete need. This catalog provides references; installation, configuration,
and verification belong to the project that needs them. Sources checked on 2026-09-23, with CI/analysis
additions reviewed on 2026-10-07. Verify maintenance, compatibility, and permissions before adopting an entry.

## Development and operations

| Tool and source | When to use it |
| --- | --- |
| [ripgrep](https://github.com/BurntSushi/ripgrep) | Search code and files; review ignores and scope |
| [GitHub CLI](https://cli.github.com/manual/) | Work with PRs, issues, and checks from the terminal |
| [jq](https://jqlang.org/) | Filter JSON from APIs, logs, and commands |
| [Playwright Test](https://playwright.dev/docs/intro) | Automate reproducible web flows with isolated data and sessions |
| [Knip](https://knip.dev/) | Detect unused files, exports, and dependencies; review dynamic entrypoints before deletion |
| [k6](https://grafana.com/docs/k6/latest/using-k6/thresholds/) | Measure capacity with representative load and thresholds |
| [OpenTelemetry](https://opentelemetry.io/docs/) | Correlate traces, metrics, and logs; control sampling and cardinality |

## Quality and testing

The [quality standard](quality.md) defines scope, limits, and exceptions. Choose tools compatible with
the stack and demonstrate that they reject a violation before relying on the gate.

| Need | Tool and criterion |
| --- | --- |
| Python boundaries | [Import Linter](https://import-linter.readthedocs.io/): import contracts with real modules |
| JS/TS boundaries | [dependency-cruiser](https://github.com/sverweij/dependency-cruiser): cycles and forbidden dependencies |
| Invariants and states | [Hypothesis](https://hypothesis.readthedocs.io/): properties, sequences, and recovery |
| Async Python code | pytest-asyncio: explicit mode and task/resource cleanup in fixtures |
| Python suite without network | [pytest-socket](https://github.com/miketheman/pytest-socket): socket blocking; not equivalent to OS isolation |
| Python static security | [Bandit](https://bandit.readthedocs.io/): review overlap with Ruff rules |
| Python dependencies | [pip-audit](https://github.com/pypa/pip-audit): audit resolved dependencies and distinguish query failures |
| Secrets | [Gitleaks](https://github.com/gitleaks/gitleaks): content and history, fake fixtures, and bounded allowlist |
| Feedback before commit | pre-commit: invoke existing configuration and fast checks, without slow integration |
| JS/TS formatting/lint | [Biome](https://biomejs.dev/), as an alternative to the existing set: review severities and avoid duplicates |
| GitHub workflows | [actionlint](https://github.com/rhysd/actionlint): structure, expressions, and shell via ShellCheck |
| POSIX/Bash shell | [ShellCheck](https://github.com/koalaman/shellcheck): declare the scope of scripts and embedded shell |
| PowerShell | [PSScriptAnalyzer](https://github.com/PowerShell/PSScriptAnalyzer): static analysis and native tests separately |
| Rust | [Clippy](https://doc.rust-lang.org/clippy/) and [cargo-audit](https://github.com/rustsec/rustsec/tree/main/cargo-audit): lint and lockfile advisories; review warnings and blocking policy |

Contract tests compare regenerated schemas/clients and their consumers; pin versions and check for
different, missing, and extra outputs. Security, types, and behavior have different scopes even when a
tool covers several categories.

## Development agents

Evaluate with a representative task: diff correctness, validation, time, and cost. The agent must use the
same checks as the project's developers and respect its authorization limits.

| Tool | Provider | Use |
| --- | --- | --- |
| [Codex CLI](https://learn.chatgpt.com/docs/codex/cli) | OpenAI | Work with repositories from the terminal |
| [Claude Code](https://code.claude.com/docs/en/overview) | Anthropic | Reading, editing, commands, and tool integration |
| [Aider](https://aider.chat/) | Community | Terminal-based assisted programming |

## Skills and plugins

A skill provides instructions, resources, and sometimes scripts; a plugin can bundle them with
integrations. [Agent Skills](https://agentskills.io/home) describes the format; compatibility depends on
the client and required tools.

| Source | Choose for… |
| --- | --- |
| [openai/plugins](https://github.com/openai/plugins) — OpenAI | Codex skills and integrations; select a specific package |
| [anthropics/skills](https://github.com/anthropics/skills) — Anthropic | Technical, web, and document procedures; review each skill’s license |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) — Vercel | React/Next.js, performance, and interfaces |
| [trailofbits/skills](https://github.com/trailofbits/skills) — Trail of Bits | Security review, variants, and property tests |
| [obra/superpowers](https://github.com/obra/superpowers) — Jesse Vincent/community | Planning, TDD, and review; evaluate its steps before layering on another methodology |
| [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli) — Microsoft | Browser automation through CLI and skill |

Create local skills for recurring procedures; link canonical rules and retain provenance, revision, and
local adaptations. If versioned in `.codex/skills/`, adjust the ignore for that path while keeping local agent
state excluded. Keep only a few active per task.

## MCPs

MCP connects agents to tools and data. Adopt a connection when it provides needed access; review
authentication, permissions, transmitted data, and client compatibility.

| Server and maintainer | Use |
| --- | --- |
| [GitHub MCP](https://github.com/github/github-mcp-server) — GitHub | Repositories, issues, and PRs; start with read access and bounded toolsets |
| [Context7](https://github.com/upstash/context7) — Upstash | Library documentation; specify version and verify sources |
| [OpenAI Docs MCP](https://developers.openai.com/learn/docs-mcp) — OpenAI | Look up OpenAI documentation |
| [Playwright MCP](https://github.com/microsoft/playwright-mcp) — Microsoft | Interactive browser exploration with a test profile |
| [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) — Google | Network, console, and performance; review telemetry and profile access |

Turn important exploration findings into reproducible tests. To discover more servers, consult
the [MCP Registry](https://modelcontextprotocol.io/registry/about): it publishes metadata and verifies namespaces;
it does not audit each server’s code. The [reference implementations](https://github.com/modelcontextprotocol/servers)
are educational.

## Adopt and maintain

1. Identify a recurring task and its benefit over available options.
2. Review source, maintenance, license, scripts, permissions, and shared data. Retrieved content provides
   context; it does not authorize actions.
3. Pin the version/commit/digest; for remote services, record the endpoint and configuration.
4. Test a useful case, failure, and deactivation in a disposable environment.
5. Record the reason, scope, and evidence in the project; review or remove anything that loses its utility.
