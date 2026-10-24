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
