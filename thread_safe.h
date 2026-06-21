#pragma once
#include <shared_mutex>
#include <mutex>
#include <condition_variable>
#include <queue>
#include <string>
#include <atomic>

struct LogEntry {
    std::string message;
    bool is_error = false;
};

class LogQueue {
public:
    void push(const std::string& message, bool is_error = false);
    bool wait_and_pop(LogEntry& entry);
    void shutdown();

private:
    std::mutex mtx_;
    std::condition_variable cv_;
    std::queue<LogEntry> queue_;
    std::atomic<bool> shutdown_{false};
};

class WorkQueue {
public:
    void push(const std::string& file);
    bool wait_and_pop(std::string& file);
    void shutdown();

private:
    std::mutex mtx_;
    std::condition_variable cv_;
    std::queue<std::string> queue_;
    std::atomic<bool> shutdown_{false};
};

struct Shared {
    std::shared_mutex data_mtx;
    size_t total_occ = 0;
    std::atomic<bool> complete{false};
    LogQueue log_queue;
    WorkQueue work_queue;
};
