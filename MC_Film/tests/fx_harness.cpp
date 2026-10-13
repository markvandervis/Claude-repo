// ============================================================================
//  fx_harness.cpp - runs MC Film Grain or MC Film Halation on the CPU.
//  Build with -DMCF_GRAIN or -DMCF_HALATION and -DMCF_DCTL="path".
//  stdin: "width height" then width*height pixels (three floats each);
//  stdout: one pixel per line as three hex floats.
// ============================================================================
#include "mcf_shim.h"
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <vector>

#include MCF_DCTL

struct FloatParam { const char* name; float* value; };
struct IntParam   { const char* name; int*   value; };

#ifdef MCF_GRAIN
static FloatParam g_f[] = {
    { "uiGrainAmount", &uiGrainAmount }, { "uiGrainSize", &uiGrainSize },
    { "uiGrainColour", &uiGrainColour }, { "uiShadowGrain", &uiShadowGrain }, { "uiSeed", &uiSeed } };
static IntParam g_i[] = { { "uiBypass", &uiBypass }, { "uiNegative", &uiNegative }, { "uiGauge", &uiGauge } };
#else
static FloatParam g_f[] = {
    { "uiHalAmount", &uiHalAmount }, { "uiHalSize", &uiHalSize },
    { "uiHalColour", &uiHalColour }, { "uiHalThreshold", &uiHalThreshold }, { "uiBloom", &uiBloom } };
static IntParam g_i[] = { { "uiBypass", &uiBypass }, { "uiInput", &uiInput }, { "uiGauge", &uiGauge },
                          { "uiSizeMode", &uiSizeMode },
                          { "uiQuality", &uiQuality } };
#endif

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
    int w = 0, h = 0;
    if (scanf("%d %d", &w, &h) != 2) return 2;
    size_t n = (size_t)w * h;
    std::vector<float> R(n), G(n), B(n);
    char t[3][64];
    for (size_t i = 0; i < n; ++i)
    {
        if (scanf("%63s %63s %63s", t[0], t[1], t[2]) != 3) return 2;
        R[i] = strtof(t[0], 0); G[i] = strtof(t[1], 0); B[i] = strtof(t[2], 0);
    }
    g_texWidth = w;
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x)
        {
#ifdef MCF_GRAIN
            size_t i = (size_t)y * w + x;
            float3 o = transform(w, h, x, y, R[i], G[i], B[i]);
#else
            float3 o = transform(w, h, x, y, R.data(), G.data(), B.data());
#endif
            printf("%a %a %a\n", (double)o.x, (double)o.y, (double)o.z);
        }
    return 0;
}
