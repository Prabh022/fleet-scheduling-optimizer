#include "Scheduler.h"

#include <algorithm>
#include <climits>
#include <utility>

namespace {

// Zone-to-zone driving times in minutes for the five sample zones.
// The matrix is symmetric, so only one direction of each pair is stored.
const std::pair<std::string, std::string> kZonePairs[] = {
    {"Brampton", "Mississauga"}, {"Brampton", "Etobicoke"},
    {"Brampton", "Toronto"},     {"Brampton", "Vaughan"},
    {"Mississauga", "Etobicoke"}, {"Mississauga", "Toronto"},
    {"Mississauga", "Vaughan"},  {"Etobicoke", "Toronto"},
    {"Etobicoke", "Vaughan"},    {"Toronto", "Vaughan"},
};
const int kZonePairMinutes[] = {25, 30, 45, 25, 20, 35, 40, 25, 35, 35};

}  // namespace

int travelTimeMinutes(const std::string& fromZone, const std::string& toZone) {
    if (fromZone == toZone) return 10;  // driving within one zone
    const std::size_t count = sizeof(kZonePairs) / sizeof(kZonePairs[0]);
    for (std::size_t i = 0; i < count; ++i) {
        if ((kZonePairs[i].first == fromZone && kZonePairs[i].second == toZone) ||
            (kZonePairs[i].first == toZone && kZonePairs[i].second == fromZone))
            return kZonePairMinutes[i];
    }
    return 30;  // unknown pair: conservative default
}

void Scheduler::setFleet(const std::vector<Vehicle>& vehicles) {
    vehicles_ = vehicles;
    routes_.clear();
    for (const auto& v : vehicles_) routes_[v.id] = {};
    unassigned_.clear();
}

bool Scheduler::simulate(const Vehicle& vehicle, const std::vector<Job>& route,
                         std::vector<RouteEntry>* entries) const {
    int clock = vehicle.shiftStart;
    std::string zone = vehicle.homeZone;
    std::vector<RouteEntry> computed;
    for (const auto& job : route) {
        const int arrival = clock + travelTimeMinutes(zone, job.zone);
        const int start = std::max(arrival, job.earliestStart);
        const int end = start + job.duration;
        if (end > job.latestEnd) return false;  // misses the job's time window
        computed.push_back(RouteEntry{job, start, end});
        clock = end;
        zone = job.zone;
    }
    // The vehicle must be back in its home zone before the shift ends.
    if (clock + travelTimeMinutes(zone, vehicle.homeZone) > vehicle.shiftEnd)
        return false;
    if (entries != nullptr) *entries = computed;
    return true;
}

int Scheduler::travelMinutes(const Vehicle& vehicle,
                             const std::vector<Job>& route) const {
    int total = 0;
    std::string zone = vehicle.homeZone;
    for (const auto& job : route) {
        total += travelTimeMinutes(zone, job.zone);
        zone = job.zone;
    }
    total += travelTimeMinutes(zone, vehicle.homeZone);  // drive back home
    return total;
}

bool Scheduler::insertBest(const Job& job) {
    bool found = false;
    int bestCost = INT_MAX;
    int bestEnd = INT_MAX;
    std::string bestVehicleId;
    std::vector<Job> bestRoute;

    for (const auto& vehicle : vehicles_) {
        if (!vehicle.canServe(job.requiredType, job.minCapacity)) continue;
        const std::vector<Job>& current = routes_[vehicle.id];
        const int baseTravel = travelMinutes(vehicle, current);
        for (std::size_t pos = 0; pos <= current.size(); ++pos) {
            std::vector<Job> candidate = current;
            candidate.insert(candidate.begin() + static_cast<long>(pos), job);
            std::vector<RouteEntry> entries;
            if (!simulate(vehicle, candidate, &entries)) continue;
            const int addedTravel = travelMinutes(vehicle, candidate) - baseTravel;
            const int jobEnd = entries[pos].end;
            // Cheapest insertion wins; ties go to the route that finishes
            // this job earliest (leaves the most slack for later jobs).
            if (addedTravel < bestCost ||
                (addedTravel == bestCost && jobEnd < bestEnd)) {
                found = true;
                bestCost = addedTravel;
                bestEnd = jobEnd;
                bestVehicleId = vehicle.id;
                bestRoute = candidate;
            }
        }
    }
    if (found) routes_[bestVehicleId] = bestRoute;
    return found;
}

bool Scheduler::tryRelocateFor(const Job& job) {
    for (const auto& vehicle : vehicles_) {
        if (!vehicle.canServe(job.requiredType, job.minCapacity)) continue;
        const std::vector<Job> route = routes_[vehicle.id];
        for (std::size_t i = 0; i < route.size(); ++i) {
            const Job blocker = route[i];
            const auto savedRoutes = routes_;  // restore point if this fails
            auto& mutableRoute = routes_[vehicle.id];
            mutableRoute.erase(mutableRoute.begin() + static_cast<long>(i));
            // Commit only if BOTH the waiting job and the relocated job end
            // up assigned; otherwise roll everything back.
            if (insertBest(job) && insertBest(blocker)) return true;
            routes_ = savedRoutes;
        }
    }
    return false;
}

void Scheduler::scheduleAll(const std::vector<Job>& jobs) {
    routes_.clear();
    for (const auto& v : vehicles_) routes_[v.id] = {};

    // Highest priority first; within a priority, tightest deadline first.
    std::vector<Job> order = jobs;
    std::sort(order.begin(), order.end(), [](const Job& a, const Job& b) {
        if (a.priority != b.priority) return a.priority < b.priority;
        if (a.latestEnd != b.latestEnd) return a.latestEnd < b.latestEnd;
        return a.earliestStart < b.earliestStart;
    });

    std::vector<Job> waiting;
    for (const auto& job : order) {
        if (!insertBest(job)) waiting.push_back(job);
    }

    // Improvement pass: relocate already-placed jobs to free up slots.
    // Repeat while progress is being made (bounded, the instance is small).
    for (int round = 0; round < 3 && !waiting.empty(); ++round) {
        std::vector<Job> stillWaiting;
        bool progress = false;
        for (const auto& job : waiting) {
            if (tryRelocateFor(job)) {
                progress = true;
            } else {
                stillWaiting.push_back(job);
            }
        }
        waiting = stillWaiting;
        if (!progress) break;
    }
    unassigned_ = waiting;
}

std::vector<RouteEntry> Scheduler::routeFor(const std::string& vehicleId) const {
    std::vector<RouteEntry> entries;
    for (const auto& vehicle : vehicles_) {
        if (vehicle.id == vehicleId) {
            simulate(vehicle, routes_.at(vehicleId), &entries);
            break;
        }
    }
    return entries;
}

int Scheduler::routeTravelMinutes(const Vehicle& vehicle) const {
    return travelMinutes(vehicle, routes_.at(vehicle.id));
}

int Scheduler::routeServiceMinutes(const Vehicle& vehicle) const {
    int total = 0;
    for (const auto& job : routes_.at(vehicle.id)) total += job.duration;
    return total;
}

std::string Scheduler::unassignedReason(const Job& job) const {
    bool anyOfType = false;
    bool anyWithCapacity = false;
    for (const auto& vehicle : vehicles_) {
        if (vehicle.type == job.requiredType) {
            anyOfType = true;
            if (vehicle.capacity >= job.minCapacity) anyWithCapacity = true;
        }
    }
    if (!anyOfType)
        return "no vehicle of required type '" + job.requiredType + "' in the fleet";
    if (!anyWithCapacity)
        return "no " + job.requiredType + " has the required capacity of " +
               std::to_string(job.minCapacity);
    if (!job.windowFeasible())
        return "the job's own time window is shorter than the job itself";
    return "no feasible time slot: every suitable vehicle conflicts with its "
           "shift, the job's time window, or jobs already scheduled";
}
