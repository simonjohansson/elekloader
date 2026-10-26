# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise the clone registry and optional native MIDI dispatch."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CC = shutil.which('cc')
CF_CALL = os.environ.get('ELEKLOADER_CF_CALL')
STOCK = os.environ.get('ELEKLOADER_DN2_SYX')


@unittest.skipUnless(CC, 'native C compiler is unavailable')
class RegistryTests(unittest.TestCase):
    def test_stock_registered_and_missing_ids(self):
        for flags in ([], ['-DEMPTY']):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as out:
                executable = Path(out) / 'registry'
                result = subprocess.run([CC, '-std=c99', '-Wall', '-Werror', *flags,
                                         '-I', str(ROOT / 'elekloader/sdk/include'),
                                         str(ROOT / 'tests/test_dn2_machines.c'), '-o', str(executable)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                subprocess.run([str(executable)], check=True)


@unittest.skipUnless(CF_CALL and STOCK and os.environ.get('ELEKLOADER_CROSS'),
                     'needs DN2 stock, cross compiler and ELEKLOADER_CF_CALL')
class ParameterDispatchTests(unittest.TestCase):
    def test_parameter_lookup_maps_clones_and_custom_filters_but_identity_reads_keep_ids(self):
        from elekloader import patch, syx
        from elekloader.devices.digitone_mk2 import DEVICE
        from elekloader.sdk import build as sdk
        from elekloader.sdk.sharc import filter_artifact, voice_artifact

        stock = syx.Syx.load(STOCK)
        image = stock.section(3)
        for address, expected in ((0x40036478, '712800de4e75'), (0x4003649c, '712800df4e75')):
            offset = address - DEVICE.main_load
            self.assertEqual(image[offset:offset + 6], bytes.fromhex(expected))
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            base = [sdk.build(str(ROOT / 'mods' / source), STOCK, str(work / source))[0]
                    for source in ('core-dn2', 'machines-dn2')]
            for kind, first, getter_pc, type_offset, producer in (
                    ('synth', 5, 0x40036462, 0xde, voice_artifact),
                    ('filter', 6, 0x40036486, 0xdf, filter_artifact)):
                with self.subTest(kind=kind):
                    stage = work / kind
                    stage.mkdir()
                    (stage / 'machine.c').write_text('#include "mk2/machines.h"\n'
                        'const struct mk2_%s clone={%d,0,"CLONE","CLONE"};\n'
                        'const struct mk2_%s custom={8,1,"CUSTOM","CUSTOM"};\n' % (kind, first, kind))
                    (stage / 'kernel.json').write_text(json.dumps(producer(bytes(4), bytes(4), 0, 8, 20)))
                    (stage / 'mod.json').write_text(json.dumps({
                        'id': kind + '-dispatch-test', 'version': '0.1', 'device': 'digitone-mk2', 'os': '1.12',
                        'sources': ['machine.c'], 'sharc': {'artifact': 'kernel.json'},
                        'resources': {'core': '0.1'}, 'requires': ['core', 'machines-dn2'],
                        'contribute': [{'to': table, 'data': '00000000',
                                        'relocs': [[0, 'abs32', 'sym:' + symbol, 0]]}
                                       for table, symbol in [('mk2_' + kind + 's', 'clone'),
                                                             ('mk2_voice_' + kind + 's', 'custom')]]}))
                    mod = sdk.build(str(stage), STOCK, str(stage / 'build'))[0]
                    outputs, manifest = patch.build(STOCK, base + [mod], 'TEST', log=lambda *args: None)
                    firmware = stage / 'test.syx'
                    firmware.write_bytes(outputs['syx'])
                    vtable, getter = 0x47f3a000, 0x47f3a100
                    pokes = [{'addr': hex(vtable + 0x28), 'hex': getter.to_bytes(4, 'big').hex()},
                             {'addr': hex(getter), 'hex': '202f00044e75'}]
                    calls, expected, modes = [], [], []
                    identity = manifest['_map']['dn2_real_reader' if kind == 'synth' else 'dn2_filter_real_reader']
                    # Page and default callers reach the stock reader directly; it maps like the getter.
                    pcs = {'identity': identity, 'parameter': getter_pc,
                           'reader': 0x4004b7f2 if kind == 'synth' else 0x4004b860}
                    for i, machine_id in enumerate((0, 1, 2, 3, 4, 5, 6, 8, 9, 31, 32)):
                        address = 0x47f3b000 + i * 0x100
                        sound = bytearray(0xe0)
                        sound[:4] = vtable.to_bytes(4, 'big')
                        sound[type_offset] = machine_id
                        pokes.append({'addr': hex(address), 'hex': sound.hex()})
                        owner = 0x47f3d000 + i * 0x20
                        pokes.append({'addr': hex(owner + 0x10), 'hex': address.to_bytes(4, 'big').hex()})
                        for mode, pc in pcs.items():
                            calls.append({'pc': hex(pc), 'args': [hex(owner if mode == 'parameter' else address)]})
                            modes.append(mode)
                            # A custom synth keeps its ID; a custom filter reads as its stock clone.
                            mapped = {first: 0, 8: 1}.get(machine_id, 4 if kind == 'synth' else 0)
                            expected.append(mapped if mode != 'identity' and first <= machine_id < 32
                                            and not (kind == 'synth' and machine_id == 8) else machine_id)
                    # Native MIDI handlers must reach the setter through the real owner getters.
                    owner_vtable, setter, allowed = 0x47f3a200, 0x47f3a320, 0x47f3a300
                    table = bytearray(0x7c)
                    for offset, address in ((0x34, setter), (0x38, allowed),
                                            (0x74, 0x40036462), (0x78, 0x40036486)):
                        table[offset:offset + 4] = address.to_bytes(4, 'big')
                    pokes += [{'addr': hex(owner_vtable), 'hex': table.hex()},
                              {'addr': hex(allowed), 'hex': '70014e75'},
                              {'addr': hex(setter), 'hex': '202f000823c047f3f0004e75'}]
                    for i, machine_id in enumerate((0, first)):
                        sound_address, owner = 0x47f3e000 + i * 0x100, 0x47f3e200 + i * 0x20
                        sound = bytearray(0xe0)
                        sound[:4] = vtable.to_bytes(4, 'big')
                        sound[type_offset] = machine_id
                        owner_data = bytearray(0x20)
                        owner_data[:4] = owner_vtable.to_bytes(4, 'big')
                        owner_data[0x10:0x14] = sound_address.to_bytes(4, 'big')
                        pokes += [{'addr': hex(sound_address), 'hex': sound.hex()},
                                  {'addr': hex(owner), 'hex': owner_data.hex()}]
                        cc, nrpn = (40, 201) if kind == 'synth' else (16, 148)
                        for pc, key, value in ((0x40038bc6, cc, 7), (0x400374f6, nrpn, 896)):
                            calls.append({'pc': hex(pc), 'args': [hex(owner), str(key), str(value), '0', '0'],
                                          'reads': [{'addr': '0x47f3f000', 'len': 4}]})
                    request = stage / 'request.json'
                    request.write_text(json.dumps({'pokes': pokes, 'calls': calls}))
                    result = subprocess.run([CF_CALL, str(firmware), str(request), '--base-sha', stock.sha256],
                                            capture_output=True, text=True, timeout=300)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
                    self.assertEqual(len(rows), len(calls))
                    for row, value, mode in zip(rows, expected, modes):
                        self.assertTrue(row['ok'], row)
                        self.assertEqual(row['d'][0], value, (mode, row))
                        self.assertEqual(row['d'][1:], row['d_in'][1:])
                        self.assertEqual(row['a'][2:7], row['a_in'][2:7])
                        self.assertEqual(row['a'][1], vtable if mode == 'parameter' else row['a_in'][1])
                        self.assertEqual(row['a'][7], row['sp0'] + 4)
                    dispatched = rows[len(expected):]
                    self.assertNotEqual(dispatched[0]['reads'], ['00000000'])
                    for row in dispatched:
                        self.assertTrue(row['ok'], row)
                        self.assertEqual(row['d'][0], 1, row)
                        self.assertEqual(row['reads'], dispatched[0]['reads'])

    def test_curve_plotter_draws_only_inside_the_graph(self):
        from elekloader import patch, syx
        from elekloader.sdk import build as sdk
        from elekloader.sdk.sharc import filter_artifact

        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            base = [sdk.build(str(ROOT / 'mods' / source), STOCK, str(work / source))[0]
                    for source in ('core-dn2', 'machines-dn2')]
            stage = work / 'curve'
            stage.mkdir()
            # In range, above 16 (drawn at the top) and 0xff (no dot), across all 51 columns.
            (stage / 'machine.c').write_text('#include "mk2/machines.h"\n'
                'static void curve(uint32_t freq, uint32_t reso, uint8_t y[51]) {\n'
                '    for (unsigned x = 0; x < 51; ++x) y[x] = x % 4 == 3 ? 0xff : x < 17 ? x : 200;\n'
                '    y[0] = freq >> 8; y[1] = reso >> 8; }\n'
                'const struct mk2_filter custom = {8,1,"CURVE","CURVE",curve};\n')
            (stage / 'kernel.json').write_text(json.dumps(filter_artifact(bytes(4), bytes(4), 0, 8, 20)))
            (stage / 'mod.json').write_text(json.dumps({
                'id': 'curve-test', 'version': '0.1', 'device': 'digitone-mk2', 'os': '1.12',
                'sources': ['machine.c'], 'sharc': {'artifact': 'kernel.json'}, 'resources': {'core': '0.1'},
                'requires': ['core', 'machines-dn2'],
                'contribute': [{'to': 'mk2_voice_filters', 'data': '00000000',
                                'relocs': [[0, 'abs32', 'sym:custom', 0]]}]}))
            mod = sdk.build(str(stage), STOCK, str(stage / 'build'))[0]
            outputs, manifest = patch.build(STOCK, base + [mod], 'TEST', log=lambda *args: None)
            firmware = stage / 'test.syx'
            firmware.write_bytes(outputs['syx'])
            # A 128 x 64 canvas, stored by column, 2 words a column (the stock pixel writer's layout).
            canvas, data = 0x47f3a000, 0x47f3a100
            header = bytearray(0x18)
            header[4:8], header[8:12] = (128).to_bytes(4, 'big'), (64).to_bytes(4, 'big')
            header[12:16], header[16:20] = (2).to_bytes(4, 'big'), data.to_bytes(4, 'big')
            pokes = [{'addr': hex(canvas), 'hex': header.hex()}, {'addr': hex(data), 'hex': '00' * 1024}]
            draw = manifest['_map']['dn2_filter_draw_curve']
            calls = [{'pc': hex(draw), 'args': [str(t), hex(canvas), '0x0c00', '0x0500'],
                      'reads': [{'addr': hex(data), 'len': 1024}]} for t in (8, 1, 6, 9)]
            request = stage / 'request.json'
            request.write_text(json.dumps({'pokes': pokes, 'calls': calls}))
            result = subprocess.run([CF_CALL, str(firmware), str(request), '--base-sha', syx.Syx.load(STOCK).sha256],
                                    capture_output=True, text=True, timeout=300)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            self.assertEqual(len(rows), 4)
            expected = set()
            for x in range(51):
                v = 12 if x == 0 else 5 if x == 1 else None if x % 4 == 3 else min(x, 16)
                if v is not None:
                    expected.add((21 + x, 7 + v))  # canvas y counts from the bottom
            # The canvas persists across the calls: only the custom ID draws, the others add nothing.
            for row in rows:
                self.assertTrue(row['ok'], row)
                self.assertEqual(row['d'][2:], row['d_in'][2:])
                self.assertEqual(row['a'][2:7], row['a_in'][2:7])
                self.assertEqual(row['a'][7], row['sp0'] + 4)
                bits = bytes.fromhex(row['reads'][0])
                drawn = {(x, y) for x in range(128) for y in range(64)
                         if int.from_bytes(bits[8 * x + 4 * (y >> 5):8 * x + 4 * (y >> 5) + 4], 'big')
                         & (0x80000000 >> (y & 31))}
                self.assertEqual(drawn, expected)
                self.assertTrue(all(21 <= x <= 71 and 7 <= y <= 23 for x, y in drawn))


if __name__ == '__main__':
    unittest.main()
