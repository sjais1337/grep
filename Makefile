CXX = g++
CXXFLAGS = -std=c++17 -pthread -O2
SRCS = main.cpp file_processor.cpp logger.cpp thread_safe.cpp
TARGET = grep

.PHONY: all clean test verify-data benchmark-data

all: $(TARGET)

$(TARGET): $(SRCS)
	$(CXX) $(CXXFLAGS) $(SRCS) -o $(TARGET)

verify-data:
	$(CXX) $(CXXFLAGS) dataset/generator_verify.cpp -o dataset/generator_verify
	cd dataset && ./generator_verify

benchmark-data:
	$(CXX) $(CXXFLAGS) dataset/generator_benchmark.cpp -o dataset/generator_benchmark
	cd dataset && ./generator_benchmark

test: $(TARGET)
	python3 tests/run_tests.py

benchmark: $(TARGET)
	python3 tests/benchmark_stats.py

clean:
	rm -f $(TARGET) dataset/generator_verify dataset/generator_benchmark
