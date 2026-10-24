// SPDX-License-Identifier: GPL-3.0-or-later
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { sha } from '../src/bytes.ts'
import { DIGITONE_MK2, targetOf } from '../src/devices.ts'
import { ModError } from '../src/elemod.ts'
import { Mod2, check } from '../src/link.ts'
import * as formats from '../src/formats.ts'
import * as sharc from '../src/sharc.ts'

const corpus = JSON.parse(readFileSync(new URL('../../tests/fixtures/sharc.json', import.meta.url), 'utf8'))
const bytes = (hex: string): Uint8Array => Uint8Array.from(Buffer.from(hex, 'hex'))
const original = bytes(corpus.original)
const profile = DIGITONE_MK2.releases[0].sharc!
const inertArtifact = JSON.parse(readFileSync(new URL('../../examples/sharc-sine/sine.sharc.json', import.meta.url), 'utf8'))
inertArtifact.entries = null
inertArtifact.stack_bytes = 0
const synthetic = { ...profile, decodedSha256: sha(original), ownedRanges: [[0x20002000, 0x20002020] as [number, number]] }
const refusal = (fn: () => unknown, error: string) => assert.throws(fn, e => e instanceof ModError && e.message === error)

test('active DN2 keyed sine and historical fixed pair stay exactly matched', () => {
  const rel = DIGITONE_MK2.releases[0], target = targetOf(DIGITONE_MK2, rel)
  const bridge = JSON.parse(readFileSync(new URL('../../mods/core-dn2/bridge.sharc.json', import.meta.url), 'utf8'))
  const fixed = JSON.parse(readFileSync(new URL('../../tests/fixtures/sharc-fixed-pair.json', import.meta.url), 'utf8'))
  const core = (artifact: unknown) => new Mod2({ elemod: 2, id: 'core', version: '0.1', target,
    sections: { '.boot': { align: 4, parts: [['hex', '00000000']] } }, sharc: artifact }, 'core')
  const image = new Uint8Array(rel.mainLen)
  const bad = (bridgeArtifact: unknown, artifact: unknown) => check([core(bridgeArtifact), new Mod2({ elemod: 2, id: 'sine', version: '0.1', target,
    sections: {}, sharc: artifact }, 'sine')], image).some(p => p.includes('unqualified active SHARC app'))
  const original = JSON.parse(readFileSync(new URL('../../examples/sharc-sine/sine.sharc.json', import.meta.url), 'utf8'))
  assert.equal(bad(bridge, original), false)
  assert.equal(bad(fixed.core, fixed.app), false)
  assert.equal(bad(bridge, fixed.app), true)
  assert.equal(bad(fixed.core, original), true)
  const changed = structuredClone(original)
  const changedCode = bytes(changed.segments[0].hex)
  changedCode[328] ^= 1
  changed.segments[0].hex = Buffer.from(changedCode).toString('hex')
  assert.equal(bad(bridge, changed), true)
  for (const [hz, accepted] of [[220, true], [660, true], [880, true], [219, false], [881, false]] as const) {
    const artifact = structuredClone(fixed.app)
    const code = bytes(artifact.segments[0].hex)
    const step = Math.round(hz * 2 ** 32 / 48000)
    code.set([(step >>> 16) & 255, (step >>> 24) & 255, step & 255, (step >>> 8) & 255], 328)
    artifact.segments[0].hex = Buffer.from(code).toString('hex')
    assert.equal(bad(fixed.core, artifact), !accepted, `${hz} Hz`)
    code[327] ^= 1
    artifact.segments[0].hex = Buffer.from(code).toString('hex')
    assert.equal(bad(fixed.core, artifact), true, `${hz} Hz with neighboring byte changed`)
  }
})

test('prelinked inert payload covers only its DN2 owner', () => {
  const payload = sharc.modulePayload(inertArtifact, profile)
  assert.deepEqual(payload.owner, profile.appRange)
  assert.equal(payload.entries, null)
  const bad = structuredClone(inertArtifact)
  bad.zero[0].size_bytes += 4
  refusal(() => sharc.modulePayload(bad, profile), 'SHARC zero range is unaligned or exceeds its owner')
  const active = structuredClone(inertArtifact)
  active.entries = { init_offset_bytes: 0, render_offset_bytes: 768 }
  refusal(() => sharc.modulePayload(active, profile), 'SHARC entry is not in owned code')
})

for (const c of corpus.parse_cases) test(`SHARC parse: ${c.name}`, () => {
  const data = bytes(c.hex)
  if (c.error) refusal(() => sharc.parse(data, profile), c.error)
  else {
    const records = sharc.parse(data, profile)
    assert.equal(records.length, c.records)
    assert.deepEqual(Buffer.concat(records.map(r => r.raw)), Buffer.from(data))
    assert.deepEqual(sharc.insert(data, { ...profile, decodedSha256: sha(data) }), data)
  }
})

for (const c of corpus.span_cases) test(`SHARC address: ${c.name}`, () => {
  const action = () => sharc.byteSpan(profile, c.address, c.size, c.unit)
  if (c.error) refusal(action, c.error)
  else assert.deepEqual(action(), c.result)
})

for (const c of corpus.insert_cases) test(`SHARC insert: ${c.name}`, () => {
  const p = { ...synthetic, ownedRanges: c.owned ?? synthetic.ownedRanges, decodedMax: c.limit ?? profile.decodedMax }
  const action = () => sharc.insert(original, p, c.loads.map(([a, h]: [number, string]) => [a, bytes(h)]), c.fills)
  if (c.error) refusal(action, c.error)
  else assert.equal(Buffer.from(action()).toString('hex'), c.result)
  assert.equal(Buffer.from(original).toString('hex'), corpus.original)
})

test('SHARC golden keeps ordered overlap and rewrites only the last FIRST', () => {
  const result = sharc.insert(original, synthetic, [[0x20002000, bytes('11223344')]], [[0x20002010, 8, 0]])
  assert.equal(sha(result), corpus.expected_sha256)
  const records = sharc.parse(result, synthetic)
  assert.deepEqual(records.map(r => r.offset), [0, 16, 36, 52, 68, 88, 108, 124])
  assert.deepEqual(records.map(r => r.flags), [0x5001, 1, 0x801, 0x5001, 1, 1, 0x101, 0x8001])
  assert.deepEqual(records.filter(r => r.flags === sharc.FIRST).map(r => r.argument), [36, 72])
  assert.deepEqual([0, 1, 2, 4, 7].map(i => records[i].raw), sharc.parse(original, profile).filter((_, i) => i !== 3).map(r => r.raw))
  assert.equal(records[1].target, records[4].target)
  refusal(() => sharc.insert(result, synthetic), 'SHARC stock DSP hash does not match the profile')
  assert.deepEqual([records[6].count, records[6].raw.length], [8, 16])
})

test('SHARC decoded limit, hash identity and payload type', () => {
  assert.equal(sharc.parse(original, { ...profile, decodedMax: 104 }).length, 6)
  refusal(() => sharc.parse(original, { ...profile, decodedMax: 103 }), 'SHARC decoded stream exceeds the profile limit')
  refusal(() => sharc.insert(original, profile), 'SHARC stock DSP hash does not match the profile')
  refusal(() => sharc.insert(original, synthetic, [[0x20002000, [1, 2, 3, 4] as unknown as Uint8Array]]), 'SHARC load payload must be bytes')
})

test('SHARC keeps copies with Uint8Array and Node Buffer inputs', () => {
  for (const mutable of [original.slice(), Buffer.from(original)]) {
    const records = sharc.parse(mutable, profile), noop = sharc.insert(mutable, synthetic)
    mutable[16] = 0
    assert.deepEqual(records[1].raw, original.slice(16, 36))
    assert.deepEqual(noop, original)
  }
})

test('SHARC preserves a historical protected load during insertion elsewhere', () => {
  const data = bytes(corpus.parse_cases.find((c: {name: string}) => c.name === 'original_protected_load').hex)
  const p = { ...synthetic, decodedSha256: sha(data) }
  const result = sharc.insert(data, p, [[0x20002000, bytes('11223344')]])
  assert.deepEqual(sharc.parse(result, p)[1].raw, data.slice(16, 36))
})

test('SHARC instruction patch requires exact unique stock load', () => {
  const data = bytes(corpus.parse_cases.find((c: {name: string}) => c.name === 'original_protected_load').hex)
  const p = { ...synthetic, decodedSha256: sha(data), patchRanges: [[0x20001000, 0x20001004] as [number, number]] }
  const patched = sharc.insert(data, p, [], [], [[0x20001000, bytes('0506'), bytes('aabb')]])
  assert.equal(Buffer.from(patched.subarray(84, 88)).toString('hex'), 'aabb0708')
  refusal(() => sharc.insert(data, p, [], [], [[0x20001000, bytes('0006'), bytes('aabb')]]),
    'SHARC patch stock instruction does not match')
  refusal(() => sharc.insert(data, { ...p, patchRanges: [] }, [], [], [[0x20001000, bytes('0506'), bytes('aabb')]]),
    'SHARC patch is outside the profile patch range')
  refusal(() => sharc.insert(original, { ...p, decodedSha256: sha(original) }, [], [], [[0x20001000, bytes('0506'), bytes('aabb')]]),
    'SHARC patch needs one unambiguous stock load')
})

test('SHARC owner-stock exact no-op', { skip: !process.env.ELEKLOADER_DN2_SYX }, async () => {
  const raw = readFileSync(process.env.ELEKLOADER_DN2_SYX!)
  const [parsed, device, release] = await formats.load(raw)
  assert.equal(device, DIGITONE_MK2)
  assert.equal(release, DIGITONE_MK2.releases[0])
  const stored = parsed.stored.get(profile.section)!, decoded = parsed.section(profile.section)
  assert.deepEqual([sha(stored), stored.length], [profile.storedSha256, profile.storedLen])
  assert.deepEqual([sha(decoded), decoded.length], [profile.decodedSha256, profile.decodedLen])
  const records = sharc.parse(decoded, profile)
  assert.equal(records.length, 95)
  assert.deepEqual(Buffer.concat(records.map(r => r.raw)), Buffer.from(decoded))
  assert.deepEqual(sharc.insert(decoded, profile), decoded)
  const spans = records.filter(r => r.flags === sharc.LOAD || r.flags === sharc.FILL)
    .map(r => sharc.byteSpan(profile, r.target, r.count, 'loader-byte', false))
  assert.equal(spans.reduce((n, [a, b], i) => n + spans.slice(i+1).filter(([c, d]) => a < d && c < b).length, 0), 15)
  refusal(() => sharc.insert(decoded, profile, [], [[0x20090000, 4, 0]]), 'SHARC new load or fill is outside the profile-owned ranges')
  const patched = sharc.insert(decoded, profile, [], [], [[0x2838489a, bytes('8715ffff78ff'), bytes('3e06160006eb')]])
  const changed = [...decoded.keys()].filter(i => decoded[i] !== patched[i])
  assert.equal(changed.length, 6)
  assert.equal(Buffer.from(patched.subarray(changed[0], changed[0] + 6)).toString('hex'), '3e06160006eb')
  const outputs = formats.write(parsed, parsed.stored.get(device.mainSection)!, device)
  assert.deepEqual(Buffer.from(outputs.syx), raw)
  formats.verify(outputs, parsed, formats.mainImage(parsed, device), device)
})
