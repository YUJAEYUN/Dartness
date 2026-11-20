# Dartness collaboration

- Human-readable docs/ are the project requirements and design authority. Read docs/wiki/index.md and the relevant source pages before changes.
- Read docs/work-state.md to resume. Keep confirmed requirements, proposals, observations, and hypotheses distinct.
- Discuss consequential design choices with the user, one at a time. Routine implementation within agreed scope is autonomous.
- Do not silently rewrite docs to match code. Investigate discrepancies and explain which side needs correction.
- Native agent memory is supplementary; verify it against docs and evidence. No custom memory engine is required.
- Write human-facing docs and explanations in concise Korean. Agent-only instructions and code identifiers use English.
- Do not treat the development environment proposal as adopted architecture. Avoid speculative abstractions.
- Never commit credentials, internal client lists, team mappings, or private query outputs.
- Documentation checks: python -m pip install -r requirements-docs.txt; python -m mkdocs build --strict.
- A passing docs build does not establish semantic consistency, diagram correctness, or DART extraction accuracy.
- Update the relevant source docs, wiki links, and work state when behavior or meaningful decisions change.

- Follow docs/development-workflow.md: use a task branch and PR; do not push task changes directly to main.
- Review relevant docs/wiki/code relationships using docs/consistency.md. Record evidence and unimplemented or unverified scope; do not claim semantic consistency from a passing build.
- Explain changes to fixtures, expected outputs, check exclusions, or CI rules separately in the PR.

- Use natural Korean familiar to developers. Prefer direct questions in templates and complete sentences over abstract labels or compressed noun lists. Explain technical terms when needed without changing their meaning.
- Check wording with explicit examples and reader tasks. Linters can flag known wording patterns, but cannot establish that Korean is clear or natural. Do not add blanket bans or claim a readability score proves quality.

- Code checks (Python 3.12): install requirements-dev.txt, then run python -m ruff check ., python -m ruff format --check ., python -m mypy, and python -m pytest -q.
- Amount normalization is not disclosure extraction or fact validation. Preserve this distinction in docs and code.

- Before extraction work, read docs/testing.md. Derive expected answers from source evidence, not implementation output. Mark real, modified, development, and held-out cases honestly; draft fixtures are not verified extraction tests.
