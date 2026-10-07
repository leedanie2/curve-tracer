#!/usr/bin/env python3
"""Assert the blueprint §3 / §14.5 topology against the schematic's netlist.

ERC proves the schematic is electrically legal; it says nothing about whether
it is the circuit the blueprint describes. This script does. It exports the
netlist with kicad-cli (so it reads what KiCad sees, not what anyone meant to
draw) and checks every connection §3 depends on: each op-amp pin, the gains,
the feedback tap position, the limiter, the clamp polarities, the Nucleo pin
map, the star ground, and test-point coverage. It also reads the constants
firmware/core/ct_config.h converts with and requires them to describe this
board, so changing a resistor without changing the firmware fails here.

Run it after every hand edit to the schematic:

    python3 hardware/tools/check_topology.py
    python3 hardware/tools/check_topology.py --self-test

--self-test also plants known faults in a copy of the netlist and requires
every one of them to be caught. A check that cannot fail is the failure mode
blueprint §11 records twice; the first version of this script had one (it
never asserted U1B's output pin, so tying two op-amp outputs together
passed).

Exit status: 0 all checks pass, 1 a check failed, 2 the netlist could not be
produced.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SCH = os.path.join(HERE, '..', 'curve-tracer.kicad_sch')
MAC_CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
CT_CONFIG = os.path.join(HERE, '..', '..', 'firmware', 'core', 'ct_config.h')


# --------------------------------------------------------------- netlist

_TOK = re.compile(r'\s*(\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+)', re.S)


def _parse(text):
    stack = [[]]
    for m in _TOK.finditer(text):
        tok = m.group(1)
        if tok == '(':
            stack.append([])
        elif tok == ')':
            node = stack.pop()
            stack[-1].append(node)
        elif tok.startswith('"'):
            stack[-1].append(tok[1:-1].replace('\\"', '"'))
        else:
            stack[-1].append(tok)
    return stack[0][0]


def _all(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def _one(node, key):
    found = _all(node, key)
    return found[0] if found else None


class Netlist:
    def __init__(self, text):
        root = _parse(text)
        self.comps = {}
        for c in _all(_one(root, 'components'), 'comp'):
            fields = {}
            for f in _all(_one(c, 'fields') or [], 'field'):
                fields[_one(f, 'name')[1]] = f[2] if len(f) > 2 and isinstance(f[2], str) else ''
            fp = _one(c, 'footprint')
            self.comps[_one(c, 'ref')[1]] = dict(
                value=_one(c, 'value')[1], footprint=fp[1] if fp else '', fields=fields)
        self.nets = {}
        self.pin = {}
        for n in _all(_one(root, 'nets'), 'net'):
            name = _one(n, 'name')[1].lstrip('/')
            nodes = [(_one(x, 'ref')[1], _one(x, 'pin')[1]) for x in _all(n, 'node')]
            self.nets[name] = nodes
            for node in nodes:
                self.pin[node] = name

    def on(self, ref, pin):
        return self.pin.get((ref, str(pin)))

    def set_value(self, ref, value):
        """Change one part's value (used by --self-test)."""
        self.comps[ref]['value'] = value

    def move(self, ref, pin, net):
        """Re-home one pin onto another net (used by --self-test)."""
        old = self.on(ref, pin)
        self.nets[old].remove((ref, str(pin)))
        self.nets.setdefault(net, []).append((ref, str(pin)))
        self.pin[(ref, str(pin))] = net


def export_netlist(sch):
    cli = os.environ.get('KICAD_CLI') or shutil.which('kicad-cli') or MAC_CLI
    if not os.path.exists(cli) and not shutil.which(cli):
        sys.exit(f'kicad-cli not found (set KICAD_CLI); looked for {cli}')
    out = tempfile.NamedTemporaryFile(suffix='.net', delete=False).name
    r = subprocess.run([cli, 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', out, sch],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.getsize(out):
        sys.stderr.write(r.stdout + r.stderr)
        sys.exit(2)
    with open(out) as f:
        text = f.read()
    os.unlink(out)
    return text


def firmware_constants(path=CT_CONFIG):
    """The analogue-chain constants the firmware converts with."""
    consts = {}
    with open(path) as f:
        for m in re.finditer(r'#define\s+(CT_\w+)\s+\(?(-?[\d.]+)f?\)?', f.read()):
            consts[m.group(1)] = float(m.group(2))
    return consts


# --------------------------------------------------------------- checks

def ohms(value):
    """'23.2k 0.1%' -> 23200.0, '51 1%' -> 51.0, '1 1% 1W' -> 1.0"""
    v = value.split()[0].rstrip('R')
    mult = {'k': 1e3, 'M': 1e6}
    return float(v[:-1]) * mult[v[-1]] if v[-1] in mult else float(v)


# Every op-amp pin, explicitly. A check that skips a pin cannot catch it.
OPAMP_PINS = {
    'U1': {1: 'OPA_SWEEP_OUT', 2: 'OPA_SWEEP_IN-', 3: 'DAC_SWEEP',
           5: 'DAC_GATE', 6: 'GATE_IN-', 7: 'GATE_AMP', 4: 'GND', 8: '+15V'},
    'U2': {1: 'BUF_HI', 2: 'BUF_HI', 3: 'SHUNT_HI',
           5: 'SHUNT_LO', 6: 'BUF_LO', 7: 'BUF_LO', 4: 'GND', 8: '+15V'},
    'U3': {1: 'DA_OUT', 2: 'DA_N', 3: 'DA_P',
           5: 'VDIV', 6: 'KBUF_OUT', 7: 'KBUF_OUT', 4: 'GND', 8: '+15V'},
}

# Named nets deliberately without a test point: op-amp input nodes (a probe
# there perturbs the loop) and per-shunt pads (SHUNT_HI reaches the selected
# one through J4).
TP_EXEMPT = {'DA_P', 'DA_N', 'GATE_IN-', 'SH1_TOP', 'SH2_TOP', 'SH3_TOP'}


def run_checks(nl, report, fw=None):
    on = nl.on

    def between(ref, a, b):
        return {on(ref, 1), on(ref, 2)} == {a, b}

    def val(ref):
        return ohms(nl.comps[ref]['value'])

    def chk(desc, cond):
        report.append((bool(cond), desc))

    # op-amps, pin by pin, and one driver per net
    for u, pins in OPAMP_PINS.items():
        bad = {p: on(u, p) for p, n in pins.items() if on(u, p) != n}
        chk(f'{u}: all 8 pins as specified {bad or ""}', not bad)
    drivers = {}
    for u in OPAMP_PINS:
        for p in (1, 7):
            drivers.setdefault(on(u, p), []).append(f'{u}.{p}')
    shared = {n: d for n, d in drivers.items() if len(d) > 1}
    chk(f'one op-amp output per net {shared or ""}', not shared)

    # §3.1 sweep source
    chk('DAC_SWEEP reaches PA6 (CN10-13)', ('J8', '13') in nl.nets.get('DAC_SWEEP', []))
    chk('R_f (R1) FB_SENSE-IN-, R_g (R2) IN- to GND',
        between('R1', 'FB_SENSE', 'OPA_SWEEP_IN-') and between('R2', 'OPA_SWEEP_IN-', 'GND'))
    g = 1 + val('R1') / val('R2')
    chk(f'sweep gain 1 + R1/R2 = {g:.4f} (§3.1: 3.32)', abs(g - 3.32) < 1e-9)
    chk('C_f (C1) footprint across R_f', between('C1', 'FB_SENSE', 'OPA_SWEEP_IN-'))
    chk('R_B (R3) 330 Ω, op-amp output to BD139_B',
        between('R3', 'OPA_SWEEP_OUT', 'BD139_B') and val('R3') == 330)
    chk('Q1 BD139: B=BD139_B, C=+15V, E=BD139_E',
        on('Q1', 3) == 'BD139_B' and on('Q1', 2) == '+15V' and on('Q1', 1) == 'BD139_E')
    chk('D1 B-E clamp: anode at emitter, cathode at base',
        on('D1', 2) == 'BD139_E' and on('D1', 1) == 'BD139_B')
    chk('R_sense (R5) 10 Ω, BD139_E to FB_SENSE',
        between('R5', 'BD139_E', 'FB_SENSE') and val('R5') == 10)
    chk('R_iso (R7) 22 Ω, FB_SENSE to LOAD',
        between('R7', 'FB_SENSE', 'LOAD') and val('R7') == 22)
    chk('§14.5(5) feedback tap after R_sense and before R_iso',
        on('R1', 1) == 'FB_SENSE' and on('R5', 2) == 'FB_SENSE' and on('R7', 1) == 'FB_SENSE')
    chk('Q2 limiter: B=BD139_E, E=FB_SENSE, C=BD139_B',
        on('Q2', 1) == 'BD139_E' and on('Q2', 2) == 'FB_SENSE' and on('Q2', 3) == 'BD139_B')
    for alt, main in (('R4', 'R3'), ('R6', 'R5'), ('R8', 'R7')):
        chk(f'{alt} alternate-value footprint parallel to {main}',
            {on(alt, 1), on(alt, 2)} == {on(main, 1), on(main, 2)})

    # §3.2 gate, §3.6 gate protection
    chk('DAC_GATE reaches PA4 (CN7-32)', ('J7', '32') in nl.nets.get('DAC_GATE', []))
    g2 = 1 + val('R9') / val('R10')
    chk(f'gate gain = {g2:.4f}, same as sweep (§3.2)',
        between('R9', 'GATE_AMP', 'GATE_IN-') and between('R10', 'GATE_IN-', 'GND') and g2 == g)
    chk('gate series 1 kΩ GATE_AMP to DUT_G (§3.6)', between('R11', 'GATE_AMP', 'DUT_G') and val('R11') == 1000)
    chk('gate Zener D2: cathode DUT_G, anode GNDPWR, 12 V part',
        on('D2', 1) == 'DUT_G' and on('D2', 2) == 'GNDPWR' and 'C12' in nl.comps['D2']['value'])

    # drain path, shunts, range select
    chk('PTC F1: LOAD to PTC_OUT', between('F1', 'LOAD', 'PTC_OUT'))
    for i, (r, o) in enumerate((('R12', 1), ('R13', 100), ('R14', 10000)), 1):
        chk(f'range {i}: J3 {2*i-1}-{2*i} force to {r} ({o:g} Ω) to DUT_D; J4 {2*i} senses the same pad',
            on('J3', 2 * i - 1) == 'PTC_OUT' and on('J3', 2 * i) == f'SH{i}_TOP'
            and between(r, f'SH{i}_TOP', 'DUT_D') and val(r) == o
            and on('J4', 2 * i) == f'SH{i}_TOP' and on('J4', 2 * i - 1) == 'SHUNT_HI')
    chk('J3 and J4 carry the range-select silkscreen footprint',
        all('RangeSelect' in nl.comps[j]['footprint'] for j in ('J3', 'J4')))
    chk('SHUNT_LO Kelvin tap through NT1 onto DUT_D', between('NT1', 'SHUNT_LO', 'DUT_D'))
    chk('J7/J8 use the mirrored-numbering Nucleo carrier socket (DECISIONS.md L-2), not the stock socket',
        all('NucleoCarrier' in nl.comps[j]['footprint'] for j in ('J7', 'J8')))
    chk('DUT socket J6: 1=G 2=D 3=S', on('J6', 1) == 'DUT_G' and on('J6', 2) == 'DUT_D' and on('J6', 3) == 'GNDPWR')

    # §3.3 instrumentation amp
    chk('R3/R4 arm: 1 kΩ BUF_HI to DA_P, 20 kΩ DA_P to GND',
        between('R15', 'BUF_HI', 'DA_P') and between('R16', 'DA_P', 'GND'))
    chk('R1/R2 arm: 1 kΩ BUF_LO to DA_N, 20 kΩ DA_N to DA_OUT',
        between('R17', 'BUF_LO', 'DA_N') and between('R18', 'DA_N', 'DA_OUT'))
    ga = val('R18') / val('R17')
    chk(f'difference gain R2/R1 = {ga:g} (§3.3: 20), R4/R3 matched',
        ga == 20 and val('R16') / val('R15') == 20)

    # §3.4 Kelvin
    dv = (val('R20') + val('R21')) / val('R21')
    rdiv = val('R20') + val('R21')
    chk(f'Kelvin divider across KELVIN_HI/KELVIN_LO = /{dv:g} (§3.4: /4)',
        between('R20', 'KELVIN_HI', 'VDIV') and between('R21', 'VDIV', 'KELVIN_LO') and dv == 4)
    chk(f'Kelvin divider total {rdiv / 1e3:g}k (§3.4: 400k, 2.5 uA/V of DUT-node loading)',
        rdiv == 400e3)
    chk('Kelvin header J5: 1=KELVIN_HI 2=KELVIN_LO', on('J5', 1) == 'KELVIN_HI' and on('J5', 2) == 'KELVIN_LO')

    # §3.5 ADC pins, §3.7 isolation
    for adc, src, r, c, d, pin in (('ADC1_I', 'DA_OUT', 'R19', 'C3', 'D4', '28'),
                                   ('ADC2_V', 'KBUF_OUT', 'R22', 'C4', 'D5', '38')):
        chk(f'{adc}: {src} through {r} = 1 kΩ (§3.5, §3.7) to CN7-{pin}, 10 nF and BAT54S at the pin',
            between(r, src, adc) and val(r) == 1000 and ('J7', pin) in nl.nets.get(adc, [])
            and between(c, adc, 'GND') and on(d, 3) == adc and on(d, 1) == 'GND' and on(d, 2) == '+3V3')

    # power and ground
    for u, c in (('U1', 'C6'), ('U2', 'C7'), ('U3', 'C8')):
        chk(f'{u} decoupled by {c}', between(c, '+15V', 'GND'))
    chk('BD139 collector decoupling C2', between('C2', '+15V', 'GNDPWR'))
    chk('star ground: GND and GNDPWR distinct, joined only by NT2',
        'GND' in nl.nets and 'GNDPWR' in nl.nets and between('NT2', 'GNDPWR', 'GND'))
    chk('+15 V never reaches the Nucleo', not any(r in ('J7', 'J8') for r, _ in nl.nets['+15V']))
    chk('PA5 (CN10-11, drives LD2) unconnected', (on('J8', 11) or 'unconnected').startswith('unconnected'))

    # the firmware converts with constants that must describe this board
    if fw is not None:
        board = {
            'CT_GAIN_SWEEP': 1 + val('R1') / val('R2'),
            'CT_GAIN_GATE': 1 + val('R9') / val('R10'),
            'CT_SHUNT_OHM': val('R12'),
            'CT_DIFFAMP_GAIN': val('R18') / val('R17'),
            'CT_VDIV': (val('R20') + val('R21')) / val('R21'),
            'CT_RDIV_OHM': val('R20') + val('R21'),
            'CT_R_ISO_OHM': val('R7'),
        }
        for name, want in board.items():
            have = fw.get(name)
            chk(f'firmware {name} = {have} matches the board ({want:g})',
                have is not None and abs(have - want) <= 1e-4 * abs(want))

    # test points
    tps = {nl.on(r, 1) for r in nl.comps if r.startswith('TP')}
    named = {n for n in nl.nets if not n.startswith(('unconnected', 'Net-'))}
    missing = sorted(named - tps - TP_EXEMPT)
    chk(f'every named net has a test point; missing {missing or "none"}', not missing)


# Faults the checks must catch. Each is a mistake that ERC would pass.
FAULTS = [
    ('two op-amp outputs tied together', [('U1', 7, 'OPA_SWEEP_OUT')]),
    ('feedback tapped after R_iso (§14.5(5))', [('R1', 1, 'LOAD')]),
    ('B-E clamp reversed', [('D1', 2, 'BD139_B'), ('D1', 1, 'BD139_E')]),
    ('difference amp inputs swapped', [('U3', 3, 'DA_N'), ('U3', 2, 'DA_P')]),
    ('Kelvin sense jumper wired to the wrong shunt', [('J4', 2, 'SH2_TOP')]),
    ('ADC1 wired to PA1 instead of PA0', [('J7', 28, 'unconnected-x'), ('J7', 30, 'ADC1_I')]),
    ('Kelvin divider back to 30k/10k: firmware rdiv no longer matches', [('R20', None, '30k 0.1%'), ('R21', None, '10k 0.1%')]),
    ('ADC isolation back to 51 ohm', [('R19', None, '51 1%')]),
    ('stock (mirrored) socket footprint on the Nucleo', [('J7', 'fp', 'Connector_PinSocket_2.54mm:PinSocket_2x19_P2.54mm_Vertical')]),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('schematic', nargs='?', default=DEFAULT_SCH)
    ap.add_argument('--netlist', help='check an existing KiCad S-expression netlist instead of exporting one')
    ap.add_argument('--self-test', action='store_true', help='also require every planted fault to be caught')
    args = ap.parse_args()

    text = open(args.netlist).read() if args.netlist else export_netlist(args.schematic)
    fw = firmware_constants() if os.path.exists(CT_CONFIG) else None
    report = []
    run_checks(Netlist(text), report, fw)
    if fw is None:
        report.append((False, f'firmware constants not found at {CT_CONFIG}'))
    for ok, desc in report:
        print(('PASS  ' if ok else 'FAIL  ') + desc)
    fails = sum(not ok for ok, _ in report)
    print(f'\n{len(report) - fails}/{len(report)} checks pass')
    status = 1 if fails else 0

    if args.self_test:
        print('\nself-test: each planted fault must fail at least one check')
        for name, moves in FAULTS:
            nl = Netlist(text)
            for ref, pin, net in moves:
                if pin == 'fp':
                    nl.comps[ref]['footprint'] = net
                elif pin is None:
                    nl.set_value(ref, net)
                else:
                    nl.move(ref, pin, net)
            planted = []
            run_checks(nl, planted, fw)
            caught = [d for ok, d in planted if not ok]
            print(('caught  ' if caught else 'MISSED  ') + name + (f'  <- {caught[0]}' if caught else ''))
            if not caught:
                status = 1
    return status


if __name__ == '__main__':
    sys.exit(main())
