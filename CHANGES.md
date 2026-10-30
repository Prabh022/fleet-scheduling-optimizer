# Changes

## Scenario E tests for priority ordering — October 30, 2026

- Added `scenario_e` to the test suite (`tests/run_tests.py`, plus new
  fixtures `tests/fixtures/scenario_e_vehicles.csv` and
  `scenario_e_jobs.csv`): one van, three jobs, with the lower-priority
  job (E1) listed first in the file. The suite checks that the
  higher-priority job (E2) takes the contested morning slot
  (08:10–09:10), E1 is left unassigned with the "no feasible time
  slot" reason, and the later non-conflicting job (E3) is still
  scheduled (13:00–13:30) — summary 2 of 3 assigned, 30 minutes of
  travel. The suite is now 65 checks, all passing. README updated
  (five scenarios). No production code changed.

## CSV schedule export — October 22, 2026

- The program now accepts an optional third argument: a path to write
  the finished schedule to as CSV (`vehicle_id,job_id,zone,start,end,
  priority` — one row per assigned job, vehicles in fleet order, jobs
  in route order). Runs without the argument are unchanged: nothing
  extra is printed or written. An unwritable path is reported as a
  clean error (message + exit 1), not a crash.
- Test suite: added Scenario D for the export — the written rows must
  equal the hand-checked Scenario B schedule exactly, and an
  unwritable path must exit 1. The suite is now 52 checks, all passing;
  on the bundled sample data the export contains the expected 32
  assignment rows and the printed results are unchanged (32 of 35
  assigned, 550 travel minutes).

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
