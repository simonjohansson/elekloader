// SPDX-License-Identifier: GPL-3.0-or-later
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { DIGITONE_MK2, devices } from '../src/devices.ts'

const profile = DIGITONE_MK2.releases[0].sharc!

test('DN2 SHARC evidence does not grant memory or activate an ABI', () => {
  assert.equal(profile.processor, 'ADSP-21569')
  assert.equal(profile.isa, 'sharc+-visa')
  assert.equal(profile.siliconRevision, null)
  assert.deepEqual(profile.ownedRanges, [])
  assert.equal('abi' in profile, false)
  assert.deepEqual(DIGITONE_MK2.dspPayloads, {})
  assert.deepEqual(devices().flatMap(d => d.releases.filter(r => r.sharc).map(r => [d.key, r.version])),
    [['digitone-mk2', '1.12']])
})

test('DN2 address units and capacity endpoints remain distinct', () => {
  for (const [core, loader] of [[0x268438, 0x28268438], [0x2dd600, 0x282dd600],
    [0x300000, 0x28300000], [0x38489a, 0x2838489a]]) {
    const matches = profile.l1Aliases.filter(([lo, hi]) => lo <= core && core < hi)
    assert.equal(matches.length, 1)
    const [lo, hi, base] = matches[0]
    assert.equal(base + core - lo, loader)
    assert.equal((base + hi - lo) % 4, 0)
  }
  assert.equal(2 * 0x1c244d, 0x38489a)
  assert.equal(2 * 0x1c12e2 + 0x28000000, 0x283825c4)
  const [lo, hi, base] = profile.l2Pc16
  assert.deepEqual([base, base + 2 * (hi - lo)], profile.l2Bytes)
  assert.equal(base + 2 * (0xb89c53 - lo), 0x200138a6)
  assert.ok(profile.protected.some(([a, b]) => a <= 0x200fe000 && 0x200fe000 < b))
  assert.equal(profile.protected.some(([a, b]) => a <= 0x282dd600 && 0x282dd600 < b), false)
  assert.equal(profile.ownedRanges.some(([a, b]) => a <= 0x282dd600 && 0x282dd600 < b), false)
})

test('DN2 transport, flash, stored and decoded DSP have independent budgets', () => {
  assert.deepEqual([profile.storedMax, profile.decodedMax], [0x100000, 0xfffff])
  assert.equal(profile.decodedMax + 1, 0x100000)
  assert.equal(DIGITONE_MK2.updateMax, 0x200000)
  assert.equal(DIGITONE_MK2.flashLimit - DIGITONE_MK2.flashAt, 0x300000)
  assert.equal(profile.storedMax - profile.storedLen, 446500)
  assert.equal(profile.decodedMax - profile.decodedLen, 211619)
})
