"""Run the isolated Android fixture and sample reported thermal sensors with adb."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time


def metrics(output):
    for line in output.splitlines():
        if line.startswith('PHASE6 '):
            return json.loads(line[len('PHASE6 '):])
    raise RuntimeError('Instrumentation failed:\n' + output)


def run(args):
    if args.capture_output:
        return dict(result=metrics(args.capture_output.read_text(encoding='utf-8-sig')))
    adb = [args.adb] + (['-s', args.serial] if args.serial else [])
    subprocess.run(adb + ['shell', 'input', 'keyevent', 'WAKEUP'], check=True)
    command = adb + ['shell', 'am', 'instrument', '-w', '-e', 'size', str(args.size),
        '-e', 'lang', args.lang, '-e', 'soakSeconds', str(args.soak_seconds)]
    if args.verify:
        command += ['-e', 'verify', 'true']
    command += ['com.lucrazy.panel.phase6test.test/com.lucrazy.komicove.LibraryPhase6Instrumentation']
    # A temporary output file avoids a full pipe blocking the device at completion.
    samples = []
    start = time.monotonic()
    with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as output:
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
        while True:
            thermal = subprocess.run(adb + ['shell', 'dumpsys', 'thermalservice'],
                capture_output=True, text=True, timeout=10)
            readings = {}
            for value, kind, name, status in re.findall(
                    r'Temperature\{mValue=([\d.]+), mType=(\d+), mName=([^,]+), mStatus=(\d+)\}', thermal.stdout):
                if float(value) > 0:
                    readings[name] = dict(celsius=float(value), type=int(kind), status=int(status))
            samples.append(dict(seconds=time.monotonic()-start, sensors=readings))
            try:
                process.wait(timeout=10)
                break
            except subprocess.TimeoutExpired:
                pass
        output.seek(0)
        captured = output.read()
    return dict(result=metrics(captured),
                thermal_samples=samples,
                thermal_sampling='adb thermalservice, every 10s throughout fixture preparation, verification and soak; reported sensors, USB connected')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial')
    parser.add_argument('--size', type=int, choices=[1000, 5000, 10000], default=10000)
    parser.add_argument('--lang', choices=['pt', 'en'], default='pt')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--soak-seconds', type=int, default=0)
    parser.add_argument('--capture-output', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = run(args)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    summary = {key: value for key, value in report['result'].items() if key != 'soak'}
    print(json.dumps(summary))
