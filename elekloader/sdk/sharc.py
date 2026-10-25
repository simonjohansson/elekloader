# SPDX-License-Identifier: GPL-2.0-or-later
"""Package a prelinked DN2 voice kernel; compilation belongs to the mod."""
import json
from pathlib import Path

from ..devices.digitone_mk2 import DEVICE
from ..sharc import module_payload


def voice_artifact(code, data, render_offset_bytes, machine_id, stack_bytes):
    """Kernel PC16 0xbc8400, data 0x20094000; offsets exclude the 2 KiB adapter.

    The kernel gets 14 KiB code (including its read-ahead guard) and 15 KiB
    data. Return the normal SDK's JSON artifact, with a pinned adapter.
    """
    profile = DEVICE.releases['1.12'].sharc
    if not isinstance(code, bytes) or not code or len(code) % 2 or len(code) > 14336 - 64:
        raise ValueError('DN2 voice code must fit 14 KiB with its 64-byte guard')
    if not isinstance(data, bytes) or not data or len(data) % 4 or len(data) > 15360:
        raise ValueError('DN2 voice data must fit 15 KiB and be four-byte aligned')
    adapter = json.loads((Path(__file__).parent / 'include/digitone-mk2/voice-bridge.json').read_text())
    code += b'\x01\x00' * ((14336 - len(code)) // 2)
    end = 16384 + len(data)
    doc = {'abi': profile['voice_abi'], 'machine_id': machine_id,
           'segments': [adapter, {'offset_bytes': 2048, 'kind': 'code', 'hex': code.hex()},
                        {'offset_bytes': 16384, 'kind': 'data', 'hex': data.hex()}],
           'zero': ([{'offset_bytes': end, 'size_bytes': 31744 - end}] if end < 31744 else [])
                   + [{'offset_bytes': 31744, 'size_bytes': 1024}],
           'entries': {'render_offset_bytes': 2048 + render_offset_bytes},
           'stack_bytes': stack_bytes}
    module_payload(doc, profile)
    return doc
