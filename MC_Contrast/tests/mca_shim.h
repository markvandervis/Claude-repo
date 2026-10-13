// ============================================================================
//  mca_shim.h
//  ---------------------------------------------------------------------------
//  A minimal host-side emulation of the DaVinci Resolve DCTL environment so
//  that MC Contrast can be compiled *unmodified* by a normal C or C++
//  compiler and executed on the CPU.  Test harness only - not needed to use
//  the DCTL in Resolve.
//
//  Emulated: __DEVICE__, __CONSTANT__, float2/3/4, DEFINE_UI_PARAMS,
//  DEFINE_UI_TOOLTIP, DEFINE_LUT / APPLY_LUT (3D .cube, trilinear) and the
//  _-prefixed math intrinsics.  _exp10f is deliberately NOT provided.
// ============================================================================
#pragma once

#ifdef __cplusplus
  #include <cmath>
  #include <cstdio>
#else
  #include <math.h>
  #include <stdio.h>
#endif

// ---------------------------------------------------------------------------
//  Qualifiers
// ---------------------------------------------------------------------------
#define __DEVICE__   static inline
#define __CONSTANT__ static const

// ---------------------------------------------------------------------------
//  Vector types
// ---------------------------------------------------------------------------
// typedef form so that the same header works when the DCTL is compiled as C99
// (which is closer to what Resolve's CUDA / OpenCL backends do) as well as C++
typedef struct { float x, y; } float2;
typedef struct { float x, y, z; } float3;
typedef struct { float x, y, z, w; } float4;

static inline float2 make_float2(float x, float y)                   { float2 v; v.x=x; v.y=y; return v; }
static inline float3 make_float3(float x, float y, float z)          { float3 v; v.x=x; v.y=y; v.z=z; return v; }
static inline float4 make_float4(float x, float y, float z, float w) { float4 v; v.x=x; v.y=y; v.z=z; v.w=w; return v; }

// ---------------------------------------------------------------------------
//  Math intrinsics (names and semantics per the DCTL reference)
// ---------------------------------------------------------------------------
static inline float _fmaxf(float a, float b)            { return a > b ? a : b; }
static inline float _fminf(float a, float b)            { return a < b ? a : b; }
static inline float _clampf(float x, float a, float b)  { return x < a ? a : (x > b ? b : x); }
static inline float _saturatef(float x)                 { return _clampf(x, 0.0f, 1.0f); }
static inline float _fabs(float x)                      { return fabsf(x); }
static inline float _fmod(float a, float b)             { return fmodf(a, b); }
static inline float _powf(float a, float b)             { return powf(a, b); }
static inline float _expf(float x)                      { return expf(x); }
static inline float _exp2f(float x)                     { return exp2f(x); }
static inline float _logf(float x)                      { return logf(x); }
static inline float _log2f(float x)                     { return log2f(x); }
static inline float _log10f(float x)                    { return log10f(x); }
static inline float _sqrtf(float x)                     { return sqrtf(x); }
static inline float _rsqrtf(float x)                    { return 1.0f / sqrtf(x); }
static inline float _floor(float x)                     { return floorf(x); }
static inline float _ceil(float x)                      { return ceilf(x); }
static inline float _round(float x)                     { return roundf(x); }
static inline float _hypotf(float a, float b)           { return hypotf(a, b); }
static inline float _copysignf(float a, float b)        { return copysignf(a, b); }
static inline float _fdimf(float a, float b)            { return fdimf(a, b); }
static inline float _fmaf(float a, float b, float c)    { return fmaf(a, b, c); }
static inline float _sinf(float x)                      { return sinf(x); }
static inline float _cosf(float x)                      { return cosf(x); }
static inline float _tanf(float x)                      { return tanf(x); }
static inline float _asinf(float x)                     { return asinf(x); }
static inline float _acosf(float x)                     { return acosf(x); }
static inline float _atanf(float x)                     { return atanf(x); }
static inline float _atan2f(float a, float b)           { return atan2f(a, b); }

// ---------------------------------------------------------------------------
//  DEFINE_UI_PARAMS
//  Resolve turns each declaration into a host-controlled variable.  Here we do
//  the same: a mutable file-scope variable initialised to the DCTL's default,
//  which the harness can then overwrite.  Everything after the default value
//  (ranges, combo enumerations, labels) is discarded - the enumeration
//  constants are declared separately below so that they stay explicit and can
//  be verified against the .dctl source by the test suite.
// ---------------------------------------------------------------------------
#define DCTL_FIRST_IMPL(a, ...) a
#define DCTL_FIRST(...)         DCTL_FIRST_IMPL(__VA_ARGS__, 0)

#define DEFINE_UI_PARAMS(name, label, type, ...) DCTL_UIP_##type(name, __VA_ARGS__)

#define DCTL_UIP_DCTLUI_SLIDER_FLOAT(name, ...) static float name = (float)(DCTL_FIRST(__VA_ARGS__));
#define DCTL_UIP_DCTLUI_SLIDER_INT(name, ...)   static int   name = (int)  (DCTL_FIRST(__VA_ARGS__));
#define DCTL_UIP_DCTLUI_VALUE_BOX(name, ...)    static float name = (float)(DCTL_FIRST(__VA_ARGS__));
#define DCTL_UIP_DCTLUI_CHECK_BOX(name, ...)    static int   name = (int)  (DCTL_FIRST(__VA_ARGS__));
#define DCTL_UIP_DCTLUI_COMBO_BOX(name, ...)    static int   name = (int)  (DCTL_FIRST(__VA_ARGS__));

// Constant tables are passed to functions through __CONSTANTREF__.
#define __CONSTANTREF__ const
#define __TEXTURE__ const float*
static int g_texWidth __attribute__((unused)) = 1;
#define _tex2D(tex, x, y) ((tex)[(y) * g_texWidth + (x)])

// Tooltips are UI only.
#define DEFINE_UI_TOOLTIP(name, text)


// Combo-box enumerations
enum { MCA_DWG, MCA_ACESCCT };

// ---------------------------------------------------------------------------
//  DEFINE_LUT / APPLY_LUT: the .cube is loaded on first use from MCA_LUT_DIR
// ---------------------------------------------------------------------------
#ifndef MCA_LUT_DIR
  #define MCA_LUT_DIR "."
#endif
#include <stdlib.h>
#include <string.h>

typedef struct { const char* file; int n; float* data; } McaShimLut;

static void mca_shim_load(McaShimLut* L)
{
    char path[1024], line[512];
    snprintf(path, sizeof(path), "%s/%s", MCA_LUT_DIR, L->file);
    FILE* fh = fopen(path, "r");
    if (!fh) { fprintf(stderr, "cannot open LUT %s\n", path); exit(3); }
    int count = 0;
    while (fgets(line, sizeof(line), fh))
    {
        if (!strncmp(line, "LUT_3D_SIZE", 11))
        {
            L->n = atoi(line + 11);
            L->data = (float*)malloc(sizeof(float) * 3 * L->n * L->n * L->n);
            continue;
        }
        char c = line[0];
        if (!L->data || !((c >= '0' && c <= '9') || c == '-' || c == '.')) continue;
        float r, g, b;
        if (sscanf(line, "%f %f %f", &r, &g, &b) == 3 && count < L->n * L->n * L->n)
        {
            L->data[3 * count] = r; L->data[3 * count + 1] = g; L->data[3 * count + 2] = b;
            ++count;
        }
    }
    fclose(fh);
    if (!L->data || count != L->n * L->n * L->n) { fprintf(stderr, "bad LUT %s\n", path); exit(3); }
}

static float3 mca_shim_apply(McaShimLut* L, float r, float g, float b)
{
    if (!L->data) mca_shim_load(L);
    int n = L->n;
    float v[3] = { r, g, b }, f[3];
    int i[3];
    for (int k = 0; k < 3; ++k)
    {
        float p = (v[k] > 0.0f ? (v[k] < 1.0f ? v[k] : 1.0f) : 0.0f) * (float)(n - 1);
        i[k] = (int)floorf(p);
        if (i[k] > n - 2) i[k] = n - 2;
        f[k] = p - (float)i[k];
    }
    float o[3] = { 0.0f, 0.0f, 0.0f };
    for (int db = 0; db < 2; ++db)
        for (int dg = 0; dg < 2; ++dg)
            for (int dr = 0; dr < 2; ++dr)
            {
                float w = (dr ? f[0] : 1.0f - f[0]) * (dg ? f[1] : 1.0f - f[1]) * (db ? f[2] : 1.0f - f[2]);
                const float* q = L->data + 3 * (((i[2] + db) * n + (i[1] + dg)) * n + (i[0] + dr));
                o[0] += w * q[0]; o[1] += w * q[1]; o[2] += w * q[2];
            }
    return make_float3(o[0], o[1], o[2]);
}

#define DEFINE_LUT(name, path) static McaShimLut name = { #path, 0, 0 };
#define APPLY_LUT(r, g, b, name) mca_shim_apply(&name, (r), (g), (b))
