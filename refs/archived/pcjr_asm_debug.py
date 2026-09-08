#!/usr/bin/env python3
"""PCjr 8088 byte workbench (v5.3).

Pure stdlib. Holds the verified pure functions used to construct and
check Cartridge BASIC machine-code images for the IBM PCjr. The MCP
server imports this module; the CLI remains for local verification.

Run the stage gates after a server restart:
    python3 pcjr_asm_debug.py selftest

v5: handler-opcode coverage (iret, dec r16, push/pop r16, moffs A1/A3,
mov r16,r/m16 8B, mov r/m8,imm8 C6), length-safe decode, tolerant hex
input, and OOB-safe branch checks.
v5.1: fail-fast decode (P1): unknown opcodes and unsupported group /N
halt decode with a "; FAIL:" marker instead of falling back to db.
v5.2: composite gate() folds selfloc + rel8/rel16 construction +
branch verify + decode + optional byte compare + emit into one
round-trip. P1 fail-fast decode retained.
v5.3: 81 /7 iw decode (cmp r/m16,imm16) added. The gate decode-fail
fixture gd switches from 81 to 63 so it still halts.
"""
import json
import re
import sys

GOLDEN_HEX = ("0E1F55E800005D8DAE7A00BA6200EC2440B400894600"
              "89C6B9307531DB31FFBA6200EC244039F0740A85F674"
              "0347EB014389C6E2EA895E02897E045DCB")

GOLDEN_DATA = """1000 DATA &H0E,&H1F,&H55,&HE8,&H00,&H00,&H5D,&H8D,&HAE,&H7A,&H00
1010 DATA &HBA,&H62,&H00,&HEC,&H24,&H40,&HB4,&H00,&H89,&H46,&H00
1020 DATA &H89,&HC6,&HB9,&H30,&H75,&H31,&HDB,&H31,&HFF,&HBA,&H62
1030 DATA &H00,&HEC,&H24,&H40,&H39,&HF0,&H74,&H0A,&H85,&HF6,&H74
1040 DATA &H03,&H47,&HEB,&H01,&H43,&H89,&HC6,&HE2,&HEA,&H89,&H5E
1050 DATA &H02,&H89,&H7E,&H04,&H5D,&HCB
1060 DATA -1
"""

def parse(text):
    """BASIC DATA block -> byte list (stops at -1 sentinel)."""
    out = []
    for raw in text.splitlines():
        line = raw.strip().split("'")[0].strip()
        if not line:
            continue
        line = re.sub(r'^\d+\s+', '', line)
        if line.upper().startswith("DATA"):
            line = line[4:].lstrip()
        for tok in re.findall(r'&[Hh][0-9A-Fa-f]+|&[Oo][0-7]+|-?\d+', line):
            if tok.upper().startswith('&H'):
                v = int(tok[2:], 16)
            elif tok.upper().startswith('&O'):
                v = int(tok[2:], 8)
            else:
                v = int(tok, 10)
            if v == -1:
                return out
            if not (0 <= v <= 255):
                raise ValueError(f"out of byte range: {tok!r}")
            out.append(v)
    return out

def emit(data, start=1000, step=10, wrap=11):
    """byte list -> BASIC DATA block with sentinel."""
    lines, n = [], (len(data) + wrap - 1) // wrap
    for i in range(n):
        chunk = data[i * wrap:(i + 1) * wrap]
        lines.append(f"{start + i * step} DATA "
                     + ",".join(f"&H{b:02X}" for b in chunk))
    lines.append(f"{start + n * step} DATA -1")
    return "\n".join(lines)

def patch(data, patches):
    """Non-mutating (offset,value) edits; ValueError on bad input."""
    out = list(data)
    for off, val in patches:
        if not (0 <= off < len(data)):
            raise ValueError(f"offset out of range: {off}")
        if not (0 <= val <= 255):
            raise ValueError(f"value out of byte range: {val}")
        out[off] = val
    return out

def check(actual, expected):
    """Compare byte lists -> report dict (simple form)."""
    a, e = list(actual), list(expected)
    first = next((i for i in range(min(len(a), len(e))) if a[i] != e[i]), None)
    if first is None and len(a) != len(e):
        first = min(len(a), len(e))
    return {"ok": len(a) == len(e) and first is None,
            "delta": len(a) - len(e), "first_diff": first}

def check_detail(actual, expected, context=8):
    """Compare byte lists -> report with hex context around first divergence."""
    a, e = list(actual), list(expected)
    first = next((i for i in range(min(len(a), len(e))) if a[i] != e[i]), None)
    if first is None and len(a) != len(e):
        first = min(len(a), len(e))

    lo = max(0, (first if first is not None else 0) - context)
    hi = min(max(len(a), len(e)),
             (first if first is not None else 0) + context)

    return {
        "ok": len(a) == len(e) and first is None,
        "len_actual": len(a),
        "len_expected": len(e),
        "delta": len(a) - len(e),
        "first_diff": first,
        "context_start": lo,
        "context_end": hi,
        "expected_context_hex": "".join(f"{b:02X}" for b in e[lo:hi]),
        "actual_context_hex": "".join(f"{b:02X}" for b in a[lo:hi]),
    }

def rel8(insn, target):
    """Short branch displacement bytes (next-ip = insn+2)."""
    disp = target - (insn + 2)
    if not (-128 <= disp <= 127):
        raise ValueError(f"rel8 out of range: {disp}")
    return [disp & 0xFF]

def rel16(insn, target):
    """Near call/jmp displacement bytes (next-ip = insn+3)."""
    if not (-32768 <= target - (insn + 3) <= 32767):
        raise ValueError("rel16 out of range")
    disp = (target - (insn + 3)) & 0xFFFF
    return [disp & 0xFF, (disp >> 8) & 0xFF]

def selfloc_disp(pop_off, base=128):
    """lea bp,[bp+disp16] displacement bytes after call get_ip / pop bp."""
    disp = base - pop_off
    if not (0 <= disp <= 0xFFFF):
        raise ValueError(f"selfloc out of range: {disp}")
    return [disp & 0xFF, (disp >> 8) & 0xFF]

def selfloc_full(pop_offset, base=128):
    """Full self-location instruction bytes plus the resolved BP target.

    Contract: after `call get_ip` / `pop bp`, BP = pop_offset. We emit
    `lea bp,[bp+disp16]` so BP becomes `base`. The complete instruction
    is `8D AE <disp16-lo> <disp16-hi>`.
    """
    disp = base - pop_offset
    if not (0 <= disp <= 0xFFFF):
        raise ValueError(f"selfloc out of range: {disp}")
    lo, hi = disp & 0xFF, (disp >> 8) & 0xFF
    return {
        "pop_offset": pop_offset,
        "base": base,
        "disp": disp,
        "disp16_hex": f"{hi:02X}{lo:02X}",
        "lea_hex": f"8DAE{lo:02X}{hi:02X}",
        "result_bp": base,
        "asm": f"lea bp,[bp+0x{disp:04X}]",
    }

REGS16 = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di"]
REG8 = ["al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"]
EA0 = ["[bx+si]", "[bx+di]", "[bp+si]", "[bp+di]", "[si]", "[di]", None, "[bx]"]

OP1 = {0x0E: "push cs", 0x1F: "pop ds", 0xEC: "in al,dx",
       0xCB: "retf", 0x45: "inc bp", 0x4D: "dec bp",
       0xCF: "iret",
       }

REL8 = {0x74: "je", 0x75: "jne", 0x72: "jc",
        0xEB: "jmp", 0xE2: "loop"}

IMM8 = {0x24: "and al,0x%02X", 0xB4: "mov ah,0x%02X",
        0xE4: "in al,0x%02X", 0xE6: "out 0x%02X,al",
        0xB0: "mov al,0x%02X"}

IMM16 = {0xBA: "mov dx,0x%04X", 0xB9: "mov cx,0x%04X"}

MNEMO = {0x89: "mov", 0x31: "xor", 0x39: "cmp", 0x85: "test"}

MNEMO16_REG_RM = {0x8B: "mov",   # MOV r16, r/m16 (reg = destination)
                  0x2B: "sub"}    # SUB r16, r/m16 (reg = destination)

MNEMO8_RM_REG = {0x88: "mov"}    # MOV r/m8, r8

MNEMO8_REG_RM = {0x3A: "cmp",    # CMP r8, r/m8
                 0x8A: "mov"}    # MOV r8, r/m8 (reg = destination)

def _s8(v):
    return v - 256 if v >= 128 else v

def _s16(v):
    return v - 65536 if v >= 32768 else v

def _u16(lo, hi):
    return lo | (hi << 8)

def _need(data, off, n):
    """True when n bytes remain starting at offset off."""
    return off + n <= len(data)

def decode(data):
    """byte list -> [(offset, length, text)] for the verified subset.

    Fail-fast (v5.1): the first unknown opcode halts decode; the
    remaining bytes are one entry with a "; FAIL:" marker. Truncated
    trailing instructions are marked, never raised.
    """
    out, off, n = [], 0, len(data)
    while off < n:
        b = data[off]
        start = off
        if b in OP1:
            off += 1
            text = OP1[b]
        elif 0x40 <= b <= 0x47:
            off += 1
            text = f"inc {REGS16[b - 0x40]}"
        elif 0x48 <= b <= 0x4F:
            off += 1
            text = f"dec {REGS16[b - 0x48]}"
        elif 0x50 <= b <= 0x57:
            off += 1
            text = f"push {REGS16[b - 0x50]}"
        elif 0x58 <= b <= 0x5F:
            off += 1
            text = f"pop {REGS16[b - 0x58]}"
        elif b in (0xA1, 0xA3):
            if not _need(data, off, 3):
                text = f"db 0x{b:02X} ; truncated (need 3)"
                off += 1
            else:
                imm = _u16(data[off + 1], data[off + 2])
                off += 3
                text = (f"mov ax,[0x{imm:04X}]" if b == 0xA1
                        else f"mov [0x{imm:04X}],ax")
        elif b in REL8:
            if not _need(data, off, 2):
                text = f"db 0x{b:02X} ; truncated (need 2)"
                off += 1
            else:
                text = f"{REL8[b]} 0x{(off + 2 + _s8(data[off + 1])) & 0xFFFF:04X}"
                off += 2
        elif b == 0xE8:
            if not _need(data, off, 3):
                text = f"db 0x{b:02X} ; truncated (need 3)"
                off += 1
            else:
                next_ip = off + 3
                target = (next_ip + _s16(_u16(data[off + 1], data[off + 2]))) & 0xFFFF
                text = f"call 0x{target:04X}"
                off += 3
        elif b in IMM8:
            if not _need(data, off, 2):
                text = f"db 0x{b:02X} ; truncated (need 2)"
                off += 1
            else:
                text = IMM8[b] % data[off + 1]
                off += 2
        elif b in IMM16:
            if not _need(data, off, 3):
                text = f"db 0x{b:02X} ; truncated (need 3)"
                off += 1
            else:
                text = IMM16[b] % _u16(data[off + 1], data[off + 2])
                off += 3
        elif 0xB8 <= b <= 0xBF:
            if not _need(data, off, 3):
                text = f"db 0x{b:02X} ; truncated (need 3)"
                off += 1
            else:
                imm = _u16(data[off + 1], data[off + 2])
                off += 3
                text = f"mov {REGS16[b - 0xB8]},0x{imm:04X}"
        elif b == 0x8D or b in MNEMO or b in (0x88, 0x3A, 0x80, 0x8B, 0xC6,
                                               0x2B, 0x8A, 0x81):
            off, text = _modrm(data, off)
        else:
            rest = "".join(f"{x:02X}" for x in data[start:])
            off = n
            text = (f"; FAIL: unknown opcode 0x{b:02X} at 0x{start:04X}, "
                    f"decode halted (remaining {rest})")
        out.append((start, off - start, text))
    return out

def _modrm(data, off):
    opcode = data[off]
    if not _need(data, off, 2):
        return off + 1, f"db 0x{opcode:02X} ; truncated (need modrm)"
    m = data[off + 1]
    mod, reg, rm = (m >> 6) & 3, (m >> 3) & 7, m & 7
    p = off + 2

    if mod == 3:
        rm8 = REG8[rm]
        rm16 = REGS16[rm]
        mem = ""
    elif mod == 0:
        if rm == 6:
            if not _need(data, p, 2):
                return off + 1, f"db 0x{opcode:02X} ; truncated (need disp16)"
            disp = _u16(data[p], data[p + 1])
            p = off + 4
            mem = f"[0x{disp:04X}]"
        else:
            mem = EA0[rm]
    elif mod == 1:
        if not _need(data, p, 1):
            return off + 1, f"db 0x{opcode:02X} ; truncated (need disp8)"
        disp = data[p]
        p = off + 3
        base = EA0[rm]
        mem = f"[bp+0x{disp:02X}]" if rm == 6 else f"{base}+0x{disp:02X}"
    else:
        if not _need(data, p, 2):
            return off + 1, f"db 0x{opcode:02X} ; truncated (need disp16)"
        disp = _u16(data[p], data[p + 1])
        p = off + 4
        base = EA0[rm]
        mem = f"[bp+0x{disp:04X}]" if rm == 6 else f"{base}+0x{disp:04X}"

    def rm_oper(use8):
        if mod == 3:
            return rm8 if use8 else rm16
        return mem

    if opcode == 0x8D:
        return p, f"lea {REGS16[reg]},{mem}"
    if opcode in MNEMO:
        return p, f"{MNEMO[opcode]} {rm_oper(False)},{REGS16[reg]}"
    if opcode in MNEMO16_REG_RM:
        return p, f"{MNEMO16_REG_RM[opcode]} {REGS16[reg]},{rm_oper(False)}"
    if opcode in MNEMO8_RM_REG:
        return p, f"{MNEMO8_RM_REG[opcode]} {rm_oper(True)},{REG8[reg]}"
    if opcode in MNEMO8_REG_RM:
        return p, f"{MNEMO8_REG_RM[opcode]} {REG8[reg]},{rm_oper(True)}"
    if opcode == 0x80:
        if not _need(data, p, 1):
            return off + 1, "db 0x80 ; truncated (need imm8)"
        imm = data[p]
        p += 1
        if reg == 7:
            return p, f"cmp {rm_oper(True)},0x{imm:02X}"
        return len(data), (f"; FAIL: 0x80 group /{reg} unsupported at "
                           f"0x{off:04X}, decode halted")
    if opcode == 0x81:
        if not _need(data, p, 2):
            return off + 1, "db 0x81 ; truncated (need imm16)"
        imm = _u16(data[p], data[p + 1])
        p += 2
        if reg == 7:
            return p, f"cmp {rm_oper(False)},0x{imm:04X}"
        return len(data), (f"; FAIL: 0x81 group /{reg} unsupported at "
                           f"0x{off:04X}, decode halted")
    if opcode == 0xC6:
        if not _need(data, p, 1):
            return off + 1, "db 0xC6 ; truncated (need imm8)"
        imm = data[p]
        p += 1
        if reg == 0:
            return p, f"mov {rm_oper(True)},0x{imm:02X}"
        return len(data), (f"; FAIL: 0xC6 group /{reg} unsupported at "
                           f"0x{off:04X}, decode halted")
    return len(data), (f"; FAIL: unknown ModRM opcode 0x{opcode:02X} at "
                       f"0x{off:04X}, decode halted")

def branch_checks(data, checks):
    """Verify (insn_addr, target) pairs against decoded displacements."""
    reports = []
    for at, target in checks:
        if not (0 <= at < len(data)):
            reports.append({
                "at": at, "target": target, "actual": None, "ok": False,
                "error": "offset out of range",
            })
            continue
        b = data[at]
        if b in REL8:
            if not _need(data, at, 2):
                reports.append({
                    "at": at, "target": target, "actual": None, "ok": False,
                    "error": "truncated branch",
                })
                continue
            rel = _s8(data[at + 1])
            actual = (at + 2 + rel) & 0xFFFF
        elif b == 0xE8:
            if not _need(data, at, 3):
                reports.append({
                    "at": at, "target": target, "actual": None, "ok": False,
                    "error": "truncated branch",
                })
                continue
            rel = _s16(_u16(data[at + 1], data[at + 2]))
            actual = (at + 3 + rel) & 0xFFFF
        else:
            reports.append({
                "at": at, "target": target, "actual": None, "ok": False,
                "error": f"opcode 0x{b:02X} is not a supported branch",
            })
            continue
        reports.append({"at": at, "target": target, "actual": actual,
                        "ok": actual == target})
    return {"ok": all(r["ok"] for r in reports), "checks": reports}

def gate(hex_bytes, selfloc_at, pop_offset=6, base=128, checks=None,
         expected_hex=None):
    """Composite emission gate: construct, verify, and emit in one pass.

    Two-phase contract:
      - The assistant supplies a complete image with placeholder bytes
        at every displacement site, plus (selfloc_at, branch checks)
        that locate them.
      - This function fills the selfloc displacement and every branch
        displacement from the (at, target) list, then decodes, verifies
        branches, optionally byte-compares, and emits the DATA block.

    `hex_bytes` is never mutated; a copy is patched.

    Returns one dict. Never raises.
    """
    data = _hex_or_error(hex_bytes)
    data = list(data)
    checks = list(checks or [])

    # 1. Self-location site validation (hard stop on failure).
    selfloc_report = {
        "at": selfloc_at,
        "pop_offset": pop_offset,
        "base": base,
        "ok": False,
        "lea_hex": None,
        "error": None,
    }
    if not (0 <= selfloc_at <= len(data) - 4):
        selfloc_report["error"] = f"selfloc_at out of range: {selfloc_at}"
    elif data[selfloc_at] != 0x8D or data[selfloc_at + 1] != 0xAE:
        selfloc_report["error"] = (
            f"expected 8D AE at 0x{selfloc_at:04X}, "
            f"got {data[selfloc_at]:02X} {data[selfloc_at + 1]:02X}")
    else:
        sf = selfloc_full(pop_offset, base)
        disp = sf["disp"]
        data[selfloc_at + 2] = disp & 0xFF
        data[selfloc_at + 3] = (disp >> 8) & 0xFF
        selfloc_report["lea_hex"] = sf["lea_hex"]
        selfloc_report["ok"] = True

    if not selfloc_report["ok"]:
        return {
            "selfloc": selfloc_report,
            "branches": [],
            "branch_ok": False,
            "branch": [],
            "decode_ok": False,
            "decode": [],
            "check": None,
            "patched_hex": None,
            "data_block": None,
            "gate_ok": False,
        }

    # 2. Branch displacement construction and patch (report, continue).
    branch_reports = []
    for at, target in checks:
        rep = {"at": at, "target": target, "kind": None,
               "disp_hex": None, "ok": False, "error": None}
        if not (0 <= at < len(data)):
            rep["error"] = "offset out of range"
            branch_reports.append(rep)
            continue
        b = data[at]
        if b in REL8:
            if not _need(data, at, 2):
                rep["error"] = "truncated (need 2)"
                branch_reports.append(rep)
                continue
            d = rel8(at, target)[0]
            data[at + 1] = d
            rep["kind"] = "rel8"
            rep["disp_hex"] = f"{d:02X}"
            rep["ok"] = True
        elif b == 0xE8:
            if not _need(data, at, 3):
                rep["error"] = "truncated (need 3)"
                branch_reports.append(rep)
                continue
            lo, hi = rel16(at, target)
            data[at + 1] = lo
            data[at + 2] = hi
            rep["kind"] = "rel16"
            rep["disp_hex"] = f"{hi:02X}{lo:02X}"
            rep["ok"] = True
        else:
            rep["error"] = f"opcode 0x{b:02X} is not a branch"
        branch_reports.append(rep)

    # 3. Decode the patched image; fail on unknown opcode or truncated tail.
    dec = decode(data)
    decode_ok = (sum(ln for _, ln, _ in dec) == len(data)
                 and not any("FAIL" in t or "truncated" in t
                             for _, _, t in dec))

    # 4. Re-verify branch targets against the patched displacements.
    br = branch_checks(data, checks)

    # 5. Optional byte compare.
    chk = None
    chk_ok = True
    if expected_hex is not None:
        chk = check_detail(data, _hex_or_error(expected_hex))
        chk_ok = chk["ok"]

    # 6. Emit the final DATA block.
    data_block = emit(data)

    gate_ok = (selfloc_report["ok"]
               and all(r["ok"] for r in branch_reports)
               and decode_ok and br["ok"] and chk_ok)

    return {
        "selfloc": selfloc_report,
        "branches": branch_reports,
        "branch_ok": br["ok"],
        "branch": br["checks"],
        "decode_ok": decode_ok,
        "decode": [(off, ln, t) for off, ln, t in dec],
        "check": chk,
        "patched_hex": "".join(f"{b:02X}" for b in data),
        "data_block": data_block,
        "gate_ok": gate_ok,
    }

def _raises(fn, args):
    try:
        fn(*args)
        return False
    except ValueError:
        return True

def selftest():
    """All stage gates against the frozen IRPING image plus v5 coverage."""
    g = list(bytes.fromhex(GOLDEN_HEX))
    d = parse(GOLDEN_DATA)
    e = emit(g)
    dec = decode(g)
    p = patch(g, [(0x19, 0x00), (0x1A, 0x01)])
    c6 = decode([0xC6, 0x46, 0xD8, 0x07])
    checks = [(0x27, 0x0033), (0x2E, 0x0031), (0x33, 0x001F)]
    gk = gate(GOLDEN_HEX, 7, 6, 128, checks, GOLDEN_HEX)
    gw = gate(GOLDEN_HEX, 0, 6, 128, checks, None)
    gu = gate(GOLDEN_HEX, 7, 6, 128, [(0x00, 0x0000)], None)
    gd = gate("0E1F55E800005D8DAE7A0063", 7, 6, 128, [], None)
    gexp = "".join(f"{b:02X}" for b in patch(g, [(0x0C, 0x63)]))
    ge = gate(GOLDEN_HEX, 7, 6, 128, checks, gexp)
    return {
        "parse_61": len(d) == 61 and d[0] == 0x0E and d[-1] == 0xCB,
        "parse_full": d == g,
        "emit_exact": e == GOLDEN_DATA.strip(),
        "emit_roundtrip": parse(e) == g,
        "decode_61": sum(ln for _, ln, _ in dec) == len(g),
        "decode_31": len(dec) == 31,
        "decode_test_si_si": dec[20][2] == "test si,si",
        "decode_out_imm8": decode([0xE6, 0x43])[0][2] == "out 0x43,al",
        "decode_in_imm8": decode([0xE4, 0x40])[0][2] == "in al,0x40",
        "decode_latch_path": ([t for _, _, t in decode(
            [0xE6, 0x43, 0xE4, 0x40, 0xE4, 0x40])] ==
            ["out 0x43,al", "in al,0x40", "in al,0x40"]),
        "decode_b0_latch_setup": ([t for _, _, t in decode(
            [0xB0, 0x00, 0xE6, 0x43, 0xE4, 0x40, 0xE4, 0x40])] ==
            ["mov al,0x00", "out 0x43,al", "in al,0x40", "in al,0x40"]),
        "decode_88_c3": decode([0x88, 0xC3])[0][2] == "mov bl,al",
        "decode_88_46": decode([0x88, 0x46, 0x00])[0][2] == "mov [bp+0x00],al",
        "decode_3a_c3": decode([0x3A, 0xC3])[0][2] == "cmp al,bl",
        "decode_80_fb_00": decode([0x80, 0xFB, 0x00])[0][2] == "cmp bl,0x00",
        "decode_b8_0100": decode([0xB8, 0x01, 0x00])[0][2] == "mov ax,0x0001",
        "decode_inc_si": decode([0x46])[0][2] == "inc si",
        # v5 handler coverage
        "decode_iret": decode([0xCF])[0][2] == "iret",
        "decode_push_ax": decode([0x50])[0][2] == "push ax",
        "decode_pop_ax": decode([0x58])[0][2] == "pop ax",
        "decode_dec_dx": decode([0x4A])[0][2] == "dec dx",
        "decode_push_bp": decode([0x55])[0][2] == "push bp",
        "decode_pop_bp": decode([0x5D])[0][2] == "pop bp",
        "decode_a1_moffs": decode([0xA1, 0x08, 0x00])[0][2] == "mov ax,[0x0008]",
        "decode_a3_moffs": decode([0xA3, 0x08, 0x00])[0][2] == "mov [0x0008],ax",
        "decode_8b_46_d8": decode([0x8B, 0x46, 0xD8])[0][2] == "mov ax,[bp+0xD8]",
        # C6 desync regression: one 4-byte instruction, not four singles
        "decode_c6_unit": (len(c6) == 1 and c6[0][1] == 4
                           and c6[0][2] == "mov [bp+0xD8],0x07"),
        # truncation safety: render, never raise
        "decode_c6_truncated": "truncated" in decode([0xC6, 0x46, 0xD8])[0][2],
        "decode_rel8_truncated": "truncated" in decode([0x74])[0][2],
        "branch_oob_safe": branch_checks([0x74, 0x00], [(5, 0)])["ok"] is False,
        "branch_audit": branch_checks(
            list(bytes.fromhex(GOLDEN_HEX)),
            [(0x27, 0x0033), (0x2E, 0x0031), (0x33, 0x001F)],
        )["ok"],
        "patch_len61": len(p) == 61,
        "patch_19_1A": p[0x19] == 0x00 and p[0x1A] == 0x01,
        "check_good": check(g, g)["ok"],
        "check_drop": check(g[:0x23] + g[0x24:], g)["first_diff"] == 0x23,
        "rel_call": rel16(0x03, 0x0006) == [0x00, 0x00],
        "rel_je": rel8(0x27, 0x0033) == [0x0A],
        "rel_loop": rel8(0x33, 0x001F) == [0xEA],
        "selfloc": selfloc_disp(6, 128) == [0x7A, 0x00],
        "selfloc_full_6": selfloc_full(6, 128)["lea_hex"] == "8DAE7A00",
        "selfloc_full_result": selfloc_full(6, 128)["result_bp"] == 128,
        "check_detail_ok": check_detail(g, g)["ok"],
        "check_detail_drop": check_detail(g[:0x23] + g[0x24:], g)["first_diff"] == 0x23,
        "emit_wrap5_roundtrip": parse(emit(g, wrap=5)) == g,
        "rel8_range_err": _raises(rel8, (0, 200)),
        # tolerant hex input
        "hex_spaced": _hex_or_error("0E 1F") == [0x0E, 0x1F],
        "hex_prefixed": _hex_or_error("0x0E1F") == [0x0E, 0x1F],
        "hex_bad": _raises(_hex_or_error, ("0G",)),
        # v5.1 S4 decode opcodes
        "decode_sub_cx_ax": decode([0x2B, 0xC8])[0][2] == "sub cx,ax",
        "decode_jc_rel8": decode([0x72, 0xFE])[0][2] == "jc 0x0000",
        "decode_mov_ah_al": decode([0x8A, 0xE0])[0][2] == "mov ah,al",
        "branch_jc": branch_checks([0x72, 0xFE], [(0, 0)])["ok"],
        "decode_s4_group": [t for _, _, t in decode(
            [0x2B, 0xC8, 0x72, 0xFE, 0x8A, 0xE0, 0x80, 0xFC, 0x03])] ==
            ["sub cx,ax", "jc 0x0002", "mov ah,al", "cmp ah,0x03"],
        # v5.1 P1 fail-fast decode
        "decode_unknown_halts": (
            len(decode([0x00])) == 1
            and "FAIL" in decode([0x00])[0][2]),
        # v5.3 81 /7 iw decode
        "decode_81_rm_imm16": (
            decode([0x81, 0x7E, 0x00, 0xDC, 0x00])[0][2]
            == "cmp [bp+0x00],0x00DC"),
        "decode_81_r16_imm16": (
            decode([0x81, 0xF8, 0xDC, 0x00])[0][2] == "cmp ax,0x00DC"),
        "decode_81_group_unsupported_halts": (
            "FAIL" in decode([0x81, 0xC1, 0x07, 0x00])[0][2]),
        "decode_80_group_unsupported_halts": (
            "FAIL" in decode([0x80, 0xC1, 0x07])[0][2]),
        "decode_c6_group_unsupported_halts": (
            "FAIL" in decode([0xC6, 0xC9, 0x07])[0][2]),
        # v5.2 composite gate
        "gate_golden_ok": gk["gate_ok"] is True,
        "gate_golden_exact": gk["patched_hex"] == GOLDEN_HEX,
        "gate_golden_data": gk["data_block"] == GOLDEN_DATA.strip(),
        "gate_wrong_site_fails": (gw["gate_ok"] is False
                                   and gw["selfloc"]["error"] is not None),
        "gate_bad_branch_fails": (gu["gate_ok"] is False
                                  and gu["branches"][0]["error"] is not None),
        "gate_decode_fail": (gd["gate_ok"] is False
                             and gd["decode_ok"] is False),
        "gate_expected_mismatch": (ge["gate_ok"] is False
                                   and ge["check"] is not None
                                   and ge["check"]["ok"] is False
                                   and ge["decode_ok"] is True),
    }

def _hex_or_error(txt):
    """Tolerant hex string -> byte list. Whitespace and optional 0x ok."""
    try:
        s = txt.strip()
        if s.lower().startswith("0x"):
            s = s[2:]
        s = re.sub(r'\s+', '', s)
        return list(bytes.fromhex(s))
    except ValueError as exc:
        raise ValueError(f"invalid hex bytes: {exc}")

def main(argv):
    if not argv or argv[0] == "selftest":
        all_pass = True
        for name, ok in selftest().items():
            if not ok:
                all_pass = False
            print(("PASS" if ok else "FAIL"), name)
        print("ALL_PASS", all_pass)
        return

    cmd = argv[0]
    if cmd == "parse":
        data = parse(sys.stdin.read())
        print("".join(f"{b:02X}" for b in data))
    elif cmd in ("decode", "dis"):
        data = parse(sys.stdin.read())
        for off, ln, text in decode(data):
            hx = "".join(f"{b:02X}" for b in data[off:off + ln])
            print(f"{off:04X}: {hx:<9} {text}")
    elif cmd == "emit":
        data = _hex_or_error(argv[1])
        print(emit(data))
    elif cmd == "patch":
        data = parse(sys.stdin.read())
        p = [(int(s.split('=')[0], 0), int(s.split('=')[1], 0)) for s in argv[1:]]
        print(emit(patch(data, p)))
    elif cmd == "check":
        actual = _hex_or_error(argv[1])
        expected = _hex_or_error(argv[2]) if len(argv) > 2 else list(bytes.fromhex(GOLDEN_HEX))
        print(json.dumps(check_detail(actual, expected), indent=2))
    elif cmd == "rel8":
        print(json.dumps(rel8(int(argv[1]), int(argv[2]))))
    elif cmd == "rel16":
        print(json.dumps(rel16(int(argv[1]), int(argv[2]))))
    elif cmd == "selfloc":
        pop = int(argv[1])
        base = int(argv[2]) if len(argv) > 2 else 128
        print(json.dumps(selfloc_full(pop, base), indent=2))
    elif cmd == "branch":
        data = _hex_or_error(argv[1])
        checks = []
        for s in argv[2:]:
            a, t = s.split("=")
            checks.append((int(a, 0), int(t, 0)))
        print(json.dumps(branch_checks(data, checks), indent=2))
    elif cmd == "gate":
        hx = _hex_or_error(argv[1])
        selfloc_at = int(argv[2], 0)
        pop = int(argv[3], 0) if len(argv) > 3 else 6
        base = int(argv[4], 0) if len(argv) > 4 else 128
        checks = []
        for s in argv[5:]:
            a, t = s.split("=")
            checks.append((int(a, 0), int(t, 0)))
        print(json.dumps(gate(hx, selfloc_at, pop, base, checks), indent=2))
    else:
        print("usage: pcjr_asm_debug.py selftest|parse|decode|emit HEX|"
              "patch off=val...|check HEX [REF_HEX]|rel8 I T|rel16 I T|"
              "selfloc POP [BASE]|branch HEX at=target ...|"
              "gate HEX SELFAT [POP] [BASE] [at=target ...]")

if __name__ == "__main__":
    main(sys.argv[1:])
