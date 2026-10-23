# SPDX-License-Identifier: GPL-2.0-or-later
"""The DN2's observed ADI boot-record subset, separate from the Octatrack DSP.

Original implementation from the documented 16-byte header contract and small
synthetic vectors. No external parser code is included. See docs/SHARC-BOOT.md.
"""
from dataclasses import dataclass
import functools
import operator
import struct

from .elemod import ModError, sha

LOAD, FILL, FIRST, INIT, FINAL = 0x0001, 0x0101, 0x5001, 0x0801, 0x8001
KINDS = (LOAD, FILL, FIRST, INIT, FINAL)


def _uint32(value):
    return type(value) is int and 0 <= value <= 0xffffffff


def byte_span(profile, address, size, unit='loader-byte', *, check_protected=True):
    """Canonical loader-byte interval; `size` is bytes in every address view.

    Allocation excludes protected ranges; an existing record may only be mapped.
    """
    if not _uint32(address) or not _uint32(size) or not size:
        raise ModError('SHARC address and nonempty byte count must be uint32')
    if unit == 'loader-byte':
        intervals = [(base, base + hi - lo, base) for lo, hi, base in profile['l1_aliases']]
        intervals += [(lo, hi, lo) for lo, hi in (profile['l2_bytes'], profile['ddr_bytes'])]
    elif unit == 'core-byte':
        intervals = list(profile['l1_aliases'])
        intervals += [(lo, hi, lo) for lo, hi in (profile['l2_bytes'], profile['ddr_bytes'])]
    elif unit == 'pc16':
        intervals = [(lo // 2, hi // 2, base) for lo, hi, base in profile['l1_aliases']]
        intervals += [profile['l2_pc16']]
    else:
        raise ModError('unsupported SHARC address unit: %s' % unit)
    scale = 2 if unit == 'pc16' else 1
    for lo, hi, base in intervals:
        start = base + (address - lo) * scale
        end = start + size
        if lo <= address < hi and end <= base + (hi - lo) * scale and end <= 0x100000000:
            if check_protected and any(start < stop and begin < end
                                       for begin, stop, _reason in profile['protected']):
                raise ModError('SHARC byte span overlaps a protected region')
            return start, end
    raise ModError('SHARC byte span is outside the supported address map')


@dataclass(frozen=True)
class Record:
    offset: int
    flags: int
    target: int
    count: int
    argument: int
    raw: bytes


def parse(stream, profile):
    """Read an ordered stream without normalizing headers, loads or overlaps."""
    if len(stream) > profile['decoded_max']:
        raise ModError('SHARC decoded stream exceeds the profile limit')
    records, firsts = [], []
    offset, active = 0, None
    final = False
    while offset < len(stream):
        def fail(message):
            raise ModError('SHARC boot record at +0x%x: %s' % (offset, message))
        if len(stream) - offset < 16:
            fail('truncated header')
        header = stream[offset:offset + 16]
        code, target, count, argument = struct.unpack('<4I', header)
        if code >> 24 != 0xad:
            fail('invalid header signature')
        if functools.reduce(operator.xor, header):
            fail('invalid header checksum')
        flags = code & 0xffff
        if flags not in KINDS:
            fail('unsupported flags 0x%04x' % flags)
        end = offset + 16 + (count if flags == LOAD else 0)
        if end > len(stream):
            fail('truncated payload')
        if flags in (LOAD, FILL):
            if active is None:
                fail('load or fill outside an application')
            if not count or target % 4 or count % 4:
                fail('load or fill address/count must be nonempty and four-byte aligned')
            if flags == LOAD and argument:
                fail('load argument must be zero')
            try:
                byte_span(profile, target, count, check_protected=False)
            except ModError as error:
                fail(str(error))
        else:
            if count:
                fail('entry record requires zero count')
            try:
                byte_span(profile, target, 2, 'pc16', check_protected=False)
            except ModError as error:
                fail(str(error))
            if flags == FIRST:
                if active is not None:
                    fail('FIRST before the preceding application ends')
                active = target
                firsts.append((offset, argument))
            else:
                if active is None or target != active or argument:
                    fail('entry does not match its FIRST application')
                active = None
                if flags == FINAL:
                    final = True
                    if end != len(stream):
                        fail('bytes after FINAL')
        records.append(Record(offset, flags, target, count, argument, bytes(stream[offset:end])))
        offset = end
    if not final:
        raise ModError('SHARC boot stream has no FINAL record')
    for index, (offset, argument) in enumerate(firsts):
        expected = firsts[index + 1][0] if index + 1 < len(firsts) else len(stream)
        if offset + 16 + argument != expected:
            raise ModError('SHARC FIRST at +0x%x: wrong next-application distance' % offset)
    return records


def _header(flags, target, count, argument):
    raw = bytearray(struct.pack('<4I', 0xad000000 | flags, target, count, argument))
    raw[2] = functools.reduce(operator.xor, raw)
    return bytes(raw)


def insert(stream, profile, *, loads=(), fills=()):
    """Insert once before FINAL; load tuples are (address, bytes), fills (address, count, word).

    Only profile-owned loader-byte ranges are eligible. The real DN2 profile has
    none until its runtime ownership gate passes; synthetic profiles test this code.
    """
    records = parse(stream, profile)
    if sha(stream) != profile['decoded_sha256']:
        raise ModError('SHARC stock DSP hash does not match the profile')
    additions, spans = [], []
    for target, data in loads:
        if not isinstance(data, bytes):
            raise ModError('SHARC load payload must be bytes')
        spans.append((target, len(data)))
        additions.append((LOAD, target, len(data), 0, data))
    for target, count, word in fills:
        if not _uint32(word):
            raise ModError('SHARC fill word must be uint32')
        spans.append((target, count))
        additions.append((FILL, target, count, word, b''))
    if not additions:
        return bytes(stream)
    occupied = [byte_span(profile, r.target, r.count, check_protected=False)
                for r in records if r.flags in (LOAD, FILL)]
    for target, count in spans:
        lo, hi = byte_span(profile, target, count)
        if target % 4 or count % 4:
            raise ModError('SHARC new load or fill must be four-byte aligned')
        if not any(start <= lo and hi <= end for start, end in profile['owned_ranges']):
            raise ModError('SHARC new load or fill is outside the profile-owned ranges')
        if any(lo < end and start < hi for start, end in occupied):
            raise ModError('SHARC new load or fill overlaps an existing load or fill')
        occupied.append((lo, hi))
    extra = sum(16 + len(data) for _flags, _target, _count, _word, data in additions)
    if len(stream) + extra > profile['decoded_max']:
        raise ModError('SHARC decoded stream exceeds the profile limit')
    first = next(r for r in reversed(records) if r.flags == FIRST)
    if first.argument + extra > 0xffffffff:
        raise ModError('SHARC FIRST distance overflows uint32')
    inserted = b''.join(_header(flags, target, count, word) + data
                        for flags, target, count, word, data in additions)
    result = b''.join((stream[:first.offset], _header(FIRST, first.target, 0, first.argument + extra),
                       stream[first.offset + 16:records[-1].offset], inserted, records[-1].raw))
    parse(result, profile)
    return result
