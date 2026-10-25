/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdint.h>
#include "digitone-mk2/machines.h"

#define FIRST 5
#define COUNT 32
struct names { const char *name, *label, *hint; };
struct descriptor { const char *name, *label; uint32_t params[9]; };
struct string_rep { uint32_t length, capacity; int32_t references; char text[32]; };

extern const struct dn2_synth *const dn2_synths[];
extern const struct dn2_synth *const dn2_voice_synths[];
extern const struct names dn2_stock_names[5];
extern const uint32_t dn2_stock_permit[5];
extern const struct descriptor dn2_stock_descriptors[5];
extern const char dn2_unknown_name[], dn2_unknown_label[];

uint32_t dn2_list[COUNT], dn2_list_bytes;
static const struct dn2_synth *registered[COUNT];
static uint8_t voices[COUNT];
static struct descriptor descriptors[COUNT];
static struct string_rep strings[COUNT][2];
static uint32_t ready;

static const char *representation(struct string_rep *r, const char *s, unsigned max)
{
    unsigned n = 0;
    while (n < max && s[n]) {
        unsigned char c = s[n];
        r->text[n++] = c >= 'a' && c <= 'z' ? c - 'a' + 'A' : c;
    }
    r->text[n] = 0;
    r->length = r->capacity = n;
    r->references = -1;             /* Stock std::string must not free this representation. */
    return r->text;
}

void dn2_ensure(void)
{
    if (ready)
        return;
    const struct dn2_synth *const *e;
    for (unsigned voice = 0; voice < 2; ++voice)
    for (e = voice ? dn2_voice_synths : dn2_synths; *e; ++e) {
        const struct dn2_synth *s = *e;
        if (s->id < FIRST || s->id >= COUNT || s->clone > 3 || !s->name || !s->label
                || registered[s->id])
            continue;
        registered[s->id] = s;
        voices[s->id] = voice;
        descriptors[s->id] = dn2_stock_descriptors[s->clone];
        if (voice)
            for (unsigned i = 0; i < 9; ++i)
                descriptors[s->id].params[i] = 0;
        descriptors[s->id].name = representation(&strings[s->id][0], s->name, 31);
        descriptors[s->id].label = representation(&strings[s->id][1], s->label, 7);
    }
    /* Stock ordering puts FM DRUM before WAVETONE and MIDI last. */
    dn2_list[0] = 0; dn2_list[1] = 2; dn2_list[2] = 1; dn2_list[3] = 3;
    unsigned n = 4;
    for (unsigned id = FIRST; id < COUNT; ++id)
        if (registered[id])
            dn2_list[n++] = id;
    dn2_list[n++] = 4;
    dn2_list_bytes = n * 4;
    ready = 1;
}

uint32_t dn2_clone_type(uint32_t type)
{
    if (type < FIRST || type >= COUNT)
        return type;
    dn2_ensure();
    /* A missing mod keeps its saved identity, but sends MIDI's silent type to the DSP. */
    return registered[type] ? registered[type]->clone : 4;
}

uint32_t dn2_is_voice(uint32_t type)
{
    dn2_ensure();
    return type < COUNT && voices[type];
}

uint32_t dn2_dsp_type(uint32_t type)
{
    return dn2_is_voice(type) ? type : dn2_clone_type(type);
}

uintptr_t dn2_voice_page(uint32_t type, uint32_t page)
{
    if (!dn2_is_voice(type))
        return 0;
    return (uintptr_t)(page ? &dn2_stock_descriptors[4] : &descriptors[type]);
}

uintptr_t dn2_descriptor(uint32_t type)
{
    if (type < FIRST)
        return (uintptr_t)&dn2_stock_descriptors[type];
    dn2_ensure();
    return (uintptr_t)(type < COUNT && registered[type] ? &descriptors[type]
                                                      : &dn2_stock_descriptors[4]);
}

uintptr_t dn2_name(uint32_t type)
{
    if (type < FIRST)
        return (uintptr_t)dn2_stock_names[type].name;
    dn2_ensure();
    return (uintptr_t)(type < COUNT ? registered[type] ? registered[type]->name : "MISSING"
                                   : dn2_unknown_name);
}

uintptr_t dn2_label(uint32_t type)
{
    if (type < FIRST)
        return (uintptr_t)dn2_stock_names[type].label;
    dn2_ensure();
    return (uintptr_t)(type < COUNT ? registered[type] ? registered[type]->label : "MISS"
                                   : dn2_unknown_label);
}

uintptr_t dn2_hint(uint32_t type)
{
    if (type >= COUNT)
        return (uintptr_t)dn2_unknown_name;
    return (uintptr_t)dn2_stock_names[dn2_clone_type(type)].hint;
}

uint32_t dn2_permit(uint32_t type, uint32_t track)
{
    if (type >= COUNT || track >= 16)
        return 0;
    if (type >= FIRST) {
        dn2_ensure();
        /* The OS also checks this when loading a sound: rejecting it loses the saved ID.
         * Missing IDs stay out of the selector; MIDI permissions let their silent fallback load. */
        type = registered[type] ? registered[type]->clone : 4;
    }
    return ((dn2_stock_permit[type] >> 16) >> track) & 1;
}
