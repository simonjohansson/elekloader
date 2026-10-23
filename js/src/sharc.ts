// SPDX-License-Identifier: GPL-3.0-or-later
// The DN2's observed boot-record subset. Paired with elekloader/sharc.py; no external parser code.
import { sha } from './bytes.ts'
import type { SharcProfile } from './devices.ts'
import { ModError } from './elemod.ts'

export const LOAD = 0x0001, FILL = 0x0101, FIRST = 0x5001, INIT = 0x0801, FINAL = 0x8001
const KINDS = [LOAD, FILL, FIRST, INIT, FINAL]
const uint32 = (n: number): boolean => Number.isInteger(n) && n >= 0 && n <= 0xffffffff

/** Canonical loader-byte interval. Size is bytes in every address view.
 * Allocation excludes protected ranges; an existing record may only be mapped. */
export function byteSpan(profile: SharcProfile, address: number, size: number, unit = 'loader-byte', checkProtected = true): [number, number] {
  if (!uint32(address) || !uint32(size) || !size)
    throw new ModError('SHARC address and nonempty byte count must be uint32')
  let intervals: [number, number, number][]
  if (unit === 'loader-byte') {
    intervals = profile.l1Aliases.map(([lo, hi, base]) => [base, base + hi - lo, base])
    intervals.push(...[profile.l2Bytes, profile.ddrBytes].map(([lo, hi]): [number, number, number] => [lo, hi, lo]))
  } else if (unit === 'core-byte') {
    intervals = [...profile.l1Aliases]
    intervals.push(...[profile.l2Bytes, profile.ddrBytes].map(([lo, hi]): [number, number, number] => [lo, hi, lo]))
  } else if (unit === 'pc16') {
    intervals = profile.l1Aliases.map(([lo, hi, base]) => [lo / 2, hi / 2, base])
    intervals.push(profile.l2Pc16)
  } else throw new ModError(`unsupported SHARC address unit: ${unit}`)
  const scale = unit === 'pc16' ? 2 : 1
  for (const [lo, hi, base] of intervals) {
    const start = base + (address - lo) * scale, end = start + size
    if (lo <= address && address < hi && end <= base + (hi - lo) * scale && end <= 0x100000000) {
      if (checkProtected && profile.protected.some(([begin, stop]) => start < stop && begin < end))
        throw new ModError('SHARC byte span overlaps a protected region')
      return [start, end]
    }
  }
  throw new ModError('SHARC byte span is outside the supported address map')
}

export type Record = { offset: number; flags: number; target: number; count: number; argument: number; raw: Uint8Array }

/** Read an ordered stream without normalizing headers, loads or overlaps. */
export function parse(stream: Uint8Array, profile: SharcProfile): Record[] {
  if (stream.length > profile.decodedMax) throw new ModError('SHARC decoded stream exceeds the profile limit')
  const records: Record[] = [], firsts: [number, number][] = []
  let offset = 0, active: number | null = null, final = false
  const view = new DataView(stream.buffer, stream.byteOffset, stream.byteLength)
  while (offset < stream.length) {
    const fail = (message: string): never => { throw new ModError(`SHARC boot record at +0x${offset.toString(16)}: ${message}`) }
    if (stream.length - offset < 16) fail('truncated header')
    const header = stream.subarray(offset, offset + 16)
    const code = view.getUint32(offset, true), target = view.getUint32(offset + 4, true)
    const count = view.getUint32(offset + 8, true), argument = view.getUint32(offset + 12, true)
    if (code >>> 24 !== 0xad) fail('invalid header signature')
    if (header.reduce((a, b) => a ^ b, 0)) fail('invalid header checksum')
    const flags = code & 0xffff
    if (!KINDS.includes(flags)) fail(`unsupported flags 0x${flags.toString(16).padStart(4, '0')}`)
    const end = offset + 16 + (flags === LOAD ? count : 0)
    if (end > stream.length) fail('truncated payload')
    if (flags === LOAD || flags === FILL) {
      if (active === null) fail('load or fill outside an application')
      if (!count || target % 4 || count % 4) fail('load or fill address/count must be nonempty and four-byte aligned')
      if (flags === LOAD && argument) fail('load argument must be zero')
      try { byteSpan(profile, target, count, 'loader-byte', false) } catch (error) { fail((error as Error).message) }
    } else {
      if (count) fail('entry record requires zero count')
      try { byteSpan(profile, target, 2, 'pc16', false) } catch (error) { fail((error as Error).message) }
      if (flags === FIRST) {
        if (active !== null) fail('FIRST before the preceding application ends')
        active = target
        firsts.push([offset, argument])
      } else {
        if (active === null || target !== active || argument) fail('entry does not match its FIRST application')
        active = null
        if (flags === FINAL) {
          final = true
          if (end !== stream.length) fail('bytes after FINAL')
        }
      }
    }
    records.push({ offset, flags, target, count, argument, raw: Uint8Array.from(stream.subarray(offset, end)) })
    offset = end
  }
  if (!final) throw new ModError('SHARC boot stream has no FINAL record')
  for (const [index, [at, argument]] of firsts.entries()) {
    const expected = index + 1 < firsts.length ? firsts[index + 1][0] : stream.length
    if (at + 16 + argument !== expected)
      throw new ModError(`SHARC FIRST at +0x${at.toString(16)}: wrong next-application distance`)
  }
  return records
}

function header(flags: number, target: number, count: number, argument: number): Uint8Array {
  const raw = new Uint8Array(16), view = new DataView(raw.buffer)
  for (const [i, n] of [(0xad000000 | flags) >>> 0, target, count, argument].entries()) view.setUint32(4 * i, n, true)
  raw[2] = raw.reduce((a, b) => a ^ b, 0)
  return raw
}

function join(chunks: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(chunks.reduce((n, chunk) => n + chunk.length, 0))
  let offset = 0
  for (const chunk of chunks) { out.set(chunk, offset); offset += chunk.length }
  return out
}

/** One insertion before FINAL. Only the profile's qualified loader-byte ranges are eligible. */
export function insert(stream: Uint8Array, profile: SharcProfile,
  loads: [number, Uint8Array][] = [], fills: [number, number, number][] = []): Uint8Array {
  const records = parse(stream, profile)
  if (sha(stream) !== profile.decodedSha256) throw new ModError('SHARC stock DSP hash does not match the profile')
  const additions: [number, number, number, number, Uint8Array][] = [], spans: [number, number][] = []
  for (const [target, data] of loads) {
    if (!(data instanceof Uint8Array)) throw new ModError('SHARC load payload must be bytes')
    spans.push([target, data.length])
    additions.push([LOAD, target, data.length, 0, data])
  }
  for (const [target, count, word] of fills) {
    if (!uint32(word)) throw new ModError('SHARC fill word must be uint32')
    spans.push([target, count])
    additions.push([FILL, target, count, word, new Uint8Array()])
  }
  if (!additions.length) return Uint8Array.from(stream)
  const occupied = records.filter(r => r.flags === LOAD || r.flags === FILL).map(r => byteSpan(profile, r.target, r.count, 'loader-byte', false))
  for (const [target, count] of spans) {
    const [lo, hi] = byteSpan(profile, target, count)
    if (target % 4 || count % 4) throw new ModError('SHARC new load or fill must be four-byte aligned')
    if (!profile.ownedRanges.some(([start, end]) => start <= lo && hi <= end))
      throw new ModError('SHARC new load or fill is outside the profile-owned ranges')
    if (occupied.some(([start, end]) => lo < end && start < hi))
      throw new ModError('SHARC new load or fill overlaps an existing load or fill')
    occupied.push([lo, hi])
  }
  const extra = additions.reduce((n, [, , , , data]) => n + 16 + data.length, 0)
  if (stream.length + extra > profile.decodedMax) throw new ModError('SHARC decoded stream exceeds the profile limit')
  const first = records.findLast(r => r.flags === FIRST)!
  if (first.argument + extra > 0xffffffff) throw new ModError('SHARC FIRST distance overflows uint32')
  const inserted = additions.flatMap(([flags, target, count, word, data]) => [header(flags, target, count, word), data])
  const result = join([stream.subarray(0, first.offset), header(FIRST, first.target, 0, first.argument + extra),
    stream.subarray(first.offset + 16, records.at(-1)!.offset), ...inserted, records.at(-1)!.raw])
  parse(result, profile)
  return result
}
