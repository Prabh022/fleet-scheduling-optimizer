#ifndef VEHICLE_H
#define VEHICLE_H

#include <string>

// A single vehicle in the fleet, as loaded from vehicles.csv.
// All times are minutes since midnight (e.g. 06:00 -> 360).
struct Vehicle {
    std::string id;
    std::string type;      // "van", "truck", or "car"
    int capacity = 0;      // maximum load the vehicle can carry (generic units)
    int shiftStart = 0;    // minutes since midnight
    int shiftEnd = 0;      // minutes since midnight
    std::string homeZone;  // zone where the vehicle starts and ends its day

    // Length of the working day in minutes.
    int shiftMinutes() const;
    // True if this vehicle can physically take a job needing the given
    // vehicle type and minimum capacity.
    bool canServe(const std::string& requiredType, int minCapacity) const;
};

#endif  // VEHICLE_H
