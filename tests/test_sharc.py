# SPDX-License-Identifier: GPL-2.0-or-later
"""Firmware-free SHARC corpus; ELEKLOADER_DN2_SYX enables exact owner-stock checks."""
import json
import os
import copy
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

    def test_instruction_patch_requires_exact_unique_stock_load(self):
        case = next(c for c in CORPUS['parse_cases'] if c['name'] == 'original_protected_load')
        data = bytes.fromhex(case['hex'])
        profile = dict(SYNTHETIC, decoded_sha256=sha(data),
                       patch_ranges=((0x20001000, 0x20001004),))
        patched = sharc.insert(data, profile, patches=[(0x20001000, b'\x05\x06', b'\xaa\xbb')])
        self.assertEqual(patched[84:88], b'\xaa\xbb\x07\x08')
        self.assertEqual(patched[:84] + patched[88:], data[:84] + data[88:])
        self.refusal(lambda: sharc.insert(data, profile,
                     patches=[(0x20001000, b'\x00\x06', b'\xaa\xbb')]),
                     'SHARC patch stock instruction does not match')
        self.refusal(lambda: sharc.insert(data, dict(profile, patch_ranges=()),
                     patches=[(0x20001000, b'\x05\x06', b'\xaa\xbb')]),
                     'SHARC patch is outside the profile patch range')
        self.refusal(lambda: sharc.insert(ORIGINAL, dict(profile, decoded_sha256=sha(ORIGINAL)),
                     patches=[(0x20001000, b'\x05\x06', b'\xaa\xbb')]),
                     'SHARC patch needs one unambiguous stock load')

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
        patched = sharc.insert(decoded, PROFILE, patches=[
            (0x2838489a, bytes.fromhex('8715ffff78ff'), bytes.fromhex('3e06160006eb'))])
        changed = [i for i, (a, b) in enumerate(zip(decoded, patched)) if a != b]
        self.assertEqual(len(changed), 6)
        self.assertEqual(patched[changed[0]:changed[0] + 6], bytes.fromhex('3e06160006eb'))
        outputs = formats.write(parsed, parsed.stored[device.main_section], device)
        self.assertEqual(outputs['syx'], raw)
        formats.verify(outputs, parsed, formats.main_image(parsed, device), device)

    def test_prelinked_inert_payload_boundaries(self):
        artifact = json.loads((Path(__file__).parents[1] / 'examples/sharc-sine/sine.sharc.json').read_text())
        payload = sharc.module_payload(artifact, PROFILE)
        self.assertEqual(payload['owner'], PROFILE['app_range'])
        self.assertIsNone(payload['entries'])
        for change, message in (
                (lambda d: d['segments'][0].update(offset_bytes=4),
                 'SHARC payload has a gap or overlap in its owner'),
                (lambda d: d['zero'][1].update(size_bytes=364),
                 'SHARC zero range is unaligned or exceeds its owner'),
                (lambda d: d.update(stack_bytes=1),
                 'inert SHARC payload must declare zero stack'),
                (lambda d: d.update(entries={'init_offset_bytes': 0,
                                               'render_offset_bytes': 424}),
                 'SHARC entry is not in owned code')):
            bad = copy.deepcopy(artifact)
            change(bad)
            self.refusal(lambda: sharc.module_payload(bad, PROFILE), message)

    @unittest.skipUnless(STOCK, 'missing ELEKLOADER_DN2_SYX')
    def test_inert_section_round_trip_keeps_other_sections(self):
        stock, dev, _rel = formats.load(STOCK)
        artifact = json.loads((Path(__file__).parents[1] / 'examples/sharc-sine/sine.sharc.json').read_text())
        payload = sharc.module_payload(artifact, PROFILE)
        base = payload['owner'][0]
        stream = sharc.insert(stock.section(7), PROFILE,
                              loads=[(base + off, data) for off, _kind, data in payload['segments']],
                              fills=[(base + off, count, 0) for off, count in payload['zero']])
        out = formats.write(stock, stock.stored[dev.main_section], dev,
                            stored_sharc=formats.pack_main(stream, dev))
        facts = formats.verify(out, stock, formats.main_image(stock, dev), dev,
                               want_sharc=stream)
        self.assertIn('sections 2, 4, 5, 8, byte for byte', facts['untouched'])
        with self.assertRaisesRegex(formats.FormatError, 'section 7 is not stock'):
            formats.verify(out, stock, formats.main_image(stock, dev), dev)
        with self.assertRaisesRegex(formats.FormatError, 'SHARC section does not depack to the patched stream'):
            formats.verify(out, stock, formats.main_image(stock, dev), dev,
                           want_sharc=stock.section(7))


if __name__ == '__main__':
    unittest.main()
