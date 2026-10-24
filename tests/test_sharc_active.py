# SPDX-License-Identifier: GPL-2.0-or-later
"""Active DN2 sine integration; requires owner stock and a ColdFire cross compiler."""
import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest

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
            stock, dev, rel = formats.load(STOCK)
            image = formats.main_image(stock, dev)
            self.assertIsNone(link.link([core], image).sharc_stream)
            self.assertEqual(link.check([core, app], image), [])

            old_core = copy.deepcopy(core.doc)
            old_core.pop('sharc')
            self.assertIn('active SHARC application requires a qualified matching core bridge',
                          link.check([link.Mod2(old_core, 'old-core'), app], image))
            mutated = copy.deepcopy(app.doc)
            code = mutated['sharc']['segments'][0]
            code['hex'] = ('00' if code['hex'][:2] != '00' else '01') + code['hex'][2:]
            self.assertTrue(any('unqualified active SHARC app' in problem for problem in
                                link.check([core, link.Mod2(mutated, 'mutated')], image)))
            for frequency, accepted in ((220, True), (660, True), (880, True),
                                        (219, False), (881, False)):
                varied = copy.deepcopy(app.doc)
                code = varied['sharc']['segments'][0]
                data = bytearray.fromhex(code['hex'])
                step = round(frequency * (1 << 32) / 48000)
                word = step.to_bytes(4, 'big')
                data[328:332] = word[:2][::-1] + word[2:][::-1]
                code['hex'] = data.hex()
                problems = link.check([core, link.Mod2(varied, 'varied')], image)
                self.assertEqual(not any('unqualified active SHARC app' in p for p in problems),
                                 accepted, frequency)
                data[327] ^= 1
                code['hex'] = data.hex()
                self.assertTrue(any('unqualified active SHARC app' in p for p in
                                    link.check([core, link.Mod2(varied, 'varied')], image)))
            relocated = copy.deepcopy(app.doc)
            relocated['sharc']['zero'][0]['offset_bytes'] += 4
            relocated['sharc']['zero'][0]['size_bytes'] -= 4
            with self.assertRaisesRegex(elemod.ModError, 'gap or overlap'):
                link.Mod2(relocated, 'relocated')

            linked = link.link([core, app], image, sharc_stream=stock.section(7))
            profile = rel.sharc
            records = sharc.parse(linked.sharc_stream, profile)
            self.assertEqual(len(records), profile['record_count'] + 5)
            self.assertEqual(linked.layout['sharc']['hook'], profile['hook'][0])
            self.assertEqual(linked.layout['sharc']['core'], list(profile['core_range']))
            outputs = formats.write(stock, formats.pack_main(linked.image, dev), dev,
                                    stored_sharc=linked.sharc_stored)
            facts = formats.verify(outputs, stock, linked.image, dev,
                                   want_sharc=linked.sharc_stream)
            self.assertIn('sections 2, 4, 5, 8, byte for byte', facts['untouched'])


if __name__ == '__main__':
    unittest.main()
