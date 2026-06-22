#include <chrono>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <algorithm>
#include <cctype>

using namespace std;

static string to_lower(const string& str) {
    string lower_str = str;
    transform(lower_str.begin(), lower_str.end(), lower_str.begin(), [](unsigned char c) { return tolower(c); });
    return lower_str;
}

static size_t count_matches(const string& buffer, const string& pattern)
{
    size_t count = 0;
    string::size_type last_pos = 0, find_pos;

    while((find_pos = buffer.find(pattern, last_pos)) != string::npos) {
        count++;
        last_pos = find_pos + pattern.size();
    }

    return count;
}

static size_t search_file(const string& filename, const string& pattern, bool ignore_case)
{
    ifstream file(filename, ios::binary | ios::ate);
    if(!file.is_open()) {
        return 0;
    }

    size_t file_size = static_cast<size_t>(file.tellg());
    if(file_size == 0) {
        return 0;
    }

    file.seekg(0);
    string buffer(file_size, '\0');
    file.read(&buffer[0], static_cast<streamsize>(file_size));
    buffer.resize(static_cast<size_t>(file.gcount()));

    if(ignore_case) {
        buffer = to_lower(buffer);
    }

    return count_matches(buffer, pattern);
}

int main(int argc, char* argv[])
{
    if(argc < 3) {
        cerr << "usage: sequential_baseline <pattern> <file> [file2 ...]\n";
        return 1;
    }

    string pattern = argv[1];
    bool ignore_case = false;
    vector<string> files;

    for(int i = 2; i < argc; ++i) {
        string arg = argv[i];
        if(arg == "-i") {
            ignore_case = true;
        } else {
            files.push_back(arg);
        }
    }

    if(ignore_case) {
        pattern = to_lower(pattern);
    }

    auto start = chrono::high_resolution_clock::now();
    size_t total = 0;

    for(const auto& file : files) {
        total += search_file(file, pattern, ignore_case);
    }

    auto end = chrono::high_resolution_clock::now();
    auto ms = chrono::duration_cast<chrono::microseconds>(end - start).count() / 1000.0;

    cout << "count=" << total << "\n";
    cout << "time_ms=" << ms << "\n";
    return 0;
}
