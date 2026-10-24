/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Selache's 32-bit unsigned division ABI, without an external runtime object. */
#include <stdint.h>

uint32_t ___udiv32(uint32_t dividend, uint32_t divisor)
{
    uint32_t quotient = 0, remainder = 0;
    for (unsigned bit = 0; bit < 32; ++bit) {
        uint32_t carry = remainder >> 31;
        remainder = (remainder << 1) | (dividend >> 31);
        dividend <<= 1;
        quotient <<= 1;
        if (carry || remainder >= divisor) {
            remainder -= divisor;
            quotient |= 1;
        }
    }
    return quotient;
}

#ifdef HOST
#include <stdio.h>
int main(void)
{
    uint32_t x = 0x12345678u;
    for (unsigned i = 0; i < 100000; ++i) {
        x ^= x << 13; x ^= x >> 17; x ^= x << 5;
        uint32_t a = x;
        x ^= x << 13; x ^= x >> 17; x ^= x << 5;
        uint32_t b = x | 1u;
        if (___udiv32(a, b) != a / b) {
            fputs("unsigned division mismatch\n", stderr);
            return 1;
        }
    }
    return 0;
}
#endif
