# SPDX-License-Identifier: GPL-2.0-or-later
"""Build and inspect this exact firmware-free probe; target execution is separate."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PIN = '2b26d3b75c53063575bc5c820fa0d38879335187'
TOOLS = ('selcc', 'selas', 'seld', 'seldump')
FLAGS = ['-proc', 'ADSP-21569', '-char-size-8', '-O1']
CODE_SHA256 = 'b1d44a42ede778a634f72e0a1885054163211133188b1c01606c93dbe05d3ab0'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def command(args, cwd=None, text_output=False):
    result = subprocess.run([str(a) for a in args], cwd=cwd, text=True,
                            capture_output=True, check=False)
    require(result.returncode == 0, f'{args[0]} failed:\n{result.stdout}{result.stderr}')
    require(not result.stderr.strip(), f'{args[0]} diagnostics:\n{result.stderr}')
    require(text_output or not result.stdout.strip(),
            f'{args[0]} unexpected diagnostics:\n{result.stdout}')
    require(not re.search(r'(?im)\b(error|warning|unimplemented)\b', result.stdout),
            f'{args[0]} diagnostics:\n{result.stdout}')
    return result.stdout


def section_rows(dump, raw):
    # Read the pinned inspector's table, not a new general-purpose ELF reader.
    rows = {}
    for match in re.finditer(
            r"(?m)^([0-9a-f]{4})\s+(\w+)\s+([0-9a-f]{8})\s+([0-9a-f]{8})\s+"
            r"([0-9a-f]{8})\s+([0-9a-f]{8}):B\s+\d+\s+\d+\s+\d+\s+\d+\s+'([^']*)'", dump):
        index, kind, flags, address, offset, size, name = match.groups()
        row = dict(index=int(index, 16), kind=kind, flags=int(flags, 16),
                   address=int(address, 16), offset=int(offset, 16), size=int(size, 16))
        require(kind != 'nobits', 'unexpected BSS: this probe initializes both state words')
        require(row['offset'] + row['size'] <= len(raw), f'truncated section {name}')
        row['bytes'] = raw[row['offset']:row['offset'] + row['size']]
        require(name not in rows, f'duplicate section {name}')
        rows[name] = row
    require(rows, 'inspector returned no section table')
    return rows


def validate_data(data):
    require(len(data) == 152, 'expected 128 table + 16 width + 8 state bytes')
    require(struct.unpack_from('<4I', data, 128) == (1, 4, 4, 4),
            'ineffective char-size-8 or wrong integer/float/pointer widths')
    expected = b''.join(struct.pack('<f', float(f'{0.125 * math.sin(i * math.pi / 32):.9f}'))
                        for i in range(32))
    require(data[:128] == expected, 'sine table differs from independently rounded values')
    require(data[144:] == bytes(8), 'phase/increment initializers are not zero')


def validate_link(raw, dump, disassembly):
    require(len(raw) >= 52 and raw[:7] == b'\x7fELF\x01\x01\x01', 'not little-endian ELF32')
    require(struct.unpack_from('<HHI', raw, 16) == (2, 0x85, 1), 'not a SHARC executable')
    require(struct.unpack_from('<I', raw, 24)[0] == 0x180000, 'missing/wrong executable entry')
    shoff = struct.unpack_from('<I', raw, 32)[0]
    shentsize, shnum = struct.unpack_from('<HH', raw, 46)
    require(shentsize == 40 and shoff + shentsize * shnum <= len(raw), 'truncated section headers')
    rows = section_rows(dump, raw)
    require({name for name, row in rows.items() if row['flags'] & 2} ==
            {'probe_code', 'probe_data'}, 'unexpected loadable section/runtime')
    code, data = rows['probe_code'], rows['probe_data']
    require((code['address'], code['size'], code['flags']) == (0x180000, 320, 7),
            'missing/stubbed code or changed synthetic placement')
    require((data['address'], data['flags']) == (0x2c0000, 3), 'changed data placement')
    validate_data(data['bytes'])
    require(digest(code['bytes']) == CODE_SHA256, 'executable bytes differ from inspected probe')
    require(not any(row['kind'] in ('rela', 'rel') for row in rows.values()),
            'unresolved relocations in executable')
    symbols = {}
    for match in re.finditer(
            r"(?m)^[0-9a-f]{4}\s+(UNDEF|[0-9a-f]{8})\s+([0-9a-f]{8})\s+"
            r"[0-9a-f]{8}\s+(\w+)\s+(\w+)\s+[0-9a-f]{8}\s+'([^']*)'", dump):
        section, value, kind, binding, name = match.groups()
        require(not name or section != 'UNDEF', f'unresolved symbol {name}')
        if binding == 'global':
            require(name not in symbols, f'duplicate symbol {name}')
            symbols[name] = (int(value, 16), kind)
    expected = {}
    for name, value, kind in [('sine_init', 0x180000, 'function'),
                              ('sine_sample', 0x18000f, 'function'),
                              ('sine_render', 0x18004c, 'function'),
                              ('sine_widths', 0x2c0080, 'object')]:
        for prefix in ('', '_'):
            for suffix in ('', '.'):
                expected[prefix + name + suffix] = (value, kind)
    require(symbols == expected, 'missing/extra exports or incorrect entrypoints')
    instructions = re.findall(r'(?m)^  ([0-9a-f]{8})\s+([0-9a-f]+)\s+(.+)$', disassembly)
    decoded = bytearray()
    for pc, encoded, mnemonic in instructions:
        require(int(pc, 16) == 0x180000 + len(decoded) // 2, 'disassembly gap/overlap')
        require(len(encoded) in (4, 8, 12) and not mnemonic.startswith('.'),
                f'unknown instruction: {mnemonic}')
        decoded.extend(bytes.fromhex(encoded))
    require(decoded == code['bytes'], 'disassembly did not account for every code byte')
    for instruction in ('f3=-f1', 'cjump sine_sample (db)', 'r3=lshift r4 by r1',
                        'dm (i4,m5)=r1', 'rframe'):
        require(instruction in disassembly, f'missing operation: {instruction}')
    return dict(code_bytes=320, data_bytes=152, bss_bytes=0,
                code_sha256=digest(code['bytes']), data_sha256=digest(data['bytes']),
                decoded_instructions=len(instructions),
                entrypoints_pc_parcels={name: symbols[name][0] for name in
                                       ('sine_init.', 'sine_sample.', 'sine_render.')})


def rejected(label, operation, expected_message):
    try:
        operation()
    except ValueError as error:
        require(expected_message in str(error), f'{label}: unexpected rejection: {error}')
        return label
    raise ValueError(f'{label}: incorrectly accepted')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selache', type=Path, help='clean source checkout of the pinned Selache commit')
    args = parser.parse_args()
    selache = args.selache.resolve()
    require(command(['git', 'rev-parse', 'HEAD'], cwd=selache, text_output=True).strip() == PIN,
            f'Selache must be pinned to {PIN}')
    require(not command(['git', 'status', '--porcelain', '--untracked-files=normal'],
                        cwd=selache, text_output=True).strip(), 'Selache source checkout is not clean')
    tools = {name: selache / 'target/release' / name for name in TOOLS}
    require(all(path.is_file() for path in tools.values()), 'build the four tools using the README command')
    flags = FLAGS + ['-no-std-inc', '-I', str(selache / 'libsel/include')]
    root = HERE.parent.parent
    (root / 'out').mkdir(exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='sharc-sine-probe-', dir=root / 'out'))
    print(f'Fresh probe directory: {out}', flush=True)
    commands = []

    def run(args, text_output=False):
        commands.append([str(a) for a in args])
        return command(args, text_output=text_output)

    def compile_c(source, stem, options=None):
        obj = out / f'{stem}.doj'
        run([tools['selcc'], *(flags if options is None else options), '-c', '-o', obj, source])
        require(obj.is_file(), f'compiler returned success without {obj.name}')
        return obj

    def link_object(obj, stem):
        exe = out / f'{stem}.dxe'
        run([tools['seld'], '-proc', 'ADSP-21569', '-T', HERE / 'synthetic.ldf',
             '-entry', 'sine_init.', '-Map', out / f'{stem}.map', '-o', exe, obj])
        require(exe.is_file(), 'linker returned success without executable')
        return exe

    def inspect(exe):
        raw = exe.read_bytes()
        dump = run([tools['seldump'], '-fh', '-sh', '-n', '.symtab', exe], True)
        disassembly = run([tools['seldump'], '-ns', 'probe_code', exe], True)
        return raw, dump, disassembly

    source = HERE / 'sine.c'
    run([tools['selcc'], *flags, '-S', '-o', out / 'sine.s', source])
    obj = compile_c(source, 'sine')
    obj_dump = run([tools['seldump'], '-all', obj], True)
    require('CPU_name = ADSP-21569' in obj_dump and "'Encoding'\t'SW'" in obj_dump,
            'wrong processor/encoding attributes')
    (out / 'object.txt').write_text(obj_dump)
    exe = link_object(obj, 'sine')
    raw, dump, disassembly = inspect(exe)
    facts = validate_link(raw, dump, disassembly)
    (out / 'executable.txt').write_text(dump)
    (out / 'disassembly.txt').write_text(disassembly)
    repeat = link_object(compile_c(source, 'repeat'), 'repeat')
    require(repeat.read_bytes() == raw, 'second fresh compile/link differs')

    negative = []
    negative.append(rejected('zero-exit diagnostic',
                             lambda: run([sys.executable, '-c',
                                          "import sys; sys.stderr.write('warning: code omitted\\n')"]),
                             'diagnostics'))
    for label, changed, message in [
            ('truncated executable', raw[:100], 'truncated section headers'),
            ('zero entrypoint', raw[:24] + bytes(4) + raw[28:], 'missing/wrong executable entry')]:
        negative.append(rejected(label, lambda: validate_link(changed, dump, disassembly), message))
    bad_data = bytearray(section_rows(dump, raw)['probe_data']['bytes'])
    bad_data[0:4] = struct.pack('<f', -32.0)
    negative.append(rejected('corrupt table', lambda: validate_data(bad_data), 'sine table differs'))
    for label, text, message in [
            ('missing render export', source.read_text().replace('sine_render(', 'missing_render('),
             'missing/extra exports'),
            ('stubbed render', source.read_text().split('void sine_render(')[0] +
             'void sine_render(float *output) {}\n', 'missing/stubbed code')]:
        candidate = out / f'{label.replace(" ", "-")}.c'
        candidate.write_text(text)
        candidate_exe = link_object(compile_c(candidate, candidate.stem), candidate.stem)
        negative.append(rejected(label, lambda: validate_link(*inspect(candidate_exe)), message))
    wrong_flags = [flag.replace('-char-size-8', '-char-size-32') for flag in flags]
    wrong_exe = link_object(compile_c(source, 'wrong-width', wrong_flags), 'wrong-width')
    require(wrong_exe.read_bytes() == raw, 'char-size option behavior changed; requalify')
    wrong_data = bytearray(section_rows(dump, raw)['probe_data']['bytes'])
    wrong_data[128:144] = struct.pack('<4I', 1, 1, 1, 1)
    negative.append(rejected('wrong width artifact', lambda: validate_data(wrong_data),
                             'ineffective char-size-8'))
    for label, text, message, do_link in [
            ('malformed C', 'void bad( {\n', 'expected type', False),
            ('unresolved helper', 'void absent(void); void sine_init(void) { absent(); }\n',
             'unresolved', True)]:
        candidate = out / f'{label.replace(" ", "-")}.c'
        candidate.write_text(text)
        def build_bad():
            candidate_obj = compile_c(candidate, candidate.stem)
            if do_link:
                link_object(candidate_obj, candidate.stem)
        negative.append(rejected(label, build_bad, message))

    # Retain a tiny real miscompile, independently decoded as IEEE binary32.
    bad_float = out / 'negative-initializer.c'
    bad_float.write_text('const float bad_sample = -0.125f;\n')
    bad_obj = compile_c(bad_float, 'negative-initializer')
    bad_dump = run([tools['seldump'], '-all', bad_obj], True)
    bad_rows = section_rows(bad_dump, bad_obj.read_bytes())
    bad_word = bad_rows['seg_dmda']['bytes']
    expected_word = struct.pack('<f', -0.125)
    require(bad_word == struct.pack('<I', 0xc2000000), 'known compiler defect changed; requalify adaptation')
    negative.append(rejected('negative float initializer',
                             lambda: require(bad_word == expected_word, 'incorrect IEEE float'),
                             'incorrect IEEE float'))
    (out / 'negative-initializer.txt').write_text(bad_dump)
    ignored = compile_c(source, 'ignored-option', flags + ['-elekloader-invalid-option'])
    require(ignored.read_bytes() == obj.read_bytes(), 'unknown-option behavior changed; requalify')

    report = dict(status='compile-and-inspection-pass; target-not-executed',
                  selache_commit=PIN, host=platform.platform(), python=sys.version,
                  target_flags=flags, linked_objects=['sine.doj'], linked_runtime_files=[],
                  headers={'libsel/include/stdint.h': {
                      'license': 'MIT', 'sha256': digest((selache / 'libsel/include/stdint.h').read_bytes())}},
                  tools={name: {'license': 'GPL-3.0', 'sha256': digest(path.read_bytes())}
                         for name, path in tools.items()},
                  sources={name: digest((HERE / name).read_bytes())
                           for name in ('sine.c', 'synthetic.ldf', 'qualify.py')},
                  artifacts={name: digest((out / name).read_bytes())
                             for name in ('sine.doj', 'sine.dxe', 'sine.s', 'sine.map')},
                  facts=facts, negative_cases=negative,
                  known_negative_initializer={'expected_bits': 'be000000', 'actual_bits': 'c2000000',
                                              'actual_float': struct.unpack('<f', bad_word)[0]},
                  unknown_compiler_option='silently accepted; wrapper exposes no compiler flags',
                  char_size_32='accepted but emits identical byte-addressed probe; widths checked directly',
                  commands=commands)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {facts["code_bytes"]} code bytes, {facts["data_bytes"]} data bytes; '
          f'{len(negative)} negative checks. Target execution remains issue #33.\n{out / "report.json"}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        sys.exit(f'FAIL: {error}')
