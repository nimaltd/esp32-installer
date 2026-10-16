/*
 * Prints demo's answer, 52 when CONFIG_DEMO_BASE=50 from sdkconfig.defaults
 * won over the setting's default of 40. On the linux target it then ends, so
 * CI can read what it printed.
 */

#include <stdio.h>
#include <stdlib.h>
#include "demo.h"
#include "sdkconfig.h"

#ifndef DEMO_FAST
#error "DEMO_FAST, from demo's installer.yml, did not reach main"
#endif

void app_main(void)
{
    printf("demo says %d after %lld us\n", demo_answer(), (long long)demo_uptime_us());
    fflush(stdout);

#if CONFIG_IDF_TARGET_LINUX
    exit(0);
#endif
}
