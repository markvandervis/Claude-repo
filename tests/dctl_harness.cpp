// ============================================================================
//  dctl_harness.cpp
//  ---------------------------------------------------------------------------
//  Compiles the real Lightroom_Color_Mixer.dctl on the host through
//  dctl_shim.h and runs it over pixels supplied on stdin.
//
//  Usage:
//      dctl_harness [name=value ...]  < pixels.txt  > results.txt
//
//  Every line of stdin holds one pixel as three whitespace separated floats
//  (decimal or C99 hex float).  Every output line holds the processed pixel as
//  three hex floats, which round trips bit exactly through the test suite.
//
//  "name" is any UI parameter name from the DCTL, e.g. uiRedSat=50.
// ============================================================================

#include "dctl_shim.h"

#include <cstdlib>
#include <cstring>
#include <cstdio>

// The DCTL is included verbatim - this is what makes the harness a real syntax
// and behaviour check of the shipped file rather than a copy of it.
#include "../Lightroom_Color_Mixer.dctl"

// ---------------------------------------------------------------------------
//  Parameter binding
// ---------------------------------------------------------------------------
struct FloatParam { const char* name; float* value; };
struct IntParam   { const char* name; int*   value; };

static FloatParam g_floatParams[] = {
    { "uiGlobalSat",       &uiGlobalSat       },
    { "uiVibrance",        &uiVibrance        },
    { "uiAmount",          &uiAmount          },
    { "uiRedHue",          &uiRedHue          },
    { "uiRedSat",          &uiRedSat          },
    { "uiRedLum",          &uiRedLum          },
    { "uiOrangeHue",       &uiOrangeHue       },
    { "uiOrangeSat",       &uiOrangeSat       },
    { "uiOrangeLum",       &uiOrangeLum       },
    { "uiYellowHue",       &uiYellowHue       },
    { "uiYellowSat",       &uiYellowSat       },
    { "uiYellowLum",       &uiYellowLum       },
    { "uiGreenHue",        &uiGreenHue        },
    { "uiGreenSat",        &uiGreenSat        },
    { "uiGreenLum",        &uiGreenLum        },
    { "uiAquaHue",         &uiAquaHue         },
    { "uiAquaSat",         &uiAquaSat         },
    { "uiAquaLum",         &uiAquaLum         },
    { "uiBlueHue",         &uiBlueHue         },
    { "uiBlueSat",         &uiBlueSat         },
    { "uiBlueLum",         &uiBlueLum         },
    { "uiPurpleHue",       &uiPurpleHue       },
    { "uiPurpleSat",       &uiPurpleSat       },
    { "uiPurpleLum",       &uiPurpleLum       },
    { "uiMagentaHue",      &uiMagentaHue      },
    { "uiMagentaSat",      &uiMagentaSat      },
    { "uiMagentaLum",      &uiMagentaLum      },
    { "uiProtectNeutrals", &uiProtectNeutrals },
    { "uiPreserveLum",     &uiPreserveLum     },
    { "uiHueFalloff",      &uiHueFalloff      },
    { "uiSatProtect",      &uiSatProtect      },
};

static IntParam g_intParams[] = {
    { "uiEncoding",      &uiEncoding      },
    { "uiPreview",       &uiPreview       },
    { "uiPreviewRegion", &uiPreviewRegion },
    { "uiBypass",        &uiBypass        },
};

static bool assignParam(const char* name, const char* value)
{
    for (unsigned i = 0; i < sizeof(g_floatParams) / sizeof(g_floatParams[0]); ++i)
        if (strcmp(name, g_floatParams[i].name) == 0)
        {
            *g_floatParams[i].value = strtof(value, 0);
            return true;
        }

    for (unsigned i = 0; i < sizeof(g_intParams) / sizeof(g_intParams[0]); ++i)
        if (strcmp(name, g_intParams[i].name) == 0)
        {
            *g_intParams[i].value = (int)strtol(value, 0, 10);
            return true;
        }

    return false;
}

int main(int argc, char** argv)
{
    for (int i = 1; i < argc; ++i)
    {
        char buffer[256];
        snprintf(buffer, sizeof(buffer), "%s", argv[i]);

        char* eq = strchr(buffer, '=');
        if (!eq)
        {
            fprintf(stderr, "harness: bad argument '%s' (expected name=value)\n", argv[i]);
            return 2;
        }
        *eq = '\0';

        if (!assignParam(buffer, eq + 1))
        {
            fprintf(stderr, "harness: unknown parameter '%s'\n", buffer);
            return 2;
        }
    }

    char line[512];
    while (fgets(line, sizeof(line), stdin))
    {
        char* cursor = line;
        while (*cursor == ' ' || *cursor == '\t') ++cursor;
        if (*cursor == '\0' || *cursor == '\n' || *cursor == '#') continue;

        char* end = 0;
        float r = strtof(cursor, &end); cursor = end;
        float g = strtof(cursor, &end); cursor = end;
        float b = strtof(cursor, &end);

        float3 out = transform(1920, 1080, 0, 0, r, g, b);
        printf("%a %a %a\n", (double)out.x, (double)out.y, (double)out.z);
    }

    return 0;
}
