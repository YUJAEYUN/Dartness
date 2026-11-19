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
