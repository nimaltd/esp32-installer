/**
 * @file        places.c
 * @brief       CONFIG_PLACES_BASE comes from places.defaults, which places'
 *              before-project lines add to the build through {library}, and
 *              places_private.h is on the include path only through {library}
 *              in its component lines.
 */

#include "places.h"
#include "places_private.h"
#include "sdkconfig.h"

int places_answer(void)
{
    return CONFIG_PLACES_BASE + PLACES_PRIVATE_TWO;
}
