/**
 * @file        demo.c
 * @brief       CONFIG_DEMO_BASE comes from the Kconfig esp32-installer wrote,
 *              and esp_timer from the REQUIRES it wrote.
 */

#include "demo.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

int demo_answer(void)
{
    return CONFIG_DEMO_BASE + 2;
}

int64_t demo_uptime_us(void)
{
#if CONFIG_IDF_TARGET_LINUX
    /* On the linux target esp_timer is its header and nothing more, so the
       time comes from the FreeRTOS tick. Its header is still found only
       through the REQUIRES esp32-installer wrote. */
    return (int64_t)xTaskGetTickCount() * portTICK_PERIOD_MS * 1000;
#else
    return esp_timer_get_time();
#endif
}
