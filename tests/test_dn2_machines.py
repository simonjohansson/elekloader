# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise the C clone registry without firmware or a cross compiler."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CC = shutil.which('cc')


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


if __name__ == '__main__':
    unittest.main()
