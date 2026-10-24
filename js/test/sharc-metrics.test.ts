// SPDX-License-Identifier: GPL-3.0-or-later
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { sha } from '../src/bytes.ts'
import { DIGITONE_MK2, targetOf } from '../src/devices.ts'
import { ModError } from '../src/elemod.ts'
import * as formats from '../src/formats.ts'
import { Mod2, check, link } from '../src/link.ts'
import * as sharc from '../src/sharc.ts'

const release = DIGITONE_MK2.releases[0], profile = release.sharc!
const target = targetOf(DIGITONE_MK2, release)
const bytes = (hex: string): Uint8Array => Uint8Array.from(Buffer.from(hex, 'hex'))
const artifact = (path: string): any => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'))
const standardCore = artifact('../../mods/core-dn2/bridge.sharc.json')
const measuredCore = artifact('../../mods/core-dn2-metrics/bridge.sharc.json')
const l1App = artifact('../../examples/sharc-sine/sine.sharc.json')
const mismatch = 'active SHARC measurement requires a matching measurement core and L2 application'
const unqualified = 'core 0.1 has unqualified active SHARC core bytes or entry'
const stackError = 'active SHARC stack exceeds the profile limit'
const app = (abi = profile.metricsAbi, stack = 128): any => ({ abi,
  segments: [{ offset_bytes: 0, kind: 'code', hex: '0100'.repeat(34) }],
  zero: [{ offset_bytes: 68, size_bytes: 32768 - 68 }],
  entries: { init_offset_bytes: 0, render_offset_bytes: 2 }, stack_bytes: stack })
const modules = (bridge: any, payload: any): Mod2[] => [
  new Mod2({ elemod: 2, id: 'core', version: '0.1', target,
    sections: { '.boot': { align: 4, parts: [['hex', '00000000']] } }, sharc: bridge }, 'core'),
  new Mod2({ elemod: 2, id: 'app', version: '0.1', target, sections: {}, sharc: payload }, 'app'),
]
const problems = (bridge: any, payload: any): string[] => check(modules(bridge, payload), new Uint8Array(release.mainLen))
const refusal = (fn: () => unknown, message: string): void => {
  assert.throws(fn, e => e instanceof ModError && e.message === message)
}

test('optional measurement uses the existing L1 gap and the unchanged L2 app envelope', () => {
  assert.equal(profile.metricsAbi, 'dn2-master-mono32-l2-metrics-v1')
  const core = sharc.modulePayload(measuredCore, profile, true), measured = sharc.modulePayload(app(), profile)
  assert.deepEqual(core.owner, [0x282dd600, 0x282ddd98])
  assert.deepEqual(measured.owner, profile.l2AppRange)
  assert.equal(core.metrics, true)
  assert.equal(measured.metrics, true)
  assert.equal(sharc.modulePayload(l1App, profile).metrics, false)
  assert.equal(sharc.modulePayload(app(profile.l2Abi), profile).metrics, false)
  assert.equal(core.stackBytes, 124)
  assert.equal(profile.stackMax, 544)
  assert.deepEqual(profile.ownedRanges, [[0x282dd600, 0x282dde00], [0x20090000, 0x20098000]])
  assert.deepEqual(profile.metricsHook, [0x28393cbe, '01112600388a', '3e0616004aed'])
  const inert = app(); inert.entries = null; inert.stack_bytes = 0
  refusal(() => sharc.modulePayload(inert, profile), 'SHARC measurement ABI needs active callbacks')
  const oversized = app(); oversized.zero[0].size_bytes += 4
  refusal(() => sharc.modulePayload(oversized, profile), 'SHARC zero range is unaligned or exceeds its owner')
  refusal(() => sharc.modulePayload({ ...app(), abi: profile.abi }, profile), 'SHARC zero range is unaligned or exceeds its owner')
})

test('measurement pairs are exclusive and account for the extra eight-byte call frame', () => {
  assert.deepEqual(problems(measuredCore, app(profile.metricsAbi, 420)), [])
  for (const n of [421, 424, 428]) assert.deepEqual(problems(measuredCore, app(profile.metricsAbi, n)), [stackError])
  assert.deepEqual(problems(standardCore, app(profile.l2Abi, 428)), [])
  assert.deepEqual(problems(standardCore, app(profile.l2Abi, 429)), [stackError])
  assert.deepEqual(problems(standardCore, app()), [mismatch])
  assert.deepEqual(problems(measuredCore, app(profile.l2Abi)), [mismatch])
  assert.deepEqual(problems(measuredCore, l1App), [mismatch])
  const mods = modules(measuredCore, app())
  const extra = new Mod2({ elemod: 2, id: 'other', version: '0.1', target, sections: {}, sharc: app() }, 'other')
  assert(check([...mods, extra], new Uint8Array(release.mainLen)).includes('only one SHARC application may own the DN2 reservation'))
})

test('the measurement core claims its reply channel even when its document omits resources', () => {
  assert.equal(profile.metricsResource, 'sharc:reply-header:2')
  const image = new Uint8Array(release.mainLen), mods = modules(measuredCore, app())
  assert.deepEqual(mods[0].names, [])
  assert.deepEqual(mods[0].impliedNames(image), [profile.metricsResource])
  assert.deepEqual(mods[1].impliedNames(image), [])
  assert.deepEqual(modules(standardCore, app(profile.l2Abi))[0].impliedNames(image), [])
  const other = new Mod2({ elemod: 2, id: 'other', version: '0.1', target, sections: {},
    resources: { names: [profile.metricsResource] } }, 'other')
  assert.deepEqual(check([...mods, other], image), ['core 0.1 and other 0.1 both claim sharc:reply-header:2'])
  assert.deepEqual(mods[0].names, [profile.metricsResource])
})

test('the measurement core stays pinned while bounded app code and entries may change', () => {
  for (let segment = 0; segment < measuredCore.segments.length; ++segment) {
    const changed = structuredClone(measuredCore), raw = bytes(changed.segments[segment].hex)
    raw[0] ^= 1
    changed.segments[segment].hex = Buffer.from(raw).toString('hex')
    assert.deepEqual(problems(changed, app()), [unqualified])
  }
  for (const change of ['entry', 'stack']) {
    const changed = structuredClone(measuredCore)
    if (change === 'entry') changed.entries.hook_offset_bytes += 2
    else changed.stack_bytes -= 4
    assert.deepEqual(problems(changed, app()), [unqualified])
  }
  // These are packaging checks; the synthetic app bytes are not executed.
  const changed = app()
  changed.segments[0].hex = 'deadbeef' + changed.segments[0].hex.slice(8)
  changed.entries.render_offset_bytes = 0
  assert.deepEqual(problems(measuredCore, changed), [])
  changed.entries.render_offset_bytes = 4
  refusal(() => sharc.modulePayload(changed, profile), 'SHARC entry is in the instruction read-ahead guard')
})

/** Resolve the last loader write, including fills; no stock bytes are stored in this test. */
function loaded(stream: Uint8Array, at: number, length: number): Uint8Array {
  const records = sharc.parse(stream, profile)
  return Uint8Array.from({ length }, (_, i) => {
    const address = at + i
    const row = records.findLast(r => (r.flags === sharc.LOAD || r.flags === sharc.FILL) && r.target <= address && address < r.target + r.count)
    assert(row, `no loader byte at ${address.toString(16)}`)
    return row.flags === sharc.LOAD ? row.raw[16 + address - row.target] : row.argument >>> ((address - row.target) % 4 * 8) & 255
  })
}

test('owner-stock measurement writer binds only the measured path and keeps stock patch checks',
  { skip: !process.env.ELEKLOADER_DN2_SYX }, async () => {
    const [stock, device] = await formats.load(readFileSync(process.env.ELEKLOADER_DN2_SYX!))
    const image = formats.mainImage(stock, device), stream = stock.section(profile.section)
    const measuredMods = modules(measuredCore, app())
    const stateSegment = measuredMods[0].sharc!.segments.find(([off]) => off === profile.metricsCallbackOffsetBytes)!
    stateSegment[2] = Buffer.from(stateSegment[2])
    const measured = link(measuredMods, image, null, stream).sharcStream!
    assert.deepEqual(stateSegment[2], Buffer.alloc(152))
    const plain = link(modules(standardCore, app(profile.l2Abi)), image, null, stream).sharcStream!
    // Captured from the pre-measurement linker against this exact stock.
    assert.equal(sha(plain), 'cf22d1fd665a4cfaa30b4082d7171af041ba51e96a4c02c9fe42dcdbf63e958b')
    const originalL1 = link(modules(standardCore, l1App), image, null, stream).sharcStream!
    assert.equal(sha(originalL1), 'faca192f22590371417221d116cefaa4e7caa0b0317d1a270e980bb72d31257a')
    assert.equal(Buffer.from(loaded(measured, 0x282dd600, 12)).toString('hex'), '0080bc0000ed160000000000')
    assert.equal(Buffer.from(loaded(plain, 0x282dd600, 12)).toString('hex'), '0080bc000180bc0000000000')
    assert.equal(new DataView(loaded(measured, 0x282ddd00, 4).buffer).getUint32(0, true), 0xbc8001)
    assert.deepEqual(loaded(measured, 0x282ddd04, 148), new Uint8Array(148))
    assert.deepEqual(loaded(measured, 0x282dda00, 768), bytes(measuredCore.segments[1].hex))
    assert.deepEqual(loaded(plain, 0x282dda00, 920), new Uint8Array(920))
    const [pitchOffset, table] = profile.keyedPitchTable!
    assert.deepEqual(loaded(measured, profile.appRange![0] + pitchOffset, table.length / 2), bytes(table))
    assert.deepEqual(loaded(measured, 0x282dddcc, 52), new Uint8Array(52))
    const [at, original, replacement] = profile.metricsHook!
    assert.deepEqual(loaded(measured, at, 6), bytes(replacement))
    assert.deepEqual(loaded(plain, at, 6), bytes(original))
    const coreHash = sha(bytes(measuredCore.segments[2].hex))
    assert.equal(coreHash, profile.activeMetricsCore!.segments[2][2])
    assert.deepEqual(bytes(measuredCore.segments[2].hex), new Uint8Array(152))
    const wrong = bytes(original); wrong[0] ^= 1
    refusal(() => sharc.insert(stream, profile, [], [], [[at, wrong, bytes(replacement)]]), 'SHARC patch stock instruction does not match')
    refusal(() => sharc.insert(stream, profile, [], [], [[at - 2, bytes('000000000000'), bytes(replacement)]]), 'SHARC patch is outside the profile patch range')
    refusal(() => sharc.insert(stream, profile, [[0x28393cc4, bytes('00000000')]]), 'SHARC new load or fill is outside the profile-owned ranges')
  })
