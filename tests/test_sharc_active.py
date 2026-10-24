# SPDX-License-Identifier: GPL-2.0-or-later
"""Active DN2 sine integration; requires owner stock and a ColdFire cross compiler."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elekloader import elemod, formats, link, sharc  # noqa: E402
from elekloader.sdk import build as sdk  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STOCK = os.environ.get('ELEKLOADER_DN2_SYX')


@unittest.skipUnless(STOCK and os.environ.get('ELEKLOADER_CROSS'),
                     'needs ELEKLOADER_DN2_SYX and ELEKLOADER_CROSS')
class ActiveSineTests(unittest.TestCase):
    def test_stock_bound_bridge_and_qualified_sine(self):
        with tempfile.TemporaryDirectory() as work:
            core_path, _ = sdk.build(str(ROOT / 'mods/core-dn2'), STOCK, work)
            app_path, _ = sdk.build(str(ROOT / 'examples/sharc-sine'), STOCK, work)
            core, app = elemod.load_any(core_path), elemod.load_any(app_path)
            asm_path, _ = sdk.build(str(ROOT / 'examples/sharc-sine-asm'), STOCK, work)
            asm = elemod.load_any(asm_path)
            stock, dev, rel = formats.load(STOCK)
            image = formats.main_image(stock, dev)
            self.assertIsNone(link.link([core], image).sharc_stream)
            self.assertEqual(link.check([core, app], image), [])
            self.assertEqual(link.check([core, asm], image), [])
            # Packaging acceptance does not qualify these synthetic bytes for execution.
            for selected in (app, asm):
                for mutation in ('code', 'data', 'entry', 'stack'):
                    changed = copy.deepcopy(selected.doc)
                    artifact = changed['sharc']
                    if mutation in ('code', 'data'):
                        segment = artifact['segments'][1 if mutation == 'data' else 0]
                        data = bytearray.fromhex(segment['hex'])
                        data[4] ^= 1
                        segment['hex'] = data.hex()
                    elif mutation == 'entry':
                        artifact['entries']['render_offset_bytes'] += 2
                    else:
                        artifact['stack_bytes'] -= 4
                    self.assertEqual(link.check([core, link.Mod2(changed, mutation)], image), [])

            old_core = copy.deepcopy(core.doc)
            old_core.pop('sharc')
            self.assertIn('active SHARC application requires a qualified matching core bridge',
                          link.check([link.Mod2(old_core, 'old-core'), app], image))
            mutated = copy.deepcopy(app.doc)
            code = mutated['sharc']['segments'][0]
            code['hex'] = ('00' if code['hex'][:2] != '00' else '01') + code['hex'][2:]
            self.assertEqual(link.check([core, link.Mod2(mutated, 'mutated')], image), [])
            for mutation in ('entry', 'stack'):
                changed = copy.deepcopy(core.doc)
                if mutation == 'entry':
                    changed['sharc']['entries']['hook_offset_bytes'] += 2
                else:
                    changed['sharc']['stack_bytes'] -= 4
                self.assertTrue(any('unqualified active SHARC core bytes or entry' in p for p in
                                    link.check([link.Mod2(changed, mutation), app], image)))
            for change, message in (
                    (lambda a: a['entries'].update(render_offset_bytes=768), 'entry is not in owned code'),
                    (lambda a: a['entries'].update(init_offset_bytes=1), 'entry is not in owned code'),
                    (lambda a: a['segments'][0].update(offset_bytes=4), 'gap or overlap'),
                    (lambda a: a['zero'][0].update(size_bytes=56), 'exceeds its owner')):
                changed = copy.deepcopy(app.doc)
                change(changed['sharc'])
                with self.assertRaisesRegex(elemod.ModError, message):
                    link.Mod2(changed, 'invalid-envelope')
            bad_core = copy.deepcopy(core.doc)
            code = bad_core['sharc']['segments'][0]
            code['hex'] = ('00' if code['hex'][:2] != '00' else '01') + code['hex'][2:]
            large_stack = copy.deepcopy(app.doc)
            large_stack['sharc']['stack_bytes'] = rel.sharc['stack_max']
            for message, mods in (
                ('only one SHARC application may own the DN2 reservation', [core, app, asm]),
                ('active SHARC application requires a qualified matching core bridge',
                 [link.Mod2(old_core, 'old-core'), app]),
                ('unqualified active SHARC core bytes or entry',
                 [link.Mod2(bad_core, 'bad-core'), app]),
                ('active SHARC stack exceeds the profile limit',
                 [core, link.Mod2(large_stack, 'large-stack')]),
            ):
                with self.subTest(refusal=message), self.assertRaisesRegex(elemod.ModError, message):
                    link.link(mods, image, sharc_stream=stock.section(7))
            with self.assertRaisesRegex(elemod.ModError, 'SHARC application needs the stock section-7 stream'):
                link.link([core, app], image)
            fixed = json.loads((ROOT / 'tests/fixtures/sharc-fixed-pair.json').read_text())
            fixed_core_doc = copy.deepcopy(core.doc)
            fixed_core_doc['sharc'] = fixed['core']
            fixed_app_doc = copy.deepcopy(app.doc)
            fixed_app_doc['sharc'] = fixed['app']
            fixed_core = link.Mod2(fixed_core_doc, 'fixed-core')
            fixed_app = link.Mod2(fixed_app_doc, 'fixed-app')
            self.assertEqual(link.check([fixed_core, fixed_app], image), [])
            self.assertIn('active SHARC application needs the fixed keyed pitch table',
                          link.check([core, fixed_app], image))
            with self.assertRaisesRegex(elemod.ModError, 'unqualified active SHARC app bytes or entry'):
                link.link([fixed_core, app], image, sharc_stream=stock.section(7))
            self.assertTrue(any('unqualified active SHARC app' in p for p in
                                link.check([fixed_core, app], image)))
            self.assertTrue(any('unqualified active SHARC app' in p for p in
                                link.check([fixed_core, asm], image)))
            for frequency, accepted in ((220, True), (660, True), (880, True),
                                        (219, False), (881, False)):
                varied = copy.deepcopy(fixed_app.doc)
                code = varied['sharc']['segments'][0]
                data = bytearray.fromhex(code['hex'])
                step = round(frequency * (1 << 32) / 48000)
                word = step.to_bytes(4, 'big')
                data[328:332] = word[:2][::-1] + word[2:][::-1]
                code['hex'] = data.hex()
                problems = link.check([fixed_core, link.Mod2(varied, 'varied')], image)
                self.assertEqual(not any('unqualified active SHARC app' in p for p in problems),
                                 accepted, frequency)
                data[327] ^= 1
                code['hex'] = data.hex()
                self.assertTrue(any('unqualified active SHARC app' in p for p in
                                    link.check([fixed_core, link.Mod2(varied, 'varied')], image)))
            relocated = copy.deepcopy(app.doc)
            relocated['sharc']['zero'][0]['offset_bytes'] += 4
            relocated['sharc']['zero'][0]['size_bytes'] -= 4
            with self.assertRaisesRegex(elemod.ModError, 'gap or overlap'):
                link.Mod2(relocated, 'relocated')

            bad_table = copy.deepcopy(app.doc)
            data = bytearray.fromhex(bad_table['sharc']['segments'][1]['hex'])
            data[152] ^= 1
            bad_table['sharc']['segments'][1]['hex'] = data.hex()
            with self.assertRaisesRegex(elemod.ModError, 'active SHARC application needs the fixed keyed pitch table'):
                link.link([core, link.Mod2(bad_table, 'bad-table')], image, sharc_stream=stock.section(7))

            l2doc = copy.deepcopy(app.doc)
            a = l2doc['sharc']
            a['abi'] = rel.sharc['l2_abi']
            a['segments'][1]['offset_bytes'] = 16384
            a['zero'] = [{'offset_bytes': 768, 'size_bytes': 16384 - 768},
                         {'offset_bytes': 16588, 'size_bytes': 32768 - 16588}]
            l2app = link.Mod2(l2doc, 'l2-app')
            linked_l2 = link.link([core, l2app], image, sharc_stream=stock.section(7))
            records = sharc.parse(linked_l2.sharc_stream, rel.sharc)
            binding = next(r for r in records if r.target == rel.sharc['core_range'][0])
            import struct
            self.assertEqual(binding.raw[16:], struct.pack('<III', 0xbc80a0, 0xbc80bf, 0))
            table_at, table = rel.sharc['keyed_pitch_table']
            table_record = next(r for r in records if r.target == rel.sharc['app_range'][0] + table_at)
            self.assertEqual(table_record.raw[16:].hex(), table)
            self.assertIn('only one SHARC application may own the DN2 reservation',
                          link.check([core, app, l2app], image))
            with self.assertRaisesRegex(elemod.ModError, 'unqualified active SHARC app'):
                link.link([fixed_core, l2app], image, sharc_stream=stock.section(7))

            for selected in (app, asm):
                linked = link.link([core, selected], image, sharc_stream=stock.section(7))
                profile = rel.sharc
                with patch.dict(profile, stored_max=len(linked.sharc_stored) - 1):
                    with self.assertRaisesRegex(elemod.ModError, 'SHARC stored section exceeds the profile limit'):
                        link.link([core, selected], image, sharc_stream=stock.section(7))
                records = sharc.parse(linked.sharc_stream, profile)
                self.assertEqual(len(records), profile['record_count'] + 6)
                self.assertEqual(linked.layout['sharc']['hook'], profile['hook'][0])
                self.assertEqual(linked.layout['sharc']['core'], list(profile['core_range']))
                outputs = formats.write(stock, formats.pack_main(linked.image, dev), dev,
                                        stored_sharc=linked.sharc_stored)
                facts = formats.verify(outputs, stock, linked.image, dev,
                                       want_sharc=linked.sharc_stream)
                self.assertIn('sections 2, 4, 5, 8, byte for byte', facts['untouched'])


if __name__ == '__main__':
    unittest.main()
