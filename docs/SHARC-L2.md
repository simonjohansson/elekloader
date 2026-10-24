# Bounded DN2 L2 app placement

Issue [#51](https://github.com/simonjohansson/elekloader/issues/51) adds an
experimental 32 KiB placement for the existing keyed master-output callback
contract on exact Digitone II OS 1.12. It is one bounded reservation, not an
allocator or a claim that the rest of L2/DDR is free. Existing L1 mods retain
their original ABI and placement. The pinned bridge, H1 instruction patch,
stack limits, guards, stock identity, protected ranges, overlap checks and
outer firmware verification remain in force.

## Placement

| Bytes | Loader address | Instruction view |
|---|---|---|
| L2 app | `0x20090000..0x20097fff` | PC16 `0xbc8000..0xbcbfff` |
| Reference code area | first 16 KiB | Selache SW LDF byte alias starts `0x01790000` |
| Reference data area | `0x20094000..0x20097fff` | BW data uses its byte address |

The artifact covers the whole reservation with LOAD/FILL ranges. The linker
binds callbacks using the profile's address map, not a hardcoded L1 bias.
It installs the fixed pitch table at loader `0x282ddd98`, within the retained
L1 reservation. No callback, patch, or instruction from a stock image is
supplied by the app. The app still has at most 428 declared borrowed-stack
bytes after the bridge's 116; more code/data does not provide more stack.

## Evidence and uncertainty

Stock OS SHA-256 is
`7e5b8a733d4ab1fdf7e5d22757f7d8eddaa3cbf71d0858874a791844c02ceb35`;
its decoded section 7 is
`336e340aa0cdcd34e314cfa44849f709a3134f6bd4cd57dfc7e15702c83115e2`.
The last original L2 load ends at `0x2008823c`; protected special/ROM
workspace starts at `0x200fa000`. Absence of boot loads alone is insufficient.

A private earlier `L201` probe loaded 12,108 code bytes and 9,952 data bytes
in this window while the L1 sine played. `L202` executed an L2 sine on the
unit. Those probes bypassed normal packaging; they motivated this bounded
SDK integration rather than establishing arbitrary-program safety.

The [memory warning](https://github.com/angellinares/dn2_firmware_explore/blob/39815895720b84c59ce2fa0ff5b13bd47dc415d2/docs/waverider-dsp-silence.md)
reports apparent L2-tail pointers. For exact 1.12 stock, all three raw
`0x200c0008` matches are inside decoded compute instructions, not immediate
address operands. Both `0x200c1f84` matches occur in the same increasing
int16 sequence (including 8068, 8204, 8353); interpreting each pair as a
32-bit pointer is not justified. The DDR occurrence of `0x200918c0` remains
unclassified packed data and therefore an explicit unresolved observation.

A private index built using [DigiKit's SHARC analysis](https://github.com/ElekLabs/digikit/tree/9dee5d56c328e7091babdfd2c1d363657db78b96/tools/sharc_dev/sharcdb)
found no decoded direct memory accesses, data references or propagated
pointer targets into `0x20088240..0x200f9fff`. It resolved 2,979 propagated
pointer rows and left 192 unknown; this analysis covers only a subset of
25,878 indirect accesses. It cannot establish global memory ownership.
The exact DSP hash is registered there under 1.11; matching DSP bytes does
not prove the surrounding 1.12 runtime configuration is identical.

[DDR canary research](https://github.com/angellinares/dn2_firmware_explore/blob/39815895720b84c59ce2fa0ff5b13bd47dc415d2/docs/sharc-ddr.md)
reports a bounded physical scan with no observed writes above `0x80531000`.
That DDR observation does not establish this L2 reservation's ownership.
A canary cannot detect reads, same-value writes or overwrite-and-restore.

Use one qualified data-access view. The source investigation reports real
hardware silence after mixing cached DM/PM mutable DDR access; emulator
success does not qualify cache coherency. This change does not alter cache,
interrupt or memory-controller configuration. The 64-byte NOP tail is a
conservative packaging policy, not a cache/fetch proof for arbitrary code.
Long-running stock-project stress, all indirect users, interrupt interleavings
and physical cycle budgets remain separate qualification work in #41/#51.
ModelDigi's measured 1,204-byte stack drop still needs #42.

## Normal-build qualification on 24 October 2026

The external repository `/Users/simonjohansson/src/digitone-2-mod-hack`
provides `mise run build-c-l2` and `mise run build-asm-l2`. Each compiles its
current source, creates the artifact, and uses the submodule's ordinary
SDK, lint and firmware builder. The original L1 commands still produce
exactly the same firmware bytes. The local split is 16 KiB code, including
64 guard bytes, plus 16 KiB data; this permits 16,320 linked code bytes.
These particular C/ASM programs contain 676/524 linked code bytes and 204
data bytes each. Unused NOP/zero space is not counted as executed DSP work.

Fresh PX-fixed Digikit runs cold-loaded both exact generated firmwares,
read back the installed 16 KiB code segments and bound L2 callback words,
and observed changing state at `0x20094000`, 16 KiB into the app. Both ran
3,122 blocks, with no modeled halt/missing block, silent idle/release,
identical stereo channels and peak 0.125. Notes 60/69/72 played at about
523.24/880/1046.49 Hz (the external sources deliberately double phase).
Both PCM SHA-256 values are
`275cc7c6690f1c366a085920045998ffc337eae674b5a767e4f38d4fa9f910d7`.
This matches the previous L1 examples; it is emulator output, not a timing
calibration or a physical PCM hash.

The stock-backed checks passed: 35 Python units, five linker-refusal
suites, 24 SHARC tests, 27 DN2 tests, 144 TypeScript tests (no skips),
32 matching cross-engine cases (nine built, 23 refused), and five external
producer/toolchain tests. The latter cover the 16,320-byte code maximum
and refusal when the 64-byte guard would be lost.

Private reproducibility evidence is under
`/Users/simonjohansson/src/elekloader-sharc/out/sharc51-l2-20261024/`:
`preflash-checks.json`, per-variant build/emulator reports, parity inputs
and results, and the physical candidate budget/hash report. Source and
compiler identities are retained; firmware/captures are never committed.

## Physical USB note checks

Both normal-build L2 candidates passed on the connected DN2, with the
owner's DigiHealth 1.3 included and responding after each verified reboot:

| Candidate | Firmware SHA-256 | Decoded update bytes, including preamble |
|---|---|---:|
| C `LC03` | `63d17ffed02ddc4b141adaa1cbca9f80a7cd98ac7571cbb64fd439172bc477c9` | 1,933,224 |
| ASM `LA03` | `d93516ef54b9b6fcec9771852325d0c59eaf46ef09287458bf36549aff87bd2b` | 1,933,192 |

The limit is 2,097,152 decoded bytes, leaving at least 163,928 bytes.
DigiHealth module SHA-256 is
`731f55a9289bdb55f08c97fea662be0f653028551554c2146f7e3599f752b6ac`.
The update dialog was inspected before each authorized remote YES; installed
version and reset helper uptime were checked afterward. The first C version
check was too early and still saw the old image. That short capture was
retained as invalid, and the reported C capture was taken fresh after the
new version and reboot were established. No repeated confirmation was sent.

Each valid capture contains 864,256 stereo frames over 18.0053 seconds,
1,688 buffers and zero dropped buffers. Notes 48/60/69/72/81/84 played at
about 261.63/523.24/880/1046.53/1760/2093 Hz, within 0.082 cent at nominal
48 kHz. Stereo channels were identical, peak was 0.17857146, and the final
second was silent. The capture clock was not independently calibrated.
Changing notes followed by release-to-silence demonstrates continuing
processing for this workload; no cycle counter or exception telemetry was
added. USB output level differs from the emulator's pre-USB block level.

C capture SHA-256:
`75579eccd15d73697ed59b35d827637c183abbe45cf9b644b447c7b9e74e11c3`.
ASM capture SHA-256:
`9fb78a7a2095a9ebe5cff7de7f8f2674b2c695102ce1cda374342eca40960ea2`.
Reports/events/CAF files and the invalid early C capture stay in the private
evidence directory above. The device was left running `LA03`, with DigiHealth
responding and the last note released. These short USB tests do not qualify
all L2 users, sustained stock-project stress, DAC behavior, hardware cycle
margin or ModelDigi. #51 retains the unresolved memory observations; #41
retains physical timing/context work, and #42 retains the larger stack.
