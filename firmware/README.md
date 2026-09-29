# firmware/ — STM32 curve tracer

MVP scope: **range 1 only, DC sweep, no pulsed mode, no auto-ranging.**
Target board is the **Nucleo-F303RE**. Measurement logic lives in `core/`,
which has no STM32 dependency and is tested on the host against a modelled
DUT — see [Testing without hardware](#testing-without-hardware).

```
core/    portable sweep engine, CSV writer, parameters, command parser
sim/     modelled DUT + a host binary that speaks the same protocol
tests/   C suites for the engine and format, pytest for the CSV contract
stm32/   CubeIDE project: HAL glue, peripheral init, interrupts
```

---

## The CSV contract

This section and `core/ct_csv.h` define the format. **Change them together
or not at all** — the Python host in `host/` parses what is specified here.

### Framing

One rule, which makes command responses and sweep output shareable on a
single serial link:

| First character | Meaning |
|---|---|
| `#` | metadata or informational |
| `!` | error response |
| anything else | a CSV row |

Lines end **CRLF**, so a raw serial terminal stays readable.

### A complete sweep

```
# curve-tracer csv
# schema: 1
# fw: 0.1.0
# board: nucleo-f303re
# device: 2N7000
# date: 2026-09-28T14:03:11Z
# date_src: host
# range: 1
# mode: dc
# temp_c: 31.4
# temp_src: mcu_die
# settle_us: 20
# n: 200
# oversample_n: 64
# i_limit_ma: 60.00
# vds_max: 10.000
# vgs_list: 2.500,3.000,3.500
# cal_gain_sweep: 3.320
# cal_gain_gate: 3.320
# cal_shunt_ohm: 1.000
# cal_diffamp_gain: 20.00
# cal_vdiv: 4.000
# cal_vref: 3.300
# cal_adc_full_scale: 4095
# cal_dac_full_scale: 4095
# columns: point,vgs_set_v,vds_set_v,vds_meas_v,i_meas_ma,i_acc,v_acc,range,flags
point,vgs_set_v,vds_set_v,vds_meas_v,i_meas_ma,i_acc,v_acc,range,flags
0,2.499,0.000,0.000,0.0000,0,0,1,
1,2.499,0.714,0.622,3.9890,6336,12352,1,
...
# end: ok
```

### Columns

| Column | Unit | Meaning |
|---|---|---|
| `point` | — | index within the whole sweep, across all gate steps; detects dropped lines |
| `vgs_set_v` | V | gate voltage **commanded**, after DAC quantisation |
| `vds_set_v` | V | drain voltage **commanded**, after DAC quantisation |
| `vds_meas_v` | V | drain voltage **measured** by ADC2, Kelvin-sensed at the DUT |
| `i_meas_ma` | mA | current through the shunt |
| `i_acc` | counts | **sum** of `oversample_n` raw current conversions |
| `v_acc` | counts | **sum** of `oversample_n` raw voltage conversions |
| `range` | — | always `1` in this build |
| `flags` | — | empty for a valid point; see below |

### `vds_set_v` and `vds_meas_v` are not redundant

This is the single most misread part of the format, so it is worth being
blunt about: **the two columns are different physical quantities, and their
difference is a measurement, not noise.**

- `vds_set_v` is the DAC code converted through the **nominal** gain of 3.32.
  It is what the amplifier's feedback node was *told* to produce. It contains
  no measurement at all.
- `vds_meas_v` is what **ADC2 actually read** at the DUT terminals through
  the Kelvin sense lines.

They differ because the feedback node is tapped **ahead of `R_iso`**
(blueprint §3.1), so the drop across `R_iso` (22 Ω) and the shunt burden
(1 Ω on range 1) are downstream of the loop and uncorrected:

```
delta = vds_set_v - vds_meas_v ≈ I × (R_iso + R_shunt) = I × 23 Ω
```

**At 50 mA that delta should be about 1.15 V** (blueprint §3.1), and it
should grow smoothly and monotonically with current. That makes it a useful
diagnostic:

| What you see | What it means |
|---|---|
| delta ≈ I × 23 Ω | working as designed |
| delta ≈ 0 at high current | Kelvin leads probably shorted to the force leads, or sensing the wrong node |
| delta scattered / non-monotonic | noise on ADC2, or a bad Kelvin connection |
| delta much larger than I × 23 Ω | extra series resistance — lead, socket or contact |

**Plot `vds_meas_v`, never `vds_set_v`.** The whole reason the instrument has
a four-wire sense is that the commanded value is wrong by over a volt at full
current. `vds_set_v` is retained for diagnosis and for reconstructing what
was asked for, not for plotting.

### Raw accumulators

`i_acc` and `v_acc` are the **sum** of `oversample_n` conversions, not the
mean — with the default 64 samples they span 0..262080.

They are in the format so an archived sweep survives a calibration change.
If the 3.32 gain turns out to be 3.31 on the bench, or the shunt measures
0.998 Ω, every CSV ever captured can be re-derived from the raw counts using
the `cal_*` header fields. Without them, a calibration correction would mean
re-measuring every device. Nine extra bytes a row is a cheap insurance
premium against that.

To re-derive:

```python
mean   = i_acc / oversample_n
volts  = mean / cal_adc_full_scale * cal_vref
i_ma   = volts / (cal_diffamp_gain * cal_shunt_ohm) * 1000
v_dut  = v_acc / oversample_n / cal_adc_full_scale * cal_vref * cal_vdiv
```

### The `flags` column and the current limit

**Any row with a non-empty `flags` field is not a valid measurement point.**
A host should filter on `flags == ""` by default.

Currently one flag exists, `ilimit`. When a measured current exceeds
`i_limit_ma`, the firmware — in this order, per blueprint §4:

1. zeroes the sweep DAC,
2. emits the offending point **with `flags=ilimit`**,
3. terminates both loops,
4. emits `# end: ilimit`.

The offending point is kept because it tells you *where* the DUT ran away,
which is exactly what you need to choose a lower ceiling. The ordering
matters: zeroing before emitting means the DUT is not held at an over-limit
bias for the ~5.5 ms the row takes to transmit. `tests/test_sweep.c` asserts
that ordering explicitly rather than trusting it.

### `# end:` reasons

| Reason | Meaning |
|---|---|
| `ok` | ran to completion |
| `ilimit` | aborted, firmware current limit |
| `stopped` | aborted, host sent STOP |

A transcript without an `# end:` line is **truncated** — treat it as a failed
capture, not a short sweep.

### Metadata the firmware cannot know

Two fields are host-supplied because the MCU genuinely has no way to
determine them. Both say so rather than guessing.

- **`date`** — a Nucleo has no battery-backed RTC time source. Set it with
  `SET date <ISO8601>` and the header reports `date_src: host`. Unset, it
  emits `date: unset` / `date_src: none`, and the host should stamp the file
  when saving.
- **`device`** — the firmware cannot identify what is in the socket. Defaults
  to `unknown`.

### Temperature is the MCU die, not the DUT

`temp_c` is the **STM32's internal die temperature**, labelled
`temp_src: mcu_die`. It is included because §5 asks for a temperature field,
but be clear about what it is not:

- it is **not** the DUT temperature, which is what a self-heating measurement
  needs;
- it is **not** ambient — it reads high by the MCU's own dissipation;
- the F303 has **no factory temperature calibration** (unlike L4/G4), so it is
  derived from the datasheet's *typical* V25 = 1.43 V and 4.3 mV/°C, both with
  wide tolerances. Treat it as indicative to a few degrees, not as a
  measurement.

If DC-vs-pulsed self-heating work needs real DUT temperature, that is an
external sensor, not this field.

---

## Command interface

Commands share the serial link with CSV output, are case-insensitive, and are
terminated by CR, LF or CRLF.

| Command | Effect |
|---|---|
| `ID` | firmware version, board, schema |
| `GET` | every parameter, one `# name: value` per line |
| `SET <name> <value>` | assign; replies `# ok: name=value` or `! err: ...` |
| `SWEEP` | run a sweep, emitting a full CSV block |
| `STOP` | abort a running sweep (also Ctrl-C, 0x03) |
| `HELP` | command list |

### Settable parameters

| Name | Default | Range | Notes |
|---|---|---|---|
| `settle_us` | 20 | 1 – 1000000 | blueprint §4; DUT settling dominates, not the amplifier |
| `n` | 200 | 2 – 4096 | points per gate step |
| `oversample_n` | 64 | 1 – 1024 | samples summed per reading |
| `i_limit_ma` | 60 | 0.001 – 165 | **DUT protection ceiling** |
| `vds_max` | 10.0 | 0.1 – 10.96 | ceiling is DAC full scale × 3.32 |
| `vgs_list` | `0` | 0 – 10.96, ≤16 entries | comma-separated, no spaces |
| `device` | `unknown` | ≤31 chars | no `,` `#` CR LF |
| `date` | unset | ≤31 chars | ISO 8601 from the host |

`range` is reported but **rejects writes** in this build.

**Setters reject, they never clamp.** `SET i_limit_ma 500` is an error and
leaves the old value in place; it does not silently become 165. For a DUT
protection ceiling, a silently-adjusted value is a safety bug, not a
convenience. The same applies to `vgs_list`: a malformed list leaves the
previous one entirely intact rather than partially applying.

### Example session

```
SET device 2N7000
SET date 2026-09-28T14:03:11Z
SET vgs_list 2.5,3.0,3.5,4.0
SET vds_max 8
SET i_limit_ma 55
SET n 200
SWEEP
```

---

## Testing without hardware

`core/` depends only on `core/ct_device.h`, a struct of function pointers.
Two implementations satisfy it:

- `stm32/Core/Src/ct_hal_device.c` — real DACs, ADCs and UART
- `sim/ct_sim_device.c` — a modelled DUT, with output captured to a buffer

The sweep engine cannot tell them apart, so every test below runs the
**actual firmware logic**, not a reimplementation of it.

```sh
make            # build the simulator and the test binaries
make test       # run all three C suites
make demo       # a short MOSFET sweep to stdout
pytest tests/test_csv_contract.py
```

The simulator is also a standalone tool that speaks the real protocol, so the
Python host can be developed against it with no board attached. It **streams**
— each line is written and flushed as the sweep produces it, exactly as rows
arrive over the serial link — so the host's live plot is developed and tested
against it rather than against a replayed file:

```sh
printf 'SET n 50\nSET vgs_list 2.5,3.0,3.5\nSWEEP\n' | ./build/ct_sim --dut mosfet
./build/ct_sim --dut diode --noise 8 < commands.txt > data/sim_diode.csv
```

### What the models are

| `--dut` | Model |
|---|---|
| `mosfet` | square-law with a subthreshold exponential tail; `--vth`, `--k`, `--lambda` |
| `diode` | `I = Is(exp(V/nVt) − 1)`; `--is`, `--n-diode`, `--rs` |
| `resistor` | ohmic; `--rload`. The simplest way to trip the current limit |

The simulator models the **whole signal chain**, not just the device: the
commanded voltage becomes a node voltage, the DUT draws current, that current
drops across `R_iso` and the shunt, and what remains is what ADC2 would
Kelvin-sense. So `vds_set_v` and `vds_meas_v` differ in simulation for the
same physical reason they differ on the bench, and the tests can assert the
23 Ω relationship above.

**It is a test fixture, not a circuit simulator.** No reactive elements, no
settling, no loop dynamics — sims 08–11 in `sim/` cover those. Its purpose is
to exercise the sweep engine, the CSV writer and the current limit.

### What the tests cover

| Suite | Checks |
|---|---|
| `test_sweep.c` | row counts, header ordering, **limit fires**, **DAC zeroed before emit**, STOP, settle called per point, ramp endpoints, accumulator semantics, the `vds` delta |
| `test_csv.c` | row shape, field count, float formatting and rounding, buffer-overflow safety, framing rule, CRLF, metadata presence |
| `test_params.c` | bounds rejection, `vgs_list` parsing, unit conversions, command parsing, line framing, overlong lines |
| `test_csv_contract.py` | the format as a naive Python host consumes it, **no truncation on a full-size family**, **output streams rather than arriving in one block** |

Current status: **176 C checks and 16 pytest cases, all passing.**

---

## Pin assignments

**Every pin below is a choice made while writing this firmware. The blueprint
specifies none of them. Check each against the Nucleo-F303RE pinout before
flashing.**

| Signal | Pin | Peripheral | Arduino / connector | Why this pin |
|---|---|---|---|---|
| Gate / step source | **PA4** | `DAC1_OUT1` | A2 (CN8-3) | the only DAC1 channel not on PA5 |
| Sweep source | **PA6** | `DAC2_OUT1` | D12 (CN10-13) | **avoids LD2 on PA5** — see below |
| Current sense | **PA0** | `ADC1_IN1` | A0 (CN8-1) | §4 assigns current to ADC1 |
| Voltage sense | **PC0** | `ADC2_IN6` | A5 (CN8-6) | §4 assigns voltage to ADC2; PA4–PA7 are taken |
| Serial TX | **PA2** | `USART2_TX` | ST-LINK VCP | fixed by the board |
| Serial RX | **PA3** | `USART2_RX` | ST-LINK VCP | fixed by the board |
| Die temperature | — | `ADC1_IN16` | internal | not a DUT reading |

### Why the sweep DAC is not on PA5

The obvious mapping for "two DACs" is the two channels of peripheral DAC1,
`DAC1_OUT1` on PA4 and `DAC1_OUT2` on PA5. **PA5 also drives LD2, the green
user LED, on every Nucleo-64** — the LED and its series resistor would hang
directly off the DAC output as an uncontrolled load. The F303RE has a second
DAC peripheral, so the sweep source uses `DAC2_OUT1` on PA6 instead.

**Cost:** DAC1 and DAC2 are separate peripherals and cannot perform a
synchronised dual-channel update. The DC sweep sets gate then drain
sequentially, so this costs nothing today, but it would matter if pulsed mode
is restored. Recorded in blueprint §3.5.

### "USB CDC" is the ST-LINK VCP

Blueprint §4 originally said "USB CDC virtual COM", which describes what the
*host* sees. The F303RE's native USB device peripheral (PA11/PA12) is **not
routed to a connector on a Nucleo-64** — no socket, no pull-up. The board's
VCP is the ST-LINK's, wired to USART2, and it enumerates on the PC as a USB
CDC serial port.

So the host opens an ordinary serial device at 115200, and the firmware needs
**no USB stack, no descriptors, no middleware**. Do not add USB device
middleware to this project; on this board it would have nothing to connect
to. Corrected in blueprint §4.

### Peripheral configuration

If the `.ioc` misbehaves, this table is authoritative — recreating the project
from it takes a few minutes.

| Peripheral | Setting |
|---|---|
| Clock | HSI 8 MHz → /2 → PLL ×18 → **72 MHz**, Flash latency 2 |
| | HSI not HSE: the Nucleo's 8 MHz comes from the ST-LINK MCO, absent when standalone |
| AHB / APB1 / APB2 | ÷1 / ÷2 / ÷1 → 72 / 36 / 72 MHz |
| ADC12 clock | PLL ÷1 → 72 MHz |
| ADC1, ADC2 | 12-bit, single-ended, software trigger, scan off, **601.5-cycle sampling** |
| DAC1, DAC2 | 12-bit right-aligned, trigger none, **output buffer enabled** |
| USART2 | 115200 8N1, TX+RX, RXNE and TC interrupts, priority 1 |
| TIM6 | prescaler 71 → 1 MHz free-running, for the µs delay |

Both ADCs are calibrated at startup (`HAL_ADCEx_Calibration_Start`). On the
F303 an uncalibrated ADC can sit several LSB off, which on range 1 is tens of
microamps.

---

## Timing

At 115200 baud a ~64-byte row takes **~5.5 ms** to transmit, against **~1.1 ms**
for 128 conversions (2 channels × 64 samples at 601.5 cycles). **Transmission
dominates.**

A blocking write would therefore hold the DUT at each bias point roughly five
times longer than the measurement needs — the self-heating that pulsed mode
exists to suppress. So TX is an interrupt-driven 4 KB ring buffer, and
`ct_hal_tx_pump()` is called from inside the conversion and delay loops so
transmission overlaps measurement. A 200-point sweep lands near **1.2 s**.

The ring only blocks if the host stops reading, and then only at the point
where it fills.

---

## Building

### Host (simulator and tests)

```sh
make            # gcc/clang, no dependencies beyond libm
make test
```

Built with `-Wall -Wextra -Wpedantic -Wshadow -Wconversion -Werror`.

### STM32

`stm32/` contains hand-written sources and a **hand-written `.ioc`**, not a
CubeMX export. `Drivers/` — the F3 HAL and CMSIS, tens of megabytes of vendor
code — is deliberately not vendored into this repo.

1. Open `stm32/curve-tracer.ioc` in STM32CubeIDE.
2. Let it generate `Drivers/` and the project files.
3. Add `core/` to the include path and the build (the sources reference it as
   `../../core`).
4. Build and flash.

If CubeMX rejects the `.ioc`, recreate the project from the peripheral table
above and copy in `Core/Src/main.c`, `ct_hal_device.c`, `stm32f3xx_hal_msp.c`
and `stm32f3xx_it.c`. That path is fully specified and does not depend on my
`.ioc` being right.

---

## Known limitations

- **Range 1 only.** Ranges 2 and 3 need the jumper and a `range` command.
- **No pulsed mode.** `duty_off_us` is deliberately absent from the parameter
  table rather than present and ignored.
- **No auto-ranging.**
- **No calibration storage.** The `cal_*` constants are compile-time, in
  `core/ct_config.h`. Bench calibration currently means editing and
  reflashing — though because the raw accumulators are in the CSV, past
  captures can be corrected without re-measuring.
- **Die temperature is uncalibrated** and is not a DUT reading.
- **Nothing here has run on hardware.** As of 2026-09-28 the bench is blocked
  on a lab trainer fault (`docs/characterization.md`, 2026-09-24), so every
  figure in this file comes from the host simulation or from datasheets. The
  pin assignments in particular have never been verified against a real board.
