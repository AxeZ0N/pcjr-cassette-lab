#!/usr/bin/env python3
"""Local integration: pjasm.assemble -> pcjr_asm_debug validators.

Boundary under test:
    pjasm output (bytes) validated by pcjr_asm_debug decode /
    branch_checks / check. No MCP, no anchors, no hardware.

Protocol: each check is a named boolean. A FAIL names the boundary
that broke. Run from any cwd; the script inserts its own dir first.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pcjrasm as PJ
import pcjr_asm_debug as ASM

# IRPING branch sites from the frozen stage-B layout. These must be
# verifiable by pcjr_asm_debug.branch_checks without pjasm knowledge.
IRPING_BRANCHES = [(0x27, 0x0033),   # je  loop_dec
                   (0x2E, 0x0031),   # jmp after_inc
                   (0x33, 0x001F)]   # loop loop_start

def run():
    results = {}

    # 0. Environment sanity: is the other tool itself green?
    try:
        st = ASM.selftest()
        results["debug_asm_selftest"] = bool(st) and all(st.values())
    except Exception as exc:  # surfaced, not swallowed
        results["debug_asm_selftest"] = False
        results["debug_asm_selftest_err"] = str(exc)

    # 1. pjasm produces the frozen image.
    img = PJ.assemble(PJ.IRPING_SRC)
    ok = img["ok"]
    data = img["data"] if ok else b""
    results["pjasm_assemble_ok"] = ok
    results["pjasm_golden_exact"] = (
        ok and data == bytes.fromhex(PJ.GOLDEN_HEX))
    results["pjasm_size_61"] = (ok and img["size"] == 61)

    # 2. debug_asm fully decodes pjasm output with no FAIL/truncated tail.
    if ok:
        dec = ASM.decode(data)
        texts = [t for _, _, t in dec]
        results["decode_clean"] = all(
            "FAIL" not in t and "truncated" not in t for t in texts)
        results["decode_31"] = (len(dec) == 31)
        results["decode_consumed"] = (
            sum(ln for _, ln, _ in dec) == len(data))
    else:
        results["decode_clean"] = False
        results["decode_31"] = False
        results["decode_consumed"] = False

    # 3. debug_asm verifies branch displacements inside pjasm output.
    if ok:
        results["branch_audit"] = ASM.branch_checks(
            list(data), IRPING_BRANCHES)["ok"]
    else:
        results["branch_audit"] = False

    # 4. debug_asm byte-compare against the same golden.
    if ok:
        results["check_ok"] = ASM.check(
            list(data), list(bytes.fromhex(PJ.GOLDEN_HEX)))["ok"]
    else:
        results["check_ok"] = False

    all_pass = all(
        v for k, v in results.items() if not k.endswith("_err"))
    for name in sorted(results):
        print(("PASS" if results[name] else "FAIL"), name)
    print("ALL_PASS", all_pass)
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(run())
