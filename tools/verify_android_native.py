"""Check release archive integrity and 16 KiB native library alignment."""
import argparse
import struct
import zipfile
from pathlib import Path


def verify(path):
    errors = []
    count = 0
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            errors.append(f"Corrupt archive member: {bad}")
        for entry in archive.infolist():
            if not entry.filename.endswith('.so'):
                continue
            data = archive.read(entry)
            if data[:4] != b'\x7fELF':
                errors.append(f"Not an ELF library: {entry.filename}")
                continue
            if data[4] != 2:  # Google Play's 16 KiB requirement applies to 64-bit.
                continue
            count += 1
            endian = '<' if data[5] == 1 else '>'
            offset = struct.unpack_from(endian + 'Q', data, 32)[0]
            stride, number = struct.unpack_from(endian + 'HH', data, 54)
            for index in range(number):
                header = offset + index * stride
                kind = struct.unpack_from(endian + 'I', data, header)[0]
                alignment = struct.unpack_from(endian + 'Q', data, header + 48)[0]
                if kind == 1 and alignment < 16384:
                    errors.append(f"ELF LOAD alignment < 16 KiB: {entry.filename}")
            if path.suffix == '.apk' and entry.compress_type == zipfile.ZIP_STORED:
                with path.open('rb') as source:
                    source.seek(entry.header_offset + 26)
                    name_length, extra_length = struct.unpack('<HH', source.read(4))
                payload_offset = entry.header_offset + 30 + name_length + extra_length
                if payload_offset % 16384:
                    errors.append(f"APK ZIP alignment < 16 KiB: {entry.filename}")
        if not count:
            errors.append('No 64-bit native libraries found; verify the supported ABIs.')
    return count, errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archives', type=Path, nargs='+')
    args = parser.parse_args()
    failed = False
    for path in args.archives:
        count, errors = verify(path)
        print(f'{path.name}: {count} 64-bit libraries, ' + ('FAIL' if errors else 'PASS'))
        for error in errors:
            print(error)
        failed |= bool(errors)
    raise SystemExit(1 if failed else 0)
