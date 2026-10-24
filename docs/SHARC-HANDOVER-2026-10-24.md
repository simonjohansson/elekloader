# SHARC/DN2 handover — 24 October 2026

## Current checkpoint

Research and implementation are paused at the owner's request. The DN2 is
disconnected. The current focus is the sine and issues #34, #40 and #41;
resume ModelDigi only after that work. DT2 is unavailable; prepare it offline.

- Worktree remains `/Users/simonjohansson/src/elekloader-sharc`, branch
  `sharc`, based on `origin/digitone-2-support`. Commit directly and linearly;
  no PRs. Use `gh -R simonjohansson/elekloader` because the default is upstream.
  DT2 offline evidence was committed and pushed as `867cbd1`; see
  `docs/SHARC-DT2.md` and `out/sharc-dt2-probe/LOCAL-REPRO.md`.
- `examples/sharc-sine-asm/README.md` records the assembly example, exact
  artifact, reproducible C comparison and successful physical `SA01` capture
  committed as `b9fa0fb`.
  The last completed update transfer/confirmation was `SA01`, including
  DigiHealth 1.3. Audio and DigiHealth responded; a final installed-version
  query was not obtained before disconnection. No device command is pending.
- Preserve `/private/tmp/sharc-sine-20261024/`: it contains the physical
  `L202`, stock-DSP `SC01`, active-empty `SE01` and assembly `SA01` captures,
  candidates, event logs, analyses and Python/TypeScript parity results.
  `L202-notes.analysis.json` records successful physical L2 sine output.
- Physical controls `SC01` and `SE01` both played and returned to silence,
  but their recordings differed. Byte-identical stock/empty output is proved
  only in the emulator; physical noninterference remains unresolved.
- `/private/tmp/sharc-sine-20261024/timing/README.md` describes the private
  empty/C/assembly cycle-counter experiment. Exact installed candidates
  `TE01`, `TC01` and `TA01` passed bounded context and native emulator checks.
  None was flashed; physical timing remains unmeasured. Keep these private
  experiments outside the public active-artifact allowlist.
- Additional DT2 bridge experiments are private under ignored
  `out/sharc-dt2-probe/`. They do not grant a DT2 profile or physical support.
  Preserve this evidence during cleanup; do not commit firmware or captures.

ModelDigi inputs below are retained for later work.

## Goal and issue order

The overarching [#29](https://github.com/simonjohansson/elekloader/issues/29) is to make the DN2 SHARC path simple for mod authors, prove a keyed sine first, then port the DSP section of ModelDigi, with DT2 following independently. Normal consumers should build a module with the same SDK/patch flow as DN/DT mk1 and should not need a compiler installed when a mod supplies a qualified SHARC artifact. Prefer free/open author tooling; document proprietary fallback.

- [#47](https://github.com/simonjohansson/elekloader/issues/47) keyed physical sine is complete (`SK02`, commit `a6276ee`). The physical device played eight tracked notes, with the user's DigiHealth fork. Do not reopen this gate for ModelDigi.
- [#42](https://github.com/simonjohansson/elekloader/issues/42) is open. A **real** ModelDigi oscillator built by pinned Selache ran in the Digikit SHARC runner and exactly matched original host Q31 output plus all 116 state bytes for the cost-driver scenario 0 and three nearby cases. It remains a synthetic executable, not a normal SDK artifact or active device candidate. The high-frequency three-shape/modulated exploratory case mismatched and belongs in [#43](https://github.com/simonjohansson/elekloader/issues/43).
- [#46](https://github.com/simonjohansson/elekloader/issues/46) physical ModelDigi iteration stays open until an active ModelDigi candidate is SDK-built, validated and recorded on the device. Keep timing, cache/coherency, stock routes and sustained workload separate from emulator evidence.
- [#35](https://github.com/simonjohansson/elekloader/issues/35), [#41](https://github.com/simonjohansson/elekloader/issues/41), and [#33](https://github.com/simonjohansson/elekloader/issues/33) contain prior SHARC boot, H1 hook and runner evidence. Read current issue state before changing their scope.

## Source, tools and reproducible offline ModelDigi proof

- ModelDigi source: `/Users/simonjohansson/src/ModelDigi`, pinned at `c412bdf2ab3b0b5b62484e8195c2f880d1964c67`. Original oscillator files are under `/Users/simonjohansson/src/ModelDigi/dsp/`. The target uses integer Q31 mono at 48 kHz with six samples of algorithmic latency. Keep the commercial oscillator reference named only `REFERENCE`.
- Elekloader probe and instructions: `/Users/simonjohansson/src/elekloader-sharc/examples/modeldigi-sharc-probe/README.md`, `probe.py`, `driver.c`, `div.c`, `synthetic.ldf` in the same directory. Run from the worktree: `mise exec python@3.12.13 -- python examples/modeldigi-sharc-probe/probe.py /Users/simonjohansson/src/ModelDigi /private/tmp/elekloader-sharc-selache /private/tmp/digikit-sharc-px`.
- Free compiler/toolchain: `/private/tmp/elekloader-sharc-selache`, pinned at `2b26d3b75c53063575bc5c820fa0d38879335187`, built tools in `/private/tmp/elekloader-sharc-selache/target/release/` (`selcc`, `selas`, `seld`, `seldump`, `selload`). Emulator: PX-fixed `/private/tmp/digikit-sharc-px`, pinned at `ded547e14e63977c1a6e808812d46243e13c43d0`; native emulator `/private/tmp/digikit-sharc-px/out/native/target-wt/digikit-sharc-px/generic/release/digi-emud`. Do not assume an upstream Digikit runner without the PX fix passes.
- Last successful probe output: `/var/folders/78/v3nf7bhn69ncpf3qdj8ppybc0000gn/T/modeldigi-sharc-13fu1d8l/report.json`; its executable SHA-256 was `37fba952ddf1886a9fc629e70632d923302deb6b87aafbe114c510cbacfb3e58`. Synthetic code 12,106 bytes, loaded data 9,952 bytes, observed maximum stack drop 1,204 bytes, all 2,960 emitted instructions decoded confidently. The current DN2 H1 bridge/app reservation is only 2,048 bytes, so a qualified L2 application area and revised stack allowance are needed for ModelDigi. The probe's local compiler adaptations are documented in [#42](https://github.com/simonjohansson/elekloader/issues/42#issuecomment-6382360083), including a real Selache `modulate` miscompile workaround and a local GPL-2.0-or-later 32-bit divide helper.
- Target code must still get a checked Q31-to-float adapter, mono routing, init/render binding, and safe owned placement. Do not treat an inert L2 load or synthetic linker map as proof of those. Existing SDK format/qualification is intentionally narrow: `/Users/simonjohansson/src/elekloader-sharc/elekloader/sharc.py`, `/Users/simonjohansson/src/elekloader-sharc/elekloader/link.py`, `/Users/simonjohansson/src/elekloader-sharc/elekloader/devices/digitone_mk2.py`, `/Users/simonjohansson/src/elekloader-sharc/js/src/`, and `/Users/simonjohansson/src/elekloader-sharc/docs/FORMAT.md`. Python/TypeScript parity, device checks, and docs must move together if artifact behavior changes. Read the supplied `AGENTS.md` instructions: public/schema/format changes need a concrete scope decision first. The latest user gave broad authority to make decisions, but do not silently widen safety gates.

## Private firmware and physical evidence (never commit these)

- Stock DN2 1.12: `/Users/simonjohansson/src/elekloader/out/dn2-baseline-20261023/stock/Digitone_II_OS1.12.syx`, SHA-256 `7e5b8a733d4ab1fdf7e5d22757f7d8eddaa3cbf71d0858874a791844c02ceb35`.
- Baseline keyed sine + DigiHealth firmware: `/private/tmp/sharc47-SK02.syx`, SHA-256 `d89cb023a89478d495dfe62b9f71e35c1715f47d595226055253e89f7d52b2cd`. DigiHealth fork checkout: `/private/tmp/digihealth-dn2-remote`; built module: `/private/tmp/sharc44-dh/digihealth-1.3.elemod`. Author source fork is `/Users/simonjohansson/src/digihealth`.
- Inert L2 ModelDigi candidate: `/private/tmp/sharc42-L2-inert.syx`, version `L201`, SHA-256 `986507cb887069f1a01b6f77c15c395e3ea496bfc6bfc3ad0713a8d21432463a`; private build `/private/tmp/sharc42-probe/build-l2-inert.py`; boot loads from `/private/tmp/sharc42-probe/l2.ldr` to `0x20090000` (12,108 bytes) and `0x20094000` (9,952 bytes). Physical 24.01-second capture `/private/tmp/sharc42-probe/l2-device-notes.caf`, SHA-256 `df528a825db188ed7b8084830a3efae3ef4e27caec02b5a6a6b4b0ff0be84ab9`; analysis `/private/tmp/sharc42-probe/analyze-l2-audio.py`, MIDI/capture source `/private/tmp/sharc42-probe/l2-device-notes.py`, event log `/private/tmp/sharc42-probe/l2-device-notes.json`. Emulator experiment `/private/tmp/sharc42-probe/l2-emu.py`, WAVs in `/private/tmp/sharc42-probe/l2-emu/`.
- **Earlier active L2 sine experiment:** `/private/tmp/sharc42-L2-sine.syx`, version `L202`, SHA-256 `811b25f736c8dfdd5eb47c6d30f4bb5ae39f37cfbac263ef65bf502db2697782`. It retains the **same main OS** as `SK02`/`L201`, including DigiHealth; only section 7 differs. It keeps the L1 keyed core and note table, loads relocated sine code at `0x20090000` (664 bytes) and data at `0x20094000` (204 bytes), and points the H1 core's init/render binding at L2 PC16 `0xbc80a0`/`0xbc80bf`. This was assembled as a *private explicit-profile experiment*, not accepted by the normal SDK. Private source: `/private/tmp/sharc42-probe/l2-sine.ldf`, `/private/tmp/sharc42-probe/build-l2-sine.py`, `/private/tmp/sharc42-probe/build-l2-sine-candidate.py`; executable/loader/map in `/private/tmp/sharc42-probe/l2-sine/`.
- `L202` validation: stock section 2/4/5/8 preservation, main identity, boot records, protected ranges, decoded/stored limits and container verification passed. Digikit cold-booted it, read back both L2 loads, ran note-on/off with no DSP halt or missing audio blocks; 48 kHz stereo float capture `/private/tmp/sharc42-probe/l2-sine-emu/L202.wav` measured ~439.99 Hz, peak 0.125, equal channels. Emulator script `/private/tmp/sharc42-probe/l2-sine-emu.py`. The audio file SHA-256 is `ebfb38f4f4dc8464d4624d139ab10e5e41b282c22b163cfb24a0fb403b142742`; PCM SHA-256 is `f89f484b4d21c59370d309f10db81b82da3aac490a52df11577bfcaee42556aa`. Physical USB upgrade and remote YES confirmation succeeded, `elektroid-cli info 1` reported `L202`, and DigiHealth 1.3 answered with 15-second uptime. The later physical capture is `/private/tmp/sharc-sine-20261024/L202-notes.caf`, SHA-256 `d951b4b3fdb7bc443b91a5ec7d1c56da04ea1e5c5d6e7f5f0117e6911d208cee`; its analysis confirms eight tracked notes, equal channels and release to silence. No physical L2 memory readback was taken.

Use `mise` for language runtimes. For DigiHealth remote commands, run from `/private/tmp/digihealth-dn2-remote` with `mise exec python@3.12.13 -- uv run --with mido --with python-rtmidi tools/digiusb.py ...`; calling plain `uv run` without these packages failed. Before any authorized physical test, refresh `elektroid-cli ld` and identify the DN2; its device number can change after reboot. Flashing uses `elektroid-cli upgrade <candidate.syx> <device-number>`, then the fork's `screen` and `keys YES` commands if the unit asks for confirmation. Always inspect the exact candidate/version and control setup before a flash. Keep firmware, extracted sections, `.bin`, `.elemod`, captures and private scripts out of Git.
