# DN2 keyed SHARC callback contract

This covers `dn2-master-mono32-v1` and the experimental
`dn2-master-mono32-l2-v1`, with the pinned keyed core on Digitone II
OS 1.12. It provides one exclusive master-output application. It does not
register a selectable machine, per-voice processor or stereo effect.
The [artifact envelope](FORMAT.md#digitone-ii-sharc-app) is unchanged.

## Calls and audio

```c
void sharc_init(uint32_t phase_increment);
void sharc_render(float *mono32);
```

The first argument arrives in R4. `phase_increment` advances a uint32 phase
accumulator at 48 kHz. `mono32` is the core-byte pointer `0x268438`, to 32
binary32 floats (128 bytes); its loader alias is `0x28268438`. The callback
may replace those samples or process them in place. On return, the bridge
copies this block to the right channel at core-byte address `0x2684b8`.
It offers no additional audio-buffer ownership. Both callbacks return void.

Render normally runs once per 32-sample block at 48 kHz. A block lasts about
0.667 ms, shared with stock work; that is not an available DSP time budget.
Render may run before the first init, so cold-zero state must be valid.
Init is a pitch-change call, not a boot callback: the bridge selects the
newest allocated triggered slot, waits until the following render block for
its settled pitch, then calls init. A new simultaneous trigger selects the
highest allocated slot bit. Only MIDI notes 36..84 are supported by this
reader; an unsupported pitch clears its state and emits a silent block.

Read the uint32 gate at core-byte `0x2dd9f0` (loader `0x282dd9f0`): nonzero
means the selected slot remains held. A matching release clears it; another
slot's release does not. Init sees the old/cleared gate; the bridge publishes
the selected gate after init returns. Render continues with gate zero for
release tails. The supplied entry wrapper uses a 32-sample attack/release
ramp. Authors must not write the bridge state or its binding words.

## Register, stack and system-state obligations

The pinned bridge saves/restores full R0..R8 via PX, both original PX halves,
I4/I5/I12, L4/L5, ASTATX/ASTATY and STKYX/STKYY. Callbacks may clobber the
saved data/index/status registers. L4/L5 are cleared before entering app
code and must return as zero: the bridge uses them for the stereo copy
before restoring the stock values. The bridge does not save every register
on behalf of arbitrary programs.

Callbacks must preserve all other live registers and state they use,
including R9..R15, the other processing element, unsaved DAG index/base/length
registers, modifier registers, accumulators, FIFO state and bank selection.
Preserve MODE1/MODE2, MMASK, IMASK, cache/memory configuration and hardware
PC/loop/status stack contents and depth. Do not assume inactive banks, DAG
lengths or stack bases are zero. Changing SIMD, memory widths, interrupts or
peripherals needs separate context and concurrency qualification.

Calls use the existing Selache short-word function convention: the bridge
sets I6 from I7 and pushes the old frame pointer and return PC minus one.
Return with the matching frame restoration and indirect delayed return;
the C wrapper and assembly kernel show the working sequence. M6=1, M7=-1,
M13=0 and M14=1 are required stock modifier values and must remain unchanged.
I6/I7 must return to their pre-call values. Both stack bases/lengths remain
the stock circular configuration; do not replace them with a flat stack.
The bridge's declared contribution is 116 bytes. The combined declared limit
is 544 bytes, leaving at most 428 for app calls, locals and spills. The
examples declare 128 app bytes. This declaration is not a measured high-water
mark and the checker cannot infer actual stack use from machine code.

## Owned bytes and read-ahead

The existing L1 app owns loader bytes `[0x282dda00,0x282dde00)`, 1 KiB including code,
data and zero ranges. The current example layout uses 768 bytes for code and
256 for data. The last 64 bytes of every active app code segment must be
repeated short-word NOPs (`0100` in loader order). Callback entries must lie
before that tail. Thus the example's linked instructions may occupy at most
704 bytes; padding supplies the guard. Inert apps execute no code and retain
the earlier envelope rules. The separately pinned core is unchanged.

The L2 ABI instead owns `[0x20090000,0x20098000)` (32 KiB); offsets in its
artifact are relative to that base. Compile code for the L2 PC16 alias
`0xbc8000` and use L2 byte addresses for data. Its callbacks, guard and stack
obligations are identical. L2 has no extra stack allowance. The linker also
retains the L1 app range, installs the fixed bridge table there and zeroes
its other bytes. L1 and L2 apps cannot be composed. The supplied external
L2 layout uses 16 KiB for code (including the guard) and 16 KiB for data.
It accesses data 16 KiB into the reservation; this is not merely larger
dead padding. See [L2 evidence and limits](SHARC-L2.md).

This 64-byte margin is a conservative policy retained for both ABIs, not
proof of every cache/prefetch mode or executable. The SHARC+ programming
reference, revision 1.5, sections 4-5/4-6, describes the VISA alignment buffer,
in-flight fetches and fetches continuing at memory boundaries:
[Analog Devices programming reference](https://www.analog.com/media/en/dsp-documentation/processor-manuals/sc58x-2158x-prm.pdf).
The checker validates padding and entry bounds; it does not decode arbitrary
instructions or prove that branches and writes remain within the contract.

The keyed bridge reads twelve fixed uint32 phase steps at core-byte
`0x2ddd98` (app byte offset 920). The linker checks these 48 data bytes against
the profile for L1; it installs them itself for L2. They represent notes 36..47; higher octaves shift the step.
Other app code and data may change without adding executable hashes. Keep
state within owned bytes and the supplied output buffer; preserve stock
memory everywhere else. The bridge's core range, six-byte H1 stock hook,
owner identities and firmware budgets remain independently checked.

## Qualification

Packaging is compiler-independent and certifies the envelope, not the
program. Qualify each generated executable for calling-convention behavior,
actual stack and writes, numerical output, interrupts and audio deadlines.
The edited C and ASM sines were checked in Digikit. Emulator success and
instruction counts are not physical-device timing or a full ISA guarantee.
