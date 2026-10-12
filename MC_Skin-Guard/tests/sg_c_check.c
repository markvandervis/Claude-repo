/* Portability check: compile MC_Skin-Guard-v1.0.dctl as C99.  Resolve builds a
 * DCTL as CUDA C, OpenCL C or Metal, none of which is C++, so C++-only
 * constructs (references, overloads, default arguments) must not creep in. */
#include "sg_shim.h"
#include "../MC_Skin-Guard-v1.0.dctl"

float3 sg_c_check_entry(int w, int h, int x, int y, const float* r, const float* g, const float* b)
{
    return transform(w, h, x, y, r, g, b);
}
