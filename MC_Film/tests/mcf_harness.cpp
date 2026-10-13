// ============================================================================
//  mcf_harness.cpp - runs the real MC_Film-Core DCTL on the CPU.
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

static FloatParam g_f[] = {
    { "uiExposure", &uiExposure }, { "uiPushPull", &uiPushPull }, { "uiNegContrast", &uiNegContrast },
    { "uiPrintExposure", &uiPrintExposure }, { "uiPrinterRed", &uiPrinterRed },
    { "uiPrinterGreen", &uiPrinterGreen }, { "uiPrinterBlue", &uiPrinterBlue },
    { "uiPrintContrast", &uiPrintContrast }, { "uiFilmSat", &uiFilmSat },
    { "uiBleachStrength", &uiBleachStrength }, { "uiSilverContrast", &uiSilverContrast },
    { "uiSceneTemp", &uiSceneTemp }, { "uiSceneTint", &uiSceneTint }, { "uiLayerRed", &uiLayerRed },
    { "uiLayerGreen", &uiLayerGreen }, { "uiLayerBlue", &uiLayerBlue },
};
static IntParam g_i[] = {
    { "uiGamutCompress", &uiGamutCompress }, { "uiBypass", &uiBypass }, { "uiInput", &uiInput },
    { "uiNegative", &uiNegative }, { "uiPrint", &uiPrint }, { "uiOutput", &uiOutput },
    { "uiWhite", &uiWhite }, { "uiBleach", &uiBleach }, { "uiBleachStage", &uiBleachStage }, { "uiPreserveMid", &uiPreserveMid },
};

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
    char t[3][64];
    while (scanf("%63s %63s %63s", t[0], t[1], t[2]) == 3)
    {
        float3 o = transform(1920, 1080, 0, 0, strtof(t[0], 0), strtof(t[1], 0), strtof(t[2], 0));
        printf("%a %a %a\n", (double)o.x, (double)o.y, (double)o.z);
    }
    return 0;
}
