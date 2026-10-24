# SPDX-License-Identifier: GPL-2.0-or-later
"""Compare one real ModelDigi oscillator bank on native C and SHARC."""
import argparse
from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / 'sharc-sine-probe'))
from qualify import FLAGS, PIN, command, require, section_rows  # noqa: E402

MODEL_PIN = 'c412bdf2ab3b0b5b62484e8195c2f880d1964c67'
DIGIKIT_PIN = 'ded547e14e63977c1a6e808812d46243e13c43d0'
SOURCE_HASHES = {
    'oscillator.c': '790738eaecadaf476d34325af946482c05d2093d098cdff38526fcaef6f58cdf',
    'oscillator.h': '7096ff421c09ee34f9ab31e73da761c36f6397161c4b6eb1fb556ed67a572304',
    'edge_kernel.h': '4f6a0652ad7186d92023acd21ef66000be870ba614c548da01cba079d8d257a6',
    'mixer_curve.h': '30215197a412b2063d7f205cbab59fb6ed0764de11e492a0a0d208c86f3a4c89',
}
ALIAS = 0x28000000
STACK = 0x2c7ff0
CASES = [('scenario', '', 32), ('scenario_split', 'split', 32),
         ('scenario_bounds', 'bounds', 32), ('scenario_toggle', 'toggle', 48)]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(source, old, new):
    require(source.count(old) == 1, f'ModelDigi adaptation anchor changed: {old[:40]}')
    return source.replace(old, new)


def adapt(source):
    source = replace_once(source, '    for (int32_t whole = octaves >> 16;',
                          '    int32_t whole;\n    for (whole = octaves >> 16;')
    source = replace_once(source, '    unsigned s = __builtin_clz(inc);',
                          '    unsigned s = 0;\n    uint32_t mask = 0x80000000u;\n'
                          '    while (!(inc & mask)) { ++s; mask >>= 1; }')
    source = replace_once(
        source,
        '    uint32_t m = exp2_q15[i] + (((uint32_t)(exp2_q15[i + 1] - exp2_q15[i]) * (frac & 1023)) >> 10);',
        '    uint32_t delta = exp2_q15[i + 1] - exp2_q15[i];\n'
        '    uint32_t m = exp2_q15[i] + ((delta * ((uint32_t)octaves & 1023u)) >> 10);')
    return source


def symbols_from(dump):
    return {name: int(address, 16) for address, name in re.findall(
        r"(?m)^[0-9a-f]{4}\s+[0-9a-f]{8}\s+([0-9a-f]{8})\s+.*'([^']+)'$", dump)}


def loaded_read(runner, address, size):
    result = bytearray()
    for address in range(ALIAS + address, ALIAS + address + size):
        byte = runner.state.overlay.get(address)
        if byte is None:
            raw = runner.data.read(address, 1)
            require(raw is not None, f'uninitialized SHARC read at {address:#x}')
            byte = raw[0]
        result.append(byte)
    return bytes(result)


def named_state(raw):
    words = struct.unpack('<29I', raw)

    def signed(value):
        return value - 0x100000000 if value & 0x80000000 else value

    return {'phase': list(words[0:3]), 'last': list(words[3:6]),
            'tail': [signed(value) for value in words[6:17]],
            'frame': words[17], 'seed': words[18],
            'wander': [signed(value) for value in words[19:22]],
            'drift': [signed(value) for value in words[22:25]],
            'mix_in': signed(words[25]), 'mix_residue': signed(words[26]),
            'dc_in': signed(words[27]), 'dc_out': signed(words[28])}


def run_case(modules, memory, symbols, name, host, frames, mutation=False):
    sharc_run, _, state = modules
    regs = {f'R{i}': 0x12340000 + i for i in range(16)}
    regs.update({f'S{i}': 0x56780000 + i for i in range(16)})
    regs.update({f'I{i}': 0x2c4000 + 4 * i for i in range(16)})
    regs.update({f'B{i}': 0x2c5000 + 4 * i for i in range(16)})
    regs.update({f'M{i}': 0x77 + i for i in range(16)})
    regs.update({f'L{i}': 0 for i in range(16)})
    regs.update(R4=0, I6=STACK + 8, I7=STACK, I12=symbols[name],
                M5=0, M7=0xffffffff, M13=0, M14=1, MODE1=0, MODE2=0)
    runner = sharc_run.Runner(
        memory, symbols['probe_call'], regs=regs, assume_nw32=True,
        provisional_forms=(), provisional_interpretations={},
        explicit_memory_model=False, approx_recips=False, continue_external_calls=False)
    runner.state.stack_model = True
    runner.breakpoints = frozenset([symbols['probe_returned']])
    require(loaded_read(runner, symbols['scenario_state'], 116) == bytes(116),
            'state did not cold-start at zero')
    if mutation:
        # lines[3].saw is 15528 in the checked source; zeroing it must change the saw.
        target = 0x2c001c
        require(loaded_read(runner, target, 4) == struct.pack('<i', 15528),
                'mutation target moved')
        for offset in range(4):
            runner.state.overlay[ALIAS + target + offset] = 0
    low = STACK
    try:
        for _ in range(5000000):
            runner.step()
            sp = runner.state.uregs[state.UREG_CODES['I7']]
            require(isinstance(sp, state.Const), 'unknown stack pointer')
            low = min(low, sp.value)
        raise ValueError(f'{name} did not return within five million instructions')
    except sharc_run.Halt as halt:
        require(halt.reason == 'breakpoint' and halt.pc_sw == symbols['probe_returned'],
                f'{name} halted unexpectedly: {halt.to_json()}')
    require(STACK - 4096 <= low <= STACK, f'{name} exceeded the guarded stack')
    require(not runner.state.provisional_used and not runner.state.provisional_interpreted and
            not runner.state.approx_recips_used, f'{name} used provisional semantics')
    output = loaded_read(runner, symbols['scenario_output'], frames * 4)
    actual_state = loaded_read(runner, symbols['scenario_state'], 116)
    actual_params = loaded_read(runner, symbols['scenario_params'], 32)
    require(actual_params == host[frames * 4 + 116:frames * 4 + 148],
            f'{name} parameter layout differs')
    if mutation:
        require(output != host[:frames * 4], 'arithmetic mutation went undetected')
    else:
        require(output == host[:frames * 4], f'{name} sample mismatch')
        require(actual_state == host[frames * 4:frames * 4 + 116],
                f'{name} state mismatch')
    writable = ((STACK - 4096, STACK + 4), (symbols['scenario_params'],
                 symbols['scenario_params'] + 32), (symbols['scenario_state'],
                 symbols['scenario_state'] + 116), (symbols['scenario_output'],
                 symbols['scenario_output'] + frames * 4), (0x2c003c, 0x2c0040))
    for address in runner.state.overlay:
        address -= ALIAS
        if mutation and 0x2c001c <= address < 0x2c0020:
            continue
        require(any(start <= address < end for start, end in writable),
                f'{name} wrote outside state, output, parameters and stack at {address:#x}')
    return {'case': name, 'frames': frames, 'instructions': runner.instructions,
            'stack_bytes': STACK - low, 'output_sha256': sha(output),
            'state_sha256': sha(actual_state), 'state': named_state(actual_state),
            'mutated': mutation}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('modeldigi', type=Path)
    parser.add_argument('selache', type=Path)
    parser.add_argument('digikit', type=Path, help='Digikit fork with the PX runner fix')
    args = parser.parse_args()
    model, selache, digikit = (p.expanduser().resolve() for p in
                              (args.modeldigi, args.selache, args.digikit))
    require(command(['git', 'rev-parse', 'HEAD'], cwd=model, text_output=True).strip() == MODEL_PIN,
            'ModelDigi checkout is not the pinned baseline')
    require(command(['git', 'rev-parse', 'HEAD'], cwd=selache, text_output=True).strip() == PIN,
            'Selache checkout is not the pinned compiler')
    require(command(['git', 'rev-parse', 'HEAD'], cwd=digikit, text_output=True).strip() == DIGIKIT_PIN,
            'Digikit checkout lacks the pinned PX fix')
    for repo in (model, selache, digikit):
        require(not command(['git', 'status', '--porcelain', '--untracked-files=normal'],
                            cwd=repo, text_output=True).strip(), f'{repo} has source changes')
    source_dir = model / 'dsp'
    for name, expected in SOURCE_HASHES.items():
        require(sha((source_dir / name).read_bytes()) == expected, f'ModelDigi {name} changed')
    tools = {name: selache / 'target/release' / name for name in
             ('selcc', 'selas', 'seld', 'seldump', 'selload')}
    require(all(path.is_file() for path in tools.values()), 'build the five pinned Selache tools')
    out = Path(tempfile.mkdtemp(prefix='modeldigi-sharc-'))
    (out / 'oscillator.c').write_text(adapt((source_dir / 'oscillator.c').read_text()))
    native = ['clang', '-std=c11', '-O1', '-fwrapv', '-DHOST', '-I', source_dir]
    command([*native, source_dir / 'oscillator.c', HERE / 'driver.c', '-o', out / 'host'])
    command([*native, out / 'oscillator.c', HERE / 'driver.c', '-o', out / 'host-adapted'])
    command([*native, HERE / 'div.c', '-o', out / 'div-check'])
    command([out / 'div-check'])
    host = {}
    for name, arg, frames in CASES:
        option = [arg] if arg else []
        original = subprocess.check_output([out / 'host', *option])
        adapted = subprocess.check_output([out / 'host-adapted', *option])
        require(original == adapted, f'{name} source adaptation changed native behavior')
        require(len(original) == frames * 4 + 116 + 32, f'{name} host layout changed')
        host[name] = original
    require(host['scenario'] == host['scenario_split'], 'host block split differs')
    require(host['scenario'][:24] == bytes(24) and host['scenario'][24:28] != bytes(4),
            'six-sample latency changed')

    flags = FLAGS + ['-no-std-inc', '-I', selache / 'libsel/include', '-I', source_dir]
    for name, path in (('oscillator', out / 'oscillator.c'), ('driver', HERE / 'driver.c'),
                       ('div', HERE / 'div.c')):
        command([tools['selcc'], *flags, '-c', '-o', out / f'{name}.doj', path])
    command([tools['selas'], '-proc', 'ADSP-21569', '-o', out / 'caller.doj',
             HERE.parent / 'sharc-sine-probe/caller.s'])
    exe = out / 'modeldigi.dxe'
    command([tools['seld'], '-proc', 'ADSP-21569', '-T', HERE / 'synthetic.ldf',
             '-entry', 'probe_call', '-Map', out / 'modeldigi.map', '-o', exe,
             *(out / f'{name}.doj' for name in ('oscillator', 'div', 'driver', 'caller'))])
    raw = exe.read_bytes()
    dump = command([tools['seldump'], '-fh', '-sh', '-n', '.symtab', exe], text_output=True)
    rows = section_rows(dump, raw)
    require({name for name, row in rows.items() if row['flags'] & 2} ==
            {'probe_code', 'probe_data'}, 'unexpected loadable SHARC section')
    require(not any(row['kind'] in ('rel', 'rela') for row in rows.values()),
            'unresolved relocation')
    require(not re.search(r"(?m)^[0-9a-f]{4}\s+UNDEF.*'[^']+'$", dump),
            'named unresolved symbol')
    symbols = symbols_from(dump)
    require(symbols['scenario_state'] == 0x2c0060 and
            symbols['scenario_output'] - symbols['scenario_state'] == 116 and
            symbols['scenario_params'] == 0x2c0040, 'target struct layout changed')
    require(rows['probe_data']['address'] == 0x2c0000 and
            rows['probe_data']['address'] + rows['probe_data']['size'] < STACK - 4096,
            'target data overlaps guarded stack')
    object_rows = section_rows(command([tools['seldump'], '-sh', out / 'oscillator.doj'],
                                       text_output=True), (out / 'oscillator.doj').read_bytes())
    require(object_rows['seg_l2']['bytes'] in rows['probe_data']['bytes'],
            'compiled lookup tables changed in the linker')
    command([tools['selload'], '-proc', 'ADSP-21569', '-o', out / 'modeldigi.ldr', exe])
    stream = (out / 'modeldigi.ldr').read_bytes()
    sys.path.insert(0, str(digikit))
    modules = [importlib.import_module('tools.sharc_dev.' + name) for name in
               ('sharc_run', 'sharc_trace', 'sharcldr', 'sharc_core.state')]
    require(all(Path(module.__file__).resolve().is_relative_to(digikit) for module in modules),
            'unexpected Digikit import')
    sharc_run, trace, loader, state = modules
    listing = command([tools['seldump'], '-ns', 'probe_code', exe], text_output=True)
    instructions = re.findall(r'(?m)^  ([0-9a-f]{8})\s+([0-9a-f]+)\s+(.+)$', listing)
    require(instructions and sum(len(encoded) // 2 for _, encoded, _ in instructions) ==
            rows['probe_code']['size'], 'incomplete instruction listing')
    decoded = Counter()
    memory = loader.LoadedMemory.from_stream(stream)
    for address, encoded, mnemonic in instructions:
        instruction = trace.decode_at(memory, None, int(address, 16))
        require(instruction.kind == 'confident' and instruction.length_bytes == len(encoded) // 2,
                f'unsupported SHARC instruction at {address}: {mnemonic}')
        store = re.fullmatch(r'(dm|pm)\s*\(([^)]+)\)\s*=\s*([imlb])(\d+)', mnemonic.lower())
        if store and re.search(r'\bi\d+\b', store[2]):
            require(int(store[4]) // 8 != (0 if store[1] == 'dm' else 1),
                    f'illegal same-DAG indexed store at {address}')
        decoded[instruction.type_name] += 1
    require(memory.read(ALIAS + 0x2c0000, rows['probe_data']['size']) ==
            rows['probe_data']['bytes'], 'loader data differs from linked constants')
    blocks = list(loader.parse_blocks(stream))
    blocks.append(dict(target_address=ALIAS + STACK - 4096, byte_count=4096,
                       fill=False, payload_offset=len(stream), payload_len=4096))
    memory = loader.LoadedMemory.from_stream(stream + bytes([0xa5]) * 4096, blocks)
    results = [run_case((sharc_run, trace, state), memory, symbols, name, host[name], frames)
               for name, _, frames in CASES]
    run_case((sharc_run, trace, state), memory, symbols, 'scenario', host['scenario'], 32,
             mutation=True)
    from elekloader.devices.digitone_mk2 import DEVICE
    profile = DEVICE.releases['1.12'].sharc
    reservation = profile['app_range'][1] - profile['core_range'][0]
    require(rows['probe_code']['size'] + rows['probe_data']['size'] > reservation,
            'synthetic map unexpectedly fits the current DN2 reservation')
    report = {'modeldigi_commit': MODEL_PIN, 'selache_commit': PIN,
              'digikit_commit': DIGIKIT_PIN, 'modeldigi_source_sha256': SOURCE_HASHES,
              'adapted_source_sha256': sha((out / 'oscillator.c').read_bytes()),
              'executable_sha256': sha(raw), 'loader_sha256': sha(stream),
              'code_bytes': rows['probe_code']['size'], 'data_bytes': rows['probe_data']['size'],
              'current_dn2_reservation_bytes': reservation, 'decoded_instructions': len(instructions),
              'decoded_forms': dict(decoded), 'cases': results, 'mutation_detected': True,
              'limitations': ['synthetic memory map only', 'no Q31-to-float adapter',
                              'no physical DN2 timing, cache or audio-route qualification']}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {len(results)} host-matched scenarios, {len(instructions)} decoded instructions, '
          f'{rows["probe_code"]["size"]} code bytes, {rows["probe_data"]["size"]} data bytes; '
          'mutation detected')
    print(out / 'report.json')


if __name__ == '__main__':
    main()
