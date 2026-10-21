#ifndef SCHEDULER_H
#define SCHEDULER_H

#include <map>
#include <string>
#include <vector>

#include "Job.h"
#include "Vehicle.h"

// Driving time in minutes between two zones (symmetric; same zone = 10 min
// of local driving). Zones not in the table fall back to 30 minutes.
int travelTimeMinutes(const std::string& fromZone, const std::string& toZone);

// One job placed on a vehicle's route, with the start/end times computed by
// the route simulation (a job starts at the later of its window opening and
// the vehicle's arrival after driving from the previous stop).
struct RouteEntry {
    Job job;
    int start = 0;
    int end = 0;
};

// Assigns jobs to vehicles in two phases:
//   1. Greedy cheapest insertion - jobs are considered highest priority
//      first (ties broken by earliest deadline); each job is inserted at
//      whichever position, on whichever suitable vehicle, adds the least
//      extra driving time while keeping the whole route feasible.
//   2. Relocation pass - for each job still unassigned, try removing one
//      already-placed job from a vehicle's route and re-placing it on a
//      different vehicle, if that frees a feasible slot for the waiting job.
// A route is feasible when every job respects its time window, the vehicle's
// type/capacity match, no two jobs overlap, and the vehicle is back in its
// home zone before its shift ends.
class Scheduler {
public:
    void setFleet(const std::vector<Vehicle>& vehicles);
    void scheduleAll(const std::vector<Job>& jobs);

    const std::vector<Vehicle>& fleet() const { return vehicles_; }
    // Computed route for one vehicle, in chronological order.
    std::vector<RouteEntry> routeFor(const std::string& vehicleId) const;
    const std::vector<Job>& unassigned() const { return unassigned_; }
    // Human-readable explanation of why a job could not be placed.
    std::string unassignedReason(const Job& job) const;
    int routeTravelMinutes(const Vehicle& vehicle) const;
    int routeServiceMinutes(const Vehicle& vehicle) const;

private:
    std::vector<Vehicle> vehicles_;
    std::map<std::string, std::vector<Job>> routes_;  // vehicle id -> jobs in visit order
    std::vector<Job> unassigned_;

    // Simulates driving the route in order. On success returns true and, if
    // entries is not null, fills it with each job's start/end times.
    bool simulate(const Vehicle& vehicle, const std::vector<Job>& route,
                  std::vector<RouteEntry>* entries) const;
    int travelMinutes(const Vehicle& vehicle, const std::vector<Job>& route) const;
    // Tries every insertion position on every suitable vehicle and applies
    // the cheapest feasible one. Returns true if the job was placed.
    bool insertBest(const Job& job);
    // Improvement-pass step: try to make room for `job` by relocating one
    // already-placed job to a different vehicle.
    bool tryRelocateFor(const Job& job);
};

#endif  // SCHEDULER_H
