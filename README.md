# Fleet Scheduling Optimizer

A command-line program that builds a feasible one-day schedule for a vehicle
fleet: it reads a list of vehicles and a list of jobs (deliveries or service
stops) from CSV files, assigns jobs to vehicles, and prints each vehicle's
route for the day — plus the jobs it could not place, and why.

This is a personal project built in October 2026, inspired by real-world
fleet scheduling work. The sample company, **Summit Fleet Services**, is
fictional, and all bundled data (vehicles, jobs, zones) is synthetic — any
resemblance to a real business is coincidental.

## Features

- Loads vehicles and jobs from plain CSV files (formats documented below)
- Assigns jobs respecting hard constraints:
  - vehicle type must match the job's required type
  - vehicle capacity must meet the job's minimum capacity
  - jobs must fit inside their time windows (earliest start / latest end)
  - a vehicle never has two jobs at once, and must be back in its home
    zone before its shift ends
  - driving time between zones comes from a zone-to-zone travel-time table
- Prints each vehicle's schedule in time order, with per-vehicle busy time
  and shift utilization
- Prints every unassigned job with the reason (wrong vehicle type,
  insufficient capacity, impossible time window, or no feasible slot)
- Can also write the finished schedule to a CSV file (one row per
  assigned job: vehicle, job, zone, start, end, priority) for
  spreadsheets or other tools
- No external dependencies — standard C++17 only

## How the algorithm works

Scheduling runs in two phases:

1. **Greedy cheapest insertion.** Jobs are considered highest priority
   first (priority 1–3; ties broken by earliest deadline). Each job is
   tentatively inserted at every position of every suitable vehicle's
   route. An insertion is kept only if the *whole* route stays feasible
   when re-simulated from the start of the shift (driving from the home
   zone, waiting for time windows to open, and driving back home by shift
   end). Among the feasible insertions, the one adding the least extra
   driving time wins.
2. **Relocation pass.** For each job that still has no slot, the scheduler
   tries removing one already-placed job from a vehicle's route and
   re-placing that job on a different vehicle. If both the waiting job and
   the relocated job end up assigned, the change is kept. This pass repeats
   while it keeps placing more jobs.

This is a heuristic, not an optimal solver: it produces a good feasible
schedule quickly for a single day, but it does not guarantee the
mathematically best assignment.

## Build

Requires a C++17 compiler (developed with g++):

```sh
g++ -std=c++17 -Wall -Wextra -O2 -o fleet_optimizer \
    main.cpp Vehicle.cpp Job.cpp Scheduler.cpp DataLoader.cpp
```

## Run

```sh
./fleet_optimizer                      # uses data/vehicles.csv and data/jobs.csv
./fleet_optimizer myvehicles.csv myjobs.csv   # or your own files
./fleet_optimizer myvehicles.csv myjobs.csv schedule.csv   # also export the schedule as CSV
```

## Tests

An automated test suite lives in `tests/`. It builds the program with the
exact command above and checks four scenarios:

- **Sample day** — the bundled data must still produce 32 of 35 jobs
  assigned (J29, J30, and J35 unassigned, each for the documented reason;
  550 minutes of total travel), and every printed schedule must satisfy
  the scheduling invariants, verified by re-simulating each route:
  no overlapping jobs (driving time included), every job inside its
  time window and its vehicle's shift, vehicle type and capacity
  respected, and every job accounted for exactly once.
- **Hand-checked fixture** — a tiny 2-vehicle, 5-job day in
  `tests/fixtures/` whose correct schedule is computable by hand,
  including one job with an impossible time window and one no vehicle
  is big enough for.
- **Edge cases** — an empty jobs file, a job in a zone missing from the
  travel-time table (the documented 30-minute fallback applies), and
  malformed input files, which must be rejected with an error message
  and a non-zero exit code instead of a crash.
- **CSV export** — with an output-path argument, the written file's
  rows must match the hand-checked fixture's schedule exactly, and an
  unwritable output path must fail with an error and exit code 1.

Run it with:

```sh
python3 tests/run_tests.py
```

It prints one PASS/FAIL line per check and exits non-zero if anything
fails. Requirements: `g++` and Python 3 (standard library only).

## Input formats

`data/vehicles.csv` — one vehicle per row:

```csv
id,type,capacity,shift_start,shift_end,home_zone
V01,van,1500,06:00,14:00,Brampton
```

`data/jobs.csv` — one job per row (`priority`: 1 = highest, 3 = lowest):

```csv
id,zone,earliest_start,latest_end,duration_min,required_type,min_capacity,priority
J01,Brampton,06:00,09:00,45,van,800,1
```

The bundled sample day has 12 vehicles and 35 jobs across five zones
(Brampton, Mississauga, Etobicoke, Toronto, Vaughan). Three of the sample
jobs are deliberately hard to place, so the unassigned-jobs report is
exercised.

## Sample output (trimmed from an actual run)

```text
Fleet Scheduling Optimizer
Sample data: Summit Fleet Services (fictional company, synthetic data)
Loaded 12 vehicles and 35 jobs.

=== Vehicle schedules ===

V05 (truck, capacity 5000, shift 06:00-14:00, home Brampton)
  06:10-07:40  J31  Brampton  90 min  priority 1
  07:50-09:20  J09  Brampton  90 min  priority 1
  09:30-11:00  J13  Brampton  90 min  priority 2
  12:30-13:15  J27  Brampton  45 min  priority 3
  Jobs: 4 | Busy: 365 min (service 315 + travel 50) | Utilization: 76%

V09 (car, capacity 400, shift 07:00-15:00, home Toronto)
  07:10-07:40  J15  Toronto  30 min  priority 1
  08:00-08:30  J16  Toronto  30 min  priority 2
  09:00-09:45  J19  Toronto  45 min  priority 1
  13:00-13:30  J28  Toronto  30 min  priority 3
  13:40-14:25  J25  Toronto  45 min  priority 2
  Jobs: 5 | Busy: 240 min (service 180 + travel 60) | Utilization: 50%

... (10 more vehicles) ...

=== Unassigned jobs ===

  J29 (van, Toronto, window 10:00-10:45, 60 min, priority 1)
    Reason: the job's own time window is shorter than the job itself
  J30 (truck, Mississauga, window 09:00-13:00, 60 min, priority 1)
    Reason: no truck has the required capacity of 6000
  J35 (car, Toronto, window 14:30-15:30, 45 min, priority 3)
    Reason: no feasible time slot: every suitable vehicle conflicts with its shift, the job's time window, or jobs already scheduled

=== Summary ===

Jobs assigned: 32 of 35 (3 unassigned)
Total fleet travel time: 550 minutes
```

## Project structure

```text
main.cpp          Entry point: loads data, runs the scheduler, prints results
Vehicle.h/.cpp    Vehicle record (type, capacity, shift, home zone)
Job.h/.cpp        Job record (zone, time window, duration, requirements)
Scheduler.h/.cpp  Travel-time table, route simulation, insertion + relocation
DataLoader.h/.cpp CSV parsing and HH:MM time conversion
data/             Sample input files (fictional, synthetic)
tests/            Automated test suite (run_tests.py + CSV fixtures)
CHANGES.md        Record of bug fixes and notable changes
```

## Possible extensions

- Read the travel-time table from a data file instead of code
- Multi-day scheduling and driver assignments
- An exact solver (e.g. branch and bound) for small fleets, to measure how
  close the heuristic gets to optimal
