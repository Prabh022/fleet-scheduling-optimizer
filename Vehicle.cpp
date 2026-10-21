#include "Vehicle.h"

int Vehicle::shiftMinutes() const {
    return shiftEnd - shiftStart;
}

bool Vehicle::canServe(const std::string& requiredType, int minCapacity) const {
    return type == requiredType && capacity >= minCapacity;
}
