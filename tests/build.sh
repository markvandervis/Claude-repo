#!/bin/sh
# Builds the host test harness around the real DCTL source.
# Warnings are treated as errors so that anything questionable in the DCTL
# (implicit conversions, unused results, dubious parentheses) fails the build.
set -e
cd "$(dirname "$0")"
${CXX:-g++} -std=c++11 -O2 -Wall -Wextra -Wno-unused-parameter -Werror \
    -o dctl_harness dctl_harness.cpp
echo "built tests/dctl_harness"
