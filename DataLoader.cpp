#include "DataLoader.h"

#include <fstream>
#include <sstream>
#include <stdexcept>

namespace {

std::string trim(const std::string& s) {
    const std::size_t first = s.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return "";
    const std::size_t last = s.find_last_not_of(" \t\r\n");
    return s.substr(first, last - first + 1);
}

std::vector<std::string> splitCsvLine(const std::string& line) {
    std::vector<std::string> fields;
    std::stringstream ss(line);
    std::string field;
    while (std::getline(ss, field, ',')) fields.push_back(trim(field));
    return fields;
}

std::ifstream openCsv(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("could not open file: " + path);
    return in;
}

}  // namespace

int parseTime(const std::string& text) {
    const std::size_t colon = text.find(':');
    if (colon == std::string::npos)
        throw std::runtime_error("bad time value (expected HH:MM): " + text);
    const int hours = std::stoi(text.substr(0, colon));
    const int minutes = std::stoi(text.substr(colon + 1));
    if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59)
        throw std::runtime_error("time out of range: " + text);
    return hours * 60 + minutes;
}

std::string formatTime(int minutesSinceMidnight) {
    std::ostringstream out;
    out << (minutesSinceMidnight / 60 < 10 ? "0" : "") << minutesSinceMidnight / 60
        << ':' << (minutesSinceMidnight % 60 < 10 ? "0" : "") << minutesSinceMidnight % 60;
    return out.str();
}

std::vector<Vehicle> loadVehicles(const std::string& path) {
    std::ifstream in = openCsv(path);
    std::vector<Vehicle> vehicles;
    std::string line;
    std::getline(in, line);  // header
    int row = 1;
    while (std::getline(in, line)) {
        ++row;
        if (trim(line).empty()) continue;
        const auto f = splitCsvLine(line);
        if (f.size() != 6)
            throw std::runtime_error(path + " row " + std::to_string(row) +
                                     ": expected 6 columns");
        Vehicle v;
        v.id = f[0];
        v.type = f[1];
        v.capacity = std::stoi(f[2]);
        v.shiftStart = parseTime(f[3]);
        v.shiftEnd = parseTime(f[4]);
        v.homeZone = f[5];
        vehicles.push_back(v);
    }
    return vehicles;
}

std::vector<Job> loadJobs(const std::string& path) {
    std::ifstream in = openCsv(path);
    std::vector<Job> jobs;
    std::string line;
    std::getline(in, line);  // header
    int row = 1;
    while (std::getline(in, line)) {
        ++row;
        if (trim(line).empty()) continue;
        const auto f = splitCsvLine(line);
        if (f.size() != 8)
            throw std::runtime_error(path + " row " + std::to_string(row) +
                                     ": expected 8 columns");
        Job j;
        j.id = f[0];
        j.zone = f[1];
        j.earliestStart = parseTime(f[2]);
        j.latestEnd = parseTime(f[3]);
        j.duration = std::stoi(f[4]);
        j.requiredType = f[5];
        j.minCapacity = std::stoi(f[6]);
        j.priority = std::stoi(f[7]);
        jobs.push_back(j);
    }
    return jobs;
}
