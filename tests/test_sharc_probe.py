# SPDX-License-Identifier: GPL-2.0-or-later
"""Probe checker tests: no firmware, compiler or external runner required."""
from pathlib import Path
import struct
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples/sharc-sine-probe'))
from execute import check_dag_store, check_subset, expected
from h1_spills import self_test


class ProbeChecks(unittest.TestCase):
    def test_h1_full_width_spills_and_mutations(self):
        result = self_test()
        self.assertEqual(result['roundtrips'], 1024)
        self.assertEqual(result['omitted_px1_failures'], 1024)
        self.assertEqual(result['normal32_low_byte_failures'], 1020)
        self.assertEqual(len(result['rejected_mutations']), 4)

    def test_independent_phase_boundaries(self):
        samples, phase = expected(0, 0x40000000, 4)
        self.assertEqual(struct.unpack('<4I', samples), (0, 0x3e000000, 0x80000000, 0xbe000000))
        self.assertEqual(phase, 0)
        self.assertEqual(expected(0x80000000, 0, 2), (bytes.fromhex('0000008000000080'), 0x80000000))
        self.assertEqual(expected(0xffffffff, 1, 2)[1], 1)

    def test_same_dag_indexed_stores_rejected(self):
        for space, register in [('dm', 'i6'), ('dm', 'm7'), ('dm', 'b0'), ('dm', 'l4'),
                                ('pm', 'i15'), ('pm', 'm8'), ('pm', 'b12'), ('pm', 'l9')]:
            with self.subTest(space=space, register=register):
                index = 'i6' if space == 'dm' else 'i14'
                with self.assertRaisesRegex(ValueError, 'same-DAG'):
                    check_dag_store(f'{space} (-0x3,{index})={register}')
        with self.assertRaisesRegex(ValueError, 'same-DAG'):
            check_subset('  00180000   0001   dm (i7,m7)=i6')

    def test_direct_and_opposite_dag_stores_are_exempt(self):
        for mnemonic in ('dm (0x2c0400)=i6', 'pm (0x300000)=i12',
                         'dm (i7,m7)=i12', 'pm (i14,m14)=i6', 'dm (i7,m7)=r2'):
            check_dag_store(mnemonic)

    def test_subset_rejects_unknown_and_escaping_branch(self):
        with self.assertRaisesRegex(ValueError, 'unsupported instruction'):
            check_subset('  00180000   0001   idle')
        with self.assertRaisesRegex(ValueError, 'outside instruction boundaries'):
            check_subset('  00180000   063e00180001   jump 0x180001')

    def test_delayed_return_requires_both_expected_slots(self):
        good = ('  00180000   083f343f   jump (m14,i12) (db)\n'
                '  00180002   1901   rframe\n  00180003   0001   nop\n')
        self.assertEqual(check_subset(good), {'call/return': 2, 'nop': 1})
        with self.assertRaisesRegex(ValueError, 'unqualified delayed slots'):
            check_subset(good.replace('rframe', 'nop'))


if __name__ == '__main__':
    unittest.main()
