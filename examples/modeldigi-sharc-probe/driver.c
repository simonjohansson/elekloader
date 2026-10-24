/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "oscillator.h"

modeldigi_osc_state scenario_state;
/* ModelDigi tools/cost/driver.c scenario 0, including the muted voices' state. */
modeldigi_osc_params scenario_params = {
    .frequency_q16_16 = {220u * 65536u, 330u * 65536u + 32768u,
                         441u * 65536u + 16384u},
    .waveform = {3, 4, 6},
    .level = {65535, 0, 0},
};
int32_t scenario_output[64];

void scenario(void)
{
    modeldigi_osc_init(&scenario_state);
    modeldigi_osc_render(&scenario_state, &scenario_params, scenario_output, 32);
}

void scenario_split(void)
{
    modeldigi_osc_init(&scenario_state);
    modeldigi_osc_render(&scenario_state, &scenario_params, scenario_output, 16);
    modeldigi_osc_render(&scenario_state, &scenario_params, scenario_output + 16, 16);
}

void scenario_bounds(void)
{
    scenario_params.frequency_q16_16[0] = 0;
    scenario_params.frequency_q16_16[1] = 20001u * 65536u;
    scenario_params.frequency_q16_16[2] = 12345u * 65536u;
    scenario_params.waveform[0] = 9;
    scenario_params.waveform[1] = 6;
    scenario_params.waveform[2] = 1;
    scenario_params.modulation_depth_q16_16 = 200000;
    modeldigi_osc_init(&scenario_state);
    modeldigi_osc_render(&scenario_state, &scenario_params, scenario_output, 32);
}

void scenario_toggle(void)
{
    modeldigi_osc_init(&scenario_state);
    scenario_params.analog = true;
    modeldigi_osc_render(&scenario_state, &scenario_params, scenario_output, 16);
    scenario_params.analog = false;
    modeldigi_osc_render(&scenario_state, &scenario_params, scenario_output + 16, 16);
    scenario_params.analog = true;
    modeldigi_osc_render(&scenario_state, &scenario_params, scenario_output + 32, 16);
}

#ifdef HOST
#include <stdio.h>
#include <string.h>
int main(int argc, char **argv)
{
    size_t frames = 32;
    if (argc > 1 && !strcmp(argv[1], "split")) scenario_split();
    else if (argc > 1 && !strcmp(argv[1], "bounds")) scenario_bounds();
    else if (argc > 1 && !strcmp(argv[1], "toggle")) { scenario_toggle(); frames = 48; }
    else scenario();
    if (fwrite(scenario_output, sizeof(int32_t), frames, stdout) != frames ||
        fwrite(&scenario_state, sizeof scenario_state, 1, stdout) != 1 ||
        fwrite(&scenario_params, sizeof scenario_params, 1, stdout) != 1)
        return 1;
    return 0;
}
#endif
