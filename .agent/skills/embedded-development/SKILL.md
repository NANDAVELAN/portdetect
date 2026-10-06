---
name: embedded-development
description: Use for STM32, ESP32, FreeRTOS, UART, SPI, I2C, ADC, PWM, interrupts, DMA, sensor interfacing, Raspberry Pi GPIO firmware work.
---

# Embedded Development

## Before modifying code, inspect
- Clock configuration (sources, PLL, peripheral clocks enabled)
- Pin configuration (alternate functions, pull-ups, conflicts)
- Peripheral configuration (baud, mode, prescaler, resolution)
- Interrupts (priorities, ISR length, flags cleared)
- DMA (channels, buffer size/alignment, circular vs normal, cache)
- RTOS task priorities, stack sizes, tick rate
- Shared resources and synchronization (mutex/semaphore/queue, `volatile`,
  critical sections)

## Practices
- Keep ISRs short; defer work to tasks via queues/notifications.
- Never call blocking APIs from ISRs; use `...FromISR` variants.
- Check return codes (HAL status, `esp_err_t`).
- Verify with a logic analyzer/serial log, not assumptions.
- Document pin maps and bus addresses in the repo.
- Hardware may be unavailable: state clearly what was NOT verified on-device.
