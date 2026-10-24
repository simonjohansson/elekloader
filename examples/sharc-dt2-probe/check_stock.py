# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only DT2 1.17 evidence checks; no compiler, emulator or device required."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from elekloader import formats, sharc
from elekloader.devices.digitakt_mk2 import DEVICE
from elekloader.elemod import ModError

# Research address translation only: these are capacities, not allocations.
MAP = dict(decoded_max=0xfffff,
           l1_aliases=((0x240000, 0x270000, 0x28240000),
                       (0x2c0000, 0x2f0000, 0x282c0000),
                       (0x300000, 0x320000, 0x28300000),
                       (0x380000, 0x3a0000, 0x28380000)),
           l2_bytes=(0x20000000, 0x20100000),
           l2_pc16=(0xb80000, 0xc00000, 0x20000000),
           ddr_bytes=(0x80000000, 0xa0000000), protected=())

# PC16, inspected length, digest; no firmware instruction bytes are distributed.
LANDMARKS = {
    'master_hook': (0x1c80f2, 6, '021776b5e8fbbd669e6e2bb3541d64f0f7d4d1c85bce24681685c9e9b94b338e'),
    'hook_call_and_delay_slots': (0x1c311f, 14, '10b9402f9e79a89d5dad0ab1a430c467c06cb13af54326d20059d2cd49dcc6a6'),
    'master_buffer_and_block_count': (0x1c74b0, 16, '18bb115e4d399a205e42eefd1a99770690c6c816fc6c70d937d72cbb88c125d6'),
    'control_frame_copy': (0x1c2c71, 40, '49571e89fa6d2f6d9daf8fede6444b2e336f0dd9b658d99d7608c95142986d8b'),
    'usb_pack_call': (0x1c3160, 6, '1919df52e05cba43affada5a80ff247420cca9e92afaecabbab0e142e50e4734'),
    'dac_pack_call': (0x1c7734, 6, '2159b22ced3ca5cc9e2baf379f927383b4b508e18965da2cf8df7dd41b1b96d1'),
    'voice_render_entry': (0x1c4ecf, 6, 'ac4e4f137708405f60e984913940df7406874cbc718af72ff239e60f0861abf1'),
}


def check(stock):
    raw = Path(stock).read_bytes()
    p, device, release = formats.load(raw)
    assert device is DEVICE and release is DEVICE.releases['1.17'], 'requires exact DT2 1.17'
    image = formats.main_image(p, device)
    stored, decoded = p.stored[7], p.section(7)
    assert (len(stored), sha256(stored).hexdigest()) == (184856, '39113a8ae7f7ac7336bda4a56eeb45108f0618ea451bcf9f466803017184375d')
    assert (len(decoded), sha256(decoded).hexdigest()) == (321016, '0f514a12a2255f5c081e292c47f1f29462003177658da4bbae0a22fd737fffa2')
    records = sharc.parse(decoded, MAP)
    assert Counter(r.flags for r in records) == {sharc.FIRST: 2, sharc.INIT: 1, sharc.FINAL: 1, sharc.FILL: 42, sharc.LOAD: 58}
    assert [(r.offset, r.flags, r.target, r.argument) for r in records if r.flags not in (sharc.LOAD, sharc.FILL)] == [
        (0, sharc.FIRST, 0x120230, 0x2964), (0x2964, sharc.INIT, 0x120230, 0),
        (0x2974, sharc.FIRST, 0x1c1338, 0x4bc74), (0x4e5e8, sharc.FINAL, 0x1c1338, 0)]
    assert b''.join(r.raw for r in records) == decoded
    assert max(r.target + r.count for r in records if 0x20000000 <= r.target < 0x20100000) == 0x2001ab7c
    for name, (pc, size, digest) in LANDMARKS.items():
        start, end = sharc.byte_span(MAP, pc, size, 'pc16')
        owners = [r for r in records if r.flags in (sharc.LOAD, sharc.FILL) and r.target < end and start < r.target + r.count]
        assert len(owners) == 1 and owners[0].flags == sharc.LOAD, name
        record = owners[0]
        assert record.target <= start and end <= record.target + record.count, name
        offset = 16 + start - record.target
        assert sha256(record.raw[offset:offset + size]).hexdigest() == digest, name
    sender = image[0x400cd0d8 - device.main_load:0x400cd0d8 - device.main_load + 828]
    assert sha256(sender).hexdigest() == '9ccb1f4780bcca7abbe0f34777d1823f0a1351871c7bf0cf5912192ce92ac923'
    rebuilt = formats.write(p, p.stored[device.main_section], device)
    assert rebuilt['syx'] == raw
    formats.verify(rebuilt, p, image, device)
    # Corrupt the pinned FIRST header and require refusal, without writing it.
    corrupt = bytearray(decoded)
    corrupt[2] ^= 1
    try:
        sharc.parse(corrupt, MAP)
    except ModError as error:
        assert 'checksum' in str(error)
    else:
        raise AssertionError('corrupt boot header accepted')
    return dict(status='exact-stock-static-pass', stock_sha256=sha256(raw).hexdigest(),
                main_sha256=sha256(image).hexdigest(), stored_sha256=sha256(stored).hexdigest(),
                decoded_sha256=sha256(decoded).hexdigest(), records=len(records),
                stored_bytes=len(stored), decoded_bytes=len(decoded), container_bytes=len(p.container),
                landmarks=list(LANDMARKS), noop_byte_exact=True, firmware_written=False,
                ownership_granted=False, device_qualified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock', type=Path, help='user-supplied Digitakt_II_OS1.17.syx')
    print(json.dumps(check(parser.parse_args().stock), indent=2))
