/**
 * @file        extra.c
 * @brief       CONFIG_EXTRA_BASE comes from extra.defaults, which its
 *              defaults group adds to the build, and EXTRA_OWN from its own
 *              group of CMake lines.
 */

#include "extra.h"
#include "sdkconfig.h"

#ifndef EXTRA_OWN
#error "EXTRA_OWN, from extra's own group, did not reach the library"
#endif

int extra_answer(void)
{
    return CONFIG_EXTRA_BASE + 2;
}
