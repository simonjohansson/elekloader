# Proposed DN2 SHARC sine contract (#36)

This records the original fixed-tone gate. The current played starter is
[here](../examples/sharc-sine/README.md); the owner ranges and ABI stay the same.

**Approved contract, 24 October 2026. The inert app slice was implemented in
#37; #41 has a fixed active bridge and a measured physical USB sine, while
timing and broader route qualification remain open.** This replaces the older
synthetic sizing and incoming-R4 assumptions retained in
[#36](https://github.com/simonjohansson/elekloader/issues/36).
The first target is DN2 OS 1.12 and one fixed, key-independent 440 Hz sine.
Playback on hardware is a separate gate, [#41](https://github.com/simonjohansson/elekloader/issues/41).

## The author and user paths

An author may use any compiler/linker capable of producing this machine code.
The author project emits one **prelinked, compiler-neutral JSON artifact** in
loader byte order. Elekloader does not invoke or bundle a SHARC compiler. For
the first starter, the author-generated artifact is included with the source,
so the usual three commands work without any SHARC toolchain installed:

```text
examples/sharc-sine/
  mod.json
  sine.sharc.json       # author output; contains no stock firmware bytes
  sine.c                # optional source for authors changing the sound
  entry.c               # init/render adapter
```

```json
{
  "id": "sharc-sine", "version": "0.1", "title": "SHARC sine",
  "license": "GPL-2.0-or-later", "device": "digitone-mk2", "os": "1.12",
  "requires": ["core"],
  "sharc": {"artifact": "sine.sharc.json"}
}
```

`sharc.artifact` is a relative path inside the mod folder, resolved without
escaping that folder. It replaces `sharc.sources` for this slice. The normal
SDK build checks the artifact and copies its validated envelope into the
format-2 `.elemod`; it does not copy the source file or invoke a converter.
Authors who change the C regenerate the artifact using their own toolchain
before building the mod. An optional, separate Selache exporter can demonstrate
that step, but is not on the consumer path or required by the schema. A
proprietary compiler is a possible author-side fallback, not a dependency.

```sh
python -m elekloader.sdk.build examples/sharc-sine --stock "$DN2_STOCK"
python -m elekloader.lint examples/sharc-sine/out/sharc-sine-0.1.elemod --stock "$DN2_STOCK" --with "$DN2_CORE" --json
python -m elekloader.patch --stock "$DN2_STOCK" --mod "$DN2_CORE" --mod examples/sharc-sine/out/sharc-sine-0.1.elemod --out sine.syx --version SN01
```

These commands now build the exact active fixed-sine candidate. Hardware
playback evidence is recorded separately in #41.
The end user supplies stock OS and matching core/mod files as for other
devices; no compiler, native linker, remote service or extra DSP patch step
is involved. The same parsed `.elemod` must work in Python and TypeScript.

## One narrow artifact

The JSON artifact contains exactly `abi`, `segments`, `zero`, `entries` and
`stack_bytes`. The same object is the sole new top-level `sharc` field in a
format-2 `.elemod`. Its initial ABI name is `dn2-master-mono32-v1`:

```json
{
  "abi": "dn2-master-mono32-v1",
  "segments": [
    {"offset_bytes": 0, "kind": "code", "hex": "<loader-order bytes>"},
    {"offset_bytes": 512, "kind": "data", "hex": "<data bytes>"}
  ],
  "zero": [{"offset_bytes": 664, "size_bytes": 360}],
  "entries": {"init_offset_bytes": 320, "render_offset_bytes": 370},
  "stack_bytes": 84
}
```

The hex placeholders make this a **shape example**, not an installable file.
The app's measured linked map has 424 code bytes at core-byte `0x2dda00`,
152 data bytes at `0x2ddc00`, init PC16 `0x16eda0`, render PC16 `0x16edb9`,
with 88 bytes of NOP code guard before data and 360 bytes of zero state.
The displayed entry offsets are
relative **byte** offsets: `(0x16eda0 - 0x16ed00) * 2 = 320`, and render is
`370`. The measured bridge saves consume **116 bytes**, and its call into the
application consumes at most **84 more bytes**, for **200 bytes** total in
the borrowed H1 stack frame. The core declares `stack_bytes:116`; the app
declares `stack_bytes:84`. `stack_bytes` is a declared contribution checked
against the profile; it is not proof of an arbitrary executable's behavior.
The first candidate pins the exact qualified artifact bytes, placement and
zero state. Physical playback must still check the bound against observed
state before enabling a wider set of apps.

For this ABI, the core's fixed 1 KiB owner is `[0x2dd600,0x2dda00)` and the
app's fixed 1 KiB owner is `[0x2dda00,0x2dde00)`, expressed here as **core
bytes**. The corresponding loader aliases are `0x282dd600` and `0x282dda00`;
the code PCs use 16-bit parcels (`core_byte / 2`). The active candidate grants
both 1 KiB owners only for the hash-pinned first bridge and sine. The profile,
never an author offset, grants ownership.
The active artifact uses NOP padding for the code guards, then data and zero
state fill to cover its owner. The core owns the 12-byte binding at offset 0,
its 548-byte bridge at offset 12, and NOP-fills the rest. The H1 jump is
core-owned and only installed
with a matching active app. No author-supplied stock code or loader header is
accepted.

All segment starts and lengths are four-byte aligned. Code hex is the
variable-width SHARC+ instruction byte stream in **loader order**, not raw
Selache ELF parcel order; data bytes are unchanged. Entry offsets may be
two-byte aligned and must point into the owner's code segment. Checking
decoded instruction starts is part of qualifying this pinned active candidate. Every range
must be nonempty, in bounds, disjoint and free of
protected aliases. Reject malformed hex, missing or unknown keys, booleans
as integers, wrong ABI, instruction decode gaps, wrong entry kinds, or a
second SHARC app. There is no runtime linker or general event bus. A producer
must resolve every reference and omit unwanted sections before export; a
JSON byte envelope cannot itself prove that an earlier ELF had no unresolved
relocations or identify which compiler emitted it. The existing probe's
producer checks those source-executable properties and records source hashes.
The normal SDK build consumes the artifact as-is;
it cannot detect a stale source file unless the author regenerates it.
Elekloader checks the exported bytes, target placement and stock identity,
not producer labels.

The core artifact uses the same envelope but a core-only
`entries:{"hook_offset_bytes":12}`. An inert app uses `entries:null` and
`stack_bytes:0`, with real bounded segments. An active app requires the
matching bridge and both callbacks; otherwise patching refuses. An inert app
still installs no SHARC hook or entry binding. With no app,
section 7 stays byte-identical to stock. One inert app can exercise section-7
installation while stock audio remains untouched. The SHARC-capable core and
entry-word binding are implemented for the pinned #41 candidate.

## Callback and installation boundary

The only public C callbacks are `void sharc_init(void)` and
`void sharc_render(float *mono32)`. The bridge calls init once, then render
once per 32-sample block at the observed 48 kHz boundary. The active callback
overwrites 32 float32 samples in the left half of the observed master buffer;
the bridge copies those 32 samples to the right half. It passes the verified
master address `0x268438`; incoming H1 R4 is a caller-stack pointer, not audio.
It saves/restores R0–R8 including extended bits and both PX halves, preserves
MODE/banks/DAG/loop context, and replays the displaced stock instruction.
The core binding is two little-endian PC16 entry words plus one zeroed init
flag; the app cannot supply binding bytes or patch H1 itself. The bridge's
empty binding does no callback or stereo copy.

The consumer uses the existing strict target identity and independently
checks the stock decoded SHARC stream before adding ordered LOAD/FILL records
with the existing `elekloader.sharc` record layer. It updates section 7 only
when an app is selected, leaves all other sections and bootstrap/updater
unchanged, and verifies stored and decoded section 7 against the expected
output bytes after writing. The stored/decoded/update/flash limits remain
separate checks. No-DSP builds and old mods retain byte-exact existing output.
There is no DT2, key tracking, UI, machine ID, project format or ModelDigi
work in this first slice.

## Exact implementation surface and first feedback

After approval, [#37](https://github.com/simonjohansson/elekloader/issues/37)
changes only the necessary surfaces: SDK `mod.json` input and format-2
validation; profile-owned placement; Python and TypeScript link/patch/format
parity; CLI/GUI use of the resulting `.elemod`; and FORMAT, ADAPTING and
device docs. Existing entry points gain an optional internal SHARC stream
result/argument while their no-SHARC behavior stays byte-identical. A
protocol/catalog version changes only if an actual kit call or catalog shape
changes. The first check is an **inert app**: build, lint, patch and verify
both engines with synthetic records, then compare a stock-derived candidate
offline without publishing firmware. Refusals include out-of-owner bytes,
overlap, bad entry, wrong stock stream, duplicate app and missing active core.
Next, #41 qualifies wrapper-only pass-through and the fixed sine on device.
Key tracking [#47](https://github.com/simonjohansson/elekloader/issues/47)
waits for audible fixed sine.

The proposed Python boundary is `link.link(mods, image, lock=None, *,
sharc_stream=None)`, returning `Linked.sharc_stream` only when an app requests
section 7. `formats.write(..., stored_sharc=None)` and
`formats.verify(..., want_sharc=None)` pass the optional section to ELE3's
writer and independent verifier; the TypeScript port mirrors that behavior.
`patch.build` and lint supply the stock decoded stream when needed. Existing
positional calls and outputs remain valid. Only `mod.json` input and the
format-2 `sharc` envelope are new author-facing shapes; no separate user
command, kit protocol field or catalog field is proposed.

Illustrative expected feedback (exact wording becomes a test in #37):

```text
build: sharc-sine-0.1.elemod; DN2 1.12; SHARC app 424 code + 152 data bytes
lint: compatible with core-dn2; one SHARC app; 200/544 borrowed stack bytes
patch: verified section 7, all other sections and bootstrap unchanged
refuse: SHARC segment [1024,1028) exceeds the 1024-byte app owner
refuse: active SHARC app requires the matching DN2 SHARC core
refuse: stock SHARC section differs from the profiled DN2 1.12 stream
```

This design reuses only original Elekloader bridge/probe source and the
original record parser. Digikit is a research runner, not distributed code;
its [PX fix PR](https://github.com/ElekLabs/digikit/pull/184) is still pending.
Selache is one optional author producer. Neither its output format nor its
license dictates the public Elekloader schema. The artifact must carry its
own source/build provenance in author documentation; no stock-derived bytes
may be committed.
