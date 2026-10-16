/**
 * @file        demo.c
 * @brief       CONFIG_DEMO_BASE comes from the Kconfig esp32-installer wrote,
 *              and esp_timer from the REQUIRES it wrote.
 */

#include "demo.h"
#include "esp_timer.h"
#include "sdkconfig.h"

int demo_answer(void)
{
    return CONFIG_DEMO_BASE + 2;
}

int64_t demo_uptime_us(void)
{
    return esp_timer_get_time();
}
