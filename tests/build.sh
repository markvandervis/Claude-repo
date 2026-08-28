#!/bin/sh
# Builds the host test harness around the real DCTL source.
# Warnings are treated as errors so that anything questionable in the DCTL
# (implicit conversions, unused results, dubious parentheses) fails the build.
set -e
cd "$(dirname "$0")"
${CXX:-g++} -std=c++11 -O2 -Wall -Wextra -Wno-unused-parameter -Werror \
    -o dctl_harness dctl_harness.cpp
echo "built tests/dctl_harness"

# Portability check: Resolve compiles a DCTL as CUDA C / OpenCL C / Metal, none
# of which are C++, so the same source is also built once as C99.
${CC:-gcc} -std=c99 -O2 -Wall -Wextra -Wno-unused-parameter -Werror \
    -c -o /dev/null dctl_c_check.c
echo "DCTL compiles clean as C99"
