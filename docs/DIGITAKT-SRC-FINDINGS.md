# Digitakt SRC parameter evidence

Scope: eight additional SRC parameters, sixteen logical values total, on
Digitakt mk1 OS 1.53/1.54. See [the plan](DIGITAKT-SRC-PLAN.md).
Oscillator optimization and polyphony benchmarks are outside this change.

## Why the native hooks are needed

Runtime sounds contain 53 words at +20, with the machine byte at +126.
The existing SRC bank uses slots 17–24. Unregistered audio slots 46–52
provide seven values; native slot 0 provides the eighth. Processing retains
106-byte track strides. Native note locks use separate storage.

The native descriptor table contains 164 records. Eight appended descriptors
occupy 416 bytes; seven redirected readers require preserving 600 bytes of
complete adjacent tables. The constructor and borrowed UI array keep their
original 164-entry bounds. Native slot lookup, editing, defaults, locks,
Randomize and page actions need the added IDs to participate normally.

None is LFO destination 0 and can overwrite slot 0. A custom-machine-only
virtual destination 53 distinguishes the eighth new value from None. Both
native chooser and processing paths need that mapping. Native edits can
clear sound pointers, so modulation uses the owning `core_track_machine`,
not those pointers or the machine's chosen render alias.

Stock sound conversion saves only slots 0–45. Its four spare parameter bytes
cannot store eight additions. Borrowing fractional bytes is not lossless:
cross-LFO modulation can produce valid fractional destination values on both
releases. Version 4 instead packs 803 meaningful bits in the existing record,
retaining all original SRC bits and valid common fractions. The native
standalone upgrader also needs to recognize that version before loading it.

## Reproduction

Use existing emulator dependencies and a mise-managed Python; no emulator
changes or local execution workaround are part of this branch:

```sh
PYTHONPATH=/path/to/emulator/.venv/lib/python3.12/site-packages \
ELEKLOADER_CROSS=/path/to/m68k-elf- \
mise exec python@3.12.13 -- python tests/probe_digitakt_src.py \
  --emulator /path/to/emulator \
  --stock /path/to/Digitakt_OS1.53.syx \
  --stock /path/to/Digitakt_OS1.54.syx --storage
```

The probe checks stock hashes, builds the companion/test consumers and loads
the actual linked C/assembly directly into test RAM. Calls have bounded
instruction counts and verify their return sentinel, callee-saved registers,
stack and buffer guards. These checks do not boot the firmware.

## Validation status

The final scoped sources pass 27 shared native checks on each OS. They cover
eight independent values, defaults, editing, locks/restoration, separate note
locks, None/53 choices and both LFOs, including null sound pointers. Codec
checks preserve original words, fractions, metadata and native-unwritten
output bytes; mixed kits/pools and 79-lane pattern conversion pass. A shared
legacy-machine scenario checks the existing reset, popup and LFO naming paths.

Both final scoped images boot from fresh snapshots and cold-load the named
panel-saved project. All eight distinct values and held-step locks restore;
page 2 reports native IDs 164–171. All eight controls edit independently,
and held-step editing of the last addition leaves its base value unchanged.
The actual panel LFO chooser selects raw virtual destination 53 on both
releases. Strict runtime checks pass. Screens
used for PR preparation are `docs/img/digitakt-src-page1.png` and
`docs/img/digitakt-src-page2.png` (emulated OS 1.54).

Actual standalone menu save/list/ordinary-replacement/reload passed on both
prior sixteen-value builds; 1.54 restored eight distinct nonzero values.
That is prior-build evidence; the final sources have separate compiled
sound/upgrader and mixed kit/pool checks.

The scope audit covered all ten commits from `a8d7ea5` through `c58bf9c` and
the uncommitted diff. It removed the oscillator optimization and benchmark
material, abandoned two-addition compatibility/migration, unrelated first-page
fixture features and a test of an untouched native helper. Existing-machine
reset, popup fallback and LFO naming behavior were narrowed back to `main`.
Core, the public SINE example, loader engines/checks, file formats, stable
docs, catalogs, dependencies and packaging have no net changes.

Final build/lint/patch checks pass on both OS releases, including byte-exact
verification of untouched sections 2/4/5/8. Unit tests: 21 passed. SDK checks:
12 passed and 18 skipped for missing Digitone stock/released-core fixtures. No physical hardware or Transfer
validation occurred. Hardware acceptance remains
[#4](https://github.com/simonjohansson/elekloader/issues/4).
