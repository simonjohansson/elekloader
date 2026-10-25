/* SPDX-License-Identifier: GPL-2.0-or-later */
/* cc -std=c99 -Wall -Werror -I elekloader/sdk/include tests/test_dn2_machines.c -o /tmp/dn2-machines-test */
#include <assert.h>
#include <string.h>
#include "../mods/machines-dn2/machines.c"

const struct names dn2_stock_names[5] = {
    {"FM TONE", "FM", "tone"}, {"WAVETONE", "WT", "wave"},
    {"FM DRUM", "DRUM", "drum"}, {"SWARMER", "SW", "swarm"}, {"MIDI", "MIDI", "midi"}
};
const uint32_t dn2_stock_permit[5] = {0xffff0000, 0xaaaa0000, 0x55550000, 0xff000000, 0x00ff0000};
const struct descriptor dn2_stock_descriptors[5] = {
    {"FM TONE", "FM", {11}}, {"WAVETONE", "WT", {22}},
    {"FM DRUM", "DRUM", {33}}, {"SWARMER", "SW", {44}}, {"MIDI", "MIDI", {55}}
};
const char dn2_unknown_name[] = "unknown", dn2_unknown_label[] = "?";
static const struct dn2_synth low = {5, 0, "CLONE", "CLONE"}, high = {31, 3, "OTHER", "OTHER"};
static const struct dn2_synth bad_id = {32, 0, "BAD", "BAD"}, bad_clone = {6, 4, "BAD", "BAD"};
const struct dn2_synth *const dn2_synths[] = {
#ifndef EMPTY
    &high, &bad_id, &bad_clone, &low,
#endif
    0
};
static const struct dn2_synth sine = {7, 0, "SINE", "SINE"};
const struct dn2_synth *const dn2_voice_synths[] = {
#ifndef EMPTY
    &sine,
#endif
    0
};

int main(void)
{
    dn2_ensure();
    unsigned n = dn2_list_bytes / 4;
#ifdef EMPTY
    assert(n == 5);
    assert(dn2_clone_type(5) == 4);
    assert(!strcmp((const char *)dn2_name(5), "MISSING"));
    for (unsigned t = 0; t < 16; ++t)
        assert(dn2_permit(5, t) == dn2_permit(4, t));
    (void)low; (void)high; (void)bad_id; (void)bad_clone;
    (void)sine;
    assert(!dn2_is_voice(5) && dn2_dsp_type(5) == 4);
#else
    assert(n == 8 && dn2_list[4] == 5 && dn2_list[5] == 7 && dn2_list[6] == 31);
    assert(dn2_is_voice(7) && dn2_dsp_type(7) == 7 && dn2_clone_type(7) == 0);
    assert(!dn2_is_voice(5) && dn2_dsp_type(5) == 0);
    const struct descriptor *page = (const struct descriptor *)dn2_voice_page(7, 0);
    assert(page && !strcmp(page->name, "SINE"));
    for (unsigned i = 0; i < 9; ++i)
        assert(page->params[i] == 0);
    assert(dn2_voice_page(7, 1) == (uintptr_t)&dn2_stock_descriptors[4]);
    assert(!dn2_voice_page(5, 0) && !dn2_is_voice(32));
    assert(dn2_clone_type(5) == 0 && dn2_clone_type(31) == 3);
    assert(!strcmp((const char *)dn2_name(5), "CLONE"));
    assert(!strcmp((const char *)dn2_label(31), "OTHER"));
    assert(dn2_hint(31) == (uintptr_t)dn2_stock_names[3].hint);
    const struct descriptor *d = (const struct descriptor *)dn2_descriptor(5);
    assert(d->params[0] == 11 && !strcmp(d->name, "CLONE"));
    assert(strings[5][0].length == 5 && strings[5][0].references == -1);
    for (unsigned t = 0; t < 16; ++t)
        assert(dn2_permit(31, t) == dn2_permit(3, t));
#endif
    assert(dn2_list[0] == 0 && dn2_list[1] == 2 && dn2_list[2] == 1 && dn2_list[3] == 3);
    assert(dn2_list[n-1] == 4);
    assert(dn2_clone_type(6) == 4 && dn2_clone_type(0xffffffff) == 0xffffffff);
    assert(dn2_descriptor(6) == (uintptr_t)&dn2_stock_descriptors[4]);
    for (unsigned t = 0; t < 16; ++t)
        assert(dn2_permit(6, t) == dn2_permit(4, t));
    assert(!dn2_permit(32, 0) && !dn2_permit(5, 16) && !dn2_permit(0xffffffff, 0));
    assert(dn2_name(32) == (uintptr_t)dn2_unknown_name);
    for (unsigned id = 0; id < 5; ++id) {
        assert(dn2_descriptor(id) == (uintptr_t)&dn2_stock_descriptors[id]);
        assert(dn2_name(id) == (uintptr_t)dn2_stock_names[id].name);
        assert(dn2_clone_type(id) == id);
    }
    dn2_ensure();
    assert(dn2_list_bytes == 4*n);
    return 0;
}
