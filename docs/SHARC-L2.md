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
32-bit pointer is not justified. The DDR occurrence of `0x200918c0` was initially unclassified. The later
[bounded consumer check](#the-apparent-ddr-pointer-has-a-halfword-data-consumer)
identifies it as two signed-halfword table elements for that reader.

A private index built using [DigiKit's SHARC analysis](https://github.com/ElekLabs/digikit/tree/38dfbe4ae88263511eed95691c07fc07e17b6f26/tools/sharc_dev/sharcdb)
found no decoded direct memory accesses, data references or propagated
pointer targets into `0x20088240..0x200f9fff`. It resolved 2,979 propagated
pointer rows and left 192 unknown; this analysis covers only a subset of
25,878 indirect accesses. It cannot establish global memory ownership. The private database records
`tool_commit=38dfbe4a`; this corrects the earlier prose source attribution
to `9dee5d56`. A later Type3d width discrepancy also limits its footprint
claims; see [#53](https://github.com/simonjohansson/elekloader/issues/53).
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
A ten-minute note sweep extends the physical evidence below, but sustained
heavy stock-project stress, all indirect users, interrupt interleavings
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
margin or ModelDigi. #51 retains the incomplete memory audit, including #53; #41 retains
physical timing/context work, and #42 retains the larger stack.

## The apparent DDR pointer has a halfword data consumer

The word at loader `0x804aa2e0`, read as uint32, numerically equals
`0x200918c0`. Record 23 supplies a pointer/length descriptor at loader
`0x28266e00` (index 31 of the array beginning `0x28266d08`): data start
`0x804a9908`, count 4,800. Its 9,600-byte data region ends at `0x804abe88`.
The apparent pointer occupies elements 1,260 and 1,261 of this table.
The bounded checker also executed the lookup address calculation/data load
for index 31 and the length-load delay-slot instruction: R0 returned the
expected data pointer and R1 returned 4,800, without a synthetic return frame.
Stock lookup PC16 `0x1c8110` computes the eight-byte descriptor index;
its callers at `0x1c7292` and `0x1c72ac` save the resulting pointer/count
into voice state. The reader at `0x1c78b9` loads from that data pointer.

A bounded concrete run of this exact stock instruction, using DigiKit
`38dfbe4ae88263511eed95691c07fc07e17b6f26`, explicitly seeded `MODE1=0`,
`I0=0x804aa2e0`, `M6=1`, `L0=0`. It read exactly two bytes, returned 6,336,
and advanced I0 by two. Starting at the next element returned 8,201.
Mutating only the low element changed only the first result; mutating only
the high element changed only the second. All ten bounded cases passed, including negative signed values,
with watched reads at the DDR data and no access to the candidate L2 window.
This identifies the numerical match as table data for the known consumer,
not a demonstrated L2 pointer. It is a modeled data-flow result with an
explicit SISD seed, not a complete engine or physical memory observation.

The investigation also found a separate tool mismatch: the static DB's
`mem_access` calls this Type3d load `normal-word`, while the concrete
executor correctly takes the signed-halfword path for `w=0,ex=0,l=1,x=1`.
Its comments and existing executor tests explain the encoding; the static
width function/test retain the earlier interpretation. Its pointer
propagation also advances I0 by four for this example, rather than the
executed two. This affects derived addresses, not just display labels.
#53 tracks aligning width and modifier scaling and redoing the static audit. No DigiKit code
or Elekloader acceptance check was changed to make this probe pass.
Until that is reconciled, the existing index is supporting evidence, not
a complete access-footprint proof. The all-indirect-users limitation remains.

Private source scripts, watch logs and mutation results are in
`out/sharc51-sustained-20261024/ddr-consumer-proof.json` and the copied
`sharc-ddr-consumer-proof.py` beside it. No stock bytes are distributed.

## Stock-emulator canary check

A separate coupled native run used the exact stock OS, without an app or
bridge patch. The running emulator alone filled all 32 KiB of the candidate
with `0xa5`; no firmware file or device memory was changed. The harness
verified the whole range, deliberately changed its last word by one byte,
confirmed the mismatch was detected, then restored the canary.

The entire reservation was unchanged at checkpoints across idle and four
held/released 16-note MIDI chord inputs, spanning 1,380 DSP blocks. The
modeled DSP progressed with no reported halt or missing block. This is
bounded stock-emulator evidence, not a verified 16-voice physical workload.
Checkpoint comparison cannot detect reads, same-value writes, or values
written and restored between checks, and it does not model real cache
coherency. It does not resolve #53's static pointer-scale discrepancy.

Private report: `out/sharc51-sustained-20261024/stock-canary/report.json`;
probe: `sharc51-stock-canary.py` beside the other private scripts. Native
emulator pin remains `ded547e14e63977c1a6e808812d46243e13c43d0`.

## Ten-minute physical note sweeps

A later run tested each unchanged L2 candidate for ten minutes on the
connected DN2. Both completed 392 note/release pairs: all 49 supported
notes (36..84), eight times each, in changing orders. This varies the
signal throughout the run instead of accepting a repeating audio buffer.
Each capture had 28,800,512 stereo frames over 600.0107 seconds, 56,251
buffers and zero dropped capture buffers. All expected note regions were
present, stereo channels matched exactly, samples were finite, peak was
0.17857146, and the final five seconds were silent. Pitch error stayed
below 0.090 cent at nominal 48 kHz; the capture clock was not calibrated.

| Candidate | Maximum absolute pitch error, cents | Capture SHA-256 |
|---|---:|---|
| C `LC03` | 0.0880 | `bb81535c25b0137a2ae9abbf03e1c476f69d82ebd9922f46bc1ecefbe005460f` |
| ASM `LA03` | 0.0899 | `cba4c2512a53f6792065f86bfe7018c56ee48def0233c87c830864faf0804eb4` |

The analyzer checked every note's frequency and on-time, 10 ms active RMS
windows and bounded adjacent sample differences, plus the full stereo and
finite-sample checks. These checks can detect gross gaps or discontinuities;
they cannot exclude every sub-window glitch. Zero capture drops describes
the host capture, not an internal hardware overrun counter.

This used the current project without saving/loading projects or changing
machines, effects or UI settings. It is sustained note-sweep qualification,
not a heavy stock-project/FX benchmark. The required DigiHealth 1.3 remained
responsive after both runs. The final verified device version was `LC03`,
with the last note released. The existing helper's unavailable render-load
fields do not measure SHARC progress or exceptions.

The [source investigation of stock reply word 0](https://github.com/angellinares/dn2_firmware_explore/blob/39815895720b84c59ce2fa0ff5b13bd47dc415d2/docs/sharc-load.md)
records counterintuitive decreases when work increases and does not establish
that counter as total DSP load. No hardware cycle-margin or C/ASM speed
claim is made from it. The earlier interpreter instruction benchmark and
these physical audio results remain separate evidence. #41 retains the
qualified timing/readout work; no new telemetry channel, hook or protocol
was introduced in this increment.

Private captures, events, strict analyzer and complete results are in
`/Users/simonjohansson/src/elekloader-sharc/out/sharc51-sustained-20261024/`.
`validation-report.json` ties together both physical captures, the stock
canary, descriptor/halfword mutations, tool/source pins and 35 passing
Python unit tests plus five passing linker-refusal suites. This increment
changes documentation/evidence only; the tested firmware bytes are unchanged.
