// ============================================================================
//  mcf_harness.cpp - runs a real MC Film Core / Negative / Print DCTL on the CPU.
//  Usage: mcf_harness [name=value ...] < pixels.txt > result.txt
//  One pixel per line (three floats, decimal or hex); output three hex floats.
// ============================================================================
#include "mcf_shim.h"
#include <cstdlib>
#include <cstring>
#include <cstdio>

#include MCF_DCTL

struct FloatParam { const char* name; float* value; };
struct IntParam   { const char* name; int*   value; };

#include MCF_PARAMS

int main(int argc, char** argv)
{
    for (int a = 1; a < argc; ++a)
    {
        char buf[256];
        snprintf(buf, sizeof(buf), "%s", argv[a]);
        char* eq = strchr(buf, '=');
        if (!eq) { fprintf(stderr, "bad argument %s\n", argv[a]); return 2; }
        *eq = 0;
        bool ok = false;
        for (unsigned i = 0; i < sizeof(g_f) / sizeof(g_f[0]); ++i)
            if (!strcmp(buf, g_f[i].name)) { *g_f[i].value = strtof(eq + 1, 0); ok = true; }
        for (unsigned i = 0; i < sizeof(g_i) / sizeof(g_i[0]); ++i)
            if (!strcmp(buf, g_i[i].name)) { *g_i[i].value = (int)strtol(eq + 1, 0, 10); ok = true; }
        if (!ok) { fprintf(stderr, "unknown parameter %s\n", buf); return 2; }
    }
    // one pixel per line: "r g b", or "x y r g b" for a pixel position
    char line[512];
    while (fgets(line, sizeof(line), stdin))
    {
        char t[5][64];
        int n = sscanf(line, "%63s %63s %63s %63s %63s", t[0], t[1], t[2], t[3], t[4]);
        if (n < 3) continue;
        int x = 0, y = 0, k = 0;
        if (n == 5) { x = (int)strtol(t[0], 0, 10); y = (int)strtol(t[1], 0, 10); k = 2; }
        float3 o = transform(1920, 1080, x, y, strtof(t[k], 0), strtof(t[k + 1], 0), strtof(t[k + 2], 0));
        printf("%a %a %a\n", (double)o.x, (double)o.y, (double)o.z);
    }
    return 0;
}
