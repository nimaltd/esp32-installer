/*
 * Prints demo's answer, 52 when CONFIG_DEMO_BASE=50 from sdkconfig.defaults
 * won over the setting's default of 40, extra's, 7 when extra.defaults was
 * read, with the version from version.txt, and places', 11 when
 * places.defaults was read through {library}. On the linux target it then
 * ends, so CI can read what it printed. The build stops when anything 2.0.0 or
 * 2.1.0 brings did not arrive.
 */

#include <stdio.h>
#include <stdlib.h>
#include "demo.h"
#include "extra.h"
#include "places.h"
#include "sdkconfig.h"

#ifndef DEMO_FAST
#error "DEMO_FAST, from demo's installer.yml, did not reach main"
#endif

/* From extra's group placed after project(), where main's library exists. */
#ifndef EXTRA_AFTER
#error "EXTRA_AFTER, from extra's after-project group, did not reach main"
#endif

/* From extra.defaults, which extra's before-project group adds to the build. */
#if CONFIG_EXTRA_BASE != 5
#error "extra.defaults, added by extra's before-project group, was not read"
#endif

/* From places' lines under after-project, the 2.1.0 form. */
#ifndef PLACES_AFTER
#error "PLACES_AFTER, from places' after-project lines, did not reach main"
#endif

/* From places.defaults, which places' before-project lines add through {library}. */
#if CONFIG_PLACES_BASE != 9
#error "places.defaults, added by places' before-project lines through {library}, was not read"
#endif

void app_main(void)
{
    printf("demo says %d after %lld us\n", demo_answer(), (long long)demo_uptime_us());
    printf("extra says %d, version %s\n", extra_answer(), EXTRA_VERSION);
    printf("places says %d\n", places_answer());
    fflush(stdout);

#if CONFIG_IDF_TARGET_LINUX
    exit(0);
#endif
}
