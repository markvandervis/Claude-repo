/* Portability check: the generated DCTL must also compile as plain C99. */
#include "mcf_shim.h"
#include MCF_DCTL
float3 mcf_c_check_entry(float r, float g, float b) { return transform(1, 1, 0, 0, r, g, b); }
