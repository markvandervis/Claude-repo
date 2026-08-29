// ============================================================================
//  dctl_shim.h
//  ---------------------------------------------------------------------------
//  A minimal host-side emulation of the DaVinci Resolve DCTL environment so
//  that Lightroom_Color_Mixer.dctl can be compiled *unmodified* by a normal C++
//  compiler and executed on the CPU.
//
//  This gives the test suite two things Resolve cannot easily give us:
//    * a syntax / type check of the real .dctl source (it is #included as-is),
//    * deterministic, scriptable numerical output for regression testing.
//
//  It is a test harness only - it is not needed to use the DCTL in Resolve.
//
//  The emulated surface is limited to what the DCTL actually uses:
//    __DEVICE__, __CONSTANT__, float2/float3/float4, make_floatN,
//    DEFINE_UI_PARAMS and the _-prefixed math intrinsics.
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
static inline float _exp10f(float x)                    { return powf(10.0f, x); }
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

// ---------------------------------------------------------------------------
//  Combo-box enumerations declared by the DCTL.
//  Kept in sync with Lightroom_Color_Mixer.dctl by tests/run_tests.py, which
//  parses the DCTL's DCTLUI_COMBO_BOX declarations and fails if the order or
//  the names here drift.
// ---------------------------------------------------------------------------
enum { ENC_DISPLAY = 0, ENC_LOG = 1, ENC_LINEAR = 2, ENC_DWG = 3 };
enum { PV_OFF = 0, PV_MASK = 1, PV_ISOLATE = 2 };
enum { PR_RED = 0, PR_ORANGE = 1, PR_YELLOW = 2, PR_GREEN = 3,
       PR_AQUA = 4, PR_BLUE = 5, PR_PURPLE = 6, PR_MAGENTA = 7 };
