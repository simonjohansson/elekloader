# SHARC sine compiler probe

This is the firmware-free compiler qualification for
[issue #31](https://github.com/simonjohansson/elekloader/issues/31). It builds
an actual SHARC+ sine kernel, checks its executable and retains the artifacts
for [target execution in #33](https://github.com/simonjohansson/elekloader/issues/33).
It is **not an installable mod**. There is no `mod.json`, firmware input,
boot stream, stock hook or device operation. The normal module build workflow
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
PASS: 320 code bytes, 152 data bytes; 10 negative checks. Target execution remains issue #33.
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

The observed argument register is R4, and `sine_sample` returns float bits in
R0. Calls emit `CJUMP`, delayed frame stores, indirect return and `RFRAME`.
Render adjusts I7 by +/-8 with `(NW)`, and sample by +/-4 with `(NW)`; these
instruction operands are not a measured stack byte budget. I6/I7, M5/M7/M14,
addressing mode, register preservation, frame setup and return semantics
must be established by #33 and the later stock adapter. No startup initializes
them here. The probe does not claim a stock-compatible ABI or stack high-water
mark.

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
`F3 = -F1`, with the result moved into R0. Execution of that form remains #33.

The compiler also accepts an unknown option silently. Switching this source
to `-char-size-32` produces an identical executable. That switch changes a
preprocessor macro, but the backend's historical char-size argument does not
control data layout ([preprocessor](https://github.com/js216/selache/blob/2b26d3b75c53063575bc5c820fa0d38879335187/selcc/src/lib.rs#L30-L57),
[backend](https://github.com/js216/selache/blob/2b26d3b75c53063575bc5c820fa0d38879335187/selcc/src/emit_asm.rs#L35-L43)).
The measured four-byte float/uint32 accesses suit this probe; they do not
qualify narrow loads, arbitrary C, or a general byte-addressed ABI. Neither
the option spelling nor assembler attributes prove those properties.

For #33, run the actual `sine.dxe` code with bounded, guarded state/output/stack
and explicit calling-convention setup. Include phases on both sides of bit
31, all quadrants, uint32 wrap, zero increment, init reset and repeated
32-sample blocks. Phase `0x80000000` intentionally returns negative zero.
Require actual return, samples and state; compiler success or runner exit
zero is insufficient. These execution, sound, timing and hardware checks
have not run in #31.

## Source and license closure

All four tools come from
[Selache `2b26d3b75c53063575bc5c820fa0d38879335187`](https://github.com/js216/selache/tree/2b26d3b75c53063575bc5c820fa0d38879335187),
whose tool sources declare GPL-3.0. `Cargo.lock` is used unchanged. The only
included library file is
[`libsel/include/stdint.h`](https://github.com/js216/selache/blob/2b26d3b75c53063575bc5c820fa0d38879335187/libsel/include/stdint.h),
which declares MIT and contains typedefs/macros, not runtime code. Its SHA-256
is `a9ee83d975c9606dccf6dc5b8b6792ba6a92603411f5c7448ab685d4fd00c40c`.
This example's sources declare GPL-2.0-or-later.

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
