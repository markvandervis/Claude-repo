// ============================================================================
//  sg_harness.cpp
//  ---------------------------------------------------------------------------
//  Compiles the real MC_Skin-Guard-v1.0.dctl on the host through sg_shim.h
//  and runs it over a frame supplied on stdin.
//
//  Usage:
//      sg_harness [name=value ...]  < frame.txt  > result.txt
//
//  stdin : first line "width height", then width * height lines of three
//          floats (decimal or C99 hex), row by row.
//  stdout: one line per pixel, three hex floats (bit exact round trip).
//
//  "name" is any UI parameter name from the DCTL, e.g. uiConsolidate=50.
// ============================================================================

#include "sg_shim.h"

#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <vector>

#include "../MC_Skin-Guard-v1.0.dctl"

struct FloatParam { const char* name; float* value; };
struct IntParam   { const char* name; int*   value; };

static FloatParam g_floatParams[] = {
    { "uiAmount",       &uiAmount       },
    { "uiHueCentre",    &uiHueCentre    },
    { "uiHueWidth",     &uiHueWidth     },
    { "uiSatLow",       &uiSatLow       },
    { "uiSatHigh",      &uiSatHigh      },
    { "uiLumaLow",      &uiLumaLow      },
    { "uiLumaHigh",     &uiLumaHigh     },
    { "uiSoftness",     &uiSoftness     },
    { "uiConsolidate",  &uiConsolidate  },
    { "uiRedness",      &uiRedness      },
    { "uiYellowGreen",  &uiYellowGreen  },
    { "uiProtect",      &uiProtect      },
    { "uiProtectWidth", &uiProtectWidth },
    { "uiNaturalSat",   &uiNaturalSat   },
    { "uiSkinSat",      &uiSkinSat      },
    { "uiDensity",      &uiDensity      },
    { "uiExposure",     &uiExposure     },
    { "uiEvenness",     &uiEvenness     },
    { "uiEvenRadius",   &uiEvenRadius   },
};

static IntParam g_intParams[] = {
    { "uiEncoding", &uiEncoding },
    { "uiShowMask", &uiShowMask },
    { "uiBypass",   &uiBypass   },
};

static bool assignParam(const char* name, const char* value)
{
    for (unsigned i = 0; i < sizeof(g_floatParams) / sizeof(g_floatParams[0]); ++i)
        if (strcmp(name, g_floatParams[i].name) == 0) { *g_floatParams[i].value = strtof(value, 0); return true; }
    for (unsigned i = 0; i < sizeof(g_intParams) / sizeof(g_intParams[0]); ++i)
        if (strcmp(name, g_intParams[i].name) == 0) { *g_intParams[i].value = (int)strtol(value, 0, 10); return true; }
    return false;
}

int main(int argc, char** argv)
{
    for (int i = 1; i < argc; ++i)
    {
        char buffer[256];
        snprintf(buffer, sizeof(buffer), "%s", argv[i]);
        char* eq = strchr(buffer, '=');
        if (!eq) { fprintf(stderr, "harness: bad argument '%s'\n", argv[i]); return 2; }
        *eq = '\0';
        if (!assignParam(buffer, eq + 1)) { fprintf(stderr, "harness: unknown parameter '%s'\n", buffer); return 2; }
    }

    int width = 0, height = 0;
    if (scanf("%d %d", &width, &height) != 2 || width <= 0 || height <= 0)
    {
        fprintf(stderr, "harness: expected 'width height' on the first line\n");
        return 2;
    }

    size_t n = (size_t)width * (size_t)height;
    std::vector<float> R(n), G(n), B(n);
    char token[3][64];
    for (size_t i = 0; i < n; ++i)
    {
        if (scanf("%63s %63s %63s", token[0], token[1], token[2]) != 3)
        {
            fprintf(stderr, "harness: short pixel data\n");
            return 2;
        }
        R[i] = strtof(token[0], 0);
        G[i] = strtof(token[1], 0);
        B[i] = strtof(token[2], 0);
    }

    g_texWidth = width;
    for (int y = 0; y < height; ++y)
        for (int x = 0; x < width; ++x)
        {
            float3 out = transform(width, height, x, y, R.data(), G.data(), B.data());
            printf("%a %a %a\n", (double)out.x, (double)out.y, (double)out.z);
        }
    return 0;
}
