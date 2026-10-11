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
CPL; since 2026-10-11 that includes the through-hole parts, which JLCPCB
solders by hand. `hand` lines, if any come back, stay in the JLC BOM so the
order lists every part, but are marked HAND-SOLDER and carry no LCSC number
and no CPL row. DNP lines are left out, and so are symbols excluded from the
BOM (TP6 and TP28, bare pads).

The CPL rotations are KiCad's plus a per-package correction (CORRECTIONS
below), and through-hole parts are placed at their body centre (F.Fab), not
their pin-1 origin. Run it with KiCad's Python, which has pcbnew. The
corrections are community data or read off JLCPCB's preview, not JLCPCB's
own numbers: check every polarised part in
JLCPCB's placement preview before paying (README, footprint orientation).

The script exits 1 without writing the JLC files if the CPL and the BOM
disagree: a CPL designator missing from the PCBA lines, a PCBA line without
an LCSC number or a CPL row, or a through-hole PCBA part whose LCSC number
is not in THT_VERIFIED.
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
# give SOT-23 as -90 for KiCad 6+ footprints. SOT-23 is overridden to 180
# below (DECISIONS.md P-10, revised 2026-10-11): at -90 JLCPCB's preview drew
# all four SOT-23 models 90 degrees off their pads, and at 180 their lone lead
# and pin 1 land on the footprint's. Do not revert it to the table's value
# without re-checking JLCPCB's preview.
#
# A package with no entry gets 0, which is an assumption, not data. CP_Elec
# had +180 "by analogy" with the sizes the table lists, and JLCPCB's preview
# showed C5 reversed with it (2026-10-11), so it was removed: no correction is
# taken by analogy. The through-hole entries come from JLCPCB's own preview
# (2026-10-11): at KiCad's rotation each of those models was drawn 90° off its
# footprint outline. Every polarised part is checked in the preview anyway
# (README, footprint orientation).
CORRECTIONS = [
    (r'^SOT-23', 180, 'JLCPCB preview 2026-10-11, overrides cpl_rotations_db -90'),
    (r'^SOIC-', 270, 'cpl_rotations_db'),
    (r'^TO-126-3_Vertical', 90, 'JLCPCB preview 2026-10-11'),
    (r'^PinHeader_\d+x\d+_P2\.54mm_Vertical', 90, 'JLCPCB preview 2026-10-11'),
    (r'^PinSocket_\d+x\d+_P2\.54mm_Vertical', 90, 'JLCPCB preview 2026-10-11'),
]


# Through-hole parts whose JLCPCB model is drawn right at the KiCad origin
# (pin 1), not at the body centre. J1: at its F.Fab centre JLCPCB drew the
# DC-005 about 5 mm off the board edge; at the origin it sat on its outline
# (preview, 2026-10-11).
ORIGIN_PLACED = {'J1'}


def body_centres(refs):
    """Centre of each footprint's F.Fab outline, in the CPL's coordinates.

    JLCPCB draws a part centred on the CPL point. KiCad's through-hole
    footprints have their origin on pin 1, so at the origin a 2x19 socket is
    drawn half off its pads (preview, 2026-10-11). The F.Fab outline is the
    body. Needs KiCad's Python (pcbnew).
    """
    try:
        import pcbnew
    except ImportError:
        sys.exit('export_fab: through-hole body centres need pcbnew; run with '
                 "KiCad's Python, e.g. /Applications/KiCad/KiCad.app/Contents/"
                 'Frameworks/Python.framework/Versions/3.9/bin/python3')
    board = pcbnew.LoadBoard(PCB)
    out = {}
    for ref in refs:
        fp = board.FindFootprintByReference(ref)
        items = [it for it in fp.GraphicalItems()
                 if it.GetLayer() == pcbnew.F_Fab and not isinstance(it, pcbnew.PCB_TEXT)]
        if not items:
            items = list(fp.Pads())
        if ref in ORIGIN_PLACED:
            p = fp.GetPosition()
            out[ref] = (p.x / 1e6, -p.y / 1e6)
            continue
        xs, ys = [], []
        for it in items:
            bb = it.GetBoundingBox()
            xs += [bb.GetLeft(), bb.GetRight()]
            ys += [bb.GetTop(), bb.GetBottom()]
        # pos export flips y; match it.
        out[ref] = ((min(xs) + max(xs)) / 2e6, -(min(ys) + max(ys)) / 2e6)
    return out

# Through-hole parts JLCPCB will assemble. Each was read from JLCPCB's part
# detail (cart.jlcpcb.com .../getComponentDetail) on 2026-10-11: assembly
# process THT, mode manualWeld (soldered by hand at JLCPCB), status yes.
# A through-hole PCBA part not listed here stops the export: check its
# record first, then add it.
THT_VERIFIED = {
    'C16214': 'DC-005 2.0 barrel jack (J1)',
    'C492401': 'PZ254V-11-02P 1x2 header (J2, J5)',
    'C492420': 'PZ254V-12-6P 2x3 header (J3, J4)',
    'C474882': 'KF301-5.0-3P terminal block (J6)',
    'C2897420': 'PM254-2-19-Z-8.5 2x19 socket (J7, J8)',
    'C27866': 'BD139 TO-126 (Q1)',
    'C5199801': 'RH-5001 test loop (TP1-TP27 but TP6)',
}


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
    # could place. Through-hole PCBA parts must be ones JLCPCB assembles.
    th = os.path.join(tmp, 'pos_th.csv')
    run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'front',
        '--exclude-dnp', '--smd-only', '-o', th, PCB)
    smd = {r['Ref'] for r in read_csv(th)}
    lcsc_of = {r: line['LCSC'] for line, refs in pcba for r in refs}
    tht_refs = sorted(pcba_refs - smd)
    for ref in tht_refs:
        if lcsc_of[ref] not in THT_VERIFIED:
            errors.append(f'{ref} is a through-hole PCBA part ({lcsc_of[ref]}) '
                          'not in THT_VERIFIED; check JLCPCB assembles it')
    if errors:
        sys.exit('export_fab: not writing the JLC files:\n  ' + '\n  '.join(errors))

    centres = body_centres(tht_refs)
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
            x, y = centres.get(ref, (float(p['PosX']), float(p['PosY'])))
            w.writerow([ref, f"{x:.4f}mm", f"{y:.4f}mm", 'Top', f'{rot:g}'])

    with open(os.path.join(JLC, 'curve-tracer_bom_jlc.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        # One line per LCSC part: JLCPCB loads, buys and charges the extended
        # fee per part, and J2/J5, J3/J4 and J7/J8 differ only in Value.
        by_part = {}
        for line, refs in pcba:
            entry = by_part.setdefault(line['LCSC'], [[], [], line['Footprint'], line['MPN']])
            entry[0].append(line['Value'])
            entry[1].extend(refs)
        for lcsc, (values, refs, fp, mpn) in by_part.items():
            comment = values[0] if len(set(values)) == 1 else mpn
            w.writerow([comment, ','.join(refs), fp.split(':')[-1], lcsc])
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
    print(f'JLC BOM: {len(by_part)} PCBA lines, one per LCSC part ({len(pcba_refs)} parts), '
          f'{len(merged)} HAND-SOLDER lines ({sum(len(r) for _, r in hand)} parts)')
    print(f'JLC CPL: {len(pcba_refs)} rows, every one a PCBA part; '
          f'through-hole: {",".join(tht_refs) or "none"}')
    for (pkg, deg, src), refs in sorted(rot_report.items()):
        print(f'  rotation {deg:+d} on {pkg} ({src}): {",".join(refs)}')


if __name__ == '__main__':
    main()
