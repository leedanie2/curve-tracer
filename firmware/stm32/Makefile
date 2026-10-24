# STM32 build: the Nucleo-F303RE firmware, from the command line.
#
#   make drivers    fetch ST's HAL and CMSIS (STM32CubeF3, pinned), once
#   make            build build/curve-tracer.elf, .bin and .hex
#   make flash      copy the .bin to the Nucleo's ST-LINK drive
#   make clean
#
# Needs arm-none-eabi-gcc with newlib-nano on PATH: the Arm GNU Toolchain, or
# the copy bundled inside STM32CubeIDE (set PREFIX to its bin/ directory).
# Homebrew's arm-none-eabi-gcc formula has no C library and will not link.
#
# Project sources (Core/, ../core/) build with the same strict warnings as the
# host build and -Werror. ST's HAL builds with its own warnings left visible
# but not fatal: it is vendor code, fetched, and not edited here.

PREFIX  ?= arm-none-eabi-
CC       = $(PREFIX)gcc
OBJCOPY  = $(PREFIX)objcopy
SIZE     = $(PREFIX)size

# STM32CubeF3 v1.11.4, the firmware package the .ioc names. The tag is
# annotated; the commit is what is checked.
CUBE_URL    = https://github.com/STMicroelectronics/STM32CubeF3.git
CUBE_TAG    = v1.11.4
CUBE_COMMIT = e805a235c431db2e01cea47d795fa83d597c64af
CUBE        = STM32CubeF3
DRV         = $(CUBE)/Drivers
HAL         = $(DRV)/STM32F3xx_HAL_Driver
CMSIS_DEV   = $(DRV)/CMSIS/Device/ST/STM32F3xx

DEVICE   ?= STM32F303xE
STARTUP  ?= $(CMSIS_DEV)/Source/Templates/gcc/startup_stm32f303xe.s
LDSCRIPT ?= STM32F303RETx_FLASH.ld

MCU      = -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
DEFS     = -D$(DEVICE) -DUSE_HAL_DRIVER
INCS     = -ICore/Inc -I../core
SYSINCS  = -isystem $(HAL)/Inc -isystem $(CMSIS_DEV)/Include \
           -isystem $(DRV)/CMSIS/Include

BASE     = $(MCU) $(DEFS) -std=c11 -Os -g3 -ffunction-sections -fdata-sections
STRICT   = -Wall -Wextra -Wpedantic -Wshadow -Wconversion \
           -Wno-sign-conversion -Werror
# -nostartfiles: ST's startup file is the entry point. newlib's crt0 would
# pull in exit() and with it stdio, which this firmware never uses.
LDFLAGS  = $(MCU) -T$(LDSCRIPT) --specs=nano.specs -nostartfiles \
           -Wl,--gc-sections -Wl,-Map=$(BUILD)/curve-tracer.map \
           -Wl,--print-memory-usage

BUILD    = build

APP_SRC  = $(wildcard Core/Src/*.c) $(wildcard ../core/*.c)
HAL_MODS = hal hal_cortex hal_rcc hal_rcc_ex hal_gpio hal_dma hal_flash \
           hal_flash_ex hal_pwr hal_pwr_ex hal_adc hal_adc_ex hal_dac \
           hal_dac_ex hal_tim hal_tim_ex hal_uart hal_uart_ex hal_exti
HAL_SRC  = $(patsubst %,$(HAL)/Src/stm32f3xx_%.c,$(HAL_MODS)) \
           $(CMSIS_DEV)/Source/Templates/system_stm32f3xx.c

APP_OBJ  = $(patsubst %.c,$(BUILD)/app/%.o,$(notdir $(APP_SRC)))
HAL_OBJ  = $(patsubst %.c,$(BUILD)/hal/%.o,$(notdir $(HAL_SRC)))
ASM_OBJ  = $(BUILD)/startup.o

vpath %.c Core/Src ../core $(HAL)/Src $(CMSIS_DEV)/Source/Templates

NUCLEO_VOL ?= /Volumes/NODE_F303RE

.PHONY: all drivers flash clean

all: $(BUILD)/curve-tracer.bin $(BUILD)/curve-tracer.hex
	@$(SIZE) $(BUILD)/curve-tracer.elf

drivers:
	@if [ -d $(CUBE) ]; then echo "$(CUBE) already present"; else \
	    git clone -q --depth 1 --branch $(CUBE_TAG) --filter=blob:none \
	        --sparse $(CUBE_URL) $(CUBE) && \
	    git -C $(CUBE) sparse-checkout set Drivers/STM32F3xx_HAL_Driver \
	        Drivers/CMSIS/Device/ST/STM32F3xx Drivers/CMSIS/Include; fi
	@test "$$(git -C $(CUBE) rev-parse HEAD)" = "$(CUBE_COMMIT)" || \
	    { echo "$(CUBE) is not at $(CUBE_COMMIT)"; exit 1; }
	@echo "$(CUBE) $(CUBE_TAG) at $(CUBE_COMMIT)"

$(HAL)/Inc/stm32f3xx_hal.h:
	@echo "ST's drivers are missing: run 'make drivers' first"; exit 1

$(BUILD)/app/%.o: %.c | $(HAL)/Inc/stm32f3xx_hal.h
	@mkdir -p $(dir $@)
	$(CC) $(BASE) $(STRICT) $(INCS) $(SYSINCS) -c -o $@ $<

$(BUILD)/hal/%.o: %.c | $(HAL)/Inc/stm32f3xx_hal.h
	@mkdir -p $(dir $@)
	$(CC) $(BASE) -Wall $(INCS) $(SYSINCS) -c -o $@ $<

$(ASM_OBJ): $(STARTUP) | $(HAL)/Inc/stm32f3xx_hal.h
	@mkdir -p $(dir $@)
	$(CC) $(MCU) -x assembler-with-cpp -c -o $@ $<

$(BUILD)/curve-tracer.elf: $(APP_OBJ) $(HAL_OBJ) $(ASM_OBJ) $(LDSCRIPT)
	$(CC) $(LDFLAGS) -o $@ $(APP_OBJ) $(HAL_OBJ) $(ASM_OBJ) -lc -lm

$(BUILD)/curve-tracer.bin: $(BUILD)/curve-tracer.elf
	$(OBJCOPY) -O binary $< $@

$(BUILD)/curve-tracer.hex: $(BUILD)/curve-tracer.elf
	$(OBJCOPY) -O ihex $< $@

# The Nucleo's ST-LINK mounts as a USB drive; a .bin copied onto it is
# programmed and the board resets. No programmer software needed.
flash: $(BUILD)/curve-tracer.bin
	@test -d $(NUCLEO_VOL) || { echo "$(NUCLEO_VOL) not mounted"; exit 1; }
	cp $< $(NUCLEO_VOL)/

clean:
	rm -rf $(BUILD)
