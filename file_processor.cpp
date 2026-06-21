#include "file_processor.h"
#include "logger.h"
#include <chrono>
#include <string>
#include <iostream>
#include <fstream>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <mutex>
#include <thread>
#include <future>
#include <vector>
using namespace std;

static const size_t CHUNK_SIZE = 4 * 1024 * 1024;

static string to_lower(const string& str) {
    string lower_str = str;
    transform(lower_str.begin(), lower_str.end(), lower_str.begin(), [](unsigned char c) { return tolower(c); } );
    return lower_str;
}

static string replace_all(string source, const string& from, const string& to)
{
    string new_string;
    new_string.reserve(source.length());
    string::size_type last_pos = 0;
    string::size_type find_pos;

    while((find_pos = source.find(from, last_pos)) != string::npos)
    {
        new_string.append(source, last_pos, find_pos - last_pos);
        new_string += to;
        last_pos = find_pos + from.length();
    }
    
    new_string += source.substr(last_pos);
    return new_string;
}

static size_t count_owned_matches(const string& buffer, const string& pattern, size_t owned_start, size_t owned_end, size_t buffer_offset)
{
    size_t count = 0;
    string::size_type last_pos = 0, find_pos;

    while((find_pos = buffer.find(pattern, last_pos)) != string::npos) {
        size_t match_pos = buffer_offset + find_pos;
        if(match_pos >= owned_start && match_pos < owned_end) {
            count++;
        }
        last_pos = find_pos + pattern.size();
    }

    return count;
}

static size_t search_chunk(const string& filename, size_t chunk_start, size_t chunk_end, size_t file_size, const string& pattern, bool ignore_case)
{
    size_t overlap = pattern.empty() ? 0 : pattern.size() - 1;
    size_t read_start = chunk_start;
    size_t read_end = min(chunk_end + overlap, file_size);
    size_t read_len = read_end - read_start;

    if(read_len == 0) {
        return 0;
    }

    ifstream file(filename, ios::binary);
    if(!file.is_open()) {
        return 0;
    }

    file.seekg(static_cast<streamoff>(read_start));
    string buffer(read_len, '\0');
    file.read(&buffer[0], static_cast<streamsize>(read_len));
    buffer.resize(static_cast<size_t>(file.gcount()));

    if(ignore_case) {
        buffer = to_lower(buffer);
    }

    return count_owned_matches(buffer, pattern, chunk_start, chunk_end, read_start);
}

void log_consumer(LogQueue& queue)
{
    LogEntry entry;
    while(queue.wait_and_pop(entry)) {
        if(entry.is_error) {
            Logger::getInstance().logError(entry.message);
        } else {
            Logger::getInstance().log(entry.message);
        }
    }
}

void worker(const Config& config, Shared& data)
{
    string file;
    while(data.work_queue.wait_and_pop(file)) {
        try {
            execute_search(file, config, data);
        }
        catch (const exception& e) {
            data.log_queue.push("Error processing file " + file + ": " + e.what(), true);
        }
    }
}

void execute_search(const string& filename, const Config& config, Shared& data) {
    auto start = chrono::high_resolution_clock::now();

    ifstream size_check(filename, ios::binary | ios::ate);
    if(!size_check.is_open()) {
        data.log_queue.push("Warning: Could not open file " + filename, true);
        return;
    }

    size_t file_size = static_cast<size_t>(size_check.tellg());
    size_check.close();

    string pattern = config.ignore_case ? to_lower(config.pattern) : config.pattern;
    size_t count = 0;

    if(file_size == 0) {
        count = 0;
    } else {
        size_t num_chunks = max(static_cast<size_t>(1), (file_size + CHUNK_SIZE - 1) / CHUNK_SIZE);
        vector<future<size_t>> futures;

        for(size_t i = 0; i < num_chunks; ++i) {
            size_t chunk_start = i * CHUNK_SIZE;
            size_t chunk_end = min(chunk_start + CHUNK_SIZE, file_size);
            futures.push_back(async(launch::async, search_chunk, filename, chunk_start, chunk_end, file_size, pattern, config.ignore_case));
        }

        for(auto& future : futures) {
            count += future.get();
        }
    }

    auto end = chrono::high_resolution_clock::now();
    auto duration = chrono::duration_cast<chrono::milliseconds>(end - start).count();

    std::unique_lock<std::shared_mutex> data_lock(data.data_mtx);
    data.total_occ += count;
    data_lock.unlock();
    
    data.log_queue.push("Found " + to_string(count) + " occurrences in " + filename);
    data.log_queue.push("Processed " + filename + " in " + to_string(duration) + " ms");
}


void execute_replace(const string& filename, const Config& config)
{
    ifstream infile(filename);
    if(!infile.is_open())
    {
        Logger::getInstance().logError("Warning: Could not open file for reading: " + filename);
        return;
    }

    string temp_filename = filename + ".tmp";
    ofstream outfile(temp_filename);

    if(!outfile.is_open())
    {
        Logger::getInstance().logError("Error: Could not create temporary file for writing.");
        return;
    }

    string line;
    bool changed = false;

    while(getline(infile, line))
    {
        if(line.find(config.pattern) != string::npos)
        {
            string modified = replace_all(line, config.pattern, config.replacement);
            outfile << modified << endl;
            changed = true;
        } else {
            outfile << line << endl;
        }
    }

    infile.close();
    outfile.close();

    if(changed)
    {
        if(remove(filename.c_str()) != 0)
        {
            Logger::getInstance().logError("Error: Could not remove original file.");
            return;
        }
        
        if(rename(temp_filename.c_str(), filename.c_str()) != 0)
        {
            Logger::getInstance().logError("Error: Could not rename temporary file.");
        }
        else
        {
            Logger::getInstance().log("Replaced matches in: " + filename);
        }
    } else {
        remove(temp_filename.c_str());
        Logger::getInstance().log("No matches found in: " + filename);
    }
}
