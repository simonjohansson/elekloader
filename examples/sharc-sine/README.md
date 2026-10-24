# DN2 SHARC sine: inert installation starter

This example proves that an ordinary DN2 mod can carry prelinked SHARC+ code
through SDK build, lint and firmware patch. **It does not make sound.** The
`entries:null` artifact is installed in section 7 but has no H1 audio hook;
playable fixed sine is the separate [#41](https://github.com/simonjohansson/elekloader/issues/41)
gate. Key tracking follows that gate.

`sine.c` and `entry.c` are author source. `sine.sharc.json` is their prelinked,
loader-order output; it contains no bytes from stock firmware. Its 424 code
bytes and 152 data bytes came from the pinned Selache H1 probe in
`examples/sharc-sine-probe/h1.py`. That probe checks the ELF section map,
symbols, relocations, data layout and code hashes before converting each
16-bit code parcel to loader byte order. The inspected H1 executable had
SHA-256 `238339a708a64f06e4423736f628db86bb61ed3713b1a419de603ba8a8a82aa8a`;
the converted code and data SHA-256 values are
`df7217bcb14bb7e693a03ff0fe83680dd30cbfc1230fd1fbed39665495cd4bc2`
and `17f735313bf151356989a7b29ec0cab9ea189a59062f5e22ab521d6f40946c9f`.
Those are author-output provenance, not device execution evidence.

Set `DN2_STOCK` to your exact Digitone II OS 1.12 `.syx` and `DN2_CORE` to a
matching `core-dn2` `.elemod`. Then use the same commands as any format-2 mod:

```sh
python -m elekloader.sdk.build examples/sharc-sine --stock "$DN2_STOCK"
python -m elekloader.lint examples/sharc-sine/out/sharc-sine-0.1.elemod --stock "$DN2_STOCK" --with "$DN2_CORE" --json
python -m elekloader.patch --stock "$DN2_STOCK" --mod "$DN2_CORE" --mod examples/sharc-sine/out/sharc-sine-0.1.elemod --out sine-inert.syx --version SN01
```

The SDK needs no SHARC compiler for these commands. It validates and embeds
the existing artifact, and the patcher independently verifies the resulting
firmware. If you edit the C, regenerate `sine.sharc.json` with your own
SHARC+ compiler and linker before running the SDK. The SDK cannot infer
whether a prelinked artifact reflects a changed C file. The exact artifact
shape and owner checks are in [FORMAT.md](../../docs/FORMAT.md#digitone-ii-sharc-app-inert-gate).
