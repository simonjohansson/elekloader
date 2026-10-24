# SPDX-License-Identifier: GPL-2.0-or-later
"""Reproduce the optional pinned core; normal mod builds use its saved artifact."""
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / 'examples/sharc-sine-probe'))
from qualify import PIN, command, digest, require, section_rows
sys.path.insert(0, str(ROOT))
from elekloader.devices.digitone_mk2 import DEVICE
from elekloader import sharc


def build(selache, output=None):
    selache = Path(selache).resolve()
    require(command(['git', 'rev-parse', 'HEAD'], cwd=selache, text_output=True).strip() == PIN,
            'Selache checkout is not at the pinned commit')
    require(not command(['git', 'status', '--porcelain', '--untracked-files=normal'],
                        cwd=selache, text_output=True).strip(), 'Selache checkout is not clean')
    tools = {n: selache / 'target/release' / n for n in ('selas', 'seld', 'seldump')}
    require(all(p.is_file() for p in tools.values()), 'build the pinned Selache tools')
    profile = DEVICE.releases['1.12'].sharc
    core = json.loads((HERE.parent / 'core-dn2/bridge.sharc.json').read_text())
    sharc.module_payload(core, profile, core=True)
    expected = profile['active_keyed_core']
    require([(s['offset_bytes'], s['kind'], digest(bytes.fromhex(s['hex'])))
             for s in core['segments']] == list(expected['segments'])
            and [(s['offset_bytes'], s['size_bytes']) for s in core['zero']] == list(expected['zero'])
            and core['entries'] == expected['entries'] and core['stack_bytes'] == expected['stack_bytes'],
            'standard keyed bridge differs from the pinned core')
    with tempfile.TemporaryDirectory(prefix='dn2-metrics-core-') as tmp:
        out = Path(tmp)
        command([tools['selas'], '-proc', 'ADSP-21569', '-o', out / 'metrics.doj', HERE / 'sharc-metrics.s'])
        command([tools['seld'], '-proc', 'ADSP-21569', '-T', HERE / 'metrics.ldf',
                 '-entry', 'metrics_render.', '-o', out / 'metrics.dxe', out / 'metrics.doj'])
        raw = (out / 'metrics.dxe').read_bytes()
        dump = command([tools['seldump'], '-fh', '-sh', '-n', '.symtab', out / 'metrics.dxe'], text_output=True)
        rows = section_rows(dump, raw)
        require({n for n, row in rows.items() if row['flags'] & 2} == {'metrics_code', 'metrics_data'},
                'unexpected loadable section')
        require(not any(row['kind'] in ('rel', 'rela') for row in rows.values())
                and not re.search(r"(?m)^[0-9a-f]{4}\s+UNDEF.*'[^']+'$", dump), 'unresolved relocation/symbol')
        code = rows['metrics_code']['bytes']
        require(len(code) <= 704 and rows['metrics_code']['address'] == 0x16ed00,
                'measurement code exceeds its guarded placement')
        require(rows['metrics_data']['address'] == 0x2ddd00 and rows['metrics_data']['size'] <= 152
                and not any(rows['metrics_data']['bytes']), 'measurement state must cold-start at zero')
        for name, address in (('metrics_render.', 0x16ed00), ('metrics_tail.', 0x16ed4a)):
            require(re.search(r"(?m)^[0-9a-f]{4}\s+[0-9a-f]{8}\s+%08x\s+.*'%s'$"
                              % (address, re.escape(name)), dump), 'measurement entry moved')
        code = b''.join(code[i:i+2][::-1] for i in range(0, len(code), 2))
        code += bytes.fromhex('0100') * ((768 - len(code)) // 2)
    core['abi'] = profile['metrics_abi']
    core['segments'] += [{'offset_bytes': 1024, 'kind': 'code', 'hex': code.hex()},
                         {'offset_bytes': 1792, 'kind': 'data', 'hex': bytes(152).hex()}]
    core['stack_bytes'] = 124
    payload = sharc.module_payload(core, profile, core=True)
    expected = profile['active_metrics_core']
    require([(off, kind, digest(data)) for off, kind, data in payload['segments']] == list(expected['segments'])
            and payload['zero'] == list(expected['zero']) and payload['entries'] == expected['entries']
            and payload['stack_bytes'] == expected['stack_bytes'], 'measurement core differs from the pinned profile')
    destination = Path(output or HERE / 'bridge.sharc.json')
    destination.write_text(json.dumps(core, indent=1) + '\n')
    return destination


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('selache', type=Path)
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    print(build(a.selache, a.out))
