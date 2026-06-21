#include "thread_safe.h"

void LogQueue::push(const std::string& message, bool is_error)
{
    {
        std::lock_guard<std::mutex> lock(mtx_);
        queue_.push({message, is_error});
    }
    cv_.notify_one();
}

bool LogQueue::wait_and_pop(LogEntry& entry)
{
    std::unique_lock<std::mutex> lock(mtx_);
    cv_.wait(lock, [&]() {
        return !queue_.empty() || shutdown_.load();
    });

    if(queue_.empty()) {
        return false;
    }

    entry = queue_.front();
    queue_.pop();
    return true;
}

void LogQueue::shutdown()
{
    shutdown_.store(true);
    cv_.notify_all();
}

void WorkQueue::push(const std::string& file)
{
    {
        std::lock_guard<std::mutex> lock(mtx_);
        queue_.push(file);
    }
    cv_.notify_one();
}

bool WorkQueue::wait_and_pop(std::string& file)
{
    std::unique_lock<std::mutex> lock(mtx_);
    cv_.wait(lock, [&]() {
        return !queue_.empty() || shutdown_.load();
    });

    if(queue_.empty()) {
        return false;
    }

    file = queue_.front();
    queue_.pop();
    return true;
}

void WorkQueue::shutdown()
{
    shutdown_.store(true);
    cv_.notify_all();
}
