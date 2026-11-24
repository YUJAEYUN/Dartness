# Dartness agent entrypoint

Dartness finds corporations matching user conditions from official DART disclosures. Human-readable docs/ are the requirements and design authority.

## Start

1. Read docs/work-state.md to resume and docs/wiki/index.md to find the applicable source pages.
2. Read the relevant specification before editing. Distinguish confirmed requirements, proposals, observations, and hypotheses. Do not treat the development environment proposal as adopted architecture or add speculative abstractions.
3. Check open issues/PRs for overlapping work. Follow docs/guides/development-workflow.md: use an isolated task branch/worktree; never push task changes directly to main.
4. After the first commit, open a draft PR with exactly one `Refs #number` line. Do not claim an issue already claimed by an open PR.

## Find task guidance

| Task | Read before changing |
|---|---|
| Requirements and query contracts | docs/specs/requirements.md, then the applicable contract via docs/wiki/index.md |
| DART collection or integration | docs/guides/dart-live-check.md |
| Extraction, fixtures, or expected answers | docs/guides/testing.md and the relevant source-evidence case |
| Dashboard and import boundaries | docs/design/dashboard-structure.md, docs/design/management-screen.md |
| Documentation, memory, or conflicting descriptions | docs/design/documentation.md, docs/consistency.md |
| CI, PRs, delegation, or merging | docs/guides/ci.md, docs/guides/development-workflow.md, docs/guides/delegation.md |

The wiki routes tasks to source docs; it is not a second rulebook. Native agent memory is supplementary: verify it against docs and evidence. No custom memory engine is required.

## Verify

Use Python 3.12 and Node.js 24. Install existing dependencies from requirements-dev.txt, requirements-docs.txt, and dashboard/package-lock.json as needed. Follow docs/guides/ci.md for required checks; do not claim a check passed without running it.

- Python: `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy`, `python -m pytest -q`.
- Docs: `python -m mkdocs build --strict`.
- Dashboard: `npm --prefix dashboard run docs:check`, `npm --prefix dashboard run lint`, `npm --prefix dashboard test`, `npm --prefix dashboard run build`.
- After changing generated document sources, run `npm --prefix dashboard run docs:generate` and commit the generated files. Review related source docs, wiki links, and work state together.

Passing builds/tests do not establish semantic consistency, diagram correctness, or DART extraction accuracy. Amount normalization is not disclosure extraction or fact validation.

## Preserve these boundaries

- Never silently rewrite docs to match code. Investigate conflicts using docs/consistency.md and explain which side needs correction. Report evidence and unimplemented or unverified scope.
- Derive expected answers from source evidence, never implementation output. Distinguish real, modified, development, and held-out cases honestly; draft fixtures are not verified extraction tests.
- Do not introduce third-party DART MCP servers, skills, or dedicated API wrappers. Use official OpenDART endpoints directly. General-purpose development libraries are not prohibited, but new dependencies still require approval.
- Never commit credentials, internal client lists, team mappings, or private query outputs.
- Write human-facing docs/explanations in concise, natural Korean familiar to developers. Agent-only instructions and identifiers use English. Prefer direct questions and complete sentences; explain necessary technical terms. Check wording with examples and reader tasks. Linters can flag known patterns, but do not add blanket wording bans or claim a readability score proves quality.

## Decide and finish

Discuss consequential design choices one at a time. Under docs/guides/delegation.md, routine agreed implementation, fixes, tests, refactoring, PRs, merging, and cleanup are autonomous after required checks.

Ask before changing requirements/selection/judgment rules, existing expected answers, check weakening/exclusions, permissions, dependencies/costs, or delegation policy. Ask when evidence is insufficient or failures repeat. Do not enable a standing bot or broaden delegation without approval.

Before merging:

1. Review the full diff against approved docs. Explain changes to fixtures, expected outputs, check exclusions, or CI rules separately in the PR.
2. Feature PRs (src/) and specification PRs listed in docs/briefings/index.md need a four-digit PR briefing after the PR exists.
3. Integrate the latest main, require passing CI for the current head, and merge with an expected-head SHA. Never bypass protection or treat passing CI as semantic approval.
4. Verify deployment and all acceptance criteria; update issue checklists/body and PR status with evidence before separately closing the issue. Verify merged branches are removed. Follow the detailed workflow rather than closing issues through PR keywords.
