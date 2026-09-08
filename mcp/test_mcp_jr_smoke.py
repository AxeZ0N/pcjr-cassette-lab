#!/usr/bin/env python3
"""Smoke test for the MCP jr tool after refactor.

Tests each command path without requiring external dependencies (except
ndisasm for the dis command, but it will still return an error if missing
without crashing). Uses the F1 hex bytes as a known-good binary.
"""

import os
import sys
import tempfile
from pathlib import Path

# Ensure we can import the server module
sys.path.insert(0, str(Path(__file__).parent / "mcp"))
import pcjr_tools_server as srv

# The F1 binary from the spec (61 bytes)
IRPING_HEX = (
    "0E1F55E800005D8DAE7A00"
    "BA6200EC2440B400894600"
    "89C6B9307531DB31FFBA62"
    "00EC244039F0740A85F674"
    "0347EB014389C6E2EA895E"
    "02897E045DCB"
)

def create_data_bas(hex_bytes, path):
    """Write a .bas file with DATA statements for the given hex."""
    lines = []
    for i in range(0, len(hex_bytes), 32):
        chunk = hex_bytes[i:i+32]
        vals = ",".join(f"&H{chunk[j:j+2]}" for j in range(0, len(chunk), 2))
        lines.append(f"{1000+i//2} DATA {vals}")
    lines.append("9999 DATA -1")
    with open(path, 'w') as f:
        f.write("\n".join(lines) + "\n")

def test_jr_data(bin_path):
    result = srv.jr(command="data", binfile=bin_path)
    assert "DATA -1" in result, f"data: missing sentinel in output:\n{result}"
    print("[PASS] data")

def test_jr_lint(bin_path):
    result = srv.jr(command="lint", binfile=bin_path, stage=6, result=128)
    # The result is JSON string; parse it
    import json
    d = json.loads(result)
    assert d["status"] in ("pass", "warn"), f"lint: unexpected status: {d}"
    assert d["errors"] == [], f"lint: errors present: {d}"
    print("[PASS] lint")

def test_jr_verify(bas_path, bin_path):
    result = srv.jr(command="verify", bas=bas_path, bin=bin_path)
    import json
    d = json.loads(result)
    assert d["match"] is True, f"verify: expected match, got {d}"
    print("[PASS] verify")

def test_jr_golden(bas_path, bin_path, tmpdir):
    golden_path = os.path.join(tmpdir, "golden.bin")
    result = srv.jr(command="golden", bas=bas_path, out=golden_path)
    assert os.path.exists(golden_path), "golden: output file not created"
    with open(golden_path, 'rb') as f:
        golden_hex = f.read().hex().upper()
    with open(bin_path, 'rb') as f:
        orig_hex = f.read().hex().upper()
    assert golden_hex == orig_hex, "golden: extracted bytes differ"
    print("[PASS] golden")

def test_jr_parse(bas_path):
    result = srv.jr(command="parse", bas=bas_path)
    assert result == IRPING_HEX, f"parse: expected {IRPING_HEX}, got {result}"
    print("[PASS] parse")

def test_jr_dis(bin_path):
    result = srv.jr(command="dis", binfile=bin_path)
    # ndisasm may be missing; if so result is an error string starting with "ERROR"
    if result.startswith("ERROR"):
        print("[SKIP] dis (ndisasm missing or failed)")
    else:
        assert len(result) > 0, "dis: empty output"
        assert "00000000" in result, "dis: unexpected output format"
        print("[PASS] dis")

def test_jr_build_failure(tmpdir):
    # Create a minimal asm that will fail lint (no entry prefix)
    asm_path = os.path.join(tmpdir, "bad.asm")
    with open(asm_path, 'w') as f:
        f.write("retf\n")
    result = srv.jr(command="build", src=asm_path)
    # The MCP function catches errors and returns a string starting with "ERROR (exit "
    assert result.startswith("ERROR (exit "), f"build: expected error string, got:\n{result}"
    print("[PASS] build (error handling)")

def test_jr_invalid_command():
    result = srv.jr(command="bogus")
    assert "ERROR: unknown command" in result, f"invalid command: unexpected response: {result}"
    print("[PASS] invalid command")

def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Prepare files
        bin_path = os.path.join(tmpdir, "irping.bin")
        with open(bin_path, 'wb') as f:
            f.write(bytes.fromhex(IRPING_HEX))

        bas_path = os.path.join(tmpdir, "irping.bas")
        create_data_bas(IRPING_HEX, bas_path)

        # Run tests
        test_jr_data(bin_path)
        test_jr_lint(bin_path)
        test_jr_verify(bas_path, bin_path)
        test_jr_golden(bas_path, bin_path, tmpdir)
        test_jr_parse(bas_path)
        test_jr_dis(bin_path)
        test_jr_build_failure(tmpdir)
        test_jr_invalid_command()

        print("\nAll smoke tests passed.")

if __name__ == "__main__":
    main()
