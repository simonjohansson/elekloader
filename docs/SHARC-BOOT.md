# DN2 SHARC boot records

`elekloader/sharc.py` and `js/src/sharc.ts` implement the small record subset
observed in Digitone II OS 1.12. They preserve original headers, payloads,
ordering and legal boot-phase overwrites. This is the record layer for
[#32](https://github.com/simonjohansson/elekloader/issues/32), with the release
facts from [the DN2 profile](SHARC-DN2.md). It does not enable a SHARC mod or
change the outer firmware writer, SDK, mod format or Octatrack DSP path.

The implementations are original. The format reference is the
[ADI ADSP-2156x Hardware Reference, boot chapter](https://www.analog.com/media/en/dsp-documentation/processor-manuals/adsp-2156x_hwr.pdf).
The independent synthetic insertion was specified before these implementations
and checked with the separately installed
[manual-derived checker at Digikit `38dfbe4`](https://github.com/ElekLabs/digikit/blob/38dfbe4ae88263511eed95691c07fc07e17b6f26/tools/sharc_dev/sharc_bootcheck.py).
No Digikit parser/checker source is included, and the tests require no external
decoder or compiler. These checks establish byte/structure correctness, not
successful Boot ROM execution or runtime ownership.

## The supported subset

Each header contains four little-endian uint32 values: block code, target,
byte count and argument. The block code has signature byte `0xad`, an XOR byte
at byte offset 2, and flags in its low 16 bits. XOR over all 16 header bytes
must be zero. Every supported flag combination preserves the observed low bit
0; other combinations are refused, including standalone ignored records.

| Flags | Meaning in this subset | Bytes following header |
|---|---|---|
| `0x0001` | Load to loader-byte target; argument is zero | `count` payload bytes |
| `0x0101` | Fill loader-byte target; argument is the repeated uint32 word | None |
| `0x5001` | FIRST + IGNORE; target is entry PC16; argument links applications | None; count is zero |
| `0x0801` | INIT at the preceding FIRST entry | None; count and argument are zero |
| `0x8001` | FINAL at the preceding FIRST entry | None; count and argument are zero |

Each application begins with FIRST and ends in INIT or FINAL. INIT permits a
following application; FINAL ends the entire stream. In this observed subset,
INIT/FINAL targets match their FIRST target. Each FIRST link is measured from
**after its own 16-byte header**:

```
next FIRST offset (or stream end) = FIRST offset + 16 + FIRST argument
```

The reader rejects malformed counts, headers, links, ordering and trailing
bytes. Loads/fills must be nonempty and their loader-byte addresses and counts
must be divisible by four. Entries use PC16 instruction parcels: an odd
numeric PC16 address is valid because it still maps to an even physical byte
address. The stock final entry `0x1c12e2` maps to loader byte `0x283825c4`.
The corpus also tests entry `0x1800b9`, which maps to `0x28300172`.

`byte_span` / `byteSpan` maps explicit `loader-byte`, `core-byte` or `pc16`
addresses to a canonical half-open loader-byte interval. Size always means
bytes. It rejects other units, out-of-capacity spans, wraparound and protected
ranges. Parsing maps existing records with the protected-range allocation
check disabled: an exclusion for new code must not erase or reorder historical
loads. This structural parse alone does not authorize a changed stock stream.

## One insertion

`insert` accepts loader-byte loads `(address, bytes)` and fills
`(address, byte_count, uint32_word)`. It first parses the input and checks its
exact decoded-stock hash. Every new span must lie wholly inside a
profile-owned interval, avoid protected memory and avoid every original or
new load/fill interval. Original overlaps remain legal and ordered.

The operation inserts the supplied loads, then fills, immediately before the
original FINAL. Only the last FIRST header changes: its argument grows by the
serialized insertion length and its header XOR is recomputed. Every other
original byte remains exact. The result is parsed again before it is returned.
The exact-stock hash also prevents accidentally appending to a previous result.
Calling with no additions returns the original bytes unchanged.

The active DN2 H1 bridge additionally needs one six-byte instruction replaced
inside a stock LOAD record. `insert(..., patches=...)` takes loader-byte
`(address, expected_stock_bytes, replacement_bytes)` tuples. The decoded
stock hash is checked first; the range must be explicitly listed in the
device profile, exactly match the expected bytes, and belong to one
unambiguous LOAD record. The record header, size, order and every other stock
byte stay unchanged. This does not make arbitrary overwrites or boot-phase
overlay records available to mods.

The production DN2 profile has **no owned ranges**, so it refuses every
nonempty insertion. The test profile explicitly grants a tiny synthetic L2
interval. Runtime qualification in #35 and integration in #37 must establish
the eventual reservation and consumer path; a capacity map or boot-unloaded
interval alone cannot grant memory.

The reader and insertion enforce the profile's decoded-stream budget. Stored
section size, outer transfer/flash limits, compression, seal verification and
permitted stock code patches belong to the later container integration. No
modified stock firmware is emitted by this slice.

## Tests

The checked-in [shared corpus](../tests/fixtures/sharc.json) contains no
firmware bytes. Its 104-byte original has two applications with an intentional
ordered overwrite. Adding a four-byte load plus an eight-byte fill adds 36
serialized bytes: the first FIRST argument stays 36 and the last grows from
36 to 72. The fixed 140-byte expected result has SHA-256
`29ec95ee30753ff65bf4baab5496b544b18bda4b460c32be5a186fd630ac1305`.
Expected output is literal, not generated by either implementation under test.
Both engines consume the same valid/invalid records, alias cases, insertion
boundaries and exact refusal messages.

```sh
mise exec python@3.12.13 -- python tests/test_sharc.py
mise exec node@24.21.0 -- node --test js/test/sharc.test.ts

ELEKLOADER_DN2_SYX=/path/to/Digitone_II_OS1.12.syx \
  mise exec python@3.12.13 -- python tests/test_sharc.py
ELEKLOADER_DN2_SYX=/path/to/Digitone_II_OS1.12.syx \
  mise exec node@24.21.0 -- node --test js/test/sharc.test.ts
```

Without the environment variable, the owner-stock test explicitly skips.
With it, both readers preserve all 95 original records and 15 overlapping
load/fill pairs, reproduce the decoded stream byte for byte, and reproduce and
verify the original outer firmware in memory. Stored/decoded hashes and sizes
must match the profile. No extracted data or generated firmware is saved.
