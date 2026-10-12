#!/bin/sh
# Builds the host test harness around the real DCTL source, warnings as errors,
# and checks that the DCTL also compiles as plain C99.
set -e
cd "$(dirname "$0")"
${CXX:-g++} -std=c++11 -O2 -Wall -Wextra -Wno-unused-parameter -Werror -o sg_harness sg_harness.cpp
${CC:-gcc} -std=c99 -O2 -Wall -Wextra -Wno-unused-parameter -Werror -c -o /dev/null sg_c_check.c
echo "built tests/sg_harness; DCTL compiles clean as C++11 and C99"
