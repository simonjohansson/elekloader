# SHARC support: first DN2 build

Work starts on `sharc`, based on `digitone-2-support` at
`af1b4212a1e4444f161d333492313a980a5d92d2`. The first target is Digitone II OS
1.12 and the ADSP-21569 SHARC+ VISA instruction set. No silicon stepping has
been observed; the profile records it as unknown. OS 1.12 and a compiler's
`-proc ADSP-21569` switch do not identify the chip revision.

The release's `sharc` metadata in `elekloader/devices/digitone_mk2.py` and
`js/src/devices.ts` records identity, capacities, address views and exclusions.
It grants **no runtime memory**: `owned_ranges` / `ownedRanges` is empty. It does
not enable a SHARC artifact ABI or change what existing mods may write. The
Octatrack's `dsp_payloads` / DSP56300 path remains separate.

## Reproduce the stock evidence

The assertion procedure needs only Elekloader and Python. No external decoder,
compiler or device is needed. It prints hashes and counts, never extracted bytes,
and keeps the exact no-change rebuild in memory.

```sh
mise exec python@3.12.13 -- python tests/test_sharc_profile.py
ELEKLOADER_DN2_SYX=/path/to/Digitone_II_OS1.12.syx \
  mise exec python@3.12.13 -- python tests/test_sharc_profile.py
mise exec node@24.21.0 -- node --test js/test/sharc-profile.test.ts
```

Without the stock environment variable, the two stock-dependent tests explicitly
skip. With it, every test runs; an incorrect or missing supplied file fails.
The tests verify the release identities, the current sender-analysis hash,
record inventory and exact outer no-change write/verification. They are host
checks, not boot or audio acceptance. Nothing is flashed or written as firmware.

| DN2 1.12 measurement | Value |
|---|---|
| Stock SysEx SHA-256 | `7e5b8a733d4ab1fdf7e5d22757f7d8eddaa3cbf71d0858874a791844c02ceb35` |
| Stored section 7 SHA-256 | `5ff93df8747bdf9eb28acf50391fb484d6aa6782bfe969b2b3807a8412645660` |
| Decoded section 7 SHA-256 | `336e340aa0cdcd34e314cfa44849f709a3134f6bd4cd57dfc7e15702c83115e2` |
| Stored / decoded DSP | 602,076 / 836,956 bytes |
| SysEx / container | 2,390,304 / 1,886,016 bytes |
| Records / FILL records | 95 / 37 |
| FIRST / INIT / FINAL records | 2 / 1 / 1 |
| Highest boot-loaded L2 endpoint | `0x2008823c`; this is not a free-memory boundary |

The stock stream's two FIRST entries are `(offset, PC16, next-distance)`:
`(0, 0x120230, 0x2964)` and `(0x2974, 0x1c12e2, 0xc9bd8)`. INIT is at
`0x2964`, FINAL at `0xcc54c`, and the stream ends at `0xcc55c`.
FIRST distances start after their own 16-byte headers. Entry addresses count
two-byte instruction parcels (PC16); an odd numeric PC16 address is valid.
Actual nonempty load/FILL targets and counts have four-byte alignment. Preserve original ordering: initialization loads are
legally overwritten by later application records.

## Independent budgets

These constraints apply separately; passing one does not satisfy another.

| Constraint | Limit | Evidence |
|---|---:|---|
| Stored DSP section 7 | `0x100000` bytes | ColdFire sender's first staging buffer |
| Decoded DSP stream | `0xfffff` bytes | Second 1 MiB staging buffer also carries a command byte |
| Decoded update | 8-byte preamble + container ≤ `0x200000` | DN2 branch's conservative measured USB cap |
| Flash endpoint | `flash_at + container ≤ 0x380000` | Stock settings store; container begins at `0x80000` |
| Main image unpack | No overwrite of unread packed input | Existing `syx.verify` in-place simulation |

The exact 828-byte sender region at main address `0x400cf4b0` hashes to
`fca04573f758de9f75fb20b3a56ebf4fc97d20ee8a21fa1a6f990219328cc082`.
The stock assertion checks it against the published
[sender analysis](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/docs/findings/06-sharc-engine-and-startup.md#L5221-L5255).
That is static evidence for the DSP staging limits, not execution of overflow
paths. The [DN2 device evidence](DEVICES.md#the-digitone-ii-112) explains the
separate outer transfer/flash and main-image checks.

Stock leaves 446,500 stored-DSP bytes, 211,619 decoded-DSP bytes and 211,128
bytes below the update cap. These are encoding budgets, **not free DSP RAM or a
promised module size**. Every final output must include packing, alignment,
record headers, the seal and any ColdFire growth in its own checks.

## Address views and excluded memory

The [ADSP-2156x data sheet, Rev. D Tables 2–6](https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21562-21563-21565-21566-21567-21569.pdf)
distinguishes byte, normal-word and short-word addresses. For this slice:

| View | Meaning |
|---|---|
| Core byte | A C/data byte pointer in one of the four qualified L1 capacity windows |
| Loader byte | Physical byte destination in the boot stream; L1 adds `0x28000000` to the core byte view |
| PC16 | A VISA instruction address in two-byte parcels; L1 loader byte = `0x28000000 + 2*PC16` |

Thus master-buffer byte `0x268438` maps to loader byte `0x28268438`, while
H1 PC16 `0x1c244d` maps to loader byte `0x2838489a`. Multiplying a data pointer
by two would be wrong. An entry's two-byte alignment does not permit an
unaligned load record. Normal-word addresses are not an artifact unit.

The profile records four L1 capacity windows, an L2 byte window of
`[0x20000000,0x20100000)` with its PC16 view, and the DDR byte window.
Capacity and address equivalence never establish ownership. In particular,
boot-unloaded L2 contains live firmware pointers, and the investigated 2 KiB
L1 interval `[0x2dd600,0x2dde00)` still needs valid-frame runtime evidence in
[#35](https://github.com/simonjohansson/elekloader/issues/35).

New payloads must exclude the DN2 special window
`[0x200fa000,0x200fe000)`, Boot ROM workspace from `0x200fe000` to the end of
the supported L2 window, and the configured cache tails at loader bytes
`[0x282ec000,0x282f0000)`, `[0x2831c000,0x28320000)` and
`[0x2839c000,0x283a0000)`. Addresses beyond the supported capacity windows are
also refused. The exclusions follow the bounded
[memory investigation](https://github.com/naturarum/dn2-cfw/blob/5c95c78180348c825518f2bda8d2cf1afb2a312a/notes/T3.2-sharc-memmap.md#L293-L303)
and its [cache correction](https://github.com/naturarum/dn2-cfw/blob/5c95c78180348c825518f2bda8d2cf1afb2a312a/notes/T3.2-sharc-memmap.md#L586-L593).

## Source and runtime provenance

| Material | Use in this slice |
|---|---|
| Original Elekloader metadata and assertions | GPL-2.0-or-later; the matching original TypeScript port is GPL-3.0-or-later |
| ADI data sheet / hardware reference | Address and boot-format facts; no vendor implementation copied |
| Digikit `38dfbe4ae88263511eed95691c07fc07e17b6f26` | Separately installed AGPL research oracle and published measurements; no parser, emulator or runtime source copied into Elekloader |
| Selache `2b26d3b75c53063575bc5c820fa0d38879335187` | External GPL-3.0 compiler/assembler/linker; only its MIT `stdint.h` is included by the current sine |
| Selache startup, generic linker map and division runtime | Not copied or linked into the sine; division-runtime license/header mismatch remains relevant only if later code needs it |

The [compiler probe](../examples/sharc-sine-probe/README.md) documents its exact
inputs and fallback toolchain. The [boot-record implementation](SHARC-BOOT.md) is original code against the
narrow format facts and independent synthetic vectors. No
current Digikit source is vendored, and an external development tool does not
become an embedded runtime merely because it inspected an artifact.
