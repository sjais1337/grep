#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <filesystem>

static const size_t CHUNK_SIZE = 4 * 1024 * 1024;

static void write_file(const std::string& path, const std::string& content)
{
    std::ofstream out(path, std::ios::binary);
    if(!out.is_open()) {
        std::cerr << "Failed to open: " << path << "\n";
        return;
    }
    out.write(content.data(), static_cast<std::streamsize>(content.size()));
    out.close();
    std::cout << "Created " << path << " (" << content.size() << " bytes)\n";
}

static void write_padding(std::ofstream& out, size_t count, char ch = 'x')
{
    std::string pad(count, ch);
    out.write(pad.data(), static_cast<std::streamsize>(pad.size()));
}

int main()
{
    std::filesystem::create_directories("verify");

    write_file("verify/basic.txt", "hello world hello\nhello again\n");

    write_file("verify/case.txt", "Hello HELLO hello\n");

    write_file("verify/empty.txt", "");

    write_file("verify/nomatch.txt", "nothing relevant here\n");

    {
        std::ofstream out("verify/boundary.bin", std::ios::binary);
        write_padding(out, CHUNK_SIZE - 1, 'x');
        out.write("abcabc", 6);
        out.close();
        std::cout << "Created verify/boundary.bin (" << (CHUNK_SIZE - 1 + 6) << " bytes)\n";
    }

    {
        std::ofstream out("verify/multi_a.txt", std::ios::binary);
        out.write("needle needle\n", 14);
        out.close();
        std::ofstream out2("verify/multi_b.txt", std::ios::binary);
        out2.write("needle\n", 7);
        out2.close();
        std::cout << "Created verify/multi_a.txt and verify/multi_b.txt\n";
    }

    write_file("verify/replace.txt", "foo bar foo baz foo\n");

    std::cout << "Verification datasets ready in dataset/verify/\n";
    return 0;
}
