/* ct_cmd.h — line-based text command interface, sharing the serial link with
 * CSV output. See firmware/README.md for the full reference.
 *
 *   ID                  identity
 *   GET                 dump every parameter as "# name: value"
 *   SET <name> <value>  assign; "# ok: ..." or "! err: ..."
 *   SWEEP               run a sweep, emitting a full CSV block
 *   HOLD <vds>          hold one drain level until STOP or any other input
 *   STOP                request abort (handled by the device layer)
 *   HELP                command list
 *
 * Commands are case-insensitive. Lines are terminated by CR, LF or CRLF.
 */
#ifndef CT_CMD_H
#define CT_CMD_H

#include <stddef.h>
#include <stdint.h>

#include "ct_device.h"
#include "ct_params.h"

#define CT_CMD_LINE_MAX 160u

typedef struct {
    const ct_device_t *dev;
    ct_params_t       *params;
    char               line[CT_CMD_LINE_MAX];
    size_t             len;
    int                overflow;   /* current line already too long */
} ct_cmd_ctx_t;

void ct_cmd_init(ct_cmd_ctx_t *c, const ct_device_t *dev, ct_params_t *params);

/* Feed one received character. A complete line is dispatched immediately. */
void ct_cmd_feed_char(ct_cmd_ctx_t *c, char ch);

/* Feed a buffer. */
void ct_cmd_feed(ct_cmd_ctx_t *c, const char *data, size_t len);

/* Execute one complete command line, without terminator. Exposed for tests. */
void ct_cmd_execute(ct_cmd_ctx_t *c, const char *line);

#endif /* CT_CMD_H */
