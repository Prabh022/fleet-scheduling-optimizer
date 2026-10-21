#include "Job.h"

int Job::latestStart() const {
    return latestEnd - duration;
}

bool Job::windowFeasible() const {
    return latestStart() >= earliestStart;
}
