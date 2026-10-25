# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise the C clone registry without firmware or a cross compiler."""
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
class FilterDispatchTests(unittest.TestCase):
    def test_parameter_lookup_maps_clones_but_identity_reads_keep_ids(self):
        from elekloader import patch, syx
        from elekloader.devices.digitone_mk2 import DEVICE
        from elekloader.sdk import build as sdk
        from elekloader.sdk.sharc import filter_artifact

        stock = syx.Syx.load(STOCK)
        image = stock.section(3)
        offset = 0x4003649c - DEVICE.main_load
        self.assertEqual(image[offset:offset + 6], bytes.fromhex('712800df4e75'))
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / 'machine.c').write_text('#include "mk2/machines.h"\n'
                'const struct mk2_filter clone={6,0,"CLONE","CLONE"};\n'
                'const struct mk2_filter custom={8,0,"CUSTOM","CUSTOM"};\n')
            (work / 'kernel.json').write_text(json.dumps(filter_artifact(bytes(4), bytes(4), 0, 8, 20)))
            (work / 'mod.json').write_text(json.dumps({
                'id': 'filter-dispatch-test', 'version': '0.1', 'device': 'digitone-mk2', 'os': '1.12',
                'sources': ['machine.c'], 'sharc': {'artifact': 'kernel.json'},
                'resources': {'core': '0.1'}, 'requires': ['core', 'machines-dn2'],
                'contribute': [{'to': table, 'data': '00000000',
                                'relocs': [[0, 'abs32', 'sym:' + symbol, 0]]}
                               for table, symbol in [('mk2_filters', 'clone'), ('mk2_voice_filters', 'custom')]]}))
            modules = [sdk.build(str(folder), STOCK, str(work / str(i)))[0]
                       for i, folder in enumerate([ROOT / 'mods/core-dn2', ROOT / 'mods/machines-dn2', work])]
            outputs, manifest = patch.build(STOCK, modules, 'TEST', log=lambda *args: None)
            firmware = work / 'test.syx'
            firmware.write_bytes(outputs['syx'])
            vtable, getter = 0x47f3a000, 0x47f3a100
            pokes = [{'addr': hex(vtable + 0x28), 'hex': getter.to_bytes(4, 'big').hex()},
                     {'addr': hex(getter), 'hex': '202f00044e75'}]
            calls, expected = [], []
            for i, machine_id in enumerate((0, 1, 2, 3, 4, 5, 6, 8, 9, 31, 32)):
                address = 0x47f3b000 + i * 0x100
                sound = bytearray(0xe0)
                sound[:4] = vtable.to_bytes(4, 'big')
                sound[0xdf] = machine_id
                pokes.append({'addr': hex(address), 'hex': sound.hex()})
                owner = 0x47f3d000 + i * 0x20
                pokes.append({'addr': hex(owner + 0x10), 'hex': address.to_bytes(4, 'big').hex()})
                for parameter in (False, True):
                    calls.append({'pc': hex(0x40036486 if parameter else manifest['_map']['dn2_filter_real_reader']),
                                  'args': [hex(owner if parameter else address)]})
                    expected.append(0 if parameter and machine_id in (6, 9, 31) else machine_id)
            request = work / 'request.json'
            request.write_text(json.dumps({'pokes': pokes, 'calls': calls}))
            result = subprocess.run([CF_CALL, str(firmware), str(request), '--base-sha', stock.sha256],
                                    capture_output=True, text=True, timeout=300, check=True)
            rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            self.assertEqual(len(rows), len(expected))
            for i, (row, value) in enumerate(zip(rows, expected)):
                self.assertTrue(row['ok'], row)
                self.assertEqual(row['d'][0], value)
                self.assertEqual(row['d'][1:], row['d_in'][1:])
                self.assertEqual(row['a'][2:7], row['a_in'][2:7])
                self.assertEqual(row['a'][1], vtable if i % 2 else row['a_in'][1])
                self.assertEqual(row['a'][7], row['sp0'] + 4)


if __name__ == '__main__':
    unittest.main()
