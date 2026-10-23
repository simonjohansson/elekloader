# SPDX-License-Identifier: GPL-2.0-or-later
"""Firmware-free SHARC corpus; ELEKLOADER_DN2_SYX enables exact owner-stock checks."""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elekloader import formats, sharc  # noqa: E402
from elekloader.devices.digitone_mk2 import DEVICE  # noqa: E402
from elekloader.elemod import ModError, sha  # noqa: E402

CORPUS = json.loads((Path(__file__).parent / 'fixtures/sharc.json').read_text())
ORIGINAL = bytes.fromhex(CORPUS['original'])
PROFILE = DEVICE.releases['1.12'].sharc
SYNTHETIC = dict(PROFILE, decoded_sha256=sha(ORIGINAL), owned_ranges=((0x20002000, 0x20002020),))
STOCK = os.environ.get('ELEKLOADER_DN2_SYX')


class SharcTests(unittest.TestCase):
    def refusal(self, action, message):
        with self.assertRaises(ModError) as caught:
            action()
        self.assertEqual(str(caught.exception), message)

    def test_shared_parse_corpus(self):
        for case in CORPUS['parse_cases']:
            with self.subTest(case=case['name']):
                data = bytes.fromhex(case['hex'])
                if 'error' in case:
                    self.refusal(lambda: sharc.parse(data, PROFILE), case['error'])
                else:
                    records = sharc.parse(data, PROFILE)
                    self.assertEqual(len(records), case['records'])
                    self.assertEqual(b''.join(r.raw for r in records), data)
                    self.assertEqual(sharc.insert(data, dict(PROFILE, decoded_sha256=sha(data))), data)

    def test_shared_address_corpus(self):
        for case in CORPUS['span_cases']:
            with self.subTest(case=case['name']):
                action = lambda: sharc.byte_span(PROFILE, case['address'], case['size'], case['unit'])
                if 'error' in case:
                    self.refusal(action, case['error'])
                else:
                    self.assertEqual(action(), tuple(case['result']))

    def test_shared_insert_corpus(self):
        for case in CORPUS['insert_cases']:
            with self.subTest(case=case['name']):
                profile = dict(SYNTHETIC, owned_ranges=case.get('owned', SYNTHETIC['owned_ranges']),
                               decoded_max=case.get('limit', PROFILE['decoded_max']))
                action = lambda: sharc.insert(ORIGINAL, profile,
                    loads=[(address, bytes.fromhex(data)) for address, data in case['loads']], fills=case['fills'])
                if 'error' in case:
                    self.refusal(action, case['error'])
                else:
                    self.assertEqual(action().hex(), case['result'])
                self.assertEqual(ORIGINAL.hex(), CORPUS['original'])

    def test_golden_preserves_original_order_and_changes_only_last_first(self):
        result = sharc.insert(ORIGINAL, SYNTHETIC, loads=[(0x20002000, bytes.fromhex('11223344'))],
                              fills=[(0x20002010, 8, 0)])
        self.assertEqual(sha(result), CORPUS['expected_sha256'])
        records = sharc.parse(result, SYNTHETIC)
        self.assertEqual([r.offset for r in records], [0, 16, 36, 52, 68, 88, 108, 124])
        self.assertEqual([r.flags for r in records], [0x5001, 1, 0x801, 0x5001, 1, 1, 0x101, 0x8001])
        self.assertEqual([r.argument for r in records if r.flags == sharc.FIRST], [36, 72])
        self.assertEqual([records[i].raw for i in (0, 1, 2, 4, 7)],
                         [r.raw for i, r in enumerate(sharc.parse(ORIGINAL, PROFILE)) if i != 3])
        self.assertEqual(records[1].target, records[4].target)  # legal ordered overwrite
        self.refusal(lambda: sharc.insert(result, SYNTHETIC), 'SHARC stock DSP hash does not match the profile')
        self.assertEqual((records[6].count, len(records[6].raw)), (8, 16))  # FILL carries no payload

    def test_decoded_limit_and_identity(self):
        self.assertEqual(len(sharc.parse(ORIGINAL, dict(PROFILE, decoded_max=104))), 6)
        self.refusal(lambda: sharc.parse(ORIGINAL, dict(PROFILE, decoded_max=103)),
                     'SHARC decoded stream exceeds the profile limit')
        self.refusal(lambda: sharc.insert(ORIGINAL, PROFILE), 'SHARC stock DSP hash does not match the profile')
        self.refusal(lambda: sharc.insert(ORIGINAL, SYNTHETIC, loads=[(0x20002000, [1, 2, 3, 4])]),
                     'SHARC load payload must be bytes')

    def test_parser_retains_copies_and_protected_originals(self):
        mutable = bytearray(ORIGINAL)
        records = sharc.parse(mutable, PROFILE)
        rebuilt = sharc.insert(mutable, SYNTHETIC, loads=[(0x20002000, b'1234')])
        self.assertIsInstance(rebuilt, bytes)
        mutable[16] = 0
        self.assertEqual(records[1].raw, ORIGINAL[16:36])
        # Exclusions govern new allocation; they do not rewrite valid historical loads.
        case = next(c for c in CORPUS['parse_cases'] if c['name'] == 'original_protected_load')
        data = bytes.fromhex(case['hex'])
        profile = dict(SYNTHETIC, decoded_sha256=sha(data))
        result = sharc.insert(data, profile, loads=[(0x20002000, b'\x11\x22\x33\x44')])
        self.assertEqual(sharc.parse(result, profile)[1].raw, data[16:36])

    @unittest.skipUnless(STOCK, 'missing ELEKLOADER_DN2_SYX')
    def test_owner_stock_exact_noop(self):
        raw = Path(STOCK).read_bytes()
        parsed, device, release = formats.load(raw)
        self.assertIs(device, DEVICE)
        self.assertIs(release, DEVICE.releases['1.12'])
        stored, decoded = parsed.stored[PROFILE['section']], parsed.section(PROFILE['section'])
        self.assertEqual((sha(stored), len(stored)), (PROFILE['stored_sha256'], PROFILE['stored_len']))
        self.assertEqual((sha(decoded), len(decoded)), (PROFILE['decoded_sha256'], PROFILE['decoded_len']))
        records = sharc.parse(decoded, PROFILE)
        self.assertEqual(len(records), 95)
        self.assertEqual(b''.join(r.raw for r in records), decoded)
        self.assertEqual(sharc.insert(decoded, PROFILE), decoded)
        spans = [sharc.byte_span(PROFILE, r.target, r.count, check_protected=False)
                 for r in records if r.flags in (sharc.LOAD, sharc.FILL)]
        self.assertEqual(sum(a < d and c < b for i, (a, b) in enumerate(spans) for c, d in spans[i+1:]), 15)
        self.refusal(lambda: sharc.insert(decoded, PROFILE, fills=[(0x20090000, 4, 0)]),
                     'SHARC new load or fill is outside the profile-owned ranges')
        outputs = formats.write(parsed, parsed.stored[device.main_section], device)
        self.assertEqual(outputs['syx'], raw)
        formats.verify(outputs, parsed, formats.main_image(parsed, device), device)


if __name__ == '__main__':
    unittest.main()
