/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef DN2_MACHINES_H
#define DN2_MACHINES_H
#include <stdint.h>

/* machines-dn2 0.1: contribute a pointer to dn2_synths. IDs 5..31 are
 * permanent across builds; never derive them from load order or reuse them
 * for a different mod. clone is 0=FM TONE, 1=WAVETONE, 2=FM DRUM, 3=SWARMER.
 * Names are ASCII (31 characters), labels at most 7. Requires core 0.2. */
struct dn2_synth {
    uint32_t id, clone;
    const char *name, *label;
};
#endif
