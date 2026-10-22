#!/usr/bin/env python3
"""Automated test suite for the Fleet Scheduling Optimizer.

Builds the program with the exact g++ command from the README, then runs
four scenarios and checks the printed output:

  A. Bundled sample data (data/vehicles.csv + data/jobs.csv): the known
     result (32 of 35 assigned; J29/J30/J35 unassigned with their reasons;
     550 minutes total travel) plus the scheduling invariants below.
  B. A tiny hand-checked fixture (tests/fixtures/scenario_b_*): the exact
     assignment outcome is computable by hand, including one impossible
     time window and one job no vehicle is big enough for.
  C. Edge cases: an empty jobs file, a job in a zone missing from the
     travel-time table (documented 30-minute fallback), and malformed
     input files, which must be rejected with an error and exit code 1.
  D. CSV export: with an optional third argument (output path), the
     written schedule file's rows must match the hand-checked Scenario B
     schedule exactly; an unwritable output path must exit 1 with an
     error instead of crashing.

Invariants checked independently of any expected numbers (scenarios A, B
and C2), by re-simulating every printed route from the CSV inputs:
  * every job is accounted for exactly once (assigned XOR unassigned)
  * no vehicle has overlapping jobs, driving time included: each job
    starts exactly at max(arrival after driving, window opening) and
    runs for its full duration
  * every assigned job finishes by its window's latest end, and the
    vehicle is back in its home zone by the end of its shift
  * vehicle type and capacity match every assigned job's requirements
  * each vehicle's printed Jobs/Busy/service/travel/utilization figures
    match values recomputed here, and the summary agrees with them

Usage: python3 tests/run_tests.py
Prints one PASS/FAIL line per check; exits non-zero if anything fails.
Requirements: g++ and Python 3 (standard library only).
"""

import csv
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

# ---------------------------------------------------------------------------
# Check bookkeeping
# ---------------------------------------------------------------------------

CHECKS = []  # list of (name, ok)


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok)))
    line = ("PASS" if ok else "FAIL") + ": " + name
    if not ok and detail:
        line += " -- " + detail
    print(line)
    return bool(ok)


# ---------------------------------------------------------------------------
# Travel-time table: mirrors Scheduler.cpp (same zone = 10 minutes,
# unknown pair = 30 minutes).
# ---------------------------------------------------------------------------

_ZONE_PAIRS = {
    frozenset(("Brampton", "Mississauga")): 25,
    frozenset(("Brampton", "Etobicoke")): 30,
    frozenset(("Brampton", "Toronto")): 45,
    frozenset(("Brampton", "Vaughan")): 25,
    frozenset(("Mississauga", "Etobicoke")): 20,
    frozenset(("Mississauga", "Toronto")): 35,
    frozenset(("Mississauga", "Vaughan")): 40,
    frozenset(("Etobicoke", "Toronto")): 25,
    frozenset(("Etobicoke", "Vaughan")): 35,
    frozenset(("Toronto", "Vaughan")): 35,
}


def travel_minutes(from_zone, to_zone):
    if from_zone == to_zone:
        return 10
    return _ZONE_PAIRS.get(frozenset((from_zone, to_zone)), 30)


# ---------------------------------------------------------------------------
# Input CSV loading (independent of the C++ loader)
# ---------------------------------------------------------------------------


def to_min(hhmm):
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def load_vehicles(path):
    with open(path, newline="") as fh:
        return {
            row["id"]: {
                "type": row["type"],
                "capacity": int(row["capacity"]),
                "shift_start": to_min(row["shift_start"]),
                "shift_end": to_min(row["shift_end"]),
                "home_zone": row["home_zone"],
            }
            for row in csv.DictReader(fh)
        }


def load_jobs(path):
    with open(path, newline="") as fh:
        return {
            row["id"]: {
                "zone": row["zone"],
                "earliest": to_min(row["earliest_start"]),
                "latest": to_min(row["latest_end"]),
                "duration": int(row["duration_min"]),
                "type": row["required_type"],
                "min_capacity": int(row["min_capacity"]),
                "priority": int(row["priority"]),
            }
            for row in csv.DictReader(fh)
        }


# ---------------------------------------------------------------------------
# Program output parsing
# ---------------------------------------------------------------------------

_RE_LOADED = re.compile(r"^Loaded (\d+) vehicles and (\d+) jobs\.$")
_RE_VEHICLE = re.compile(
    r"^(\S+) \((\w+), capacity (\d+), shift (\d{2}:\d{2})-(\d{2}:\d{2}), home (.+)\)$"
)
_RE_ENTRY = re.compile(
    r"^  (\d{2}:\d{2})-(\d{2}:\d{2})  (\S+)  (.+)  (\d+) min  priority (\d+)$"
)
_RE_FOOTER = re.compile(
    r"^  Jobs: (\d+) \| Busy: (\d+) min \(service (\d+) \+ travel (\d+)\)"
    r" \| Utilization: (\d+)%$"
)
_RE_UNASSIGNED = re.compile(
    r"^  (\S+) \((\w+), (.+), window (\d{2}:\d{2})-(\d{2}:\d{2}), (\d+) min,"
    r" priority (\d+)\)$"
)
_RE_REASON = re.compile(r"^    Reason: (.*)$")
_RE_SUMMARY = re.compile(r"^Jobs assigned: (\d+) of (\d+) \((\d+) unassigned\)$")
_RE_TRAVEL = re.compile(r"^Total fleet travel time: (\d+) minutes$")


def parse_output(text):
    parsed = {"vehicles": {}, "unassigned": {}, "summary": {}}
    section = None
    current = None
    for line in text.splitlines():
        if line == "=== Vehicle schedules ===":
            section = "vehicles"
            continue
        if line == "=== Unassigned jobs ===":
            section = "unassigned"
            continue
        if line == "=== Summary ===":
            section = "summary"
            continue
        m = _RE_LOADED.match(line)
        if m:
            parsed["loaded"] = (int(m.group(1)), int(m.group(2)))
            continue
        if section == "vehicles":
            m = _RE_VEHICLE.match(line)
            if m:
                current = m.group(1)
                parsed["vehicles"][current] = {
                    "type": m.group(2),
                    "capacity": int(m.group(3)),
                    "shift_start": to_min(m.group(4)),
                    "shift_end": to_min(m.group(5)),
                    "home_zone": m.group(6),
                    "entries": [],
                    "no_jobs": False,
                    "footer": None,
                }
                continue
            if current is None:
                continue
            if line == "  (no jobs assigned)":
                parsed["vehicles"][current]["no_jobs"] = True
                continue
            m = _RE_ENTRY.match(line)
            if m:
                parsed["vehicles"][current]["entries"].append(
                    {
                        "start": to_min(m.group(1)),
                        "end": to_min(m.group(2)),
                        "job_id": m.group(3),
                        "zone": m.group(4),
                        "duration": int(m.group(5)),
                        "priority": int(m.group(6)),
                    }
                )
                continue
            m = _RE_FOOTER.match(line)
            if m:
                parsed["vehicles"][current]["footer"] = {
                    "jobs": int(m.group(1)),
                    "busy": int(m.group(2)),
                    "service": int(m.group(3)),
                    "travel": int(m.group(4)),
                    "utilization": int(m.group(5)),
                }
                continue
        if section == "unassigned":
            m = _RE_UNASSIGNED.match(line)
            if m:
                current = m.group(1)
                parsed["unassigned"][current] = {"reason": ""}
                continue
            m = _RE_REASON.match(line)
            if m and current in parsed["unassigned"]:
                parsed["unassigned"][current]["reason"] = m.group(1)
                continue
        if section == "summary":
            m = _RE_SUMMARY.match(line)
            if m:
                parsed["summary"] = {
                    "assigned": int(m.group(1)),
                    "total": int(m.group(2)),
                    "unassigned": int(m.group(3)),
                }
                continue
            m = _RE_TRAVEL.match(line)
            if m:
                parsed["summary"]["travel"] = int(m.group(1))
                continue
    return parsed


# ---------------------------------------------------------------------------
# Generic invariant checks for one successful run
# ---------------------------------------------------------------------------


def check_run_invariants(label, vehicles, jobs, parsed):
    assigned_ids = [
        entry["job_id"]
        for vehicle in parsed["vehicles"].values()
        for entry in vehicle["entries"]
    ]
    unassigned_ids = list(parsed["unassigned"])

    check(
        f"{label}: every job accounted for exactly once (assigned XOR unassigned)",
        sorted(assigned_ids + unassigned_ids) == sorted(jobs)
        and len(assigned_ids) == len(set(assigned_ids))
        and not set(assigned_ids) & set(unassigned_ids),
    )

    problems = {"overlap": [], "window": [], "shift": [], "typecap": [], "footer": []}
    total_travel = 0
    for vehicle_id, vehicle in parsed["vehicles"].items():
        spec = vehicles[vehicle_id]
        clock = spec["shift_start"]
        zone = spec["home_zone"]
        service = 0
        legs = 0
        for entry in vehicle["entries"]:
            job = jobs[entry["job_id"]]
            arrival = clock + travel_minutes(zone, entry["zone"])
            legs += travel_minutes(zone, entry["zone"])
            expected_start = max(arrival, job["earliest"])
            if entry["start"] != expected_start or entry["end"] != (
                expected_start + job["duration"]
            ):
                problems["overlap"].append(entry["job_id"])
            if entry["start"] < job["earliest"] or entry["end"] > job["latest"]:
                problems["window"].append(entry["job_id"])
            if spec["type"] != job["type"] or spec["capacity"] < job["min_capacity"]:
                problems["typecap"].append(entry["job_id"])
            service += job["duration"]
            clock = entry["end"]
            zone = entry["zone"]
        if clock + travel_minutes(zone, spec["home_zone"]) > spec["shift_end"]:
            problems["shift"].append(vehicle_id)
        route_travel = legs + (
            travel_minutes(zone, spec["home_zone"]) if vehicle["entries"] else 0
        )
        total_travel += route_travel
        footer = vehicle["footer"] or {}
        shift_minutes = spec["shift_end"] - spec["shift_start"]
        expected_util = (100 * (service + route_travel)) // shift_minutes
        if (
            footer.get("jobs") != len(vehicle["entries"])
            or footer.get("service") != service
            or footer.get("travel") != route_travel
            or footer.get("busy") != service + route_travel
            or footer.get("utilization") != expected_util
        ):
            problems["footer"].append(vehicle_id)

    check(
        f"{label}: no overlapping jobs (route re-simulation incl. travel time)",
        not problems["overlap"],
        "mismatched start/end for " + ", ".join(problems["overlap"]),
    )
    check(
        f"{label}: every assigned job inside its time window",
        not problems["window"],
        "outside window: " + ", ".join(problems["window"]),
    )
    check(
        f"{label}: every vehicle back home by shift end",
        not problems["shift"],
        "late vehicles: " + ", ".join(problems["shift"]),
    )
    check(
        f"{label}: vehicle type and capacity respected for every assignment",
        not problems["typecap"],
        "violations: " + ", ".join(problems["typecap"]),
    )
    check(
        f"{label}: printed per-vehicle figures match recomputation",
        not problems["footer"],
        "mismatched vehicles: " + ", ".join(problems["footer"]),
    )
    summary = parsed["summary"]
    check(
        f"{label}: summary agrees with the printed routes",
        summary.get("assigned") == len(assigned_ids)
        and summary.get("unassigned") == len(unassigned_ids)
        and summary.get("total") == len(jobs)
        and summary.get("travel") == total_travel,
    )


def route_of(parsed, vehicle_id):
    return [
        (entry["job_id"], entry["start"], entry["end"])
        for entry in parsed["vehicles"][vehicle_id]["entries"]
    ]


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def scenario_a(binary):
    print("\n--- Scenario A: bundled sample data ---")
    vehicles = load_vehicles(ROOT / "data" / "vehicles.csv")
    jobs = load_jobs(ROOT / "data" / "jobs.csv")
    result = subprocess.run(
        [str(binary)], cwd=ROOT, capture_output=True, text=True
    )
    check("A: program exits 0 on the sample data", result.returncode == 0)
    parsed = parse_output(result.stdout)
    check("A: header reports 12 vehicles and 35 jobs", parsed.get("loaded") == (12, 35))
    summary = parsed["summary"]
    check(
        "A: 32 of 35 jobs assigned, 3 unassigned",
        summary.get("assigned") == 32
        and summary.get("total") == 35
        and summary.get("unassigned") == 3,
    )
    check(
        "A: unassigned jobs are exactly J29, J30, J35",
        set(parsed["unassigned"]) == {"J29", "J30", "J35"},
        "got " + ", ".join(sorted(parsed["unassigned"])),
    )
    reasons = {jid: info["reason"] for jid, info in parsed["unassigned"].items()}
    check(
        "A: J29 reason is the too-short time window",
        "time window is shorter than the job itself" in reasons.get("J29", ""),
    )
    check(
        "A: J30 reason is insufficient truck capacity (6000)",
        "no truck has the required capacity of 6000" in reasons.get("J30", ""),
    )
    check(
        "A: J35 reason is no feasible time slot",
        "no feasible time slot" in reasons.get("J35", ""),
    )
    check(
        "A: total fleet travel time is 550 minutes",
        summary.get("travel") == 550,
        f"got {summary.get('travel')}",
    )
    check_run_invariants("A", vehicles, jobs, parsed)


def scenario_b(binary):
    print("\n--- Scenario B: hand-checked fixture (2 vehicles, 5 jobs) ---")
    vehicles_path = FIXTURES / "scenario_b_vehicles.csv"
    jobs_path = FIXTURES / "scenario_b_jobs.csv"
    vehicles = load_vehicles(vehicles_path)
    jobs = load_jobs(jobs_path)
    result = subprocess.run(
        [str(binary), str(vehicles_path), str(jobs_path)],
        capture_output=True,
        text=True,
    )
    check("B: program exits 0", result.returncode == 0)
    parsed = parse_output(result.stdout)
    check("B: header reports 2 vehicles and 5 jobs", parsed.get("loaded") == (2, 5))
    check(
        "B: truck T1 gets only B1, 08:10-09:10 (only a truck can take it)",
        route_of(parsed, "T1") == [("B1", to_min("08:10"), to_min("09:10"))],
        f"got {route_of(parsed, 'T1')}",
    )
    check(
        "B: van V1 gets B2 08:10-08:40 then B5 12:00-12:30",
        route_of(parsed, "V1")
        == [
            ("B2", to_min("08:10"), to_min("08:40")),
            ("B5", to_min("12:00"), to_min("12:30")),
        ],
        f"got {route_of(parsed, 'V1')}",
    )
    check(
        "B: unassigned jobs are exactly B3 and B4",
        set(parsed["unassigned"]) == {"B3", "B4"},
        "got " + ", ".join(sorted(parsed["unassigned"])),
    )
    check(
        "B: B3 reason is the impossible time window (45 min in a 30 min window)",
        "time window is shorter than the job itself"
        in parsed["unassigned"].get("B3", {}).get("reason", ""),
    )
    check(
        "B: B4 reason is insufficient van capacity (9999)",
        "no van has the required capacity of 9999"
        in parsed["unassigned"].get("B4", {}).get("reason", ""),
    )
    check(
        "B: summary is 3 of 5 assigned, 50 minutes of travel",
        parsed["summary"].get("assigned") == 3
        and parsed["summary"].get("total") == 5
        and parsed["summary"].get("travel") == 50,
    )
    check_run_invariants("B", vehicles, jobs, parsed)


def scenario_c(binary):
    print("\n--- Scenario C: edge cases ---")
    vehicles_b = FIXTURES / "scenario_b_vehicles.csv"

    # C1: header-only jobs file.
    result = subprocess.run(
        [str(binary), str(vehicles_b), str(FIXTURES / "scenario_c_empty_jobs.csv")],
        capture_output=True,
        text=True,
    )
    parsed = parse_output(result.stdout)
    check("C1: empty jobs file exits 0", result.returncode == 0)
    check(
        "C1: 0 of 0 jobs assigned and the unassigned list is empty",
        parsed["summary"].get("assigned") == 0
        and parsed["summary"].get("total") == 0
        and parsed["unassigned"] == {}
        and "  (none)" in result.stdout,
    )
    check(
        "C1: idle vehicles report 0 travel minutes (no phantom travel)",
        parsed["summary"].get("travel") == 0
        and all(
            vehicle["footer"] and vehicle["footer"]["travel"] == 0
            for vehicle in parsed["vehicles"].values()
        ),
        f"summary travel = {parsed['summary'].get('travel')}",
    )

    # C2: job zone missing from the travel-time table -> 30-minute fallback.
    vehicles_path = FIXTURES / "scenario_c_unknown_zone_vehicles.csv"
    jobs_path = FIXTURES / "scenario_c_unknown_zone_jobs.csv"
    vehicles = load_vehicles(vehicles_path)
    jobs = load_jobs(jobs_path)
    result = subprocess.run(
        [str(binary), str(vehicles_path), str(jobs_path)],
        capture_output=True,
        text=True,
    )
    parsed = parse_output(result.stdout)
    check("C2: unknown-zone job exits 0", result.returncode == 0)
    check(
        "C2: job starts at 08:30 (shift start + documented 30 min fallback)",
        route_of(parsed, "U1") == [("UZ1", to_min("08:30"), to_min("09:00"))],
        f"got {route_of(parsed, 'U1')}",
    )
    check(
        "C2: travel is 60 minutes (30 out + 30 back, both fallback legs)",
        parsed["summary"].get("travel") == 60,
        f"got {parsed['summary'].get('travel')}",
    )
    check_run_invariants("C2", vehicles, jobs, parsed)

    # C3: malformed inputs must be rejected cleanly, never crash.
    result = subprocess.run(
        [str(binary), str(vehicles_b), str(FIXTURES / "scenario_c_bad_columns_jobs.csv")],
        capture_output=True,
        text=True,
    )
    check(
        "C3a: row with too few columns exits 1 with a clear error",
        result.returncode == 1
        and "Error loading input data" in result.stderr
        and "expected 8 columns" in result.stderr,
        f"exit={result.returncode}, stderr={result.stderr.strip()!r}",
    )
    result = subprocess.run(
        [str(binary), str(vehicles_b), str(FIXTURES / "scenario_c_bad_time_jobs.csv")],
        capture_output=True,
        text=True,
    )
    check(
        "C3b: non-numeric time value exits 1 with a clear error",
        result.returncode == 1
        and "Error loading input data" in result.stderr
        and "bad time value" in result.stderr,
        f"exit={result.returncode}, stderr={result.stderr.strip()!r}",
    )
    result = subprocess.run(
        [str(binary), str(vehicles_b), str(FIXTURES / "no_such_file.csv")],
        capture_output=True,
        text=True,
    )
    check(
        "C3c: missing input file exits 1 with a clear error",
        result.returncode == 1
        and "Error loading input data" in result.stderr
        and "could not open file" in result.stderr,
        f"exit={result.returncode}, stderr={result.stderr.strip()!r}",
    )


def scenario_d(binary):
    print("\n--- Scenario D: CSV schedule export ---")
    vehicles_path = FIXTURES / "scenario_b_vehicles.csv"
    jobs_path = FIXTURES / "scenario_b_jobs.csv"
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "schedule.csv"
        result = subprocess.run(
            [str(binary), str(vehicles_path), str(jobs_path), str(out_path)],
            capture_output=True,
            text=True,
        )
        check("D: export run exits 0", result.returncode == 0)
        check(
            "D: console notes the written file",
            f"Schedule written to: {out_path}" in result.stdout,
        )
        rows = []
        if out_path.exists():
            with open(out_path, newline="") as fh:
                rows = list(csv.reader(fh))
        check(
            "D: first row is the CSV header",
            bool(rows)
            and rows[0]
            == ["vehicle_id", "job_id", "zone", "start", "end", "priority"],
            f"got {rows[0] if rows else 'no file'}",
        )
        check(
            "D: rows match the hand-checked Scenario B schedule",
            rows[1:]
            == [
                ["T1", "B1", "Brampton", "08:10", "09:10", "1"],
                ["V1", "B2", "Brampton", "08:10", "08:40", "1"],
                ["V1", "B5", "Brampton", "12:00", "12:30", "3"],
            ],
            f"got {rows[1:]}",
        )

        bad_path = Path(tmp) / "no_such_dir" / "schedule.csv"
        result = subprocess.run(
            [str(binary), str(vehicles_path), str(jobs_path), str(bad_path)],
            capture_output=True,
            text=True,
        )
        check(
            "D: unwritable output path exits 1 with a clear error",
            result.returncode == 1
            and "could not write schedule file" in result.stderr,
            f"exit={result.returncode}, stderr={result.stderr.strip()!r}",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("Fleet Scheduling Optimizer -- test suite")
    with tempfile.TemporaryDirectory() as tmp:
        binary = Path(tmp) / "fleet_optimizer"
        build = subprocess.run(
            [
                "g++",
                "-std=c++17",
                "-Wall",
                "-Wextra",
                "-O2",
                "-o",
                str(binary),
                "main.cpp",
                "Vehicle.cpp",
                "Job.cpp",
                "Scheduler.cpp",
                "DataLoader.cpp",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if not check(
            "build: g++ compiles the project (README command)",
            build.returncode == 0,
            build.stderr.strip()[:400],
        ):
            print("\nBuild failed; scenarios skipped.")
            return summarize()
        scenario_a(binary)
        scenario_b(binary)
        scenario_c(binary)
        scenario_d(binary)
    return summarize()


def summarize():
    passed = sum(1 for _, ok in CHECKS if ok)
    print(f"\n{passed}/{len(CHECKS)} checks passed")
    if passed == len(CHECKS):
        print("ALL TESTS PASSED")
        return 0
    print("FAILURES PRESENT")
    return 1


if __name__ == "__main__":
    sys.exit(main())
