#pragma once 

#include "thread_safe.h"
#include "config.h"
#include <string>

void execute_search(const std::string& filename, const Config& config, Shared& data);
void execute_replace(const std::string& filename, const Config& config);
void worker(const Config& config, Shared& data);
void log_consumer(LogQueue& queue);
