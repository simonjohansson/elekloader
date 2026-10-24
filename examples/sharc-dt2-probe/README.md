# DT2 sine preparation: stock check

This is a read-only evidence probe for Digitakt II OS 1.17, not a mod or a
flashable sine. It needs only Elekloader, Python and your own stock file:

```sh
mise exec python@3.12.13 -- python examples/sharc-dt2-probe/check_stock.py \
  /path/to/Digitakt_II_OS1.17.syx
```

It checks identities, boot records, code landmarks and an exact no-change
rebuild in memory. It prints hashes and counts and writes no firmware.
[The DT2 findings](../../docs/SHARC-DT2.md) distinguish static facts, bounded
emulator evidence and the remaining runtime and physical gates.
