# lab/ - agent instructions

`lab/` is the pre-rewrite ACM1 system: the six-detector pipeline, the
simulator, and the CARE and public-dataset benchmark harnesses. It is
reference material and tooling. The product is `src/acm/` at the repo
root, and the repo-root `AGENTS.md` holds the rules that apply here too.

## Working in lab/

- Run lab commands from inside `lab/`. Its imports and paths are
  relative to this directory.
- `src/acm/` does not import anything from `lab/`. Keep it that way.
- Change lab code only when a task needs the lab tooling to run, for
  example a benchmark harness used as evidence. Do not develop new
  detection behaviour here; that work belongs in `src/acm/`.
- ML parameters live in `core/ml_defaults.py`. `configs/config_table.csv`
  holds the `data`, `sql` and `runtime` categories only, and a test
  enforces the split.
- The vendored `sim/` package and the separate Simulator project know
  nothing about ACM. Integration code stays on the ACM side.

## History

The full lab-era knowledge base is `docs/archive/kb-lab-history.md` at the repo
root. It records file maps, UI details, benchmark results and
diagnoses up to 2026-07-08. Its paths predate the move into `lab/`, so
read `scripts/...` as `lab/scripts/...`. Its conclusions are under
re-evaluation; re-measure one before you rely on it.
