#!/usr/bin/env python3
"""
jr - PCjr bridge byte pipeline (v2).

Pure, importable API functions (Section 5) plus a thin CLI wrapper.
All functions are stateless, operate on strings, and raise JrError on failure.
"""

import sys
import os
import subprocess
import tempfile
import argparse
import json
import re
from pathlib import Path

# ----------------------------------------------------------------------
# Exception
# ----------------------------------------------------------------------

class JrError(Exception):
    """Exception carrying an exit code matching the CLI exit codes."""
    def __init__(self, message, exit_code=1):
        super().__init__(message)
        self.exit_code = exit_code


# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------

RULES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jr_rules.json")
LOADER_TEMPLATE = """\
10 DEFINT A-Z
20 DIM A(__DIM__)
30 I = 0 : O = 0 : X$ = "" : B = 0 : D = 0
40 ST = 0 : RI = 0 : FA = 0
50 I = 0
60 READ D
70 IF D = -1 THEN 110
80 POKE VARPTR(A(0)) + I, D
90 I = I + 1
100 GOTO 60
110 PRINT "Loaded "; I; " bytes. Press Enter to CALL..."
120 INPUT X$
130 O = VARPTR(A(0))
140 CALL O
150 PRINT "RETURNED OK"
160 ST = PEEK(VARPTR(A(0)) + __RESULT__)
170 RI = PEEK(VARPTR(A(0)) + __RESULT__ + 2) + 256! * PEEK(VARPTR(A(0)) + __RESULT__ + 3)
180 FA = PEEK(VARPTR(A(0)) + __RESULT__ + 4) + 256! * PEEK(VARPTR(A(0)) + __RESULT__ + 5)
190 PRINT "status="; ST; " rising="; RI; " falling="; FA
200 END
"""


# ----------------------------------------------------------------------
# Hex / byte utilities
# ----------------------------------------------------------------------

def hex_to_bytes(hexstr: str) -> bytes:
    """Convert a hex string (with possible separators, &H, 0x) to bytes."""
    # Remove common prefixes first, then any other non-hex chars
    cleaned = re.sub(r'(&[hH]|0[xX])', '', hexstr)
    cleaned = re.sub(r'[^0-9a-fA-F]', '', cleaned)
    if len(cleaned) % 2 != 0:
        raise JrError(f"Odd-length hex string: {hexstr}", exit_code=1)
    return bytes.fromhex(cleaned)

def bytes_to_hex(b: bytes) -> str:
    """Convert bytes to uppercase hex string without separators."""
    return b.hex().upper()

def normalize_pattern(p: str) -> bytes:
    """Normalize a pattern string (e.g. '0E1F55') to bytes."""
    return hex_to_bytes(p)

def find_all_occurrences(data: bytes, pattern: bytes):
    """Yield starting offsets of all (overlapping) occurrences."""
    start = 0
    while True:
        idx = data.find(pattern, start)
        if idx == -1:
            break
        yield idx
        start = idx + 1

def count_occurrences(data: bytes, pattern: bytes) -> int:
    """Count occurrences (overlapping allowed)."""
    return sum(1 for _ in find_all_occurrences(data, pattern))

def first_occurrence(data: bytes, pattern: bytes) -> int:
    """Return offset of first occurrence or -1."""
    idx = data.find(pattern)
    return idx

def format_bytes_as_hex(b: bytes) -> str:
    """Format bytes as space-separated hex (for messages)."""
    return ' '.join(f'{x:02X}' for x in b)


# ----------------------------------------------------------------------
# Rule loading (with robust error handling)
# ----------------------------------------------------------------------

def load_config(path=None):
    """Load and validate the v2 config object. Returns the whole object."""
    cfg_path = path if path is not None else RULES_FILE
    try:
        with open(cfg_path, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        raise JrError(f"Config file not found: {cfg_path}", exit_code=1)
    except json.JSONDecodeError as e:
        raise JrError(f"Invalid JSON in config {cfg_path}: {e}", exit_code=1)
    except OSError as e:
        raise JrError(f"Cannot read config {cfg_path}: {e}", exit_code=1)

    if config.get("version") != 2:
        raise JrError("Only jr_rules.json v2 is supported", exit_code=1)

    rules = config.get("rules", [])
    if not isinstance(rules, list):
        raise JrError("config.rules must be a list", exit_code=1)

    rule_index = {}
    for rule in rules:
        rid = rule.get("id")
        if not rid:
            raise JrError("config rule missing id", exit_code=1)
        if rid in rule_index:
            raise JrError(f"duplicate rule id: {rid}", exit_code=1)
        rule_index[rid] = rule

    groups = config.get("groups", {})
    if not isinstance(groups, dict):
        raise JrError("config.groups must be an object", exit_code=1)
    for gname, members in groups.items():
        if not isinstance(members, list):
            raise JrError(f"group {gname} must be a list", exit_code=1)

    def check_id(rid, where):
        if rid in groups:
            raise JrError(
                f"group name '{rid}' used as rule id in {where}; "
                f"groups are CLI-only sugar (members: {groups[rid]})",
                exit_code=1,
            )
        if rid not in rule_index:
            raise JrError(f"unknown rule id '{rid}' in {where}", exit_code=1)

    shapes = config.get("shapes", {})
    if not isinstance(shapes, dict):
        raise JrError("config.shapes must be an object", exit_code=1)
    for shape_name, shape in shapes.items():
        for rid in shape.get("rules", []):
            check_id(rid, f"shape {shape_name}.rules")
        for stage_key, preset in shape.get("stage_presets", {}).items():
            for rid in preset:
                check_id(rid, f"shape {shape_name}.stage_presets.{stage_key}")

    for gname, members in groups.items():
        for rid in members:
            if rid not in rule_index:
                raise JrError(f"unknown rule id '{rid}' in group {gname}", exit_code=1)

    return config

def _expand_tokens(tokens, config):
    """Expand group tokens in only/skip; return set of rule ids."""
    groups = config.get("groups", {})
    out = set()
    for tok in tokens:
        if tok in groups:
            out.update(groups[tok])
        else:
            out.add(tok)
    return out

def resolve_rules(config, shape="bridge", stage=None, only=None, skip=None):
    """Return the ordered active rule list for shape/stage after filtering."""
    shapes = config.get("shapes", {})
    if shape not in shapes:
        raise JrError(f"unknown shape: {shape}", exit_code=1)
    shape_obj = shapes[shape]
    rule_index = {r["id"]: r for r in config.get("rules", [])}

    if shape == "bridge":
        if stage is None:
            stage = 6
        preset_key = str(stage)
        presets = shape_obj.get("stage_presets", {})
        if preset_key not in presets:
            raise JrError(f"bridge stage preset {preset_key} missing", exit_code=1)
        ordered_ids = list(presets[preset_key])
    else:
        if stage is not None:
            raise JrError("--stage is valid only for shape=bridge", exit_code=1)
        ordered_ids = list(shape_obj.get("rules", []))

    if only is not None:
        only_ids = _expand_tokens(only, config)
        ordered_ids = [rid for rid in ordered_ids if rid in only_ids]
    if skip is not None:
        skip_ids = _expand_tokens(skip, config)
        ordered_ids = [rid for rid in ordered_ids if rid not in skip_ids]

    return [rule_index[rid] for rid in ordered_ids]

def _mnemonic_matches(insn, mnemonic, operand_sub):
    """insn is (mnemonic, operands). Match mnemonic and optional operand substring."""
    im, iop = insn
    if im != mnemonic:
        return False
    if operand_sub:
        return operand_sub in iop
    return True

def check_prefix(rule, data, decoded, ceiling, R):
    pattern = normalize_pattern(rule["pattern"])
    severity = rule.get("severity", "error")
    if not data.startswith(pattern):
        prefix_len = min(len(pattern), len(data))
        actual_prefix = data[:prefix_len]
        msg = rule["message"].format(prefix=bytes_to_hex(actual_prefix))
        return False, (severity == "warn"), msg
    return True, False, None

def check_suffix(rule, data, decoded, ceiling, R):
    pattern = normalize_pattern(rule["pattern"])
    severity = rule.get("severity", "error")
    cond_hexes = rule.get("config", {}).get("cond", [])
    if cond_hexes:
        inactive = True
        for ch in cond_hexes:
            if normalize_pattern(ch) in data:
                inactive = False
                break
        if inactive:
            return True, False, None
    if not data.endswith(pattern):
        suffix_len = min(len(pattern), len(data))
        actual_suffix = data[-suffix_len:] if suffix_len > 0 else b''
        msg = rule["message"].format(suffix=bytes_to_hex(actual_suffix))
        return False, (severity == "warn"), msg
    return True, False, None

def check_opcode_count(rule, data, decoded, ceiling, R):
    mnemonic = rule["mnemonic"]
    operand_sub = rule.get("operand")
    op = rule.get("op", "eq")
    value = rule.get("value", 1)
    severity = rule.get("severity", "error")
    actual_count = sum(1 for insn in decoded if _mnemonic_matches(insn, mnemonic, operand_sub))
    if op == "eq":
        ok = (actual_count == value)
    elif op == "le":
        ok = (actual_count <= value)
    elif op == "ge":
        ok = (actual_count >= value)
    else:
        raise JrError(f"Unknown op {op} in opcode-count rule {rule['id']}", exit_code=1)
    if not ok:
        msg = rule["message"].format(count=actual_count)
        return False, (severity == "warn"), msg
    return True, False, None

def check_opcode_absent(rule, data, decoded, ceiling, R):
    mnemonic = rule["mnemonic"]
    operand_sub = rule.get("operand")
    severity = rule.get("severity", "error")
    for insn in decoded:
        if _mnemonic_matches(insn, mnemonic, operand_sub):
            return False, (severity == "warn"), rule["message"]
    return True, False, None

def check_before(rule, data, decoded, ceiling, R):
    severity = rule.get("severity", "error")
    config = rule["config"]
    a_raw = config["a"]
    a_patterns = [normalize_pattern(x) for x in (a_raw if isinstance(a_raw, list) else [a_raw])]
    b_patterns = [normalize_pattern(b) for b in config["b"]]
    first_b_off = -1
    first_b_hex = None
    for b_pat, b_hex in zip(b_patterns, config["b"]):
        idx = first_occurrence(data, b_pat)
        if idx != -1 and (first_b_off == -1 or idx < first_b_off):
            first_b_off = idx
            first_b_hex = b_hex
    if first_b_off == -1:
        return True, False, None
    a_before = False
    for a_pat in a_patterns:
        idx = first_occurrence(data, a_pat)
        if idx != -1 and idx < first_b_off:
            a_before = True
            break
    if not a_before:
        msg = rule["message"].format(b_hex=first_b_hex)
        return False, (severity == "warn"), msg
    return True, False, None

def check_selfloc(rule, data, decoded, ceiling, R):
    severity = rule.get("severity", "error")
    marker = bytes.fromhex("E800005D")
    idx = data.find(marker)
    if idx == -1:
        return False, (severity == "warn"), "selfloc marker (call get_ip / pop bp) not found"
    lea_opcode_off = idx + len(marker)
    if lea_opcode_off >= len(data):
        return False, (severity == "warn"), "selfloc: truncated after marker"
    if data[lea_opcode_off] != 0x8D:
        return False, (severity == "warn"), f"selfloc: expected LEA opcode 8D after marker, found {data[lea_opcode_off]:02X}"
    modrm_off = lea_opcode_off + 1
    if modrm_off >= len(data):
        return False, (severity == "warn"), "selfloc: missing ModRM byte"
    modrm = data[modrm_off]
    if modrm == 0x6E:
        disp_len = 1
    elif modrm == 0xAE:
        disp_len = 2
    else:
        return False, (severity == "warn"), f"selfloc: unexpected ModRM byte {modrm:02X} at offset {modrm_off}"
    disp_bytes = data[modrm_off+1 : modrm_off+1+disp_len]
    if len(disp_bytes) < disp_len:
        return False, (severity == "warn"), f"selfloc: truncated disp at offset {modrm_off+1}"
    if disp_len == 1:
        disp = disp_bytes[0]
        if disp & 0x80:
            disp -= 256
        encoding = "disp8"
    else:
        disp = int.from_bytes(disp_bytes, 'little', signed=True)
        encoding = "disp16"
    allowed_encodings = rule.get("config", {}).get("encodings", ["disp8", "disp16"])
    if encoding not in allowed_encodings:
        return False, (severity == "warn"), f"selfloc: encoding {encoding} not allowed"
    entry = idx + 3
    expected_disp = R - entry
    found_r = entry + disp
    if disp != expected_disp:
        msg = rule["message"].format(found_disp=disp, found_r=found_r,
                                      expected_disp=expected_disp)
        return False, (severity == "warn"), msg
    return True, False, None

def check_budget(rule, data, decoded, ceiling, R):
    severity = rule.get("severity", "error")
    found_size = len(data)
    if found_size > ceiling:
        msg = rule["message"].format(found_size=found_size, ceiling=ceiling)
        return False, (severity == "warn"), msg
    return True, False, None

CHECKERS = {
    "prefix": check_prefix,
    "suffix": check_suffix,
    "opcode-count": check_opcode_count,
    "opcode-absent": check_opcode_absent,
    "before": check_before,
    "selfloc": check_selfloc,
    "budget": check_budget,
}

def check_rule(rule, data, decoded, ceiling, R):
    """Dispatch a single rule to its checker. Returns (ok, is_warning, message)."""
    checker = CHECKERS.get(rule.get("kind"))
    if checker is None:
        raise JrError(f"Unknown rule kind: {rule.get('kind')}", exit_code=1)
    return checker(rule, data, decoded, ceiling, R)

# UASM self-test (with missing executable catch)
# ----------------------------------------------------------------------

def uasm_self_test(uasm_path: str, cache_dir: str) -> bool:
    """Perform one-time UASM padding check. Returns True if OK."""
    cache_file = os.path.join(cache_dir, "uasm_ok")
    if os.path.exists(cache_file):
        return True

    asm_src = """\
option casemap:none
option segment:use16

code segment
    assume cs:code
    org 0
start:
    retf
code ends
end start
"""
    with tempfile.TemporaryDirectory() as td:
        tmp_asm = os.path.join(td, "test.asm")
        tmp_bin = os.path.join(td, "test.bin")
        tmp_lst = os.path.join(td, "test.lst")

        with open(tmp_asm, "w") as f:
            f.write(asm_src)

        try:
            proc = subprocess.run(
                [uasm_path, "-bin", f"-Fl={tmp_lst}", "-Fo", tmp_bin, tmp_asm],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return False

        if proc.returncode != 0:
            return False

        with open(tmp_bin, "rb") as f:
            b = f.read()
        if len(b) != 1 or b[0] != 0xCB:
            return False

        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_file, "w") as f:
            f.write("ok")
        return True
    # TemporaryDirectory cleans up all files automatically


# ----------------------------------------------------------------------
# BASIC DATA generation and parsing
# ----------------------------------------------------------------------

def generate_data_lines(binary: bytes, start_line: int = 1000, step: int = 10) -> list:
    """Return list of DATA lines (strings) including final -1."""
    lines = []
    line_num = start_line
    for i in range(0, len(binary), 16):
        chunk = binary[i:i+16]
        hex_values = [f"&H{byte:02X}" for byte in chunk]
        lines.append(f"{line_num} DATA " + ",".join(hex_values))
        line_num += step
    lines.append(f"{line_num} DATA -1")
    return lines

def parse_bas_content(content: str, source_name: str = "<string>"):
    """
    Parse BASIC source text. Returns (bytes, errors_list).
    Tolerates optional line numbers, &H/&h, whitespace, colon-separated statements,
    trailing comments. Stop at first -1.
    """
    errors = []
    data_bytes = bytearray()
    lines = content.splitlines()
    line_number = 0
    for raw_line in lines:
        line_number += 1
        m = re.match(r'^\s*(\d+)\s+(.*)$', raw_line)
        if m:
            rest = m.group(2)
        else:
            rest = raw_line
        statements = rest.split(':')
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
            if stmt.upper().startswith('DATA'):
                data_part = stmt[4:].strip()
                # Remove any trailing comment (apostrophe or REM)
                data_part = re.split(r"('|REM\b)", data_part, maxsplit=1)[0].strip()
                tokens = data_part.split(',')
                for token in tokens:
                    token = token.strip()
                    if not token:
                        continue
                    if token.startswith("'") or token.startswith("REM"):
                        break
                    if token == '-1':
                        return bytes(data_bytes), errors
                    m = re.match(r'^&[hH]([0-9a-fA-F]{1,2})$', token)
                    if not m:
                        errors.append(f"{source_name}:{line_number}: invalid DATA token '{token}'")
                        continue
                    value = int(m.group(1), 16)
                    data_bytes.append(value)
    errors.append(f"{source_name}: no -1 sentinel found")
    return bytes(data_bytes), errors


# ----------------------------------------------------------------------
# API functions (Section 5) with robust subprocess handling
# ----------------------------------------------------------------------


def build(asm_text: str, *, stage=None, result=None, ceiling=180,
          shape="bridge", only=None, skip=None, rules=None,
          strict=False, uasm='uasm') -> dict:
    """Assemble, lint, generate DATA and loader. Returns dict on success."""
    if rules is not None:
        raise JrError("--rules is retired; use --shape handler|iret", exit_code=1)
    if shape == "bridge":
        if stage is None:
            stage = 6
    else:
        if stage is not None:
            raise JrError("--stage is valid only for shape=bridge", exit_code=1)
    if result is not None and result < 0:
        raise JrError("result must be non-negative", exit_code=1)

    cache_dir = os.path.join(os.path.expanduser("~"), ".jr_cache")
    if not uasm_self_test(uasm, cache_dir):
        raise JrError("UASM padding self-test failed", exit_code=2)

    with tempfile.TemporaryDirectory() as td:
        tmp_asm = os.path.join(td, "input.asm")
        tmp_bin = os.path.join(td, "output.bin")
        tmp_lst = os.path.join(td, "listing.lst")

        with open(tmp_asm, "w") as f:
            f.write(asm_text)

        try:
            proc = subprocess.run(
                [uasm, "-bin", f"-Fl={tmp_lst}", "-Fo", tmp_bin, tmp_asm],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise JrError(f"UASM executable not found: {uasm}", exit_code=2)

        if proc.returncode != 0:
            raise JrError(f"UASM failed: {proc.stderr}", exit_code=2)

        with open(tmp_bin, "rb") as f:
            code = f.read()
        code_len = len(code)

        R = result if result is not None else (128 if code_len <= 128 else 180)

        if R < code_len:
            raise JrError(f"Loader invariant failed: R={R} < code_len={code_len}", exit_code=5)

        bin_hex = bytes_to_hex(code)
        decoded, disasm_text = decode(bin_hex)

        if stage == 0:
            warnings = []
            lint_selection = []
        else:
            config = load_config()
            lint_result = lint(bin_hex, stage=stage, result=R, ceiling=ceiling,
                               shape=shape, only=only, skip=skip,
                               strict=strict, config=config, decoded=decoded)
            warnings = lint_result["warnings"]
            lint_selection = lint_result["rules"]

        data_block = data(bin_hex)

        needed = max(code_len, R + 6)
        dim = (needed + 1) // 2 - 1
        bas_source = LOADER_TEMPLATE.replace("__DIM__", str(dim)).replace("__RESULT__", str(R))
        bas_source += "\n" + data_block

        status = "pass" if not warnings else "warn"
        return {
            "status": status,
            "bin_hex": bin_hex,
            "data_block": data_block,
            "bas_source": bas_source,
            "errors": [],
            "warnings": warnings,
            "disasm": disasm_text,
            "lint_selection": lint_selection,
        }

def decode(bin_hex: str):
    """Run ndisasm once; return ([(mnemonic, operands), ...], raw_text)."""
    text = dis(bin_hex)
    pairs = []
    for line in text.splitlines():
        if len(line) < 10:
            continue
        rest = line[10:]
        m = re.search(r'[a-z]', rest)
        if not m:
            continue
        mnemonic_operands = rest[m.start():].strip()
        parts = mnemonic_operands.split(None, 1)
        if not parts:
            continue
        mnemonic = parts[0]
        operands = parts[1] if len(parts) > 1 else ""
        pairs.append((mnemonic, operands))
    return pairs, text

def lint(bin_hex: str, *, stage=None, result=None, ceiling=180,
         shape="bridge", only=None, skip=None, rules=None,
         strict=False, config=None, decoded=None) -> dict:
    """Run rule engine on binary hex. Returns dict on pass, raises JrError on failure."""
    if rules is not None:
        raise JrError("--rules is retired; use --shape handler|iret", exit_code=1)
    if shape == "bridge":
        if stage is None:
            stage = 6
    else:
        if stage is not None:
            raise JrError("--stage is valid only for shape=bridge", exit_code=1)
    if stage is not None and not 0 <= stage <= 6:
        raise JrError("stage must be between 0 and 6", exit_code=1)
    if ceiling < 0:
        raise JrError("ceiling must be non-negative", exit_code=1)
    if result is not None and result < 0:
        raise JrError("result must be non-negative", exit_code=1)

    if stage == 0:
        return {"status": "pass", "errors": [], "warnings": [],
                "shape": shape, "stage": stage, "rules": []}

    data_bytes = hex_to_bytes(bin_hex)
    if config is None:
        config = load_config()
    active_rules = resolve_rules(config, shape, stage, only, skip)

    selfloc_active = any(r.get("kind") == "selfloc" for r in active_rules)
    if selfloc_active and result is None:
        raise JrError("--result is required when selfloc rule is active", exit_code=1)

    R = result if result is not None else 0
    if decoded is None:
        decoded, _ = decode(bin_hex)

    errors = []
    warnings = []
    for rule in active_rules:
        ok, is_warning, msg = check_rule(rule, data_bytes, decoded, ceiling, R)
        if not ok:
            if is_warning:
                warnings.append(msg)
                if strict:
                    errors.append(msg)
            else:
                errors.append(msg)

    if errors:
        raise JrError("\n".join(errors), exit_code=4)
    status = "pass" if not warnings else "warn"
    return {"status": status, "errors": [], "warnings": warnings,
            "shape": shape, "stage": stage,
            "rules": [r["id"] for r in active_rules]}

def verify(bas_text: str, bin_hex: str) -> dict:
    """Compare BASIC DATA to binary. Returns dict. Raises JrError(7) on parse error."""
    parsed_bytes, parse_errors = parse_bas_content(bas_text)
    if parse_errors:
        raise JrError("\n".join(parse_errors), exit_code=7)
    bin_bytes = hex_to_bytes(bin_hex)
    mismatches = []
    max_len = max(len(parsed_bytes), len(bin_bytes))
    for i in range(max_len):
        exp = parsed_bytes[i] if i < len(parsed_bytes) else None
        act = bin_bytes[i] if i < len(bin_bytes) else None
        if exp != act:
            mismatches.append({"offset": i, "expected": exp, "actual": act})
    return {
        "match": len(mismatches) == 0 and len(parsed_bytes) == len(bin_bytes),
        "expected_size": len(parsed_bytes),
        "actual_size": len(bin_bytes),
        "mismatches": mismatches,
    }


def golden(bas_text: str) -> str:
    """Extract bytes from BASIC, return hex string."""
    parsed_bytes, parse_errors = parse_bas_content(bas_text)
    if parse_errors:
        raise JrError("\n".join(parse_errors), exit_code=7)
    return bytes_to_hex(parsed_bytes)


def dis(bin_hex: str) -> str:
    """Run ndisasm on binary hex, return text output."""
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
        f.write(hex_to_bytes(bin_hex))
        tmp_bin = f.name
    try:
        try:
            proc = subprocess.run(["ndisasm", "-b", "16", tmp_bin],
                                  capture_output=True, text=True)
        except FileNotFoundError:
            raise JrError("ndisasm executable not found", exit_code=2)
        if proc.returncode != 0:
            raise JrError(f"ndisasm failed: {proc.stderr}", exit_code=2)
        return proc.stdout
    finally:
        os.unlink(tmp_bin)


def data(bin_hex: str) -> str:
    """Generate DATA block (with line numbers and sentinel) from binary hex."""
    lines = generate_data_lines(hex_to_bytes(bin_hex))
    return "\n".join(lines) + "\n"


def parse(bas_text: str) -> str:
    """Extract bytes from BASIC, return hex string."""
    return golden(bas_text)


# ----------------------------------------------------------------------
# CLI wrapper
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="jr - PCjr bridge byte pipeline")
    subparsers = parser.add_subparsers(dest='command', required=True)

    p_build = subparsers.add_parser('build', help='assemble, lint, emit .data and .bas')
    p_build.add_argument('src', help='source .asm file')
    p_build.add_argument('--shape', choices=['bridge', 'handler', 'iret'], default='bridge')
    p_build.add_argument('--stage', type=int, default=None)
    p_build.add_argument('--result', type=int, default=None)
    p_build.add_argument('--ceiling', type=int, default=180)
    p_build.add_argument('--only', help='comma-separated rule ids/group names')
    p_build.add_argument('--skip', help='comma-separated rule ids/group names')
    p_build.add_argument('--strict', action='store_true')
    p_build.add_argument('--uasm', help='path to uasm executable')
    p_build.add_argument('--keep', action='store_true', help='keep intermediates on failure')
    p_build.set_defaults(func=cmd_build)

    p_lint = subparsers.add_parser('lint', help='lint a binary file')
    p_lint.add_argument('binfile')
    p_lint.add_argument('--shape', choices=['bridge', 'handler', 'iret'], default='bridge')
    p_lint.add_argument('--stage', type=int, default=None)
    p_lint.add_argument('--result', type=int, default=None)
    p_lint.add_argument('--ceiling', type=int, default=180)
    p_lint.add_argument('--only', help='comma-separated rule ids/group names')
    p_lint.add_argument('--skip', help='comma-separated rule ids/group names')
    p_lint.add_argument('--strict', action='store_true')
    p_lint.set_defaults(func=cmd_lint)

    p_verify = subparsers.add_parser('verify', help='verify .bas against .bin')
    p_verify.add_argument('bas')
    p_verify.add_argument('bin')
    p_verify.set_defaults(func=cmd_verify)

    p_golden = subparsers.add_parser('golden', help='extract golden .bin from .bas')
    p_golden.add_argument('bas')
    p_golden.add_argument('--out', help='output file (default basename.golden.bin)')
    p_golden.set_defaults(func=cmd_golden)

    p_dis = subparsers.add_parser('dis', help='disassemble with ndisasm')
    p_dis.add_argument('binfile')
    p_dis.set_defaults(func=cmd_dis)

    p_data = subparsers.add_parser('data', help='emit DATA lines from binary')
    p_data.add_argument('binfile')
    p_data.set_defaults(func=cmd_data)

    p_parse = subparsers.add_parser('parse', help='extract bytes from .bas DATA')
    p_parse.add_argument('bas')
    p_parse.add_argument('--out', help='output binary file (default stdout)')
    p_parse.set_defaults(func=cmd_parse)

    args = parser.parse_args()
    try:
        args.func(args)
    except JrError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(exc.exit_code)


def _csv(arg):
    if not arg:
        return None
    return [tok.strip() for tok in arg.split(',') if tok.strip()]

def _norm_stage(shape, stage):
    if shape == "bridge":
        return 6 if stage is None else stage
    if stage is not None:
        raise JrError("--stage is valid only for shape=bridge", exit_code=1)
    return None

def cmd_build(args):
    with open(args.src, 'r') as f:
        asm_text = f.read()
    stage = _norm_stage(args.shape, args.stage)
    result = build(
        asm_text,
        stage=stage,
        result=args.result,
        ceiling=args.ceiling,
        shape=args.shape,
        only=_csv(args.only),
        skip=_csv(args.skip),
        strict=args.strict,
        uasm=args.uasm or "uasm",
    )

    for w in result["warnings"]:
        print(f"WARN: {w}", file=sys.stderr)

    stage_label = str(stage) if stage is not None else "N/A"
    print(f"shape={args.shape} stage={stage_label} rules={','.join(result['lint_selection'])}")

    base = os.path.splitext(args.src)[0]
    bin_path = base + ".bin"
    data_path = base + ".data"
    bas_path = base + ".bas"

    with open(bin_path, 'wb') as f:
        f.write(hex_to_bytes(result["bin_hex"]))
    with open(data_path, 'w') as f:
        f.write(result["data_block"])
    with open(bas_path, 'w') as f:
        f.write(result["bas_source"])

    code_len = len(hex_to_bytes(result["bin_hex"]))
    R = args.result if args.result is not None else (128 if code_len <= 128 else 180)
    print(f"PASS: {args.src} -> {bin_path} ({code_len} bytes, R={R}) -> {bas_path}")

def cmd_lint(args):
    with open(args.binfile, 'rb') as f:
        bin_hex = bytes_to_hex(f.read())
    stage = _norm_stage(args.shape, args.stage)
    result = lint(
        bin_hex,
        stage=stage,
        result=args.result,
        ceiling=args.ceiling,
        shape=args.shape,
        only=_csv(args.only),
        skip=_csv(args.skip),
        strict=args.strict,
    )

    for w in result["warnings"]:
        print(f"WARN: {w}", file=sys.stderr)

    stage_label = str(result["stage"]) if result["stage"] is not None else "N/A"
    print(f"shape={result['shape']} stage={stage_label} rules={','.join(result['rules'])}")
    print("PASS")

def cmd_verify(args):
    with open(args.bas, 'r') as f:
        bas_text = f.read()
    with open(args.bin, 'rb') as f:
        bin_hex = bytes_to_hex(f.read())
    result = verify(bas_text, bin_hex)

    if result["match"]:
        print(f"verify: {args.bas} matches {args.bin} ({result['expected_size']} bytes)")
        sys.exit(0)
    else:
        print(f"verify: mismatch between {args.bas} and {args.bin}", file=sys.stderr)
        sys.exit(6)


def cmd_golden(args):
    with open(args.bas, 'r') as f:
        bas_text = f.read()
    hex_out = golden(bas_text)
    out_path = args.out if args.out else os.path.splitext(args.bas)[0] + ".golden.bin"
    with open(out_path, 'wb') as f:
        f.write(hex_to_bytes(hex_out))
    print(f"golden: wrote {len(hex_out)//2} bytes to {out_path}")


def cmd_dis(args):
    with open(args.binfile, 'rb') as f:
        bin_hex = bytes_to_hex(f.read())
    output = dis(bin_hex)
    sys.stdout.write(output)


def cmd_data(args):
    with open(args.binfile, 'rb') as f:
        bin_hex = bytes_to_hex(f.read())
    sys.stdout.write(data(bin_hex))


def cmd_parse(args):
    with open(args.bas, 'r') as f:
        bas_text = f.read()
    hex_out = parse(bas_text)
    if args.out:
        with open(args.out, 'wb') as f:
            f.write(hex_to_bytes(hex_out))
    else:
        sys.stdout.buffer.write(hex_to_bytes(hex_out))


if __name__ == "__main__":
    main()
