# S13.7-T1 RETIREMENT — hard cut per DS R4
# (agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md §4 adjudication).
#
# Legacy per-store segment CSVs (out_dir/segments/) are superseded by per-PlayCard
# audience CSVs written by src/audience_resolver.py at:
#   data/<store_id>/runs/<run_id>/audiences/<audience_definition_id>.csv
#
# AST grep for all importers performed before retirement:
#   grep -r "from src.segments|import segments|from src import segments" . --include="*.py"
#   grep -r "from .segments|build_segments" src/ --include="*.py"
# Result: sole importer was src/main.py — import line and call site both removed
# at S13.7-T1 (replaced with seg_files = []).  No other importers found.
#
# The module body is preserved below the guard for archaeological reference only;
# it is unreachable and will not execute.

raise NotImplementedError(
    "src/segments.py is retired at S13.7-T1. "
    "Use src/audience_resolver.materialize_audience_csvs instead."
)
