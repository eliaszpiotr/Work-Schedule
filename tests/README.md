# Test suite

The suite is organised by the boundary each test crosses. A test belongs to the
highest-level boundary it exercises, even when it also covers lower-level code.

## Categories

- `unit/` — deterministic business logic without a database, filesystem, or application window.
- `integration/` — real SQLite, migrations, services, filesystem permissions, backups, and PDF export.
- `ui/` — Qt widgets, painting, interaction, accessibility, and complete screen workflows.

This distinction keeps the test's purpose clear:

- unit tests answer whether a calculation is correct;
- integration tests answer whether components work together across a real boundary;
- UI tests answer whether the user can see and perform the intended behaviour.

## Running tests

```bash
python -m pytest
python -m pytest -m unit
python -m pytest -m integration
python -m pytest -m ui
```

Run a single file or scenario while working on it:

```bash
python -m pytest tests/ui/test_schedule_grid.py
python -m pytest tests/ui/test_schedule_grid.py::TestTotals
```

## Adding tests

Place a test in the lowest category that can prove the behaviour. Do not repeat the
same assertion at several layers unless each test protects a distinct boundary, such
as a database default, its service representation, and its visible UI state.

Prefer testing observable behaviour. Direct checks of private Qt attributes are
appropriate only for visual or interaction details that cannot be observed through a
public interface.
