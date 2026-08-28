/* Portability check: compile Lightroom_Color_Mixer.dctl as C99.
 *
 * Resolve translates a DCTL into CUDA C, OpenCL C or Metal, none of which are
 * C++.  Building the same file once as C99 catches anything that only a C++
 * compiler would accept - references, default arguments, declarations that
 * depend on C++ name lookup, struct tags used as bare type names, and so on.
 *
 * The result is not run; compiling it clean is the whole point. */

#include "dctl_shim.h"
#include "../Lightroom_Color_Mixer.dctl"

float3 dctl_c_check_call(float r, float g, float b);

float3 dctl_c_check_call(float r, float g, float b)
{
    return transform(1920, 1080, 0, 0, r, g, b);
}
