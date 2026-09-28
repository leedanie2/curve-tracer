#include "ct_cmd.h"

#include <string.h>

#include "ct_csv.h"
#include "ct_fmt.h"
#include "ct_sweep.h"

static char lower(char c)
{
    return (c >= 'A' && c <= 'Z') ? (char)(c - 'A' + 'a') : c;
}

static int ieq(const char *a, const char *b)
{
    while (*a != '\0' && *b != '\0') {
        if (lower(*a) != lower(*b)) {
            return 0;
        }
        a++;
        b++;
    }
    return *a == '\0' && *b == '\0';
}

/* Split off the next whitespace-delimited token, advancing *s past it.
 * Returns NULL when the input is exhausted. Mutates the buffer. */
static char *next_token(char **s)
{
    char *p = *s;

    while (*p == ' ' || *p == '\t') {
        p++;
    }
    if (*p == '\0') {
        *s = p;
        return NULL;
    }

    char *start = p;
    while (*p != '\0' && *p != ' ' && *p != '\t') {
        p++;
    }
    if (*p != '\0') {
        *p = '\0';
        p++;
    }
    *s = p;
    return start;
}

static void ok_kv(const ct_device_t *dev, const char *key, const char *value)
{
    char   buf[CT_CSV_LINE_MAX];
    size_t pos = 0u;

    buf[0] = '\0';
    ct_fmt_s(buf, sizeof(buf), &pos, "# ok: ");
    ct_fmt_s(buf, sizeof(buf), &pos, key);
    ct_fmt_c(buf, sizeof(buf), &pos, '=');
    ct_fmt_s(buf, sizeof(buf), &pos, value);
    ct_csv_write_line(dev, buf);
}

static void ok_u32(const ct_device_t *dev, const char *key, uint32_t v)
{
    char   buf[32];
    size_t pos = 0u;

    buf[0] = '\0';
    ct_fmt_u32(buf, sizeof(buf), &pos, v);
    ok_kv(dev, key, buf);
}

static void ok_f(const ct_device_t *dev, const char *key, float v, unsigned dp)
{
    char   buf[32];
    size_t pos = 0u;

    buf[0] = '\0';
    ct_fmt_f(buf, sizeof(buf), &pos, v, dp);
    ok_kv(dev, key, buf);
}

static void info_u32(const ct_device_t *dev, const char *key, uint32_t v)
{
    char   buf[32];
    size_t pos = 0u;

    buf[0] = '\0';
    ct_fmt_u32(buf, sizeof(buf), &pos, v);
    ct_csv_write_info(dev, key, buf);
}

static void info_f(const ct_device_t *dev, const char *key, float v, unsigned dp)
{
    char   buf[32];
    size_t pos = 0u;

    buf[0] = '\0';
    ct_fmt_f(buf, sizeof(buf), &pos, v, dp);
    ct_csv_write_info(dev, key, buf);
}

void ct_cmd_init(ct_cmd_ctx_t *c, const ct_device_t *dev, ct_params_t *params)
{
    memset(c, 0, sizeof(*c));
    c->dev    = dev;
    c->params = params;
}

static void cmd_id(ct_cmd_ctx_t *c)
{
    ct_csv_write_info(c->dev, "fw", CT_FW_VERSION);
    ct_csv_write_info(c->dev, "board", CT_BOARD);
    info_u32(c->dev, "schema", (uint32_t)CT_CSV_SCHEMA);
}

static void cmd_get(ct_cmd_ctx_t *c)
{
    const ct_params_t *p = c->params;

    info_u32(c->dev, "settle_us", p->settle_us);
    info_u32(c->dev, "n", p->n);
    info_u32(c->dev, "oversample_n", p->oversample_n);
    info_f(c->dev, "i_limit_ma", p->i_limit_ma, 2u);
    info_f(c->dev, "vds_max", p->vds_max, 3u);
    info_u32(c->dev, "range", (uint32_t)p->range);
    ct_csv_write_info(c->dev, "device", p->device);
    ct_csv_write_info(c->dev, "date", p->date[0] != '\0' ? p->date : "unset");

    char   buf[CT_CSV_LINE_MAX];
    size_t pos = 0u;
    buf[0] = '\0';
    for (uint32_t i = 0u; i < p->vgs_count; i++) {
        if (i > 0u) {
            ct_fmt_c(buf, sizeof(buf), &pos, ',');
        }
        ct_fmt_f(buf, sizeof(buf), &pos, p->vgs_list[i], 3u);
    }
    ct_csv_write_info(c->dev, "vgs_list", buf);
}

static void cmd_help(ct_cmd_ctx_t *c)
{
    ct_csv_write_line(c->dev, "# commands: ID GET SET SWEEP STOP HELP");
    ct_csv_write_line(c->dev, "# set: settle_us n oversample_n i_limit_ma vds_max vgs_list device date");
    ct_csv_write_line(c->dev, "# range is fixed at 1 in this build");
}

static void cmd_set(ct_cmd_ctx_t *c, char *rest)
{
    char *name = next_token(&rest);
    if (name == NULL) {
        ct_csv_write_error(c->dev, "SET needs a name");
        return;
    }

    /* The value is the remainder of the line, trimmed. vgs_list needs this
     * because it may contain commas, though never spaces. */
    while (*rest == ' ' || *rest == '\t') {
        rest++;
    }
    size_t vlen = strlen(rest);
    while (vlen > 0u && (rest[vlen - 1u] == ' ' || rest[vlen - 1u] == '\t')) {
        rest[--vlen] = '\0';
    }
    if (vlen == 0u) {
        ct_csv_write_error(c->dev, "SET needs a value");
        return;
    }

    ct_params_t *p = c->params;
    uint32_t     u;
    float        f;

    if (ieq(name, "settle_us")) {
        if (ct_parse_u32(rest, &u) && ct_params_set_settle_us(p, u)) {
            ok_u32(c->dev, "settle_us", p->settle_us);
        } else {
            ct_csv_write_error(c->dev, "settle_us out of range (1..1000000)");
        }
    } else if (ieq(name, "n")) {
        if (ct_parse_u32(rest, &u) && ct_params_set_n(p, u)) {
            ok_u32(c->dev, "n", p->n);
        } else {
            ct_csv_write_error(c->dev, "n out of range (2..4096)");
        }
    } else if (ieq(name, "oversample_n")) {
        if (ct_parse_u32(rest, &u) && ct_params_set_oversample(p, u)) {
            ok_u32(c->dev, "oversample_n", p->oversample_n);
        } else {
            ct_csv_write_error(c->dev, "oversample_n out of range (1..1024)");
        }
    } else if (ieq(name, "i_limit_ma")) {
        if (ct_parse_f(rest, &f) && ct_params_set_ilimit_ma(p, f)) {
            ok_f(c->dev, "i_limit_ma", p->i_limit_ma, 2u);
        } else {
            ct_csv_write_error(c->dev, "i_limit_ma out of range (0.001..165)");
        }
    } else if (ieq(name, "vds_max")) {
        if (ct_parse_f(rest, &f) && ct_params_set_vds_max(p, f)) {
            ok_f(c->dev, "vds_max", p->vds_max, 3u);
        } else {
            ct_csv_write_error(c->dev, "vds_max out of range (0.1..10.96)");
        }
    } else if (ieq(name, "vgs_list")) {
        if (ct_params_set_vgs_list(p, rest)) {
            ok_u32(c->dev, "vgs_count", p->vgs_count);
        } else {
            ct_csv_write_error(c->dev, "vgs_list malformed or out of range (0..10.96, max 16)");
        }
    } else if (ieq(name, "device")) {
        if (ct_params_set_device(p, rest)) {
            ok_kv(c->dev, "device", p->device);
        } else {
            ct_csv_write_error(c->dev, "device name too long or contains , # CR LF");
        }
    } else if (ieq(name, "date")) {
        if (ct_params_set_date(p, rest)) {
            ok_kv(c->dev, "date", p->date);
        } else {
            ct_csv_write_error(c->dev, "date too long or contains , # CR LF");
        }
    } else if (ieq(name, "range")) {
        ct_csv_write_error(c->dev, "range is fixed at 1 in this build");
    } else {
        ct_csv_write_error(c->dev, "unknown parameter");
    }
}

void ct_cmd_execute(ct_cmd_ctx_t *c, const char *line)
{
    char  work[CT_CMD_LINE_MAX];
    char *rest = work;

    size_t n = strlen(line);
    if (n >= sizeof(work)) {
        n = sizeof(work) - 1u;
    }
    memcpy(work, line, n);
    work[n] = '\0';

    char *verb = next_token(&rest);
    if (verb == NULL) {
        return;                 /* blank line: no response, no error */
    }

    if (ieq(verb, "ID")) {
        cmd_id(c);
    } else if (ieq(verb, "GET")) {
        cmd_get(c);
    } else if (ieq(verb, "SET")) {
        cmd_set(c, rest);
    } else if (ieq(verb, "SWEEP")) {
        ct_sweep_status_t st;
        ct_sweep_run(c->dev, c->params, &st);
    } else if (ieq(verb, "STOP")) {
        /* Only meaningful mid-sweep, which means it is handled by the device
         * layer's abort_requested hook while ct_sweep_run is executing. */
        ct_csv_write_info(c->dev, "stop", "requested");
    } else if (ieq(verb, "HELP")) {
        cmd_help(c);
    } else {
        ct_csv_write_error(c->dev, "unknown command; try HELP");
    }
}

void ct_cmd_feed_char(ct_cmd_ctx_t *c, char ch)
{
    if (ch == '\r' || ch == '\n') {
        if (c->overflow) {
            ct_csv_write_error(c->dev, "line too long");
            c->overflow = 0;
            c->len = 0u;
            return;
        }
        c->line[c->len] = '\0';
        if (c->len > 0u) {
            ct_cmd_execute(c, c->line);
        }
        c->len = 0u;
        return;
    }

    if (c->len + 1u >= sizeof(c->line)) {
        c->overflow = 1;        /* keep discarding until the terminator */
        return;
    }
    c->line[c->len++] = ch;
}

void ct_cmd_feed(ct_cmd_ctx_t *c, const char *data, size_t len)
{
    for (size_t i = 0u; i < len; i++) {
        ct_cmd_feed_char(c, data[i]);
    }
}
