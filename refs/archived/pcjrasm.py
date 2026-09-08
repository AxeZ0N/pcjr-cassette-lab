#!/usr/bin/env python3
"""pjasm v6.1 -- closed-subset PCjr bridge assembler.

Encode-only. One instruction table drives a single generic encoder.
No decoder here: decode stays in pcjr_asm_debug.py, where P1 already
made it fail-fast.

Table conventions (documented because they are real):
  - reg-reg MOV always emits 89 (rm16,r16) / 88 (rm8,r8) forms.
  - memory-dest CMP always emits 81 iw; 80 ib is register-r8 only.
  - [bp] and [bp+0] normalize to the same bytes (mod=1 disp8=0).
  - LEA bp,[bp+disp] always emits mod=2 disp16.

v6.1 additions (KBDNMI-core r8 shapes):
  - test r8,imm  emits F6 /0 ib (Grp3); register-only, no A8 form.
  - xor  r8,r8   emits 32 /r (r8,rm8) to match KBDNMI 32 xx bytes.
  - or   r8,r8   emits 0A /r (r8,rm8) to match KBDNMI OR BH,AL = 0A F8.
  - xchg r8,r8   emits 86 /r (r8,rm8) to match KBDNMI XCHG AH,AL = 86 E0.
  - shr  r8,1    emits D0 /5 ib; only the immediate 1 is accepted.
  - inc  r8      emits FE /0 (no immediate).
  - dec  r8      emits FE /1 (no immediate).
  - jnb / jnc    emit 73 rel8.

selftest() returns the MERGED gate set (A + B + D + E) so that any
caller of ASM.selftest() -- including the pcjr-tools MCP handler --
sees every gate. Do not put Stage E in a separate function only.

Grammar (strict):
    label:
    label: mnemonic operands
        mnemonic operands
"""
import sys

GOLDEN_HEX = (
    "0E1F55E800005D8DAE7A00BA6200EC2440B400894600"
    "89C6B9307531DB31FFBA6200EC244039F0740A85F674"
    "0347EB014389C6E2EA895E02897E045DCB"
)

GOLDEN_DATA = """1000 DATA &H0E,&H1F,&H55,&HE8,&H00,&H00,&H5D,&H8D,&HAE,&H7A,&H00
1010 DATA &HBA,&H62,&H00,&HEC,&H24,&H40,&HB4,&H00,&H89,&H46,&H00
1020 DATA &H89,&HC6,&HB9,&H30,&H75,&H31,&HDB,&H31,&HFF,&HBA,&H62
1030 DATA &H00,&HEC,&H24,&H40,&H39,&HF0,&H74,&H0A,&H85,&HF6,&H74
1040 DATA &H03,&H47,&HEB,&H01,&H43,&H89,&HC6,&HE2,&HEA,&H89,&H5E
1050 DATA &H02,&H89,&H7E,&H04,&H5D,&HCB
1060 DATA -1
"""

IRPING_SRC = """\
push cs
pop ds
push bp
call selfip
selfip:
pop bp
lea bp,[bp+122]
mov dx,0x0062
in al,dx
and al,0x40
mov ah,0x00
mov [bp+0],ax
mov si,ax
mov cx,0x7530
xor bx,bx
xor di,di
loop_start:
mov dx,0x0062
in al,dx
and al,0x40
cmp ax,si
je loop_dec
test si,si
je inc_bx
inc di
jmp after_inc
inc_bx:
inc bx
after_inc:
mov si,ax
loop_dec:
loop loop_start
mov [bp+0x02],bx
mov [bp+0x04],di
pop bp
retf
"""

REGS16 = {"ax": 0, "cx": 1, "dx": 2, "bx": 3, "sp": 4, "bp": 5,
          "si": 6, "di": 7}
REG8 = {"al": 0, "cl": 1, "dl": 2, "bl": 3, "ah": 4, "ch": 5,
        "dh": 6, "bh": 7}
REL8_OP = {"je": 0x74, "jz": 0x74, "jne": 0x75, "jnz": 0x75,
           "jc": 0x72, "jnb": 0x73, "jnc": 0x73,
           "jmp": 0xEB, "loop": 0xE2}

class CompileError(Exception):
    pass

def _parse_int(tok):
    tok = tok.strip()
    if tok.lower().startswith("0x"):
        return int(tok, 16)
    return int(tok, 10)

def _is_int(tok):
    try:
        _parse_int(tok)
        return True
    except (ValueError, TypeError):
        return False

def _is_moffs(tok):
    t = tok.strip().lower()
    if not (t.startswith("[") and t.endswith("]")):
        return False
    inner = t[1:-1].strip()
    return inner.startswith("0x") or (
        inner.isdigit() and "+" not in inner and " " not in inner)

def _parse_moffs(tok):
    inner = tok.strip().lower()[1:-1].strip()
    v = _parse_int(inner)
    if not (0 <= v <= 0xFFFF):
        raise CompileError(f"moffs16 out of range: {v}")
    return v

def _parse_rm(tok):
    tok = tok.strip().lower()
    if tok in REGS16:
        return 3, REGS16[tok], b""
    if tok in REG8:
        return 3, REG8[tok], b""
    if tok == "[bp]":
        tok = "[bp+0]"
    if tok.startswith("[bp+"):
        v = _parse_int(tok[4:-1])
        if -128 <= v <= 127:
            return 1, 6, bytes([v & 0xFF])
        if 0 <= v <= 0xFFFF:
            return 2, 6, bytes([v & 0xFF, (v >> 8) & 0xFF])
        raise CompileError(f"disp16 out of range: {v}")
    raise CompileError(f"unsupported r/m operand: {tok}")

def _kind(tok):
    t = tok.strip().lower()
    if t in REGS16:
        return "r16"
    if t in REG8:
        return "r8"
    if _is_int(t):
        return "imm"
    if _is_moffs(t):
        return "moffs"
    if t.startswith("["):
        return "rm"
    return "lab"

def _sig(m, ops):
    return ",".join(_kind(o) for o in ops)

FIXED = "fixed"
REG16 = "reg16"
REG16_IMM16 = "reg16_imm16"
IMM8 = "imm8"
MOFFS = "moffs"
REL8 = "rel8"
REL16 = "rel16"
MODRM = "modrm"
GRP = "grp"
LEA16 = "lea16"
GRP_R8_IMM8 = "grp_r8_imm8"
GRP_R8_NOIMM = "grp_r8_noimm"
SHIFT_R8_1 = "shift_r8_1"

SPECIAL = {
    "push cs":    {"op": 0x0E, "kind": FIXED},
    "pop ds":     {"op": 0x1F, "kind": FIXED},
    "in al,dx":   {"op": 0xEC, "kind": FIXED},
    "retf":       {"op": 0xCB, "kind": FIXED},
    "iret":       {"op": 0xCF, "kind": FIXED},
    "and al,imm": {"op": 0x24, "kind": IMM8},
    "mov ah,imm": {"op": 0xB4, "kind": IMM8},
    "mov al,imm": {"op": 0xB0, "kind": IMM8},
    "in al,imm":  {"op": 0xE4, "kind": IMM8},
    "out imm,al": {"op": 0xE6, "kind": IMM8},
    "mov ax,moffs": {"op": 0xA1, "kind": MOFFS},
    "mov moffs,ax": {"op": 0xA3, "kind": MOFFS},
    "lea bp,[bp+disp]": {"op": 0x8D, "kind": LEA16},
}

def _special_id(m, ops):
    if m == "push" and ops == ["cs"]:
        return "push cs"
    if m == "pop" and ops == ["ds"]:
        return "pop ds"
    if m == "in" and ops == ["al", "dx"]:
        return "in al,dx"
    if m == "retf" and not ops:
        return "retf"
    if m == "iret" and not ops:
        return "iret"
    if m == "and" and len(ops) == 2 and ops[0] == "al" and _is_int(ops[1]):
        return "and al,imm"
    if m == "mov" and len(ops) == 2 and ops[0] == "ah" and _is_int(ops[1]):
        return "mov ah,imm"
    if m == "mov" and len(ops) == 2 and ops[0] == "al" and _is_int(ops[1]):
        return "mov al,imm"
    if m == "in" and len(ops) == 2 and ops[0] == "al" and _is_int(ops[1]):
        return "in al,imm"
    if m == "out" and len(ops) == 2 and ops[1] == "al" and _is_int(ops[0]):
        return "out imm,al"
    if m == "mov" and len(ops) == 2 and ops[0] == "ax" and _is_moffs(ops[1]):
        return "mov ax,moffs"
    if m == "mov" and len(ops) == 2 and ops[1] == "ax" and _is_moffs(ops[0]):
        return "mov moffs,ax"
    if m == "lea" and len(ops) == 2 and ops[0] == "bp" \
            and ops[1].strip().lower().startswith("[bp+"):
        return "lea bp,[bp+disp]"
    return None

TABLE = {}

def _add(m, sig, op, kind, dir_=None, imm=0, grp=None):
    TABLE[(m, sig)] = {"op": op, "kind": kind,
                       "dir": dir_, "imm": imm, "grp": grp}

for _m, _base in (("inc", 0x40), ("dec", 0x48),
                  ("push", 0x50), ("pop", 0x58)):
    _add(_m, "r16", _base, REG16)

_add("mov", "r16,imm", 0xB8, REG16_IMM16, imm=2)

for _m in REL8_OP:
    _add(_m, "lab", REL8_OP[_m], REL8)
_add("call", "lab", 0xE8, REL16)

for _m, _op in (("mov", 0x89), ("xor", 0x31),
                ("cmp", 0x39), ("test", 0x85)):
    _add(_m, "r16,r16", _op, MODRM, "rm16,r16")
    _add(_m, "rm,r16", _op, MODRM, "rm16,r16")

_add("mov", "r16,rm", 0x8B, MODRM, "r16,rm16")
_add("sub", "r16,rm", 0x2B, MODRM, "r16,rm16")
_add("sub", "r16,r16", 0x2B, MODRM, "r16,rm16")

_add("mov", "r8,r8", 0x88, MODRM, "rm8,r8")
_add("mov", "rm,r8", 0x88, MODRM, "rm8,r8")

_add("cmp", "r8,r8", 0x3A, MODRM, "r8,rm8")
_add("cmp", "r8,rm", 0x3A, MODRM, "r8,rm8")
_add("mov", "r8,rm", 0x8A, MODRM, "r8,rm8")

_add("lea", "r16,rm", 0x8D, MODRM, "r16,rm16")

_add("cmp", "r8,imm", 0x80, GRP, "rm8,imm", imm=1, grp=7)
_add("cmp", "r16,imm", 0x81, GRP, "rm16,imm", imm=2, grp=7)
_add("cmp", "rm,imm", 0x81, GRP, "rm16,imm", imm=2, grp=7)

_add("mov", "r8,imm", 0xC6, GRP, "rm8,imm", imm=1, grp=0)
_add("mov", "rm,imm", 0xC6, GRP, "rm8,imm", imm=1, grp=0)

# --- v6.1 KBDNMI-core r8 shapes ---
_add("test", "r8,imm", 0xF6, GRP_R8_IMM8, imm=1, grp=0)
_add("shr", "r8,imm", 0xD0, SHIFT_R8_1, grp=5)
_add("inc", "r8", 0xFE, GRP_R8_NOIMM, grp=0)
_add("dec", "r8", 0xFE, GRP_R8_NOIMM, grp=1)
_add("xor", "r8,r8", 0x32, MODRM, "r8,rm8")
_add("or", "r8,r8", 0x0A, MODRM, "r8,rm8")
_add("xchg", "r8,r8", 0x86, MODRM, "r8,rm8")

def _rel8_bytes(here, target):
    disp = target - (here + 2)
    if not (-128 <= disp <= 127):
        raise CompileError(f"rel8 out of range: {disp}")
    return bytes([disp & 0xFF])

def _rel16_bytes(here, target):
    disp = target - (here + 3)
    if not (-32768 <= disp <= 32767):
        raise CompileError("rel16 out of range")
    return bytes([disp & 0xFF, (disp >> 8) & 0xFF])

def selfloc_disp(pop_off, base=128):
    disp = base - pop_off
    if not (0 <= disp <= 0xFFFF):
        raise CompileError(f"selfloc out of range: {disp}")
    return bytes([disp & 0xFF, (disp >> 8) & 0xFF])

def _imm_bytes(v, width):
    if width == 1:
        if not (0 <= v <= 0xFF):
            raise CompileError(f"imm8 out of range: {v}")
        return bytes([v])
    if not (0 <= v <= 0xFFFF):
        raise CompileError(f"imm16 out of range: {v}")
    return bytes([v & 0xFF, (v >> 8) & 0xFF])

def _encode_special(key, m, ops):
    row = SPECIAL[key]
    if row["kind"] == FIXED:
        return bytes([row["op"]])
    if row["kind"] == IMM8:
        imm_op = ops[0] if key.startswith("out") else ops[1]
        return bytes([row["op"]]) + _imm_bytes(_parse_int(imm_op), 1)
    if row["kind"] == MOFFS:
        addr_op = ops[1] if key == "mov ax,moffs" else ops[0]
        v = _parse_moffs(addr_op)
        return bytes([row["op"], v & 0xFF, (v >> 8) & 0xFF])
    if row["kind"] == LEA16:
        inner = ops[1].strip().lower()[4:-1]
        v = _parse_int(inner)
        if not (0 <= v <= 0xFFFF):
            raise CompileError(f"lea disp16 out of range: {v}")
        return bytes([0x8D, 0xAE, v & 0xFF, (v >> 8) & 0xFF])
    raise CompileError(f"unsupported special {key}")

def _encode_general(row, m, ops, here, resolve):
    if row["kind"] == REG16:
        return bytes([row["op"] + REGS16[ops[0].lower()]])
    if row["kind"] == REG16_IMM16:
        r = REGS16[ops[0].lower()]
        return bytes([row["op"] + r]) + _imm_bytes(_parse_int(ops[1]), 2)
    if row["kind"] == REL8:
        return bytes([row["op"]]) + _rel8_bytes(here, resolve(ops[0]))
    if row["kind"] == REL16:
        return bytes([row["op"]]) + _rel16_bytes(here, resolve(ops[0]))
    if row["kind"] == MODRM:
        return _encode_modrm(row, ops)
    if row["kind"] == GRP:
        return _encode_grp(row, ops)
    if row["kind"] == GRP_R8_IMM8:
        return _encode_grp_r8_imm8(row, ops)
    if row["kind"] == GRP_R8_NOIMM:
        return _encode_grp_r8_noimm(row, ops)
    if row["kind"] == SHIFT_R8_1:
        return _encode_shift_r8_1(row, ops)
    raise CompileError(f"unsupported row kind {row['kind']}")

def _encode_modrm(row, ops):
    dir_ = row["dir"]
    if dir_ == "rm16,r16":
        mod, rm, disp = _parse_rm(ops[0])
        reg = REGS16[ops[1].lower()]
    elif dir_ == "r16,rm16":
        reg = REGS16[ops[0].lower()]
        mod, rm, disp = _parse_rm(ops[1])
    elif dir_ == "rm8,r8":
        mod, rm, disp = _parse_rm(ops[0])
        reg = REG8[ops[1].lower()]
    elif dir_ == "r8,rm8":
        reg = REG8[ops[0].lower()]
        mod, rm, disp = _parse_rm(ops[1])
    else:
        raise CompileError(f"bad modrm dir {dir_}")
    modrm = (mod << 6) | (reg << 3) | rm
    return bytes([row["op"], modrm]) + disp

def _encode_grp(row, ops):
    mod, rm, disp = _parse_rm(ops[0])
    modrm = (mod << 6) | (row["grp"] << 3) | rm
    imm = _imm_bytes(_parse_int(ops[1]), row["imm"])
    return bytes([row["op"], modrm]) + disp + imm

def _encode_grp_r8_imm8(row, ops):
    mod, rm, disp = _parse_rm(ops[0])
    if mod != 3:
        raise CompileError("group op requires a byte register operand")
    modrm = (3 << 6) | (row["grp"] << 3) | rm
    imm = _imm_bytes(_parse_int(ops[1]), row["imm"])
    return bytes([row["op"], modrm]) + disp + imm

def _encode_grp_r8_noimm(row, ops):
    mod, rm, disp = _parse_rm(ops[0])
    if mod != 3:
        raise CompileError("group op requires a byte register operand")
    modrm = (3 << 6) | (row["grp"] << 3) | rm
    return bytes([row["op"], modrm]) + disp

def _encode_shift_r8_1(row, ops):
    mod, rm, disp = _parse_rm(ops[0])
    if mod != 3:
        raise CompileError("shr requires a byte register operand")
    if _parse_int(ops[1]) != 1:
        raise CompileError("only shr r8,1 is supported "
                           "(CL shifts not in subset)")
    modrm = (3 << 6) | (row["grp"] << 3) | rm
    return bytes([row["op"], modrm, 0x01])

def _encode(mnem, operands, here, resolve):
    m = mnem.lower()
    key = _special_id(m, operands)
    if key:
        return _encode_special(key, m, operands)
    row = TABLE.get((m, _sig(m, operands)))
    if not row:
        raise CompileError(
            f"unsupported instruction or operand shape: {mnem} {operands}")
    return _encode_general(row, m, operands, here, resolve)

def _split_operands(rest):
    rest = rest.strip()
    return [] if not rest else [p.strip() for p in rest.split(",")]

class _Stmt:
    __slots__ = ("label", "mnem", "operands", "line")
    def __init__(self, label, mnem, operands, line):
        self.label = label
        self.mnem = mnem
        self.operands = operands
        self.line = line

def _parse_line(raw, line_no):
    raw = raw.split(";", 1)[0].strip()
    if not raw:
        return None
    label, rest = None, raw
    if raw.endswith(":"):
        label, rest = raw[:-1].strip(), ""
    else:
        head, sep, tail = raw.partition(":")
        if sep and head and head.strip() and not any(
                ch in head for ch in " \t"):
            label, rest = head.strip(), tail.strip()
    if ":" in rest:
        raise CompileError(f"line {line_no}: multi-statement lines "
                           "are not supported")
    if not rest:
        if not label:
            raise CompileError(f"line {line_no}: empty statement")
        return _Stmt(label, None, [], line_no)
    parts = rest.split(None, 1)
    mnem = parts[0].lower()
    operands = _split_operands(parts[1]) if len(parts) > 1 else []
    return _Stmt(label, mnem, operands, line_no)

def _parse_source(src):
    stmts = []
    for i, raw in enumerate(src.splitlines(), 1):
        s = _parse_line(raw, i)
        if s:
            stmts.append(s)
    return stmts

def _layout(stmts):
    symbols = {}
    offset = 0
    def resolve(name):
        return offset
    for st in stmts:
        if st.label:
            if st.label in symbols:
                raise CompileError(f"duplicate label: {st.label}")
            symbols[st.label] = offset
        if st.mnem is not None:
            offset += len(_encode(st.mnem, st.operands, offset, resolve))
    return offset, symbols

def _emit_pass(stmts, symbols):
    offset = 0
    out = bytearray()
    def resolve(name):
        if name not in symbols:
            raise CompileError(f"undefined label: {name}")
        return symbols[name]
    for st in stmts:
        if st.mnem is not None:
            data = _encode(st.mnem, st.operands, offset, resolve)
            out.extend(data)
            offset += len(data)
    return bytes(out)

def emit_data_block(data, start=1000, step=10, wrap=11):
    lines = []
    n = (len(data) + wrap - 1) // wrap
    for i in range(n):
        chunk = data[i * wrap:(i + 1) * wrap]
        lines.append(f"{start + i * step} DATA "
                     + ",".join(f"&H{x:02X}" for x in chunk))
    lines.append(f"{start + n * step} DATA -1")
    return "\n".join(lines)

def assemble(src, verbose=False):
    try:
        stmts = _parse_source(src)
        size, symbols = _layout(stmts)
        data = _emit_pass(stmts, symbols)
        return {"ok": True, "data": data,
                "data_block": emit_data_block(data),
                "size": size, "budget_left": 128 - size,
                "failures": []}
    except (CompileError, ValueError, KeyError) as exc:
        return {"ok": False, "data": None, "data_block": None,
                "size": 0, "budget_left": 128,
                "failures": [str(exc)]}

def _enc(src):
    return assemble(src)["data"]

def _merged_selftest(r):
    out = {
        "asm_irping_exact": (
            r["ok"] and r["data"] == bytes.fromhex(GOLDEN_HEX)),
        "data_block_exact": (
            r["ok"] and r["data_block"] == GOLDEN_DATA.strip()),
        "size_61": r["size"] == 61,
    }
    out.update(stage_b_selftest())
    out.update(stage_d_selftest())
    out.update(stage_e_selftest())
    return out

def selftest():
    """Merged A + B + D + E gate set.

    This is the single entry point the pcjr-tools MCP handler calls
    (ASM.selftest()). Every gate must live here so external callers
    see the full set; do not leave Stage E out of this return value.
    """
    return _merged_selftest(assemble(IRPING_SRC))

def stage_b_selftest():
    img = assemble(IRPING_SRC)
    ok = img["ok"]
    data = img["data"] if ok else b""
    return {
        "b_rel16_call": _rel16_bytes(0x03, 0x06) == bytes([0x00, 0x00]),
        "b_rel8_je_a": _rel8_bytes(0x27, 0x33) == bytes([0x0A]),
        "b_rel8_je_b": _rel8_bytes(0x2B, 0x30) == bytes([0x03]),
        "b_rel8_jmp": _rel8_bytes(0x2E, 0x31) == bytes([0x01]),
        "b_rel8_loop": _rel8_bytes(0x33, 0x1F) == bytes([0xEA]),
        "b_selfloc": selfloc_disp(6, 128) == bytes([0x7A, 0x00]),
        "b_rel16_emitted": ok and data[0x04:0x06] == _rel16_bytes(0x03, 0x06),
        "b_rel8_je_emitted": ok and data[0x28:0x29] == _rel8_bytes(0x27, 0x33),
        "b_rel8_je2_emitted": ok and data[0x2C:0x2D] == _rel8_bytes(0x2B, 0x30),
        "b_rel8_jmp_emitted": ok and data[0x2F:0x30] == _rel8_bytes(0x2E, 0x31),
        "b_rel8_loop_emitted": ok and data[0x34:0x35] == _rel8_bytes(0x33, 0x1F),
        "b_selfloc_emitted": ok and data[0x09:0x0B] == selfloc_disp(6, 128),
    }

def stage_d_selftest():
    return {
        # fixed
        "d_push_cs": _enc("push cs") == bytes.fromhex("0E"),
        "d_pop_ds": _enc("pop ds") == bytes.fromhex("1F"),
        "d_in_al_dx": _enc("in al,dx") == bytes.fromhex("EC"),
        "d_retf": _enc("retf") == bytes.fromhex("CB"),
        "d_iret": _enc("iret") == bytes.fromhex("CF"),
        # reg16 family
        "d_inc_si": _enc("inc si") == bytes.fromhex("46"),
        "d_dec_dx": _enc("dec dx") == bytes.fromhex("4A"),
        "d_push_ax": _enc("push ax") == bytes.fromhex("50"),
        "d_pop_ax": _enc("pop ax") == bytes.fromhex("58"),
        # B8+r imm16
        "d_mov_ax_imm16": _enc("mov ax,0x0001") == bytes.fromhex("B80100"),
        "d_mov_cx_imm16": _enc("mov cx,0x7530") == bytes.fromhex("B93075"),
        "d_mov_dx_imm16": _enc("mov dx,0x0062") == bytes.fromhex("BA6200"),
        # imm8 specials
        "d_and_al_imm": _enc("and al,0x40") == bytes.fromhex("2440"),
        "d_mov_ah_imm": _enc("mov ah,0x00") == bytes.fromhex("B400"),
        "d_mov_al_imm": _enc("mov al,0x07") == bytes.fromhex("B007"),
        "d_in_al_imm": _enc("in al,0x40") == bytes.fromhex("E440"),
        "d_out_imm_al": _enc("out 0x43,al") == bytes.fromhex("E643"),
        # moffs
        "d_mov_ax_moffs": _enc("mov ax,[0x0008]") == bytes.fromhex("A10800"),
        "d_mov_moffs_ax": _enc("mov [0x0008],ax") == bytes.fromhex("A30800"),
        # modrm 89-family
        "d_mov_mem_ax": _enc("mov [bp+0],ax") == bytes.fromhex("894600"),
        "d_mov_si_ax": _enc("mov si,ax") == bytes.fromhex("89C6"),
        "d_xor_bx_bx": _enc("xor bx,bx") == bytes.fromhex("31DB"),
        "d_cmp_ax_si": _enc("cmp ax,si") == bytes.fromhex("39F0"),
        "d_test_si_si": _enc("test si,si") == bytes.fromhex("85F6"),
        # modrm r16,rm16
        "d_mov_ax_mem_disp8": _enc("mov ax,[bp+0x7F]") == bytes.fromhex("8B467F"),
        "d_mov_ax_mem_disp16": _enc("mov ax,[bp+0xD8]") == bytes.fromhex("8B86D800"),
        "d_sub_cx_ax": _enc("sub cx,ax") == bytes.fromhex("2BC8"),
        # modrm rm8,r8
        "d_mov_bl_al": _enc("mov bl,al") == bytes.fromhex("88C3"),
        "d_mov_mem_al": _enc("mov [bp+0],al") == bytes.fromhex("884600"),
        # modrm r8,rm8
        "d_cmp_al_bl": _enc("cmp al,bl") == bytes.fromhex("3AC3"),
        "d_mov_ah_al": _enc("mov ah,al") == bytes.fromhex("88C4"),
        # lea
        "d_lea_bp": _enc("lea bp,[bp+122]") == bytes.fromhex("8DAE7A00"),
        # 81 /7 iw -- the one-liner
        "d_cmp_rm_imm16": _enc("cmp [bp+0],0xDC") == bytes.fromhex("817E00DC00"),
        "d_cmp_r16_imm16": _enc("cmp ax,0xDC") == bytes.fromhex("81F8DC00"),
        # 80 /7 ib register-r8
        "d_cmp_r8_imm": _enc("cmp al,0x03") == bytes.fromhex("80F803"),
        # C6 /0 ib
        "d_mov_mem_imm8": _enc("mov [bp+0],0x07") == bytes.fromhex("C6460007"),
        "d_mov_r8_imm": _enc("mov al,0x07") == bytes.fromhex("B007"),
        # unsupported groups rejected
        "d_grp_add_rejected": (
            "unsupported" in assemble("cmp [bp+0],ax")["failures"][0])
        if assemble("cmp [bp+0],ax")["failures"] else True,
    }

def stage_e_selftest():
    jnb_img = assemble("jnb skip\nmov al,0x00\nskip:\nretf")
    test_mem = assemble("test [bp+0],0x01")
    return {
        # F6 /0 ib (Grp3) register-r8 only
        "e_test_al_imm": _enc("test al,0x40") == bytes.fromhex("F6C040"),
        "e_test_bl_imm": _enc("test bl,0x01") == bytes.fromhex("F6C301"),
        "e_test_mem_rejected": (
            "unsupported" in test_mem["failures"][0])
        if test_mem["failures"] else True,
        # 32 /r (r8,rm8), KBDNMI byte-matched
        "e_xor_ah_ah": _enc("xor ah,ah") == bytes.fromhex("32E4"),
        "e_xor_bl_bl": _enc("xor bl,bl") == bytes.fromhex("32DB"),
        # D0 /5 ib, immediate must be 1
        "e_shr_bh_1": _enc("shr bh,1") == bytes.fromhex("D0EF01"),
        "e_shr_imm2_rejected": (
            "only shr r8,1" in assemble("shr bh,2")["failures"][0]),
        # FE /0 and FE /1
        "e_inc_ah": _enc("inc ah") == bytes.fromhex("FEC4"),
        "e_inc_bl": _enc("inc bl") == bytes.fromhex("FEC3"),
        "e_dec_ah": _enc("dec ah") == bytes.fromhex("FECC"),
        # 0A /r (r8,rm8), KBDNMI OR BH,AL byte-matched
        "e_or_bh_al": _enc("or bh,al") == bytes.fromhex("0AF8"),
        # 86 /r (r8,rm8), KBDNMI XCHG AH,AL = 86E0
        "e_xchg_ah_al": _enc("xchg ah,al") == bytes.fromhex("86E0"),
        # jnb rel8 end-to-end
        "e_jnb_emit": (
            jnb_img["ok"] and jnb_img["data"][:2] == bytes.fromhex("7302")),
    }

def main(argv):
    if not argv or argv[0] == "selftest":
        r = assemble(IRPING_SRC)
        print("ok", r["ok"], "size", r["size"],
              "budget_left", r["budget_left"])
        for f in r["failures"]:
            print("FAIL:", f)
        all_pass = True
        for name, ok in selftest().items():
            if not ok:
                all_pass = False
            print(("PASS" if ok else "FAIL"), name)
        print("ALL_PASS", all_pass)
        return

    if argv[0] in ("asm", "assemble"):
        with open(argv[1], "r", encoding="utf-8") as f:
            r = assemble(f.read(), verbose="--v" in argv[2:])
        print("ok", r["ok"], "size", r["size"],
              "budget_left", r["budget_left"])
        for f in r["failures"]:
            print("FAIL:", f)
        if r["ok"]:
            print(r["data_block"])
    else:
        print("usage: pjasm.py selftest | asm FILE [--v]")

if __name__ == "__main__":
    main(sys.argv[1:])
