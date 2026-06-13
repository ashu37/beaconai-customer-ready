# BeaconAI Action Engine -- Makefile
#
# Added in Milestone 0 (T0.6) so the default test target runs the golden
# regression alongside any other pytest discovery. There is no GitHub Actions
# workflow in this repo today; the M0 plan explicitly says not to add one
# unless one already exists. Use the targets below in pre-PR checks.

PY ?= python

.PHONY: help test golden-test golden-regenerate

help:
	@echo "Targets:"
	@echo "  test                 -- run the full pytest suite (includes golden diff)"
	@echo "  golden-test          -- run only the M0 golden diff (fast pre-PR check)"
	@echo "  golden-regenerate    -- regenerate tests/golden/ (REQUIRES milestone justification)"

test:
	$(PY) -m pytest

golden-test:
	$(PY) -m pytest tests/test_golden_diff.py -v

# DANGER: only run when a milestone ticket explicitly authorizes regenerating
# goldens. Commit the regenerated tests/golden/ tree along with a
# justification line in the PR description that names the ticket.
golden-regenerate:
	$(PY) scripts/freeze_golden.py --regenerate
