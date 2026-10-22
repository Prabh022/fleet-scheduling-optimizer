// Fleet Scheduling Optimizer
//
// Command-line tool that assigns a day of delivery/service jobs to a fleet
// of vehicles. Sample company and data are fictional and ship with the
// project so it runs out of the box:
//
//   ./fleet_optimizer [vehicles.csv] [jobs.csv] [schedule.csv]
//
// With no arguments it reads data/vehicles.csv and data/jobs.csv. An
// optional third argument writes the finished schedule to a CSV file
// (one row per assigned job).

#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "DataLoader.h"
#include "Job.h"
#include "Scheduler.h"
#include "Vehicle.h"

namespace {

void printVehiclePlan(const Scheduler& scheduler, const Vehicle& vehicle) {
    std::cout << vehicle.id << " (" << vehicle.type << ", capacity "
              << vehicle.capacity << ", shift " << formatTime(vehicle.shiftStart)
              << '-' << formatTime(vehicle.shiftEnd) << ", home "
              << vehicle.homeZone << ")\n";
    const std::vector<RouteEntry> route = scheduler.routeFor(vehicle.id);
    if (route.empty()) {
        std::cout << "  (no jobs assigned)\n";
    }
    for (const auto& entry : route) {
        std::cout << "  " << formatTime(entry.start) << '-' << formatTime(entry.end)
                  << "  " << entry.job.id << "  " << entry.job.zone << "  "
                  << entry.job.duration << " min  priority " << entry.job.priority
                  << '\n';
    }
    const int busy = scheduler.routeServiceMinutes(vehicle) +
                     scheduler.routeTravelMinutes(vehicle);
    const int utilization =
        vehicle.shiftMinutes() > 0 ? (100 * busy) / vehicle.shiftMinutes() : 0;
    std::cout << "  Jobs: " << route.size() << " | Busy: " << busy
              << " min (service " << scheduler.routeServiceMinutes(vehicle)
              << " + travel " << scheduler.routeTravelMinutes(vehicle)
              << ") | Utilization: " << utilization << "%\n\n";
}

// Writes the finished schedule as CSV: one row per assigned job, in
// fleet order and, within a vehicle, in route order. Returns false if
// the file cannot be opened or written.
bool writeScheduleCsv(const std::string& path, const Scheduler& scheduler) {
    std::ofstream out(path);
    if (!out) return false;
    out << "vehicle_id,job_id,zone,start,end,priority\n";
    for (const auto& vehicle : scheduler.fleet()) {
        for (const auto& entry : scheduler.routeFor(vehicle.id)) {
            out << vehicle.id << ',' << entry.job.id << ',' << entry.job.zone
                << ',' << formatTime(entry.start) << ',' << formatTime(entry.end)
                << ',' << entry.job.priority << '\n';
        }
    }
    return static_cast<bool>(out);
}

}  // namespace

int main(int argc, char* argv[]) {
    const std::string vehiclesPath = argc > 1 ? argv[1] : "data/vehicles.csv";
    const std::string jobsPath = argc > 2 ? argv[2] : "data/jobs.csv";
    const std::string schedulePath = argc > 3 ? argv[3] : "";

    std::vector<Vehicle> vehicles;
    std::vector<Job> jobs;
    try {
        vehicles = loadVehicles(vehiclesPath);
        jobs = loadJobs(jobsPath);
    } catch (const std::exception& e) {
        std::cerr << "Error loading input data: " << e.what() << '\n';
        return 1;
    }

    Scheduler scheduler;
    scheduler.setFleet(vehicles);
    scheduler.scheduleAll(jobs);

    std::cout << "Fleet Scheduling Optimizer\n";
    std::cout << "Sample data: Summit Fleet Services (fictional company, "
                 "synthetic data)\n";
    std::cout << "Loaded " << vehicles.size() << " vehicles and " << jobs.size()
              << " jobs.\n\n";

    std::cout << "=== Vehicle schedules ===\n\n";
    int assignedCount = 0;
    int totalTravel = 0;
    for (const auto& vehicle : scheduler.fleet()) {
        printVehiclePlan(scheduler, vehicle);
        assignedCount += static_cast<int>(scheduler.routeFor(vehicle.id).size());
        totalTravel += scheduler.routeTravelMinutes(vehicle);
    }

    std::cout << "=== Unassigned jobs ===\n\n";
    if (scheduler.unassigned().empty()) {
        std::cout << "  (none)\n\n";
    } else {
        for (const auto& job : scheduler.unassigned()) {
            std::cout << "  " << job.id << " (" << job.requiredType << ", "
                      << job.zone << ", window " << formatTime(job.earliestStart)
                      << '-' << formatTime(job.latestEnd) << ", " << job.duration
                      << " min, priority " << job.priority << ")\n"
                      << "    Reason: " << scheduler.unassignedReason(job)
                      << "\n";
        }
        std::cout << '\n';
    }

    std::cout << "=== Summary ===\n\n";
    std::cout << "Jobs assigned: " << assignedCount << " of " << jobs.size()
              << " (" << scheduler.unassigned().size() << " unassigned)\n";
    std::cout << "Total fleet travel time: " << totalTravel << " minutes\n";

    if (!schedulePath.empty()) {
        if (!writeScheduleCsv(schedulePath, scheduler)) {
            std::cerr << "Error: could not write schedule file: " << schedulePath
                      << '\n';
            return 1;
        }
        std::cout << "Schedule written to: " << schedulePath << '\n';
    }
    return 0;
}
