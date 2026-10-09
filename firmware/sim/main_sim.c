/* main_sim.c — the firmware's command loop and sweep engine, running on the
 * host against a modelled DUT. Reads commands on stdin, writes CSV to stdout.
 *
 * This is the same core/ code the STM32 build runs; only ct_device_t changes.
 * It exists so the Python host can be developed and the CSV contract tested
 * with no board attached.
 *
 *   echo "SWEEP" | ./ct_sim --dut mosfet
 *   printf 'SET n 20\nSET vgs_list 2.5,3.0\nSWEEP\n' | ./ct_sim
 */
/* select(), fileno() and STDIN_FILENO are POSIX, hidden by -std=c11. */
#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/time.h>
#include <unistd.h>

#include "ct_cmd.h"
#include "ct_csv.h"
#include "ct_params.h"
#include "ct_sim_device.h"

/* Stream emitted bytes to stdout, flushing on each line.
 *
 * Per-line flushing is what makes this a usable development target for the
 * Python host: a sweep's rows arrive as they are produced, exactly as they do
 * over the serial link, so the live plot can be exercised with no board
 * attached. Buffering a whole sweep and writing it at the end would deliver
 * one block and leave that path untestable.
 *
 * It also removes a failure mode. This used to stage output in a 64 KB array
 * flushed after each *input* line; a 1600-row sweep overran it, and the
 * result was a transcript with no `# end:` marker and a row cut mid-field.
 * Detectable — that is exactly what README.md tells a host to treat as a
 * failed capture — but a needless trap. There is now no buffer to overflow. */
static void stdout_sink(void *user, const char *data, uint32_t len)
{
    (void)user;
    fwrite(data, 1u, (size_t)len, stdout);
    if (memchr(data, '\n', (size_t)len) != NULL) {
        fflush(stdout);
    }
}

static void usage(void)
{
    fprintf(stderr,
        "usage: ct_sim [--dut mosfet|diode|resistor] [--noise COUNTS]\n"
        "              [--vth V] [--k A/V^2] [--lambda 1/V]\n"
        "              [--is A] [--n-diode N] [--rs OHM] [--rload OHM]\n"
        "              [--rptc OHM] [--rdiv OHM]\n"
        "\n"
        "Reads commands on stdin (ID GET SET SWEEP HOLD STOP HELP), writes CSV to\n"
        "stdout. See firmware/README.md for the wire format.\n");
}

/* HOLD ends when the host sends anything. stdin is unbuffered (see main), so
 * select() sees exactly what the parser has not yet read. A bare CR or LF is
 * consumed and ignored: it is the tail of the line that started HOLD, or a
 * blank line, which the parser would ignore anyway. EOF counts as input, so
 * a piped script that ends during a HOLD does not hang. */
static int stdin_input_pending(void *user)
{
    (void)user;
    for (;;) {
        fd_set fds;
        FD_ZERO(&fds);
        FD_SET(STDIN_FILENO, &fds);
        struct timeval tv = {0, 0};
        if (select(STDIN_FILENO + 1, &fds, NULL, NULL, &tv) <= 0) {
            return 0;
        }
        int c = fgetc(stdin);
        if (c == EOF) {
            return 1;
        }
        if (c == '\r' || c == '\n') {
            continue;
        }
        ungetc(c, stdin);
        return 1;
    }
}

int main(int argc, char **argv)
{
    ct_sim_t sim;
    ct_sim_init(&sim, CT_SIM_MOSFET);

    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        const char *v = (i + 1 < argc) ? argv[i + 1] : NULL;

        if (strcmp(a, "--help") == 0 || strcmp(a, "-h") == 0) {
            usage();
            return 0;
        } else if (strcmp(a, "--dut") == 0 && v != NULL) {
            if (strcmp(v, "mosfet") == 0) {
                ct_sim_init(&sim, CT_SIM_MOSFET);
            } else if (strcmp(v, "diode") == 0) {
                ct_sim_init(&sim, CT_SIM_DIODE);
            } else if (strcmp(v, "resistor") == 0) {
                ct_sim_init(&sim, CT_SIM_RESISTOR);
            } else {
                fprintf(stderr, "ct_sim: unknown --dut '%s'\n", v);
                return 2;
            }
            i++;
        } else if (strcmp(a, "--noise") == 0 && v != NULL) {
            sim.noise_counts = strtof(v, NULL); i++;
        } else if (strcmp(a, "--vth") == 0 && v != NULL) {
            sim.vth = strtof(v, NULL); i++;
        } else if (strcmp(a, "--k") == 0 && v != NULL) {
            sim.k = strtof(v, NULL); i++;
        } else if (strcmp(a, "--lambda") == 0 && v != NULL) {
            sim.lambda = strtof(v, NULL); i++;
        } else if (strcmp(a, "--is") == 0 && v != NULL) {
            sim.is = strtof(v, NULL); i++;
        } else if (strcmp(a, "--n-diode") == 0 && v != NULL) {
            sim.n_diode = strtof(v, NULL); i++;
        } else if (strcmp(a, "--rs") == 0 && v != NULL) {
            sim.rs = strtof(v, NULL); i++;
        } else if (strcmp(a, "--rload") == 0 && v != NULL) {
            sim.r_load = strtof(v, NULL); i++;
        } else if (strcmp(a, "--rptc") == 0 && v != NULL) {
            sim.r_ptc = strtof(v, NULL); i++;
        } else if (strcmp(a, "--rdiv") == 0 && v != NULL) {
            sim.r_div = strtof(v, NULL); i++;
        } else {
            fprintf(stderr, "ct_sim: unknown option '%s'\n", a);
            usage();
            return 2;
        }
    }

    setvbuf(stdin, NULL, _IONBF, 0);
    sim.input_fn = stdin_input_pending;

    ct_sim_set_sink(&sim, stdout_sink, NULL);
    ct_device_t dev = ct_sim_device(&sim);

    ct_params_t params;
    ct_params_defaults(&params);

    /* Name the simulated part so an archived CSV is never mistaken for a
     * bench measurement. */
    switch (sim.kind) {
    case CT_SIM_DIODE:    ct_params_set_device(&params, "sim-diode");    break;
    case CT_SIM_RESISTOR: ct_params_set_device(&params, "sim-resistor"); break;
    default:              ct_params_set_device(&params, "sim-mosfet");   break;
    }

    ct_cmd_ctx_t cmd;
    ct_cmd_init(&cmd, &dev, &params);

    int c;
    while ((c = fgetc(stdin)) != EOF) {
        ct_cmd_feed_char(&cmd, (char)c);
    }
    /* A final line with no trailing newline still runs. */
    ct_cmd_feed_char(&cmd, '\n');
    fflush(stdout);

    return 0;
}
