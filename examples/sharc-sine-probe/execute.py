# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile and execute the sine with pinned external tools, without firmware."""
import argparse
from collections import Counter
import importlib
import json
import math
from pathlib import Path
import re
import struct
import sys

from qualify import HERE, command, compile_probe, digest, rejected, require, section_rows

DIGIKIT_PIN = '38dfbe4ae88263511eed95691c07fc07e17b6f26'
ALIAS = 0x28000000
OUTPUT = 0x2c0800
TOP = 0x2c1ff0
STACK_BYTES = 64
PHASE = 0x2c0090
INCREMENT = PHASE + 4
STEP_LIMIT = 3000


def expected(phase, increment, count=32):
    """Independent host calculation: decimal table rounding, then binary32 sign."""
    words = []
    for _ in range(count):
        index = phase >> 26
        value = float(f'{0.125 * math.sin((index & 31) * math.pi / 32):.9f}')
        word = struct.unpack('<I', struct.pack('<f', value))[0]
        words.append(word ^ (0x80000000 if index & 32 else 0))
        phase = (phase + increment) & 0xffffffff
    return struct.pack(f'<{count}I', *words), phase


def check_dag_store(mnemonic):
    # PRM rev 1.5 pp.13-13/16 and 15-7/10: indexed stores exclude
    # registers of their own DAG. Absolute Type 14 stores are exempt.
    store = re.fullmatch(r'(dm|pm)\s*\(([^)]+)\)\s*=\s*([imlb])(\d+)', mnemonic.lower())
    if store and re.search(r'\bi\d+\b', store[2]):
        source_dag = int(store[4]) // 8
        require(source_dag != (0 if store[1] == 'dm' else 1),
                f'illegal same-DAG indexed store: {mnemonic}')


def check_subset(disassembly):
    # Deliberately only this probe's operands/forms, not a general ISA checker.
    # PRM chapters 12-16: data-register arithmetic; legal DAG1 DM transfers;
    # delayed jumps/CJUMP with two slots; immediate MODIFY and RFRAME.
    patterns = {
        'integer/float compute': r'(?:r[0-7]=(?:pass r[0-7]|lshift r[0-7] by r[0-7]|r[0-7](?:\+| and )r[0-7])|f3=-f1|comp \(r[135],r[135]\))',
        'immediate data': r'r[01356]=-?0x[0-9a-f]+',
        'absolute DM': r'(?:dm \(0x2c009[04]\)=r[01]|r[13]=dm \(0x2c009[04]\))',
        'indexed DM': r'(?:r1=dm \(i4,m5\)|dm \(i4,m5\)=r1|dm \(i7,m7\)=(?:r2|0x[0-9a-f]+)|i12=dm \(m7,i6\))',
        'frame DM': r'(?:r[135]=dm \(-0x[3456],i6\)|dm \(-0x[3456],i6\)=r[145])',
        'compute and frame DM': r'r1=pass r0 , r3=dm \(-0x3,i6\)',
        'register move': r'(?:i4=r5|r2=i6|i6=i7)',
        'stack modify': r'i7=modify \(i7,-?0x[48]\)\(nw\)',
        'direct branch': r'(?:if (?:eq|ge) )?jump 0x[0-9a-f]+',
        'call/return': r'(?:cjump sine_sample \(db\)|jump \(m1[34],i12\) \(db\)|rframe)',
        'nop': r'nop',
    }
    census = Counter()
    rows = re.findall(r'(?m)^  ([0-9a-f]{8})\s+([0-9a-f]+)\s+(.+)$', disassembly)
    require(rows, 'empty instruction listing')
    addresses = {int(pc, 16) for pc, _, _ in rows}
    for index, (pc, encoded, mnemonic) in enumerate(rows):
        check_dag_store(mnemonic)
        kinds = [kind for kind, pattern in patterns.items() if re.fullmatch(pattern, mnemonic)]
        require(len(kinds) == 1, f'unsupported instruction at {pc}: {mnemonic}')
        require(len(encoded) in (4, 8, 12), f'unsupported instruction width at {pc}')
        census[kinds[0]] += 1
        target = re.search(r'jump (0x[0-9a-f]+)$', mnemonic)
        if target:
            require(int(target[1], 16) in addresses, f'branch outside instruction boundaries at {pc}')
        if mnemonic.endswith('(db)'):
            slots = [row[2] for row in rows[index + 1:index + 3]]
            require(len(slots) == 2 and
                    (slots == ['rframe', 'nop'] or
                     (slots[0] == 'dm (i7,m7)=r2' and slots[1].startswith('dm (i7,m7)=0x'))),
                    f'unqualified delayed slots at {pc}')
    return dict(census)


def load_runner(digikit):
    require(command(['git', 'rev-parse', 'HEAD'], cwd=digikit, text_output=True).strip() == DIGIKIT_PIN,
            f'Digikit must be pinned to {DIGIKIT_PIN}')
    require(not command(['git', 'status', '--porcelain', '--untracked-files=normal'],
                        cwd=digikit, text_output=True).strip(), 'Digikit source checkout is not clean')
    # Invoke the external AGPL runner; no implementation is copied or bundled.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(digikit))
    modules = [importlib.import_module('tools.sharc_dev.' + name)
               for name in ('sharc_run', 'sharc_trace', 'sharcldr', 'sharc_core.state')]
    for module in modules:
        require(Path(module.__file__).resolve().is_relative_to(digikit), 'unexpected runner import path')
    return modules


def read(runner, address, size):
    data = bytearray()
    for byte in range(ALIAS + address, ALIAS + address + size):
        value = runner.state.overlay.get(byte)
        if value is None:
            loaded = runner.data.read(byte, 1)
            require(loaded is not None, f'uninitialized read at {byte:#x}')
            value = loaded[0]
        data.append(value)
    return bytes(data)


def put(runner, address, value):
    for offset, byte in enumerate(struct.pack('<I', value)):
        runner.state.overlay[ALIAS + address + offset] = byte


def make_runner(modules, stream, caller, target, argument, nw32=True):
    run, _, loader, state = modules
    blocks = list(loader.parse_blocks(stream))
    for address, size, value in [(OUTPUT - 64, 256, 0x5a), (TOP - 256, 324, 0xa5)]:
        blocks.append(dict(target_address=ALIAS + address, byte_count=size, fill=False,
                           payload_offset=len(stream), payload_len=size))
        stream += bytes([value]) * size
    memory = loader.LoadedMemory.from_stream(stream, blocks)
    regs = {f'R{i}': 0x12340000 + i for i in range(16)}
    regs.update({f'S{i}': 0x56780000 + i for i in range(16)})
    regs.update({f'I{i}': 0x2c0200 + 4 * i for i in range(16)})
    regs.update({f'B{i}': 0x2c0400 + 4 * i for i in range(16)})
    regs.update({f'M{i}': 0x77 + i for i in range(16)})
    regs.update({f'L{i}': 0 for i in range(16)})
    regs.update(R4=argument, I6=TOP + 8, I7=TOP, I12=target,
                M5=0, M7=0xffffffff, M13=0, M14=1, MODE1=0, MODE2=0,
                ASTATX=0x13579bdf, ASTATY=0x2468ace0, STKYX=0x33333333, STKYY=0x44444444)
    runner = run.Runner(memory, caller, regs=regs, assume_nw32=nw32,
                        provisional_forms=(), provisional_interpretations={},
                        explicit_memory_model=False, approx_recips=False, continue_external_calls=False,
                        watchpoints=[run.Watchpoint(0, 0x100000000, on_read=False,
                                                   on_write=True, stop=False, label='all writes')])
    runner.state.stack_model = True
    runner.state.pc_stack = [0x12345, 0x67890]
    runner.state.uregs[state.UREG_CODES['LADDR']] = state.Const(0xffffffff)
    runner.state.uregs[state.UREG_CODES['CURLCNTR']] = state.Const(0xffffffff)
    runner.state.bank_model = True
    runner.state.bank_alt = {code: state.Const(0x6b000000 + code) for code in runner.state.uregs}
    return runner


def call(modules, runner, symbols, function, argument, stack_bytes=STACK_BYTES, limit=STEP_LIMIT):
    run, _, _, state = modules
    runner.state.pc_sw = symbols['probe_call']
    runner.state.uregs[state.UREG_CODES['I12']] = state.Const(symbols[function])
    runner.state.uregs[state.UREG_CODES['R4']] = state.Const(argument)
    runner.breakpoints = frozenset([symbols['probe_returned']])
    initial = dict(runner.state.uregs)
    alternate = dict(runner.state.bank_alt)
    hardware_stack = list(runner.state.pc_stack)
    low = TOP
    changed = set()
    entries = Counter()
    forms = Counter()
    writes_start = len(runner.watch_log)
    instructions_start = runner.instructions
    for _ in range(limit):
        pc = runner.state.pc_sw
        for name in ('sine_init.', 'sine_sample.', 'sine_render.'):
            if pc == symbols[name]:
                entries[name] += 1
        previous = dict(runner.state.uregs)
        try:
            runner.step()
        except run.Halt as halt:
            require(halt.reason == 'breakpoint' and halt.pc_sw == symbols['probe_returned'],
                    f'unexpected halt: {halt.to_json()}')
            break
        forms[runner._decode(pc).type_name] += 1
        changed.update(code for code, value in runner.state.uregs.items() if previous.get(code) != value)
        sp = runner.state.uregs[state.UREG_CODES['I7']]
        require(isinstance(sp, state.Const), 'unknown stack pointer')
        low = min(low, sp.value)
        require(TOP - stack_bytes <= sp.value <= TOP, f'stack bound exceeded: {sp.value:#x}')
    else:
        raise ValueError(f'non-return within {limit} steps')
    require(entries[function] == 1, f'function was omitted: {function}')
    require(entries['sine_sample.'] == (32 if function == 'sine_render.' else int(function == 'sine_sample.')),
            'sample function omitted/stubbed')
    names = {code: name for name, code in state.UREG_CODES.items()}
    clobbered = sorted(names.get(code, str(code)) for code, value in initial.items()
                       if runner.state.uregs.get(code) != value)
    allowed = {f'R{i}' for i in range(8)} | {'I4', 'I12', 'ASTATX', 'STKYX'}
    require(set(clobbered) <= allowed, f'preserved register clobber: {clobbered}')
    require(runner.state.bank_alt == alternate and runner.state.pc_stack == hardware_stack and
            not runner.state.loops and not runner.state.status_stack and not runner.state.call_stack,
            'bank/stack context clobber')
    require(not runner.state.provisional_used and not runner.state.provisional_interpreted and
            not runner.state.approx_recips_used, 'unqualified interpretation used')
    allowed_writes = [(TOP - stack_bytes, TOP + 4)]
    if function == 'sine_init.':
        allowed_writes.append((PHASE, INCREMENT + 4))
    elif function == 'sine_render.':
        allowed_writes.extend([(OUTPUT, OUTPUT + 128), (PHASE, PHASE + 4)])
    writes = runner.watch_log[writes_start:]
    for event in writes:
        require(any(ALIAS + start <= event.address and event.address + event.width <= ALIAS + end
                    for start, end in allowed_writes), f'unexpected memory write: {event}')
    require(read(runner, OUTPUT - 64, 64) == bytes([0x5a]) * 64 and
            read(runner, OUTPUT + 128, 64) == bytes([0x5a]) * 64, 'output guard changed')
    require(read(runner, TOP - 256, 256 - stack_bytes) == bytes([0xa5]) * (256 - stack_bytes) and
            read(runner, TOP + 4, 64) == bytes([0xa5]) * 64, 'stack guard changed')
    output_writes = [event for event in writes if ALIAS + OUTPUT <= event.address < ALIAS + OUTPUT + 128]
    require(len(output_writes) == (32 if function == 'sine_render.' else 0), 'incorrect output store count')
    return dict(function=function, instructions=runner.instructions - instructions_start,
                halt='breakpoint', halt_pc=symbols['probe_returned'], instruction_forms=dict(forms),
                stack_pointer_drop=TOP - low, clobbered=clobbered,
                touched=sorted(names.get(code, str(code)) for code in changed),
                entries=dict(entries), output_stores=len(output_writes))


def execute(selache, digikit):
    modules = load_runner(digikit)
    out, compile_report = compile_probe(selache)
    commands = []
    tools = selache / 'target/release'

    def run(args, text_output=False):
        commands.append([str(arg) for arg in args])
        return command(args, text_output=text_output)

    run([tools / 'selas', '-proc', 'ADSP-21569', '-o', out / 'caller.doj', HERE / 'caller.s'])
    run([tools / 'seld', '-proc', 'ADSP-21569', '-T', HERE / 'synthetic.ldf',
         '-entry', 'probe_call', '-Map', out / 'execution.map', '-o', out / 'execution.dxe',
         out / 'sine.doj', out / 'caller.doj'])
    raw = (out / 'execution.dxe').read_bytes()
    dump = run([tools / 'seldump', '-fh', '-sh', '-n', '.symtab', out / 'execution.dxe'], True)
    listing = run([tools / 'seldump', '-ns', 'probe_code', out / 'execution.dxe'], True)
    (out / 'execution.txt').write_text(dump)
    (out / 'execution-disassembly.txt').write_text(listing)
    rows = section_rows(dump, raw)
    original = section_rows((out / 'executable.txt').read_text(), (out / 'sine.dxe').read_bytes())
    code = rows['probe_code']['bytes']
    require(code[:320] == original['probe_code']['bytes'] and
            rows['probe_data']['bytes'] == original['probe_data']['bytes'], 'caller changed compiled sine')
    symbols = dict(compile_report['facts']['entrypoints_pc_parcels'])
    for name in ('probe_call', 'probe_returned'):
        match = re.search(rf"(?m)^[0-9a-f]{{4}}\s+[0-9a-f]{{8}}\s+([0-9a-f]{{8}})\s+.*'_{name}'$", dump)
        require(match is not None, f'missing caller symbol {name}')
        symbols[name] = int(match[1], 16)
    legality = check_subset(listing)
    run([tools / 'selload', '-proc', 'ADSP-21569', '-o', out / 'execution.ldr', out / 'execution.dxe'])
    stream = (out / 'execution.ldr').read_bytes()
    loaded = modules[2].LoadedMemory.from_stream(stream)
    require(loaded.read(ALIAS + 0x300000, len(code)) ==
            b''.join(code[i:i + 2][::-1] for i in range(0, len(code), 2)), 'loader instruction byte order')
    require(loaded.read(ALIAS + 0x2c0000, 152) == original['probe_data']['bytes'], 'loader data byte order')
    decoded = Counter()
    offset = 0
    for encoded in re.findall(r'(?m)^  [0-9a-f]{8}\s+([0-9a-f]+)\s+', listing):
        instruction = modules[1].decode_at(loaded, None, 0x180000 + offset // 2)
        require(instruction.kind == 'confident' and instruction.length_bytes == len(encoded) // 2,
                f'unsupported decode: {instruction}')
        decoded[instruction.type_name] += 1
        offset += instruction.length_bytes
    require(offset == len(code), 'incomplete decoder coverage')

    def fresh(nw32=True):
        return make_runner(modules, stream, symbols['probe_call'], symbols['sine_init.'], 0, nw32)

    results = []
    samples = []
    for label, increment, blocks in [('all phases', 1 << 26, 3), ('440 Hz', 39370534, 8),
                                      ('zero increment', 0, 2), ('uint32 wrap', 0xffffffff, 3),
                                      ('bit 31', 0x80000000, 2)]:
        runner = fresh()
        require(read(runner, PHASE, 8) == bytes(8), 'initial state/BSS not zero')
        # Dirty both state words so reset cannot pass by retaining loader zeroes.
        put(runner, PHASE, 0xfedcba98)
        put(runner, INCREMENT, 17)
        init = call(modules, runner, symbols, 'sine_init.', increment)
        require(read(runner, PHASE, 8) == struct.pack('<II', 0, increment), 'init failed to reset state')
        phase = 0
        rendered = []
        for _ in range(blocks):
            observation = call(modules, runner, symbols, 'sine_render.', OUTPUT)
            want, phase = expected(phase, increment)
            actual = read(runner, OUTPUT, 128)
            require(actual == want, f'{label}: sample mismatch')
            require(read(runner, PHASE, 8) == struct.pack('<II', phase, increment), f'{label}: state mismatch')
            rendered.append(observation)
            if label == '440 Hz':
                samples.extend(struct.unpack('<32f', actual))
        reset = call(modules, runner, symbols, 'sine_init.', increment)
        call(modules, runner, symbols, 'sine_render.', OUTPUT)
        require(read(runner, OUTPUT, 128) == expected(0, increment)[0], f'{label}: repeated init failed')
        results.append(dict(case=label, increment=increment, init=init, blocks=rendered, reset=reset))

    negative = []
    illegal = out / 'illegal-store.s'
    illegal.write_text('.SECTION/SW seg_swco;\nDM(I7,M7)=I6;\n.ENDSEG;\n')
    run([tools / 'selas', '-proc', 'ADSP-21569', '-o', out / 'illegal-store.doj', illegal])
    illegal_listing = run([tools / 'seldump', '-ns', 'seg_swco', out / 'illegal-store.doj'], True)
    (out / 'illegal-store.txt').write_text(illegal_listing)
    negative.append(rejected('illegal same-DAG indexed store',
                             lambda: check_subset(illegal_listing), 'same-DAG'))
    negative.append(rejected('unsupported instruction',
                             lambda: check_subset('  00180000   0001   idle'), 'unsupported instruction'))
    negative.append(rejected('non-return bound',
                             lambda: call(modules, fresh(), symbols, 'sine_render.', OUTPUT, limit=10),
                             'non-return'))
    negative.append(rejected('insufficient stack',
                             lambda: call(modules, fresh(), symbols, 'sine_render.', OUTPUT, stack_bytes=60),
                             'stack bound'))
    negative.append(rejected('unknown normal-word width',
                             lambda: call(modules, fresh(False), symbols, 'sine_render.', OUTPUT),
                             'unexpected halt'))
    negative.append(rejected('shifted output pointer',
                             lambda: call(modules, fresh(), symbols, 'sine_render.', OUTPUT + 4),
                             'unexpected memory write'))
    mutated = fresh()
    put(mutated, 0x2c0000, 0x3e000000)
    call(modules, mutated, symbols, 'sine_init.', 0)
    call(modules, mutated, symbols, 'sine_render.', OUTPUT)
    negative.append(rejected('mutated table',
                             lambda: require(read(mutated, OUTPUT, 128) == expected(0, 0)[0],
                                             'sample mismatch'), 'sample mismatch'))
    # Exercise the float-return ABI directly, including deliberate negative zero.
    direct = []
    for phase in (0, 0x40000000, 0x7fffffff, 0x80000000, 0xc0000000, 0xffffffff):
        runner = fresh()
        observation = call(modules, runner, symbols, 'sine_sample.', phase)
        actual = runner.state.uregs[modules[3].UREG_CODES['R0']]
        want = struct.unpack('<I', expected(phase, 0, 1)[0])[0]
        require(actual == modules[3].Const(want), f'float return bits differ at {phase:#x}')
        direct.append(dict(phase=phase, result_bits=f'{want:08x}', execution=observation))

    (out / 'samples.json').write_text(json.dumps(samples) + '\n')
    external = {str(Path(module.__file__).resolve().relative_to(digikit)): digest(Path(module.__file__).read_bytes())
                for name, module in sys.modules.items()
                if name.startswith('tools.') and getattr(module, '__file__', None)}
    report = dict(status='synthetic sine execution passed; not device qualification', digikit_commit=DIGIKIT_PIN,
                  compile_report='report.json', execution_commands=commands, external_sources=external,
                  sources={name: digest((HERE / name).read_bytes()) for name in ('execute.py', 'caller.s')},
                  artifacts={name: digest((out / name).read_bytes()) for name in
                             ('execution.dxe', 'execution.ldr', 'execution.map', 'samples.json')},
                  selload_sha256=digest((tools / 'selload').read_bytes()), symbols=symbols,
                  manual_subset=legality, decoded_forms=dict(decoded), cases=results,
                  direct_float_returns=direct, negative_cases=negative, step_limit=STEP_LIMIT,
                  runner_options=dict(assume_nw32=True, explicit_memory_model=False, approx_recips=False,
                                      continue_external_calls=False, provisional_forms=[],
                                      provisional_interpretations={}, stack_model=True, bank_model=True),
                  addressing='PC in 16-bit parcels; data pointers in bytes; NW modifier steps are four bytes',
                  stack_bound_bytes=STACK_BYTES, mode1=0, bss_bytes=0,
                  limitations=['No stock wrapper or device ABI', 'No cache, DMA, interrupts or Boot ROM',
                               'Binary32 values only; no 40-bit floating-point context preservation claim',
                               'No device timing or instruction-count-to-cycle conversion'])
    (out / 'execution-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {sum(len(case["blocks"]) for case in results)} blocks, {len(direct)} float returns, '
          f'{len(negative)} execution negatives.\n{out / "execution-report.json"}')
    return out, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selache', type=Path)
    parser.add_argument('digikit', type=Path)
    args = parser.parse_args()
    execute(args.selache.resolve(), args.digikit.resolve())


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, ImportError) as error:
        sys.exit(f'FAIL: {error}')
