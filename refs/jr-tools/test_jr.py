#!/usr/bin/env python3
"""Self-verification tests for jr tool (Spec Section 9, lint v2).

Fixtures here are synthetic Contract-A test artifacts, NOT hardware
anchors. Anchor regeneration for IRPING2/CH0CAL (pre-Contract-A) is a
separate follow-on scope.

Contract-A selfloc arithmetic: entry offset is 7 (push cs / pop ds /
push bp / push es / call get_ip), so R=128 needs disp = 121 = 0x79.
"""

import os
import sys
import subprocess
import tempfile
import filecmp

JR_PATH = os.path.join(os.path.dirname(__file__), "jr")

# Contract-A green bridge, R=128. 21 bytes. selfloc disp = 121 (79 00).
GREEN_BRIDGE = "0E1F5506E800005D8DAE7900E4A0B080E6A0075DCB"

# Selfloc trap: lea bp,[bp+128] instead of +121. (21 bytes)
SELFLOC_BAD = "0E1F5506E800005D8DAE8000E4A0B080E6A0075DCB"

# NMI mask (B0 00 E6 A0) present, restore absent. Bridge + selfloc.
NMI_NO_RESTORE = "0E1F5506E800005D8DAE7900B000E6A0075DCB"

# Non-NMI routine: bridge entry + selfloc + epilogue only.
NON_NMI = "0E1F5506E800005D8DAE7900075DCB"

def run_jr(args, cwd):
    """Run jr tool, return (returncode, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, JR_PATH] + args,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    return proc.returncode, proc.stdout, proc.stderr

def write_bytes(path, hexstr):
    with open(path, "wb") as f:
        f.write(bytes.fromhex(hexstr))

def test_f1_green_bridge_passes(tmpdir):
    bin_path = os.path.join(tmpdir, "green.bin")
    write_bytes(bin_path, GREEN_BRIDGE)
    rc, stdout, stderr = run_jr(
        ["lint", "green.bin", "--result", "128", "--stage", "6"], tmpdir)
    assert rc == 0, f"F1 failed: rc={rc}, stderr={stderr}"
    assert "PASS" in stdout
    assert "shape=bridge" in stdout
    print("F1 PASS")

def test_f2_selfloc_trap_fails(tmpdir):
    bin_path = os.path.join(tmpdir, "selfloc_bad.bin")
    write_bytes(bin_path, SELFLOC_BAD)
    rc, stdout, stderr = run_jr(
        ["lint", "selfloc_bad.bin", "--result", "128", "--stage", "6"], tmpdir)
    assert rc == 4, f"F2 expected rc=4, got {rc}"
    assert "selfloc" in stderr
    assert "expected displacement 121" in stderr
    assert "lea bp,[bp+128]" in stderr
    print("F2 PASS")

def test_f3_missing_nmi_restore(tmpdir):
    bin_path = os.path.join(tmpdir, "nmi_missing.bin")
    write_bytes(bin_path, NMI_NO_RESTORE)
    rc, stdout, stderr = run_jr(
        ["lint", "nmi_missing.bin", "--result", "128", "--stage", "5"], tmpdir)
    assert rc == 0, f"F3 (non-strict) expected rc=0, got {rc}: {stderr}"
    assert "WARN" in stderr
    assert "NMI restore" in stderr
    rc2, _, stderr2 = run_jr(
        ["lint", "nmi_missing.bin", "--result", "128", "--stage", "5",
         "--strict"], tmpdir)
    assert rc2 == 4, f"F3 (strict) expected rc=4, got {rc2}"
    assert "NMI restore" in stderr2
    print("F3 PASS")

def test_f4_non_nmi_passes(tmpdir):
    bin_path = os.path.join(tmpdir, "non_nmi.bin")
    write_bytes(bin_path, NON_NMI)
    rc, stdout, stderr = run_jr(
        ["lint", "non_nmi.bin", "--result", "128", "--stage", "5"], tmpdir)
    assert rc == 0, f"F4 expected rc=0, got {rc}: {stderr}"
    assert "PASS" in stdout
    print("F4 PASS")

def test_f5_data_roundtrip(tmpdir):
    bin_path = os.path.join(tmpdir, "green.bin")
    write_bytes(bin_path, GREEN_BRIDGE)
    rc, data_out, _ = run_jr(["data", "green.bin"], tmpdir)
    assert rc == 0
    data_file = os.path.join(tmpdir, "green.data")
    with open(data_file, "w") as f:
        f.write(data_out)
    parsed_bin = os.path.join(tmpdir, "roundtrip.bin")
    rc, _, stderr = run_jr(
        ["parse", "--out", "roundtrip.bin", "green.data"], tmpdir)
    assert rc == 0, f"parse failed: {stderr}"
    assert filecmp.cmp(bin_path, parsed_bin), "roundtrip mismatch"
    print("F5 PASS")

def test_f6_uasm_padding_selftest(tmpdir):
    asm_src = os.path.join(tmpdir, "trivial.asm")
    with open(asm_src, "w") as f:
        f.write("""\
option casemap:none
option segment:use16

code segment
    assume cs:code
    org 0
start:
    retf
code ends
end start
""")
    out_bin = os.path.join(tmpdir, "trivial.bin")
    lst_file = os.path.join(tmpdir, "trivial.lst")
    cmd = ["uasm", "-bin", f"-Fl={lst_file}", "-Fo", out_bin, asm_src]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, f"UASM failed: {proc.stderr}"
    with open(out_bin, "rb") as f:
        data = f.read()
    assert len(data) == 1 and data[0] == 0xCB, \
        f"padding check failed: got {data.hex()}"
    print("F6 PASS")

def test_f7_stage0_legal(tmpdir):
    bin_path = os.path.join(tmpdir, "green.bin")
    write_bytes(bin_path, GREEN_BRIDGE)
    rc, stdout, stderr = run_jr(
        ["lint", "green.bin", "--stage", "0"], tmpdir)
    assert rc == 0, f"F7 expected rc=0, got {rc}: {stderr}"
    assert "PASS" in stdout
    assert "LINTING SKIPPED" not in stdout
    print("F7 PASS")

def test_f8_handler_rejects_stage(tmpdir):
    bin_path = os.path.join(tmpdir, "green.bin")
    write_bytes(bin_path, GREEN_BRIDGE)
    rc, _, stderr = run_jr(
        ["lint", "green.bin", "--shape", "handler", "--stage", "2"], tmpdir)
    assert rc == 1, f"F8 expected rc=1, got {rc}"
    assert "stage" in stderr.lower()
    print("F8 PASS")

def test_f9_rules_retired(tmpdir):
    # Measured drift: the CLI argparse rejects --rules before the engine's
    # friendly 'use --shape' retirement check can fire. rc=2, argparse
    # message. The spec's friendly path is dead on the CLI surface.
    bin_path = os.path.join(tmpdir, "green.bin")
    write_bytes(bin_path, GREEN_BRIDGE)
    rc, _, stderr = run_jr(
        ["lint", "green.bin", "--rules", "old.json"], tmpdir)
    assert rc == 2, f"F9 expected rc=2, got {rc}"
    assert "unrecognized arguments" in stderr
    assert "--rules" in stderr
    print("F9 PASS")

def test_f10_only_skip_compose(tmpdir):
    bin_path = os.path.join(tmpdir, "green.bin")
    write_bytes(bin_path, GREEN_BRIDGE)
    rc, stdout, stderr = run_jr(
        ["lint", "green.bin", "--result", "128", "--stage", "6",
         "--only", "entry"], tmpdir)
    assert rc == 0, f"F10 (only) expected rc=0, got {rc}: {stderr}"
    assert "rules=entry" in stdout
    bad_path = os.path.join(tmpdir, "selfloc_bad.bin")
    write_bytes(bad_path, SELFLOC_BAD)
    rc2, _, stderr2 = run_jr(
        ["lint", "selfloc_bad.bin", "--result", "128", "--stage", "6",
         "--skip", "entry"], tmpdir)
    assert rc2 == 4, f"F10 (skip) expected rc=4, got {rc2}"
    assert "selfloc" in stderr2
    print("F10 PASS")

def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_f1_green_bridge_passes(tmpdir)
    with tempfile.TemporaryDirectory() as tmpdir:
        test_f2_selfloc_trap_fails(tmpdir)
    with tempfile.TemporaryDirectory() as tmpdir:
        test_f3_missing_nmi_restore(tmpdir)
    with tempfile.TemporaryDirectory() as tmpdir:
        test_f4_non_nmi_passes(tmpdir)
    with tempfile.TemporaryDirectory() as tmpdir:
        test_f5_data_roundtrip(tmpdir)
    with tempfile.TemporaryDirectory() as tmpdir:
        test_f6_uasm_padding_selftest(tmpdir)
    with tempfile.TemporaryDirectory() as tmpdir:
        test_f7_stage0_legal(tmpdir)
    with tempfile.TemporaryDirectory() as tmpdir:
        test_f8_handler_rejects_stage(tmpdir)
    with tempfile.TemporaryDirectory() as tmpdir:
        test_f9_rules_retired(tmpdir)
    with tempfile.TemporaryDirectory() as tmpdir:
        test_f10_only_skip_compose(tmpdir)
    print("All tests passed.")

if __name__ == "__main__":
    main()
