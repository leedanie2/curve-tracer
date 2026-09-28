#include "ct_fmt.h"

#include <string.h>

static size_t put(char *buf, size_t cap, size_t *pos, const char *src, size_t n)
{
    if (*pos + n + 1u > cap) {
        return 0u;
    }
    memcpy(buf + *pos, src, n);
    *pos += n;
    buf[*pos] = '\0';
    return n;
}

size_t ct_fmt_c(char *buf, size_t cap, size_t *pos, char c)
{
    return put(buf, cap, pos, &c, 1u);
}

size_t ct_fmt_s(char *buf, size_t cap, size_t *pos, const char *s)
{
    return put(buf, cap, pos, s, strlen(s));
}

size_t ct_fmt_u32(char *buf, size_t cap, size_t *pos, uint32_t v)
{
    char tmp[11];
    size_t n = 0u;

    if (v == 0u) {
        tmp[n++] = '0';
    }
    while (v > 0u) {
        tmp[n++] = (char)('0' + (v % 10u));
        v /= 10u;
    }
    /* tmp holds the digits reversed. */
    for (size_t i = 0u; i < n / 2u; i++) {
        char t = tmp[i];
        tmp[i] = tmp[n - 1u - i];
        tmp[n - 1u - i] = t;
    }
    return put(buf, cap, pos, tmp, n);
}

size_t ct_fmt_i32(char *buf, size_t cap, size_t *pos, int32_t v)
{
    size_t start = *pos;
    uint32_t mag;

    if (v < 0) {
        if (ct_fmt_c(buf, cap, pos, '-') == 0u) {
            return 0u;
        }
        /* Negate in unsigned space so INT32_MIN does not overflow. */
        mag = (uint32_t)0 - (uint32_t)v;
    } else {
        mag = (uint32_t)v;
    }
    if (ct_fmt_u32(buf, cap, pos, mag) == 0u) {
        *pos = start;
        buf[*pos] = '\0';
        return 0u;
    }
    return *pos - start;
}

static const uint32_t POW10[7] = {1u, 10u, 100u, 1000u, 10000u, 100000u, 1000000u};

size_t ct_fmt_f(char *buf, size_t cap, size_t *pos, float v, unsigned decimals)
{
    size_t start = *pos;
    int negative = 0;

    if (decimals > 6u) {
        decimals = 6u;
    }

    /* NaN is the only value not equal to itself. */
    if (v != v) {
        return ct_fmt_s(buf, cap, pos, "nan");
    }
    if (v < 0.0f) {
        negative = 1;
        v = -v;
    }
    /* Anything past this is beyond float's integer precision anyway, and no
     * quantity in this instrument comes close. */
    if (v > 2.0e9f) {
        return ct_fmt_s(buf, cap, pos, negative ? "-inf" : "inf");
    }

    const uint32_t scale = POW10[decimals];

    /* Split before scaling so large values keep their fractional digits. */
    uint32_t whole = (uint32_t)v;
    float frac = v - (float)whole;

    uint32_t scaled = (uint32_t)((frac * (float)scale) + 0.5f);
    if (scaled >= scale) {   /* rounding carried into the integer part */
        whole += 1u;
        scaled -= scale;
    }

    if (negative && (whole != 0u || scaled != 0u)) {
        if (ct_fmt_c(buf, cap, pos, '-') == 0u) {
            goto fail;
        }
    }
    if (ct_fmt_u32(buf, cap, pos, whole) == 0u) {
        goto fail;
    }
    if (decimals > 0u) {
        if (ct_fmt_c(buf, cap, pos, '.') == 0u) {
            goto fail;
        }
        /* Zero-pad the fraction to exactly `decimals` places. */
        for (unsigned d = decimals; d > 1u; d--) {
            if (scaled >= POW10[d - 1u]) {
                break;
            }
            if (ct_fmt_c(buf, cap, pos, '0') == 0u) {
                goto fail;
            }
        }
        if (ct_fmt_u32(buf, cap, pos, scaled) == 0u) {
            goto fail;
        }
    }
    return *pos - start;

fail:
    *pos = start;
    buf[*pos] = '\0';
    return 0u;
}

static const char *skip_spaces(const char *s)
{
    while (*s == ' ' || *s == '\t') {
        s++;
    }
    return s;
}

int ct_parse_f(const char *s, float *out)
{
    if (s == NULL || out == NULL) {
        return 0;
    }
    s = skip_spaces(s);

    int negative = 0;
    if (*s == '+' || *s == '-') {
        negative = (*s == '-');
        s++;
    }

    int any = 0;
    float whole = 0.0f;
    while (*s >= '0' && *s <= '9') {
        whole = whole * 10.0f + (float)(*s - '0');
        s++;
        any = 1;
    }
    float value = whole;
    if (*s == '.') {
        s++;
        float place = 0.1f;
        while (*s >= '0' && *s <= '9') {
            value += (float)(*s - '0') * place;
            place *= 0.1f;
            s++;
            any = 1;
        }
    }
    if (!any) {
        return 0;
    }
    s = skip_spaces(s);
    if (*s != '\0') {
        return 0;            /* trailing garbage is an error, not ignored */
    }
    *out = negative ? -value : value;
    return 1;
}

int ct_parse_u32(const char *s, uint32_t *out)
{
    if (s == NULL || out == NULL) {
        return 0;
    }
    s = skip_spaces(s);

    int any = 0;
    uint32_t v = 0u;
    while (*s >= '0' && *s <= '9') {
        uint32_t digit = (uint32_t)(*s - '0');
        if (v > (0xFFFFFFFFu - digit) / 10u) {
            return 0;        /* overflow */
        }
        v = v * 10u + digit;
        s++;
        any = 1;
    }
    if (!any) {
        return 0;
    }
    s = skip_spaces(s);
    if (*s != '\0') {
        return 0;
    }
    *out = v;
    return 1;
}
