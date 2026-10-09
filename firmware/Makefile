# Host build: the simulator and the tests. No STM32 toolchain required.
#
#   make            build ct_sim and the test binaries
#   make test       run every test suite
#   make demo       a short MOSFET sweep to stdout
#   make clean
#
# The STM32 build is a CubeIDE project under stm32/; see README.md.

CC      ?= cc
CFLAGS  ?= -std=c11 -O1 -g -Wall -Wextra -Wpedantic -Wshadow \
           -Wconversion -Wno-sign-conversion -Werror
INCS     = -Icore -Isim
LDLIBS   = -lm

BUILD    = build

CORE_SRC = core/ct_fmt.c core/ct_params.c core/ct_csv.c core/ct_sweep.c core/ct_hold.c core/ct_cmd.c
SIM_SRC  = sim/ct_sim_device.c

TESTS    = test_sweep test_csv test_params test_hold
TEST_BIN = $(addprefix $(BUILD)/,$(TESTS))

.PHONY: all test demo clean

all: $(BUILD)/ct_sim $(TEST_BIN)

$(BUILD):
	@mkdir -p $(BUILD)

$(BUILD)/ct_sim: $(CORE_SRC) $(SIM_SRC) sim/main_sim.c | $(BUILD)
	$(CC) $(CFLAGS) $(INCS) -o $@ $^ $(LDLIBS)

$(BUILD)/test_%: tests/test_%.c $(CORE_SRC) $(SIM_SRC) | $(BUILD)
	$(CC) $(CFLAGS) $(INCS) -Itests -o $@ $^ $(LDLIBS)

test: $(TEST_BIN)
	@fail=0; \
	for t in $(TEST_BIN); do \
	    ./$$t || fail=1; \
	    echo ""; \
	done; \
	if [ $$fail -eq 0 ]; then \
	    echo "all suites passed"; \
	else \
	    echo "FAILURES"; exit 1; \
	fi

demo: $(BUILD)/ct_sim
	@printf 'SET n 12\nSET vgs_list 2.5,3.0,3.5\nSET vds_max 5\nSWEEP\n' \
	    | ./$(BUILD)/ct_sim --dut mosfet

clean:
	rm -rf $(BUILD)
