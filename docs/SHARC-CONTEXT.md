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
| Serialized loop depth | `1`, with top LADDR/CURLCNTR both `0xffffffff` and `loops=[]` |

RND32 is set, SIMD is clear, and the L1 normal-word configuration corroborates
32-bit accesses at this entry. Circular buffering is enabled with nonzero
stack lengths. The proposed bridge must preserve that real DAG, bank and loop
context. The serialized loop slot is a retained sentinel, not evidence of an
active hardware loop; preserve all slots rather than inferring liveness from
depth alone. A fixture with zero circular lengths is insufficient.
These observations do not expose or prove preservation of hardware extended
floating-point bits.

### Bounded candidate access check

The candidate core-byte `[0x2dd600,0x2dde00)` and loader alias
`[0x282dd600,0x282dde00)` were watched across **two complete 666,667-instruction
frame periods**: restored frame 0 (silent) and frame 687 (first sounding
SPORT block, 54 of 64 samples nonzero). The latter starts from its own genuine
pre-frame state, after native replay matched every captured SPI reply and
SPORT block through frame 687. That replay uses the same native instruction
implementation as the coupled run; it checks continuation and ordering,
not independent ISA correctness.

An original private Python observer then records attempted backing-memory
reads (including unmapped reads and alias probes), DM/PM accesses and overlay
reads/writes used by SPI DMA, SPORT and IIR. It observes same-value writes;
it does not infer absence of access from unchanged bytes. Its self-check
requires detection of absent reads, repeated identical writes and the range's
exclusive end. Neither frame had an unresolved address or a candidate access.

| Frame | DM/PM reads / writes | Overlay byte reads / writes | Backing reads/probes |
|---|---:|---:|---:|
| Silent 0 | 201,894 / 146,404 | 687,276 / 584,937 | 1,043,277 |
| Sounding 687 | 201,807 / 146,325 | 686,911 / 584,618 | 1,043,898 |

These are observer event counts, not unique hardware transactions. Both runs
complete without a halt and match the native engine's modeled registers,
banks, stacks, MMRs, explicit memory ranges, page hashes and SPORT block,
with **zero differences**. The reports hash to
`edcb4da1398c6e43f695bcb934d0b0687b7da37456d367cf26ba9efbbab603ca`
(silent) and
`b6bacb758913cacb720a3ba90c6df44ecb0b6b6e1197e2bb50aeffca170be067`
(sounding).

This supports the narrow candidate in these two observed contexts. It does
not establish lifetime allocation ownership, cover every initialization or
interrupt path, or authorize a production reservation. The next bounded
integration uses these captured contexts. The bridge and placement follow-up
below separates completed checks from the external runner limitation.
Physical behavior stays in #41.

The owner-local commands, original observation scripts, source/tool hashes,
paired snapshots and reports are retained in ignored
`out/sharc35-runtime-20261023/`. No firmware, state, full manual or extracted
manual text is committed. These investigation inputs are not mod-author
requirements.

## H1 bridge follow-up

The first genuine-context run found a bug in the earlier synthetic adapter:
**incoming R4 is `0x2d1808`, a caller-stack address, not the master buffer**.
The old adapter restored registers but wrote 64 output words into the caller
frame and left the master unchanged. Its synthetic sample check therefore
was not a valid stock-output check. The revised original
[H1 bridge](../examples/sharc-sine-probe/h1-bridge.s) supplies `0x268438` to
render, copies its 32 mono floats to the adjacent right channel, then restores
R4 before replaying the displaced allocation and continuing at `0x1c2450`.

### Full-width context

The bridge allocates its save area before saving and releases it after
restoring. It preserves R0–R8 through `PX=Rn`, ordinary 32-bit PX1/PX2 stores,
and `Rn=PX`, including the original two PX halves. It leaves MODE, MMASK,
IMASK, both stack bases/lengths and the stock modifier constants unchanged.
This avoids changing global memory-width settings while interrupts are enabled.
The primary [SHARC+ PRM revision 1.5](https://www.analog.com/media/en/dsp-documentation/processor-manuals/sc58x-2158x-prm.pdf),
Figures 2-2/2-3, defines the full 40-bit transfer through PX[63:24]. Its SEC
handler example also demonstrates adjacent PX transfers without added NOPs.
The bridge's final I7 changes remain within the captured circular bounds,
avoiding wrap-related STKY changes after status restoration.

The firmware-free checker reconstructs the exact spill encodings from the
manual and tests every low-byte value against four upper-word patterns:
**1,024 cases preserve all 40 bits of R0–R8 and all 64 original PX bits**.
Omitting R0's PX1 restore fails all 1,024 cases. This is a finite bitvector
check of the emitted spill subset, not full bridge execution on silicon.

**Both pinned external runners fail the exact PX bridge.** `PX=R0` writes
the model's separate PX slot without updating PX1/PX2, so its later `R0=PX`
reads the wrong value. A three-instruction reproduction and a complete native
bridge attempt retain that failure. Do not silently repair register values or
report these runs as successful. The ordinary binary32 models also cannot
establish preservation of hardware extended bits, even after this defect is
corrected. The finite full-width check supplies a separate evidence layer.

A separate, explicitly isolated diagnostic corrects only the destination-PX
alias for the exact bridge's `PX=R0..R8` instructions. It routes the modeled
upper word to PX2 and treats omitted lower eight bits as zero; it does not
modify the external checkout or qualify hardware extended contents. Under
that correction, the **exact 548-byte bridge** passes both captured contexts:
eight phase-continuous blocks each, one init, dirty reset, empty binding,
unchanged caller state, all modeled registers/banks/loop slots, known access
addresses and exact continuation. The maximum I7 drop is **200 bytes**,
inside the imminent 544-byte H1 frame. The parent repeated this experiment;
its report counts all 180 corrected PX writes. This is explicitly a modified
binary32 model result, separate from the unchanged-runner failure above.

The actual interrupt-entry check clears active bank mask `0x4f8` to zero
under MMASK `0xe0b4fb`. The stock SECI prefix's first three pushes use the
primary stack at `0x26f7a8`, rather than H1's secondary stack at `0x2d16b0`.
Ten executed prefix instructions in each captured context verify that narrow
fact; complete interrupt nesting and return remain unqualified. A conjectured
collision based on an unchanged H1 stack bank would use the wrong context.

### Stock continuation and output routing

The separate binary32 bridge also ran through the unmodified stock H1 caller
and the next captured SPI frame in the native interpreter. Its sine survives
H1 exactly. Stock processing between H1 and the converter changes some floats
by one binary32 ULP; this bounded investigation records that transform rather
than claiming an independently derived end-to-end sample formula. The converter
produces exact positive Q31 from the observed input, and subsequent stock
processing negates the ring. Physical polarity remains unmeasured.

The first SPORT block consumes the previous double-buffer page. The **next
block matches the newly generated page byte for byte**, in both the idle and
sounding captures. A missing hook and zeroed oscillator increment each fail
that next-block sample check. Empty binding preserves both SPORT blocks and
the next SPI reply; at the same stock caller-return PC, modeled non-memory
context matches except the equal 62-instruction clock/timer overhead. Those
counts are interpreter instructions, not SHARC cycles. The parent repeated
this route check. These results qualify the route for the binary32 artifact,
not the unchanged runners' failing full-width PX artifact or a physical DN2.

### Explicit experimental placement

The exact linked bridge remains inside the previously watched 2 KiB candidate.
These are core-byte intervals with exclusive ends, not an approved reservation:

| Item | Start | End | Bytes |
|---|---:|---:|---:|
| Init/render binding and zero flag | `0x2dd600` | `0x2dd60c` | 12 |
| Bridge code | `0x2dd60c` | `0x2dd830` | 548 |
| Code guard | `0x2dd830` | `0x2dda00` | 464 |
| Sine and entry code | `0x2dda00` | `0x2ddba8` | 424 |
| Code guard | `0x2ddba8` | `0x2ddc00` | 88 |
| Table, width vector and initialized state | `0x2ddc00` | `0x2ddc98` | 152 |
| Zero data slack | `0x2ddc98` | `0x2dde00` | 360 |

Four disjoint LOADs and three FILLs cover the entire interval. Code guards
use repeated 16-bit NOP `0x0001`; data slack uses zero. Inserting these before
FINAL loads them **after stock INIT has returned**. It does not require
executing INIT in the investigator's model or asserting that INIT has no
indirect writes. Preserve INIT, all original records and its hardware setup.
The bridge calls init once on first H1 entry; the binding and state start from
explicit values. The arithmetic stream addition is 1,248 bytes including
headers; final compression, container and transfer checks remain integration
work. No flashable image is emitted by this experiment.

The stock startup clears SHL1C_CFG before later configuring it. A bounded
6,842-instruction entry slice clears both zero and deliberately dirty initial
CFG values. Captured H1 has modeled CFG=`0x414141`, CFG2=`0xf0`: caches are
enabled, with the configured tail excluded from the candidate. ADI nevertheless
cautions against code in blocks 1/2 while their data caches are enabled
(PRM printed page 8–3), describing possible DMA/system-request delays.
Neither padding nor avoiding the cache tail establishes instruction visibility
or hardware timing. A complete sounding frame executed no block-1/2 code,
so it provides no stock-code corroboration for that placement. Keep this
caution in #41's physical gate; do not change cache configuration to fit the
example or treat the source project's withdrawn crash theory as established.

The new original sources and firmware-free reproduction command live with the
[existing sine probe](../examples/sharc-sine-probe/README.md#check-the-dn2-h1-bridge).
Private stock listings, captured-state experiments and reports are retained
under ignored `out/sharc35-bridge-20261023/`, with a hash manifest. No public
artifact contract, consumer engine or profile ownership changed.

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
