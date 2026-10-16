# Digitakt mk1: eight additional SRC parameters

Keep the existing eight logical values and add eight independent values on
SRC page 2, on OS 1.53 and 1.54. Page changes affect visibility, not identity.
All additions need editing, defaults, locks, both LFOs and sound/project
persistence. This is shared support for custom firmware machines.

## Scope

Change `mods/machine-pages`, its C SDK declarations, the existing native
probes and test fixtures. Keep core, existing UI3/UI3.1 machines, the public
SINE example, loader engines/checks, file schemas and dependencies unchanged.
The test consumer retains SINE's original first-page behavior and demonstrates
only the eight new values on page 2. Oscillator optimization is outside scope.
There is no compatibility layer for the abandoned two-addition experiment.

## Native identities

| Logical values | Parameter IDs | Native sound slots | LFO destinations |
|---|---|---|---|
| Existing 0–7 | 132–139 | 17–24 | 17–24 |
| New 8–14 | 164–170 | 46–52 | 46–52 |
| New 15 | 171 | 0 | virtual 53 |
| None | native LFO ID 17 | no added value | 0 |

Retain 53 native words, 162-byte runtime sounds, 106-byte processed-track
strides and existing pattern structures. Slots 46–52 are at sound +112..124;
slot 0 is at +20. The machine byte remains +126. Never access real slot 53.
Relative to `fw_voice_params`, new values use offsets 29–35 and -17.
`cm_src_value(track, index)` provides logical 0–15 after native processing.
Note locks use their separate native lane. Blank IDs stay inert.

## Descriptor and page support

Add the explicit `cm_ui5`/`cm_ui_v5` declaration without changing `cm_machine`
or existing `cm_ui`. Its 336-byte base is followed by eight 40-byte knobs,
page count/reserved bytes and page pointer: 664 bytes total, count at +656,
pages at +660. `cm_src_page` contains a title and eight logical references
0–15 or `CM_SRC_BLANK`. Extra ranges are 0..0x7f00 with declared defaults
and existing stock looks below 164. Validate metadata before registration.

Append eight 52-byte native descriptors. Descriptor consumers admit IDs below
172; the original constructor and borrowed-look UI array remain bounded at
164. The 416-byte overwrite displaces tables that must remain complete:
preserve 600 bytes from `401abeec` (1.53) / `401ac1ec` (1.54), and redirect
these native readers to the copied tables:

| Reader site (operand +2) | Copied offset |
|---|---:|
| `4007cc10` | 0 |
| `4007a136` | 64 |
| `4007a146` | 228 |
| `4007a0e2` | 228 |
| `40079796` | 392 |
| `4007a08a` | 392 |
| `4007a098` | 600 |

Keep page selection per track. Use the view's own sound for locked sounds.
Reuse native click eligibility, redraw/cache invalidation and parameter
clipboard actions so held SRC copy/clear/paste preserves the selected page.
Apply new reset defaults and popup look fallback only to the new interface;
retain existing machines' reset, popup and LFO naming behavior.

## Both LFOs

Native None can write slot 0, so skip that application for opted-in machines.
Expose virtual destination 53 through the real chooser and range hooks;
map it to processed slot 0 only when applying modulation. Preserve raw 53
in LFO state. Scope by `core_track_machine`, including when native edits
clear engine sound pointers. Keep ordinary destinations and machines intact.

The chooser needs capacity/count 54 only for opted-in machines. Its resolver
maps None to native ID 17 and virtual 53 to ID 171; its result maps ID 171
back to 53. Generic parameter ID 171 still addresses real slot 0.

## Persistence

Keep the 160-byte saved sound and existing kit/pool/project strides. New
machines write sound version 4. Pack 803 meaningful bits into 101 bytes
(+28..123, then +127..131), most-significant bit first:

- Original SRC slots 17–24: eight raw 16-bit words.
- Other native slots 1–45: 37 words of 15 bits, retaining valid fractions.
- Eight additions: eight words of 15 bits.
- Five required zero padding bits.

All 37 common native ranges are nonnegative and fit 15 bits on both releases.
Malformed negative common values encode minimum 0; invalid additions use
metadata defaults. Preserve name, tags, machine and sample fields outside
the payload. Do not modify source sounds.

At save, the LFO hooks substitute None before native permutation lookups,
then the common wrapper packs original values after native success. At load,
validate version 4 before the native version gate; decode into private stack
buffers and stage a native version-3 record with both destinations None.
Use the native loader for metadata, then restore all 53 meaningful words on
success. Seed temporary output from the caller to preserve native-unwritten
bytes +129..133. Preserve native return values, registers, stack and failure
behavior. The standalone upgrader narrowly recognizes valid version 4 for
these machines; ordinary native upgrade/rejection behavior stays intact.

Native version-3 sounds retain their original eight values and default all
eight additions. Ordinary machines keep native version-3 saving/loading.
Added pattern locks need bypasses for native slots 46–52; slot 0 retains its
native permutation. Preserve ordinary/MIDI mappings and the 79-lane capacity.
Stock compatibility is outside the custom-machine contract.

## Validation

Use existing high-level probes for both OS releases:

1. Register eight values, edit/default them independently, preserve native
   tables and reject invalid extension metadata.
2. Apply/restore locks, preserve note locks, exercise both LFOs through None
   and the last addition, including null engine pointers.
3. Round-trip distinct values through sounds, mixed kits/pools and patterns;
   preserve original words, valid fractions and metadata; verify guards and
   native calling conventions.
4. Boot the final image, edit all eight controls, use held page actions and
   locks, save through menus, discard RAM snapshots and cold-reload a project.
5. Demonstrate eight independent audible effects in the test consumer.

Run unit tests, available SDK checks and build/lint/patch verification.
Missing fixtures are skipped, not passed. No firmware or extracted data is
committed; no hardware flashing is authorized. Physical checks remain #4.

Evidence: [DIGITAKT-SRC-FINDINGS.md](DIGITAKT-SRC-FINDINGS.md).
Tracking: [research #6](https://github.com/simonjohansson/elekloader/issues/6),
[implementation #7](https://github.com/simonjohansson/elekloader/issues/7),
[acceptance #8](https://github.com/simonjohansson/elekloader/issues/8).
