#ifndef JOB_H
#define JOB_H

#include <string>

// A single delivery/service job, as loaded from jobs.csv.
// All times are minutes since midnight.
struct Job {
    std::string id;
    std::string zone;
    int earliestStart = 0;     // may not start before this time
    int latestEnd = 0;         // must be finished by this time
    int duration = 0;          // minutes of on-site work
    std::string requiredType;  // vehicle type the job needs ("van"/"truck"/"car")
    int minCapacity = 0;       // vehicle must have at least this capacity
    int priority = 3;          // 1 = highest, 3 = lowest

    // Latest moment the job could start and still finish inside its window.
    int latestStart() const;
    // True if the job's own window is at least as long as the job itself.
    bool windowFeasible() const;
};

#endif  // JOB_H
