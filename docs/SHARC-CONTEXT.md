# DN2 SHARC runtime evidence

This is the maintainer investigation for [#35](https://github.com/simonjohansson/elekloader/issues/35),
using owner-supplied DN2 OS 1.12 and external Digikit at
`38dfbe4ae88263511eed95691c07fc07e17b6f26`. It is not part of the normal mod
build workflow. The planned SHARC boundary is compiler independent: a mod
project will supply a compatible artifact, and Elekloader will check and place
it. That integration is not enabled yet.
The Selache sine probe qualifies one producer; it does not require all mods
to use that compiler or put a compiler inside Elekloader.

## Reset input recovered

The missing peripheral reset data is available in the **ADI ADSP-2156x
SHARC+ Processor Hardware Reference, revision 1.0, December 2020**, part
82-100137-01. A [hosted copy of that primary document](https://manuals.plus/m/d9229038ca02a88c5279a39055e8d2cf1da635644f591dad3a228a7ec5318e27)
was downloaded through ordinary browser navigation. Its title and notices
identify ADI; it has 2,331 pages and 11,954,387 bytes. The historical official
file's byte identity has not been independently checked. The
[current official URL](https://www.analog.com/media/en/dsp-documentation/processor-manuals/adsp-2156x_hwr.pdf)
now serves revision 1.1.

| Input | SHA-256 |
|---|---|
| Revision 1.0 PDF | `d9229038ca02a88c5279a39055e8d2cf1da635644f591dad3a228a7ec5318e27` |
| `pdftotext -layout` extraction | `ea2a58e62cd32e30e9f9826d8e6d58ae81afe5a6cb70bb4328b1fe4d4464ddaf` |
| Per-page extraction with Digikit's `=== page N ===` headings | `1c6e5ab652da788932d24f5313876e7cba8e8ddea059b1dfd7ad5b3c8ef28121` |
| Unchanged Digikit reset parser | `f74f95b46bdbcc720aa67f6debce71c1dc714bbe32b500eb3e617ecfe8e335b2` |

Both extractions produce the same **3,558 reset entries, 586 nonzero**, with
Digikit's unchanged `parse_reset_tables`. The PDF and full text remain private
research inputs, outside source control. These are register defaults, not a
model of peripheral side effects or the ROM-to-application handoff.

Use the documented revision. [Digikit #118](https://github.com/ElekLabs/digikit/issues/118)
reports conflicting revision 1.1 table rows at `0x31026108`: DDE and DMA35
assign different defaults to the same address. The existing parser must
continue rejecting conflicting values; silently taking the first row is not
an established correction.

## Reproduction boundary

Digikit's existing `tools/emulator/ready.py` provides the sequence:

1. Verify and flatten section 7 from the owner stock, then pack its memory.
2. Build the cold state with `sharc_cold_state.cold_blob_for_memory`, using
   the reset extraction above as its `HWR` input.
3. Run `dsp_cold` to the DSP idle loop.
4. Run `sharc_live` with that state attached from the first ColdFire frame,
   saving a paired ColdFire snapshot and `.dsp` sidecar at readiness.
5. Restore that pair and run the existing `coupled_ready_exactness` gate.

Use a fresh output directory. The upstream recipe skips existing files;
existence alone does not bind a snapshot to the requested stock or settings.
Keep `SOURCE.json`, source/tool hashes, stdout/stderr and hashes of all paired
outputs with the private evidence. Neither example's exit status is a boot
certificate: `dsp_cold` also saves after a halt or exhausted instruction
budget. Require its explicit idle result and a non-stopped canonical state
inside `[0xb88a49,0xb88abb]`; require actual ColdFire readiness, paired saves,
no CF error, no DSP halt and uninterrupted audio blocks.

The firmware-independent shared core uses `SHARC_GEN_DIR` and needs no
private `.dt2cap` capture. This run used mise Python 3.12.13 and Rust 1.98.1,
`SHARC_AOT=0`, empty `SHARC_FAST_REGIONS` and `SHARC_BLOCKTRANS`, and the
existing `dsp_cold` / `sharc_live` binaries. Startup uses `DIGI_INTC_FORCE=0`;
the pinned regression uses `DIGI_INTC_FORCE=1` and `NOTE_EVENTS=trig`, as
specified by [Digikit's regression notes](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/docs/findings/07-emulator.md#L5526-L5529).
Do not change expected hashes to accommodate a different input script.

## Executed result, 23 October 2026

The recovered input unblocks execution beyond the earlier core-reset-only
halt. The freshly generated stock pair reaches:

| Check | Observed result |
|---|---|
| DSP cold start | Idle PC `0xb88a5d` after 563,750,000 instructions; no halt |
| Coupled stock boot | Ready at CF instruction 851,236,444; paired snapshots saved |
| Boot plus 1M CF instructions | 4,745 frames, zero missing blocks, no CF error or DSP halt |
| First restored frame, independent native replay | First reply, 256-byte SPORT block and next reply match the captured coupled run exactly |
| H1 breakpoint | PC16 `0x1c244d`, after 319,039 instructions within the 666,667-instruction frame period |

The replay starts from the matching paired sidecar clock `3717751577`; it
does not substitute a diagnostic clock or pair a later frame with the initial
state. The full canonical H1 state was exported at clock `3718070616`, with
SHA-256 `d5ab6843b85c81a00b11a165d3d6f465d04f769d49fba1d00cc4c23c8a94126c`.
The packed image hashes to
`fea39d589ac45b20a6dfdb3f6c89a5b9d28fd7936ff819a7a09f17f3ff847a2a`;
the ready `.dsp` sidecar to
`779afd8e47b79a4ceb48ea2825d33fedcd0102d6754ef3eb4bac544cb59ebfb4`.
These private artifacts contain firmware state and are not distributed.

**The existing exactness test still fails its state-hash assertion.** Its
100M trig workload ends at CF instruction 951,486,315 with no CF error. A
separate run of the same workload using the existing `sharc_live` diagnostics
checks the outputs that the early assertion would hide:

| 100M workload result | Observed / expected |
|---|---|
| PCM | **Exact match**, `826db0d1de8f7738ac5d0c4579198439bb5a0102b4b9d8bc36d93fa07ce15843` |
| Samples / frames / missing blocks | **72,896 / 1,139 / 0**; no DSP halt |
| ColdFire state | `8bd3e0bf6b5fbf8720481efa752a6a5d2210d3f84094984d2d92a2cf37faa59b`, differs from expected `8914ba7b7ba8f00fa544c21193df64fed614ed72c51f10f0de39c88695fa1561` |
| DSP state | `7ea6ad0952ce8dd22573a59f501876a4dbcef4dd16199e2f2bafcabbe958a475`, differs from expected `5cf54eba4b404acfae2e15eae5ef26a12459c171e1a6440a27cc2aa48a692fc6` |

The CF expectation predates the DN2 1.12 migration. Its
[serialized state includes the MAIN hash and firmware version](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/packages/emulator/boot/src/runtime.rs#L3119-L3122),
so an old-release digest cannot certify this release. The
[1.12 migration](https://github.com/ElekLabs/digikit/commit/67fee13bde3da04efe3847434370cea6c4802213)
changed fixture defaults and reported unchanged PCM pins, but left this CF
expectation unchanged. That explains why the old CF check is unsuitable;
it does **not** explain the DSP-state difference. The no-note variant also
fails and is not the documented pinned workload. No expected hash was changed.

The available evidence is a provenance-recorded fresh model with matching
pinned audio and an exact first-frame replay. It is not a passing full-state
regression or physical-device validation.

### Actual modeled H1 context

All values below are fully known in the exported model, rather than seeded
synthetic caller values or a borrowed H5 observation:

| Context | Value |
|---|---|
| MODE1 / MODE2 | `0x39011cf8` / `0x21` |
| CMMR_SYSCTL | `0x16004`; all four IMDW bits clear |
| I6 / I7 | `0x2d16b8` / `0x2d16b0` |
| B6 / B7 | Both `0x2d08c0` |
| L6 / L7 | Both `0x3e2` (994), **not zero** |
| M6 / M7 | `1` / `0xffffffff` |
| Active bank mask | `0x4f8` |
| Hardware loop depth in canonical state | `1`, **not empty** |

RND32 is set, SIMD is clear, and the L1 normal-word configuration corroborates
32-bit accesses at this entry. Circular buffering is enabled with nonzero
stack lengths. The proposed bridge must preserve that real DAG, bank and loop
context; a fixture with zero circular lengths or no loops is insufficient.
These observations do not expose or prove preservation of hardware extended
floating-point bits.

## Limits that remain

This route flattens the loader and starts at the last FIRST entry. It does
**not execute the ROM's INIT callback**. The stock INIT's linear decode
contains 2,276 instructions, 2,266 confident and 10 uncertain; this is not a
complete reachable control-flow proof. It configures DDR/clock/peripheral
state and temporary L1 data. Its complete indirect-write effects have not
been established.

The standard ready engine enables approximate reciprocals, functional timer
and peripheral models, and a normal-word 32-bit access assumption. Import
also concretizes unknown special-register bits and a small low-alias region.
Disabling fast paths does not remove these assumptions. A successful modeled
boot does not prove hardware reset, cache visibility or interrupt timing.

At H1, record memory width and compute precision separately. The
[SHARC+ programming reference](https://www.analog.com/media/en/dsp-documentation/processor-manuals/sc58x-2158x-prm.pdf)
revision 1.5, Table 30-8 (PDF page 679), defines `CMMR_SYSCTL` bits 12–9 as the
four L1 blocks' normal-word widths. `MODE1.RND32`, bit 16 in Table 29-19 (PDF
page 623), controls computation rounding. The emulator's modeled 32-bit
registers cannot prove preservation of hardware 40-bit extended contents.
The reference also specifies 40-bit rounding for fixed-to-float conversion
even with RND32 set (PDF page 101); RND32 alone cannot justify 32-bit spills
of every live stock register.

PC dumps omit full DAG/bank/stack state. Change-only watches miss reads,
same-value stores and transient writes. Neither establishes ownership of the
candidate `[0x2dd600,0x2dde00)`. The device profile must retain empty
`owned_ranges` until the bounded access investigation and integration
contract justify a reservation. Physical output and instruction visibility
remain #41's device gate, with key tracking following in #47.
