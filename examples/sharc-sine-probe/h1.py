# SPDX-License-Identifier: GPL-2.0-or-later
"""Build and check the experimental DN2 H1 bridge; no firmware or execution."""
import argparse
import json
from pathlib import Path
import re
import struct
import sys

from qualify import (HERE, TOOLS, command, compile_probe, digest, require,
                     section_rows, validate_data)
from h1_spills import verify_full_width_spills


def build(selache):
    selache = selache.resolve()
    out, compiler = compile_probe(selache)
    tools = {name: selache / 'target/release' / name for name in TOOLS}
    commands = []

    def run(args, output=None):
        commands.append([str(a) for a in args])
        text = command(args, text_output=output is not None)
        if output:
            (out / output).write_text(text)
        return text

    run([tools['selcc'], *compiler['target_flags'], '-c', '-o', out / 'entry.doj',
         HERE / 'h1-entry.c'])
    for name in ('bridge', 'hook'):
        run([tools['selas'], '-proc', 'ADSP-21569', '-o', out / f'{name}.doj',
             HERE / f'h1-{name}.s'])
    exe = out / 'h1.dxe'
    run([tools['seld'], '-proc', 'ADSP-21569', '-T', HERE / 'h1.ldf',
         '-entry', 'bridge', '-Map', out / 'h1.map', '-o', exe,
         out / 'sine.doj', out / 'entry.doj', out / 'bridge.doj'])
    dump = run([tools['seldump'], '-fh', '-sh', '-n', '.symtab', exe], 'h1.txt')
    for name in ('bridge_code', 'probe_code'):
        run([tools['seldump'], '-ns', name, exe], f'h1-{name}.txt')
    raw = exe.read_bytes()
    rows = section_rows(dump, raw)
    require({n for n, r in rows.items() if r['flags'] & 2} ==
            {'bridge_code', 'probe_code', 'probe_data'}, 'unexpected loadable section')
    require(not any(r['kind'] in ('rel', 'rela') for r in rows.values()),
            'remaining relocation')
    require(not re.search(r"(?m)^[0-9a-f]{4}\s+UNDEF.*'[^']+'$", dump),
            'named unresolved symbol')
    entries = {}
    for name in ('bridge', 'bridge_restored', 'sharc_init.', 'sharc_render.'):
        matches = re.findall(
            r"(?m)^[0-9a-f]{4}\s+[0-9a-f]{8}\s+([0-9a-f]{8})\s+[0-9a-f]{8}\s+"
            r"function\s+global\s+[0-9a-f]{8}\s+'" + re.escape(name) + "'", dump)
        require(len(matches) == 1, f'missing/ambiguous {name}')
        entries[name] = int(matches[0], 16)
    require(entries == {'bridge': 0x16eb06, 'bridge_restored': 0x16ec0f,
                        'sharc_init.': 0x16eda0, 'sharc_render.': 0x16edb9},
            'entrypoints differ from inspected artifact')
    require(struct.unpack_from('<I', raw, 24)[0] == entries['bridge'], 'wrong ELF entry')
    validate_data(rows['probe_data']['bytes'])
    expected = {
        'bridge_code': (0x16eb06, 548, 7, '1089aaf64fc9e66e2fe9b3a2b037230dfe3af66607a8c1d1b904bb0b487d10cd'),
        'probe_code': (0x16ed00, 424, 7, '6af2fcc203f99499aeb1824e4388d599e5855c094c9aa5e11b56211ca0b4e04a'),
        'probe_data': (0x2ddc00, 152, 3, '17f735313bf151356989a7b29ec0cab9ea189a59062f5e22ab521d6f40946c9f'),
    }
    loads, sections = [], {}
    for name, wanted in expected.items():
        row = rows[name]
        require((row['address'], row['size'], row['flags'], digest(row['bytes'])) == wanted,
                f'{name} differs from inspected artifact; requalify the finite bridge')
        code = name != 'probe_data'
        address = 0x28000000 + row['address'] * (2 if code else 1)
        data = (b''.join(row['bytes'][i:i + 2][::-1] for i in range(0, row['size'], 2))
                if code else row['bytes'])
        require(address % 4 == len(data) % 4 == 0, f'unaligned {name}')
        loads.append((address, data))
        sections[name] = dict(loader_start=address, bytes=len(data),
                              elf_sha256=digest(row['bytes']), loader_sha256=digest(data))
    spill_report = verify_full_width_spills(
        rows['bridge_code']['bytes'], rows['bridge_code']['address'],
        (out / 'h1-bridge_code.txt').read_text())
    hook_raw = (out / 'hook.doj').read_bytes()
    hook_dump = run([tools['seldump'], '-sh', out / 'hook.doj'], 'h1-hook.txt')
    hook = section_rows(hook_dump, hook_raw)['seg_swco']['bytes']
    # PRM Type 8a: unconditional, non-delayed absolute jump to the bridge PC16.
    require(hook == bytes.fromhex('063e0016eb06'), 'hook does not jump to the bridge')

    # Exercise existing records with original bytes only. This grants no stock range.
    sys.path.insert(0, str(HERE.parent.parent))
    from elekloader import sharc
    from elekloader.devices.digitone_mk2 import DEVICE
    original = (sharc._header(sharc.FIRST, entries['bridge'], 0, 16) +
                sharc._header(sharc.FINAL, entries['bridge'], 0, 0))
    profile = dict(DEVICE.releases['1.12'].sharc, decoded_sha256=digest(original),
                   owned_ranges=((0x282dd600, 0x282dde00),))
    binding = struct.pack('<III', entries['sharc_init.'], entries['sharc_render.'], 0)
    loads.insert(0, (0x282dd600, binding))
    fills = [(0x282dd830, 464, 0x00010001), (0x282ddba8, 88, 0x00010001),
             (0x282ddc98, 360, 0)]
    stream = sharc.insert(original, profile, loads=loads, fills=fills)
    spans = sorted((r.target, r.target + r.count) for r in sharc.parse(stream, profile)
                   if r.flags in (sharc.LOAD, sharc.FILL))
    require(spans[0][0] == 0x282dd600 and spans[-1][1] == 0x282dde00 and
            all(a[1] == b[0] for a, b in zip(spans, spans[1:])), 'coverage gap or overlap')
    (out / 'h1-synthetic.ldr').write_bytes(stream)
    report = dict(status='compile-layout-spill-pass; target-runtime-unqualified',
                  compiler_report_sha256=digest((out / 'report.json').read_bytes()),
                  sources={name: digest((HERE / name).read_bytes()) for name in
                           ('h1.py', 'h1_spills.py', 'h1-bridge.s', 'h1-entry.c',
                            'h1-hook.s', 'h1.ldf')},
                  executable_sha256=digest(raw), sections=sections, entries_pc16=entries,
                  spills=spill_report, hook_elf_hex=hook.hex(),
                  loader_fixture=dict(bytes=len(stream), sha256=digest(stream), spans=spans,
                                      scope='synthetic only; not a bootable application'),
                  commands=commands,
                  limitations=['This command does not run the separate Digikit PX-fixed bridge checks',
                               'No stock input, reservation or firmware output',
                               'No cache, interrupt timing or physical qualification'])
    (out / 'h1-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: H1 compile/layout and 1024 full-width spill cases; runtime unqualified.\n'
          + str(out / 'h1-report.json'))
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selache', type=Path, help='clean checkout of the pinned Selache commit')
    args = parser.parse_args()
    try:
        build(args.selache)
    except (ValueError, OSError) as error:
        sys.exit(f'FAIL: {error}')
