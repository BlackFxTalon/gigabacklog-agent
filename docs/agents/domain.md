# Domain Docs

The repository uses a single-context domain documentation layout.

## Before working on the project

Read:

- `CONTEXT.md` at the repository root;
- relevant ADRs under `docs/adr/`.

If these files do not exist, proceed silently. Do not create them pre-emptively. The `/domain-modeling` skill creates them lazily when terminology or architectural decisions are actually resolved.

## Use the glossary's vocabulary

Use terminology defined in `CONTEXT.md` consistently in issues, tests, implementation, and documentation. If a required concept is missing, treat it as a possible domain-modeling gap rather than inventing competing terminology.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface that conflict explicitly rather than silently overriding the recorded decision.
