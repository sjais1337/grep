#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <chrono> 
#include "config.h"
#include <thread>
#include "file_processor.h"
#include "thread_safe.h"
#include "logger.h"
#include <shared_mutex>

using namespace std;

void print_usage(const string& program_name)
{
    Logger::getInstance().logError("A grep-like tool with replacing capabilities. \n");
    Logger::getInstance().logError("USAGE:");
    Logger::getInstance().logError("  " + program_name + " [OPTIONS] <pattern> <file1> [file2]...");
    Logger::getInstance().logError("  " + program_name + " [OPTIONS] -r <replacement> <pattern> <file1> [file2]...");
    Logger::getInstance().logError("OPTIONS:");
    Logger::getInstance().logError("   -r, --replace <TEXT>   Enable find-and-replace mode.");
    Logger::getInstance().logError("   -i, --ignore-case      Perform case-insensitive matching.");
    Logger::getInstance().logError("   -n, --line-number      Prefix each line of output with its line number.");
    Logger::getInstance().logError("   -v, --invert-match     Select non-matching lines.");
    Logger::getInstance().logError("   -h, --help             Display this help message.");
}

void reporter(Shared& data){
    while (true) {
        
        if(data.complete.load()) {
            break;
        }

        std::shared_lock<std::shared_mutex> lock(data.data_mtx);
        size_t total = data.total_occ;
        lock.unlock();

        data.log_queue.push("Total occurrences found so far: " + std::to_string(total)); 

        this_thread::sleep_for(chrono::milliseconds(100));
    }
}

int main(int argc, char* argv[])
{
    if(argc < 3)
    {
        print_usage(argv[0]);
        return 1;
    }

    Config config;
    vector<string> args(argv + 1, argv + argc);

    try{
        size_t i = 0;
        while(i < args.size())
        {
            const string& arg = args[i];
            if(arg == "-h" || arg == "--help")
            {
                print_usage(argv[0]);
                return 0;
            } 
            else if (arg == "-i" || arg == "--ignore-case") {
                config.ignore_case = true;
                i++;
            } 
            else if (arg == "-n" || arg == "--line-number") {
                config.line_number = true;
                i++;
            } 
            else if (arg == "-v" || arg == "--invert-match") {
                config.invert_match = true;
                i++;
            } 
            else if (arg == "-r" || arg == "--replace") {
                config.replace_mode = true;
                if(i+1 >= args.size()) 
                    throw runtime_error("Missing replacement text after " + arg);
                config.replacement = args[i+1];
                i += 2;
            } else if(arg[0] == '-')
            {
                throw runtime_error("Unknown flag: " + arg);
            }
            else {
                if(config.pattern.empty())
                {
                    config.pattern = arg;
                } else {
                    config.files.push_back(arg);
                }
                i++;
            }
        }

        if (config.pattern.empty()) throw runtime_error("Pattern not specified.");
        if (config.files.empty()) throw runtime_error("No input files specified."); 
    } 
    catch (const exception& e)
    {
        Logger::getInstance().logError("Argument Error: " + string(e.what()));
        print_usage(argv[0]);
        return 1;
    }
    
    auto start_pool = chrono::high_resolution_clock::now();
    Shared shared_data;

    thread consumer_thread(log_consumer, ref(shared_data.log_queue));
    thread reporter_thread(reporter, ref(shared_data));

    if(config.replace_mode)
    {
        for(const auto& file : config.files)
        {
            try {
                execute_replace(file, config);
            }
            catch (const exception& e)
            {
                Logger::getInstance().logError("Error processing file " + file + ": " + e.what());
            }
        }
    }
    else
    {
        size_t pool_size = thread::hardware_concurrency();
        if(pool_size == 0) {
            pool_size = 4;
        }

        vector<thread> workers;
        for(size_t i = 0; i < pool_size; ++i) {
            workers.emplace_back(worker, ref(config), ref(shared_data));
        }

        for(const auto& file : config.files)
        {
            shared_data.work_queue.push(file);
        }

        shared_data.work_queue.shutdown();

        for(auto& t : workers) {
            if(t.joinable()) {
                t.join();
            }
        }
    }

    shared_data.complete.store(true);

    if(reporter_thread.joinable()){
        reporter_thread.join();
    }

    auto end_pool = chrono::high_resolution_clock::now();
    
    chrono::duration<double, milli> elapsed = end_pool - start_pool;
    shared_data.log_queue.push("Total occurrences found: " + std::to_string(shared_data.total_occ));
    shared_data.log_queue.push("Finished processing files in " + std::to_string(elapsed.count()) + " ms.");

    shared_data.log_queue.shutdown();

    if(consumer_thread.joinable()){
        consumer_thread.join();
    }

    return 0;
}
