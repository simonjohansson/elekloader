# SHARC sine compiler and execution probe

This is the firmware-free compiler qualification for
[issue #31](https://github.com/simonjohansson/elekloader/issues/31). It builds
an actual SHARC+ sine kernel and checks its executable. The optional execution
command covers [issue #33](https://github.com/simonjohansson/elekloader/issues/33)
using a pinned external runner and a small synthetic caller.
It is **not an installable mod**. There is no `mod.json`, firmware input,
stock hook or device operation. Execution uses an author-only loader stream.
The normal module build workflow
will be integrated separately; this developer probe adds no SDK contract.

## Build and check

The qualified author host is macOS 27.0.1 on Apple silicon, using mise Python
3.12.13 and Rust 1.98.1, with Apple's command-line developer tools installed.
Other hosts and a second contributor's clean rebuild have not been checked.

From the Elekloader checkout, install the pinned source and build its four
tools once (the first build downloads Cargo dependencies):

```sh
mise install python@3.12.13 rust@1.98.1
git clone https://github.com/js216/selache.git out/selache
(
    cd out/selache
    git checkout --detach 2b26d3b75c53063575bc5c820fa0d38879335187
    mise exec rust@1.98.1 -- cargo build --release --locked -p selcc -p selas -p seld -p seldump
)
mise exec python@3.12.13 -- python examples/sharc-sine-probe/qualify.py out/selache
```

An existing clean checkout at that exact revision works too: supply its path
as the single argument. The probe accepts no extra compiler flags. It creates
a fresh ignored `out/sharc-sine-probe-*` directory on every run, so a failed
compile cannot reuse stale output. Only a complete pass writes `report.json`.

The directory contains `sine.s`, `sine.doj`, `sine.dxe`, `sine.map`, object and
executable inspection, full disassembly, negative-case artifacts and the
report. The report records exact source/tool/header/output SHA-256 values,
the host, flags and commands. Do not commit these build artifacts.

Expected result:

```text
PASS: 320 code bytes, 152 data bytes; 10 negative checks. Compile-only qualification.
```

The fixed candidate options are `-proc ADSP-21569 -char-size-8 -O1`, with
`-no-std-inc` and an explicit include path to the pinned `libsel/include`.
Linking supplies only `sine.doj`, our small `synthetic.ldf` and an explicit
`-entry sine_init.`. No startup or runtime object/library is added. The
linker's LDF `ENTRY(...)` alone produced an ELF entry of zero in a probe, so
the actual ELF entry is checked directly.

## Kernel and emitted artifact

`sine_init(uint32_t increment)` resets the one oscillator's phase and sets its
increment. `sine_render(float *output)` writes exactly 32 mono samples to a
caller-provided buffer of at least 128 bytes, then saves phase. It calls
`sine_sample(uint32_t phase)` for each sample. These functions are an internal
probe interface, not a proposal for stock hooks or a public callback ABI.

Phase addition wraps modulo 2^32. The top six bits select one of 64 phases;
the lower five select a positive half-table, and the sixth chooses float
negation. Peak amplitude is 0.125. There is no interpolation, division, libm,
integer-to-float conversion, allocation or recursion. At a separately proven
48 kHz boundary, increment 39,370,534 gives an ideal accumulator frequency of
440.0000050664 Hz; table approximation and actual clocks remain separate.

| Item | Measured result |
|---|---|
| Executable | ELF32 little-endian, machine `0x85` (SHARC) |
| Object metadata | ADSP-21569, SW encoding; final link drops these attributes |
| Code | 320 bytes, 80 decoded instructions; 16/32/48-bit forms |
| Data | 128-byte positive half-table, 16-byte width vector, 8-byte phase/increment |
| Separate BSS | 0 bytes; both state words have explicit zero initializers |
| Named unresolved symbols / remaining relocations | None |
| Extra runtime/startup objects | None |
| `sine_init.` / `sine_sample.` / `sine_render.` | PC `0x180000` / `0x18000f` / `0x18004c` |
| Synthetic physical byte ranges | code `[0x300000,0x300140)`, data `[0x2c0000,0x2c0098)` |

**Those synthetic addresses are not reserved or safe in a DN2/DT2 OS.** The
map reports byte placement; executable code addresses, function symbols and
the disassembler use 16-bit SW parcels. Data addresses are bytes. The map's
global-symbol list contains section-relative offsets, whereas the executable
symbol table has linked addresses; use the latter for entrypoints.

The argument register is R4, and `sine_sample` returns float bits in R0.
Calls emit `CJUMP`, delayed frame stores, indirect return and `RFRAME`.
Render adjusts I7 by +/-8 with `(NW)`, and sample by +/-4 with `(NW)`.
The execution check below measures their combined stack use in bytes and
supplies the required synthetic caller state. There is no startup object.
The later stock adapter must establish its own compatible context.

## Checks and compiler limitations

The checker inspects the pinned `seldump` output and bounds-checks its byte
ranges. It requires the exact executable bytes inspected for this probe,
distinct real function addresses, complete symbol closure, the intended
IEEE-754 table and `(1,4,4,4)` for `sizeof(char,uint32_t,float,void*)`. It
accounts for every code byte in disassembly and checks the logical phase
shift, table store, call, float negation and return forms. A second fresh
compile/link must be byte-identical. A source or tool change needs deliberate
reinspection; this is not a general compiler certification harness.

Ten negative checks cover a zero-exit tool diagnostic, a truncated file, a
zero entrypoint, corrupt table data, a missing render export, stubbed render
code, wrong width data, malformed C, an unresolved helper and the following
real compiler defect:

```c
const float bad_sample = -0.125f;
```

Selache at this pin exits successfully but emits bits `0xc2000000` (-32.0),
instead of `0xbe000000` (-0.125). The checker independently decodes the object
data with Python's binary32 reader and retains this reproduction. The sine
avoids negative float initializers: its emitted runtime negation is
`F3 = -F1`, with the result moved into R0. The execution check exercises that
form, including negative zero.

The compiler also accepts an unknown option silently. Switching this source
to `-char-size-32` produces an identical executable. That switch changes a
preprocessor macro, but the backend's historical char-size argument does not
control data layout ([preprocessor](https://github.com/js216/selache/blob/2b26d3b75c53063575bc5c820fa0d38879335187/selcc/src/lib.rs#L30-L57),
[backend](https://github.com/js216/selache/blob/2b26d3b75c53063575bc5c820fa0d38879335187/selcc/src/emit_asm.rs#L35-L43)).
The measured four-byte float/uint32 accesses suit this probe; they do not
qualify narrow loads, arbitrary C, or a general byte-addressed ABI. Neither
the option spelling nor assembler attributes prove those properties.

## Execute the compiled sine

Build the loader tool from the same Selache checkout, then fetch the external
runner once. No firmware, stock manifest or Digikit device setup is needed:

```sh
(
    cd out/selache
    mise exec rust@1.98.1 -- cargo build --release --locked -p selload
)
git clone https://github.com/ElekLabs/digikit.git out/digikit
(
    cd out/digikit
    git checkout --detach 38dfbe4ae88263511eed95691c07fc07e17b6f26
)
mise exec python@3.12.13 -- python examples/sharc-sine-probe/execute.py out/selache out/digikit
```

Both arguments may name existing clean checkouts at those exact pins. This
command reruns the complete compile qualification into a new output folder,
links `caller.s`, and verifies the original 320 code bytes and 152 data bytes
remain unchanged. It checks the loader stream's code parcel byte order and
data bytes, then uses Digikit's existing `LoadedMemory` and `Runner` APIs.
The Digikit checkout is read only; no dependency installation is needed for
this runner path. The one-argument `qualify.py` command remains compile only.

Expected final line:

```text
PASS: 18 blocks, 6 float returns, 7 execution negatives.
```

`execution-report.json` is written only after all checks pass. It records the
runner pin and imported-source hashes, caller and tool hashes, commands,
static decoded forms, per-call instruction counts, actual register changes,
stack depths and exact return PCs. `samples.json` contains 256 deterministic
440 Hz samples; `execution.dxe`, `execution.ldr`, map and disassembly retain
the exact author-only executable. `report.json` separately records compile
qualification; its existence alone does not imply execution passed.

The check compares every sample's binary32 bits and both persistent state
words against an independent host calculation. Eighteen 32-sample blocks
cover all 64 table phases and quadrants, bit 31, uint32 wrap, zero increment
and repeated rendering. Each case starts with deliberately dirty state and
checks init, then repeats init after rendering. Six direct sample calls
check the R4 argument/R0 float-return path, including `0x80000000`'s negative
zero. There are no emitted numeric conversions to qualify: phase shifts,
integer additions and float negation are exercised directly.

The 24-byte synthetic caller pushes its frame link and return address.
It supplies byte-addressed I6/I7, M5=0, M7=-1, M13=0, M14=1, zero DAG lengths,
MODE1=0 (SISD), and the runner's explicit `assume_nw32=True` setting. General
registers, DAG bases/modifiers, inactive registers and flags carry sentinels.
The observed maximum I7 drop is **64 bytes**, including the caller and nested
sample frame; init uses 8 bytes. Every call must return to the exact sentinel
within 3,000 instructions. Render takes 1,654–1,686 interpreter instructions
depending on sign branches; these counts are **not SHARC cycles**.

Render changes R0–R7, I4, I12 and ASTATX in this setup; I6/I7 return to their
entry values. The harness requires R8–R15, all remaining seeded DAG/mode
registers, inactive bank, hardware PC stack, loop/status stacks and guard
bytes to survive. A write watch checks every guest store, including stores
that reproduce an existing value: only the current function's state words,
32 output words and its bounded stack are permitted. The uninitialized-memory
zero-fill option, approximate reciprocal option, provisional instructions
and external-call continuation remain disabled.

The instruction check is deliberately limited to the emitted probe. Its
operand allowlist, branch boundaries, two delayed slots and indexed-store
register classes follow the [SHARC+ programming reference, rev 1.5](https://www.analog.com/media/en/dsp-documentation/processor-manuals/sc58x-2158x-prm.pdf),
chapters 12–16; byte-pointer/NW scaling is described in chapters 6–7.
In particular, indexed DM stores exclude DAG1 source registers, and indexed
PM stores exclude DAG2 sources (pp. 13-13, 13-16, 15-7 and 15-10); direct
absolute stores are exempt. A negative `DM(I7,M7)=I6` is actually assembled,
disassembled and rejected by this manual-derived rule. Digikit independently
decodes every instruction extent; agreement alone is not the legality test.
Unknown mnemonics, a non-return bound, insufficient stack, unknown NW width,
an output pointer shifted by one word and a mutated table also fail.

The small checker tests need only Python:

```sh
mise exec python@3.12.13 -- python tests/test_sharc_probe.py
```

This proves this kernel in the explicit synthetic context only. It does not
model caches, DMA, interrupts, Boot ROM, hardware timing or the stock hook.
The numeric and register checks cover binary32 values; the runner does not
establish preservation of a hardware 40-bit floating-point context.
It is not broad compiler/ISA qualification. The fixed-tone hardware change
in #41 must add #35's actual hook-wrapper context and instruction checks,
including DAG I/B/L/M preservation and B-before-I restoration if needed.
ModelDigi work extends this harness only for operations its port emits.

## Source and license closure

All four tools come from
[Selache `2b26d3b75c53063575bc5c820fa0d38879335187`](https://github.com/js216/selache/tree/2b26d3b75c53063575bc5c820fa0d38879335187),
whose tool sources declare GPL-3.0. `Cargo.lock` is used unchanged. The only
included library file is
[`libsel/include/stdint.h`](https://github.com/js216/selache/blob/2b26d3b75c53063575bc5c820fa0d38879335187/libsel/include/stdint.h),
which declares MIT and contains typedefs/macros, not runtime code. Its SHA-256
is `a9ee83d975c9606dccf6dc5b8b6792ba6a92603411f5c7448ab685d4fd00c40c`.
This example's sources declare GPL-2.0-or-later.

Execution additionally runs Selache's `selload` and imports the separately
checked out [Digikit runner](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/tools/sharc_dev/sharc_run.py).
Digikit is AGPL-3.0-or-later. Its implementation is not copied into Elekloader
or bundled with this example; the report hashes the external files used.

The linked runtime-file set is empty. In particular, neither MIT startup nor
`libsel/src/support/runtime.s` is linked. The latter's GPL-3.0 declaration
differs from libsel's broad MIT description; future kernels that use its
helpers need their own file-level review. This records the actual sources
used, rather than resolving licensing for code this artifact does not use.

## Optional proprietary fallback

CCES is owner-installed and is not required or automatically downloaded by
this workflow. ADI's [CCES page](https://www.analog.com/en/resources/evaluation-hardware-and-software/software/adswt-cces.html)
lists ADSP-21569 support and license choices; an EZ-Kit license excludes
simulator targets. A suitable activated license must be available to the
account running a headless build.

The [CCES 3.1 installation guide](https://download.analog.com/tools/CrossCoreEmbeddedStudio/Releases/Release_3.1.0/CrossCoreEmbeddedStudio_Installation_Guide.pdf)
lists Windows and Ubuntu 20.04/22.04, with no native macOS host. On Linux,
install CCES first, then the separate SHARC+ Linux Command-Line Tools, and
put the installed tools on PATH for make/command-line builds. They support
functional simulation, not cycle-accurate simulation. A fallback would need
its own verified compiler/link flags, executable inspection and ABI execution
checks; Selache commands are not claimed to work unchanged. CCES was not
installed or run for this probe.
