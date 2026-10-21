# Changes

## Automated test suite, and an idle-vehicle travel fix

- Added `tests/`: an automated test suite (`tests/run_tests.py` plus CSV
  fixtures under `tests/fixtures/`) that builds the program with the
  README's g++ command and verifies the bundled sample day's results, the
  scheduling invariants on every printed route, a hand-checked small
  fixture, and edge cases (empty jobs file, unknown zone, malformed
  input). See the "Tests" section of the README.
- Fixed `Scheduler::travelMinutes` charging a vehicle with an empty route
  10 minutes of travel: the drive-home leg was counted from the home zone
  to itself, so an idle vehicle reported phantom travel (and busy time).
  A vehicle with no jobs now correctly reports 0 travel minutes. The fix
  changes no schedule — output on the bundled sample data and on the
  hand-checked fixture was verified byte-identical before and after.
