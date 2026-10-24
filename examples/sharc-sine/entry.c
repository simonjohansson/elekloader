/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdint.h>
void sine_init(uint32_t phase_increment);
void sine_render(float *output);
void sharc_init(void) { sine_init(39370534u); }
void sharc_render(float *mono32) { sine_render(mono32); }
