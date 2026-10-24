# SPDX-License-Identifier: GPL-2.0-or-later
"""Bounded measurement envelopes/writer; synthetic app bytes are never executed."""
import copy
import json
import os
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elekloader import devices, formats, link, sharc
from elekloader.elemod import ModError, sha
from elekloader.devices.digitone_mk2 import DEVICE

REL = DEVICE.releases['1.12']
P = REL.sharc
TARGET = devices.target_of(DEVICE, REL)
STANDARD = json.loads((ROOT / 'mods/core-dn2/bridge.sharc.json').read_text())
MEASURED = json.loads((ROOT / 'mods/core-dn2-metrics/bridge.sharc.json').read_text())
L1 = json.loads((ROOT / 'examples/sharc-sine/sine.sharc.json').read_text())
MISMATCH = 'active SHARC measurement requires a matching measurement core and L2 application'
STACK = 'active SHARC stack exceeds the profile limit'


def app(abi=None, stack=128):
    return {'abi': abi or P['metrics_abi'],
            'segments': [{'offset_bytes': 0, 'kind': 'code', 'hex': '0100' * 34}],
            'zero': [{'offset_bytes': 68, 'size_bytes': 32768 - 68}],
            'entries': {'init_offset_bytes': 0, 'render_offset_bytes': 2}, 'stack_bytes': stack}


def modules(core, payload):
    return [link.Mod2({'elemod': 2, 'id': 'core', 'version': '0.1', 'target': TARGET,
                      'sections': {'.boot': {'align': 4, 'parts': [['hex', '00000000']]}}, 'sharc': core}, 'core'),
            link.Mod2({'elemod': 2, 'id': 'app', 'version': '0.1', 'target': TARGET,
                       'sections': {}, 'sharc': payload}, 'app')]


def problems(core, payload):
    return link.check(modules(core, payload), bytes(REL.main_len))


class MetricsEnvelope(unittest.TestCase):
    def test_owner_guard_and_active_only(self):
        self.assertEqual(sharc.module_payload(MEASURED, P, True)['owner'], (0x282dd600, 0x282ddd98))
        self.assertEqual(sharc.module_payload(app(), P)['owner'], P['l2_app_range'])
        self.assertFalse(sharc.module_payload(L1, P)['metrics'])
        bad = app(); bad['entries'] = None; bad['stack_bytes'] = 0
        with self.assertRaisesRegex(ModError, '^SHARC measurement ABI needs active callbacks$'):
            sharc.module_payload(bad, P)
        bad = app(); bad['entries']['render_offset_bytes'] = 4
        with self.assertRaisesRegex(ModError, 'entry is in the instruction read-ahead guard'):
            sharc.module_payload(bad, P)
        bad = app(); bad['zero'][0]['size_bytes'] += 4
        with self.assertRaisesRegex(ModError, 'exceeds its owner'):
            sharc.module_payload(bad, P)

    def test_pairing_and_unchanged_gross_stack_ceiling(self):
        self.assertEqual(problems(MEASURED, app(stack=420)), [])
        for count in (421, 424, 428):
            self.assertEqual(problems(MEASURED, app(stack=count)), [STACK])
        self.assertEqual(problems(STANDARD, app(P['l2_abi'], 428)), [])
        self.assertEqual(problems(STANDARD, app(P['l2_abi'], 429)), [STACK])
        for core, payload in ((STANDARD, app()), (MEASURED, app(P['l2_abi'])), (MEASURED, L1)):
            self.assertEqual(problems(core, payload), [MISMATCH])

    def test_pinned_core_and_changeable_app(self):
        for index in range(3):
            changed = copy.deepcopy(MEASURED)
            data = bytearray.fromhex(changed['segments'][index]['hex']); data[0] ^= 1
            changed['segments'][index]['hex'] = data.hex()
            self.assertEqual(problems(changed, app()), ['core 0.1 has unqualified active SHARC core bytes or entry'])
        for field in ('entry', 'stack'):
            changed = copy.deepcopy(MEASURED)
            if field == 'entry': changed['entries']['hook_offset_bytes'] += 2
            else: changed['stack_bytes'] -= 4
            self.assertEqual(problems(changed, app()), ['core 0.1 has unqualified active SHARC core bytes or entry'])
        changed = app(); changed['segments'][0]['hex'] = 'deadbeef' + changed['segments'][0]['hex'][8:]
        changed['entries']['render_offset_bytes'] = 0
        self.assertEqual(problems(MEASURED, changed), [])

    def test_inferred_channel_owner_cannot_be_omitted(self):
        mods = modules(MEASURED, app())
        competitor = link.Mod2({'elemod': 2, 'id': 'other', 'version': '0.1', 'target': TARGET,
                               'sections': {}, 'resources': {'names': [P['metrics_resource']]}}, 'other')
        self.assertTrue(any(P['metrics_resource'] in error for error in link.check(mods + [competitor], bytes(REL.main_len))))
        self.assertIn(P['metrics_resource'], mods[0].names)
        self.assertEqual(problems(STANDARD, app(P['l2_abi'])), [])


@unittest.skipUnless(os.environ.get('ELEKLOADER_DN2_SYX'), 'needs owner stock')
class MetricsWriter(unittest.TestCase):
    def test_exact_placement_hooks_binding_and_old_bytes(self):
        stock, dev, _ = formats.load(os.environ['ELEKLOADER_DN2_SYX'])
        image, stream = formats.main_image(stock, dev), stock.section(7)
        measured = link.link(modules(MEASURED, app()), image, sharc_stream=stream).sharc_stream
        plain = link.link(modules(STANDARD, app(P['l2_abi'])), image, sharc_stream=stream).sharc_stream
        self.assertEqual(sha(plain), 'cf22d1fd665a4cfaa30b4082d7171af041ba51e96a4c02c9fe42dcdbf63e958b')
        self.assertEqual(sha(link.link(modules(STANDARD, L1), image, sharc_stream=stream).sharc_stream),
                         'faca192f22590371417221d116cefaa4e7caa0b0317d1a270e980bb72d31257a')
        records = sharc.parse(measured, P)
        def loaded(at, size):
            out = bytearray()
            for address in range(at, at + size):
                r = next(r for r in reversed(records) if r.flags in (sharc.LOAD, sharc.FILL) and r.target <= address < r.target + r.count)
                out.append(r.raw[16 + address - r.target] if r.flags == sharc.LOAD else (r.argument >> ((address-r.target) % 4 * 8)) & 255)
            return bytes(out)
        self.assertEqual(loaded(0x282dd600, 12), struct.pack('<III', 0xbc8000, 0x16ed00, 0))
        self.assertEqual(loaded(0x282ddd00, 4), struct.pack('<I', 0xbc8001))
        self.assertEqual(loaded(0x282ddd04, 148), bytes(148))
        self.assertEqual(loaded(0x282dda00, 768), bytes.fromhex(MEASURED['segments'][1]['hex']))
        at, table = P['keyed_pitch_table']
        self.assertEqual(loaded(P['app_range'][0] + at, len(table)//2), bytes.fromhex(table))
        self.assertEqual(loaded(0x282dddcc, 52), bytes(52))
        at, old, new = P['metrics_hook']
        self.assertEqual(loaded(at, 6), bytes.fromhex(new))
        with self.assertRaisesRegex(ModError, 'stock instruction does not match'):
            sharc.insert(stream, P, patches=[(at, bytes(6), bytes.fromhex(new))])
        with self.assertRaisesRegex(ModError, 'outside the profile patch range'):
            sharc.insert(stream, P, patches=[(at-2, bytes(6), bytes.fromhex(new))])
        with self.assertRaisesRegex(ModError, 'outside the profile-owned ranges'):
            sharc.insert(stream, P, loads=[(at+6, bytes(4))])


if __name__ == '__main__':
    unittest.main()
