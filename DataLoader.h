#ifndef DATA_LOADER_H
#define DATA_LOADER_H

#include <string>
#include <vector>

#include "Job.h"
#include "Vehicle.h"

// "HH:MM" -> minutes since midnight. Throws std::runtime_error on bad input.
int parseTime(const std::string& text);
// Minutes since midnight -> "HH:MM".
std::string formatTime(int minutesSinceMidnight);

// CSV loaders. Both expect a header row, which is skipped.
// vehicles.csv columns: id,type,capacity,shift_start,shift_end,home_zone
// jobs.csv columns:     id,zone,earliest_start,latest_end,duration_min,
//                       required_type,min_capacity,priority
// Throws std::runtime_error if the file cannot be opened or a row is malformed.
std::vector<Vehicle> loadVehicles(const std::string& path);
std::vector<Job> loadJobs(const std::string& path);

#endif  // DATA_LOADER_H
