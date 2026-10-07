#!/usr/bin/env python3
"""Export everything the JLCPCB order needs, and check it agrees with itself.

    python3 hardware/tools/export_fab.py

Writes, under hardware/fab/:

    curve-tracer_bom.csv          engineering BOM: every line, MPN, Assembly, DNP
    gerbers/                      Gerbers (Protel names), Excellon drill, drill map
    jlc/curve-tracer_gerbers.zip  gerbers/ zipped: the file the quote page takes
    jlc/curve-tracer_bom_jlc.csv  JLC BOM: Comment, Designator, Footprint, LCSC Part #
    jlc/curve-tracer_cpl_jlc.csv  JLC CPL: Designator, Mid X, Mid Y, Layer, Rotation

Each symbol's `Assembly` field decides where a part goes (DECISIONS.md,
Assembly). `PCBA` lines get an LCSC number in the JLC BOM and a row in the
CPL. `hand` lines stay in the JLC BOM so the order lists every part, but are
marked HAND-SOLDER and carry no LCSC number and no CPL row, so JLCPCB has
nothing to match and nowhere to place them. DNP lines are left out.

The CPL rotations are KiCad's plus a per-package correction (CORRECTIONS
below). Those are community data, not JLCPCB's: check every polarised part in
JLCPCB's placement preview before paying (README, footprint orientation).

The script exits 1 without writing the JLC files if the CPL and the BOM
disagree: a CPL designator missing from the PCBA lines, a PCBA line without
an LCSC number or a CPL row, or a through-hole part headed for Economic PCBA.
"""
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.normpath(os.path.join(HERE, '..'))
SCH = os.path.join(HW, 'curve-tracer.kicad_sch')
PCB = os.path.join(HW, 'curve-tracer.kicad_pcb')
FAB = os.path.join(HW, 'fab')
GERBERS = os.path.join(FAB, 'gerbers')
JLC = os.path.join(FAB, 'jlc')
MAC_CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'

LAYERS = ('F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,'
          'F.Mask,B.Mask,Edge.Cuts')

# KiCad rotation + correction = JLCPCB rotation, matched on the footprint name.
# Source: matthewlai/JLCKicadTools cpl_rotations_db.csv (last changed
# 2024-09-11), which Bouni/kicad-jlcpcb-tools also ships as its default. Both
# give SOT-23 as -90 for KiCad 6+ footprints; the +180 often quoted dates from
# KiCad 5, whose SOT-23 had pin 3 at the top.
CORRECTIONS = [
    (r'^SOT-23', -90, 'cpl_rotations_db'),
    (r'^SOIC-', 270, 'cpl_rotations_db'),
    # 5x5.4 is not in the table; every CP_Elec size that is listed is 180.
    (r'^CP_Elec_', 180, 'by analogy: every listed CP_Elec size'),
]


def cli():
    return shutil.which('kicad-cli') or MAC_CLI


def run(*args):
    r = subprocess.run([cli(), *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'kicad-cli {args[0]} {args[1]} failed:\n{r.stdout}{r.stderr}')


def read_csv(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def correction(package):
    for pat, deg, src in CORRECTIONS:
        if re.search(pat, package):
            return deg, src
    return 0, ''


def main():
    os.makedirs(GERBERS, exist_ok=True)
    os.makedirs(JLC, exist_ok=True)
    tmp = tempfile.mkdtemp()

    # Engineering BOM: unchanged columns, plus Assembly.
    run('sch', 'export', 'bom',
        '--fields', 'Reference,Value,Footprint,MPN,Manufacturer,LCSC,Assembly,${DNP},${QUANTITY}',
        '--labels', 'Refs,Value,Footprint,MPN,Manufacturer,LCSC,Assembly,DNP,Qty',
        '--group-by', 'Value,Footprint,LCSC,Assembly,${DNP}',
        '--sort-field', 'Reference',
        '-o', os.path.join(FAB, 'curve-tracer_bom.csv'), SCH)

    # The same grouping without reference ranges, for the JLC BOM.
    flat = os.path.join(tmp, 'bom_flat.csv')
    run('sch', 'export', 'bom',
        '--fields', 'Reference,Value,Footprint,MPN,LCSC,Assembly,${DNP}',
        '--labels', 'Refs,Value,Footprint,MPN,LCSC,Assembly,DNP',
        '--group-by', 'Value,Footprint,LCSC,Assembly,${DNP}',
        '--sort-field', 'Reference', '--ref-range-delimiter', '',
        '-o', flat, SCH)
    bom = read_csv(flat)

    # Gerbers and drill, in JLCPCB's documented KiCad settings: Protel
    # extensions, mask subtracted from silk, no X2/netlist attributes,
    # absolute origin, PTH and NPTH in separate Excellon files, mm.
    for f in os.listdir(GERBERS):
        os.remove(os.path.join(GERBERS, f))
    run('pcb', 'export', 'gerbers', '-l', LAYERS, '--subtract-soldermask',
        '--no-x2', '--no-netlist', '--check-zones', '-o', GERBERS + '/', PCB)
    run('pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute',
        '--excellon-units', 'mm', '--excellon-zeros-format', 'decimal',
        '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2',
        '-o', GERBERS + '/', PCB)

    # Placement: front side, DNP excluded, absolute coordinates like the
    # Gerbers.
    pos = os.path.join(tmp, 'pos.csv')
    run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'front',
        '--exclude-dnp', '-o', pos, PCB)
    placed = {r['Ref']: r for r in read_csv(pos)}

    errors = []
    pcba, hand = [], []
    for line in bom:
        if line['DNP'] or line['Assembly'] == 'DNP':
            continue
        refs = [r for r in line['Refs'].split(',') if r]
        if line['Assembly'] == 'PCBA':
            if not line['LCSC']:
                errors.append(f"PCBA line {line['Refs']} has no LCSC number")
            pcba.append((line, refs))
        elif line['Assembly'] == 'hand':
            hand.append((line, refs))
        else:
            errors.append(f"{line['Refs']}: Assembly is {line['Assembly']!r}, "
                          "expected PCBA, hand or DNP")

    pcba_refs = {r for _, refs in pcba for r in refs}
    for ref in sorted(pcba_refs - placed.keys()):
        errors.append(f'{ref} is a PCBA part with no placement row')
    if errors:
        sys.exit('export_fab: not writing the JLC files:\n  ' + '\n  '.join(errors))

    # CPL: PCBA parts only. A hand-soldered part with a CPL row is one JLCPCB
    # could place.
    th = os.path.join(tmp, 'pos_th.csv')
    run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'front',
        '--exclude-dnp', '--smd-only', '-o', th, PCB)
    smd = {r['Ref'] for r in read_csv(th)}
    for ref in sorted(pcba_refs - smd):
        errors.append(f'{ref} is PCBA but has through-hole pads; Economic PCBA is SMD only')
    if errors:
        sys.exit('export_fab: not writing the JLC files:\n  ' + '\n  '.join(errors))

    rot_report = {}
    with open(os.path.join(JLC, 'curve-tracer_cpl_jlc.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for ref in sorted(pcba_refs, key=lambda r: (re.sub(r'\d', '', r), int(re.sub(r'\D', '', r)))):
            p = placed[ref]
            deg, src = correction(p['Package'])
            rot = (float(p['Rot']) + deg) % 360
            if deg:
                rot_report.setdefault((p['Package'], deg, src), []).append(ref)
            w.writerow([ref, f"{float(p['PosX']):.4f}mm", f"{float(p['PosY']):.4f}mm",
                        'Top', f'{rot:g}'])

    with open(os.path.join(JLC, 'curve-tracer_bom_jlc.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for line, refs in pcba:
            w.writerow([line['Value'], ','.join(refs),
                        line['Footprint'].split(':')[-1], line['LCSC']])
        # One line per part to buy: the BOM groups by Value, and the test
        # points' values are their net names.
        merged = {}
        for line, refs in hand:
            key = (line['MPN'], line['Footprint'], line['LCSC'])
            merged.setdefault(key, ([], []))
            merged[key][0].append(line['Value'])
            merged[key][1].extend(refs)
        for (mpn, fp, lcsc), (values, refs) in merged.items():
            what = f'{len(refs)}x ' if len(refs) > 1 else ''
            if len(values) == 1 and values[0] != mpn:
                what += f'{values[0].split()[0]}: '
            buy = f', LCSC {lcsc}' if lcsc else ', not stocked at LCSC'
            w.writerow([f'HAND-SOLDER, not PCBA: {what}{mpn}{buy}',
                        ','.join(refs), fp.split(':')[-1], ''])

    zpath = os.path.join(JLC, 'curve-tracer_gerbers.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in sorted(os.listdir(GERBERS)):
            z.write(os.path.join(GERBERS, name), name)
    shutil.rmtree(tmp)

    print(f'gerbers: {len(os.listdir(GERBERS))} files -> {os.path.relpath(zpath, HW)}')
    print(f'JLC BOM: {len(pcba)} PCBA lines ({len(pcba_refs)} parts), '
          f'{len(merged)} HAND-SOLDER lines ({sum(len(r) for _, r in hand)} parts)')
    print(f'JLC CPL: {len(pcba_refs)} rows, every one a PCBA part')
    for (pkg, deg, src), refs in sorted(rot_report.items()):
        print(f'  rotation {deg:+d} on {pkg} ({src}): {",".join(refs)}')


if __name__ == '__main__':
    main()
