// ============================================================================
//  mcf_shim.h
//  ---------------------------------------------------------------------------
//  A minimal host-side emulation of the DaVinci Resolve DCTL environment so
//  that MC Film DCTLs can be compiled *unmodified* by a normal C or
//  C++ compiler and executed on the CPU.  Test harness only - not needed to use
//  the DCTL in Resolve.
//
//  Emulated: __DEVICE__, __CONSTANT__, __TEXTURE__ / _tex2D, float2/3/4,
//  DEFINE_UI_PARAMS, DEFINE_UI_TOOLTIP and the _-prefixed math intrinsics.
//  _exp10f is deliberately NOT provided: it is not available on every Resolve
//  backend, so a DCTL that uses it must fail to build here.
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

// Combo-box enumerations: generated from the stock lists by the test suite.
#include "mcf_enums.h"
