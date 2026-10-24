# DN2 core with optional SHARC callback timing

This is core-dn2 0.2's same ColdFire hooks and source files, with the optional
`dn2-master-mono32-l2-metrics-v1` SHARC core. Select it together with an app
whose artifact uses that ABI; ordinary L1 and unmeasured L2 apps retain
`mods/core-dn2`. The existing SDK build/patch commands and five artifact keys
are unchanged. App code can change without an executable allowlist update.

The pinned core reuses the existing bridge bytes. Its wrapper times render
only (not init), accumulating raw EMUCLK count/sum/max. It uses 768 code bytes
including at least 64 NOP guard bytes, and 152 state bytes inside the old L1
app gap. Linked instructions are 628 bytes, actual state 76 bytes. The fixed
pitch table remains at 0x282ddd98; L2 remains 32 KiB. Core stack contribution
is 124 bytes (116 bridge + 8 wrapper), leaving at most 420 app bytes within the
unchanged gross 544-byte ceiling. A declaration is not a proven high-water
mark; every app still needs context/stack/write and deadline qualification.

The exact OS 1.12 tail hook publishes one framed halfword in reply header2
for each selected page. Header 2 persists in stock; it is not cleared. Source
analysis found an apparently orphan raw-buffer accessor, so this is a bounded
exact-release contract, not a claim that the field is globally unread.
Known copied-header consumers exclude it; all four command-path marker tests
preserve other reply bytes and PCM. Integrated project/FX/audio and physical
timebase/overhead checks remain separate acceptance gates. The core claims
`sharc:reply-header:2` (also inferred by the linker); competing declared owners
refuse. No stock getter is suppressed. See [the measurement contract](../../docs/SHARC-DN2-METRICS.md).

Normal builds use the saved authored-code artifact. Only core development
needs to reproduce it with the pinned external Selache tools:

```
python mods/core-dn2-metrics/rebuild.py /path/to/pinned/selache --out /tmp/bridge.sharc.json
```

The helper compiles only this core's measurement source, checks its fixed
placement/budget/entries and profile hashes, and reuses the standard pinned
bridge artifact. It never reads a stock firmware or expands a reservation.
