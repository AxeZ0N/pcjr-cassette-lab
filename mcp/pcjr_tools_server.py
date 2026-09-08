#!/usr/bin/env python3
"""pcjr-tools MCP server (v9) - integrated guide for PCjr machine-code design.

Tools:
    search_ref   Query the digitized IBM PCjr Technical Reference strip
                 (prose; Appendix A excluded; pages.jsonl joined as metadata).
    grep_repo    Read-only repo search over the PyCJr repo.
    bios_grep    Read-only grep over refs/ibm_pcjr-bios.lst (flat 0000:0000..FFFF:FFFF).
    jr           Assemble, lint, extract, and verify bridge machine code.

Backend files (all relative to repo root):
    refs/pcjr_technical_reference.txt   raw prose strip (segment_pages source)
    refs/pages.jsonl                    derived axes/regions metadata, joined on page_id
    refs/ibm_pcjr-bios.lst              flat BIOS listing dump (gitignored)
    refs/pcjr_manual.py                 ManualStore (query/grep/peek/stats)
    refs/pcjr_bios.py                   BiosStore (grep/peek/stats)
    refs/pcjr_repo_grep.py              repo search dispatch
    refs/pcjr_hex.py                    OCR hex-normalization helpers
    refs/tech_ref_sanitize.py           segment_pages (single page attribution)
    refs/jr-tools/jr.py                 machine-code byte pipeline

Note: search_ref peek indexes exclude Appendix A (the BIOS listing is a
separate file and tool now). 1-based indexes are page positions in the
prose store, NOT the old RefStore entry numbers that included the BIOS
listing.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

_SERVER_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SERVER_DIR.parent

HOST = os.environ.get("PCJR_HOST", "127.0.0.1")
PORT_REF = int(os.environ.get("PCJR_PORT_REF", "8765"))

REF_DIR = os.environ.get("PCJR_REF_DIR", str(_REPO_ROOT / "refs"))
MANUAL_FILE = os.path.join(REF_DIR, "pcjr_technical_reference.txt")
BIOS_FILE = os.path.join(REF_DIR, "ibm_pcjr-bios.lst")
PAGES_JSONL = os.path.join(REF_DIR, "pages.jsonl")
JR_TOOLS_DIR = os.path.join(REF_DIR, "jr-tools")

sys.path.insert(0, REF_DIR)
sys.path.insert(0, JR_TOOLS_DIR)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Missing 'mcp' package. Install it with:", file=sys.stderr)
    print("  pip install -r requirements.txt", file=sys.stderr)
    raise

try:
    import pcjr_repo_grep as GREP
    import pcjr_manual as MANUAL
    import pcjr_bios as BIOS
    import jr as JR
except ImportError as exc:
    print("Missing grep/manual/bios/jr module in PCJR_REF_DIR:", file=sys.stderr)
    print(f"  expected ref dir: {REF_DIR}", file=sys.stderr)
    print(f"  expected jr-tools dir: {JR_TOOLS_DIR}", file=sys.stderr)
    print(f"  error: {exc}", file=sys.stderr)
    raise

from mcp.server.transport_security import TransportSecuritySettings

ALLOWED_BDS_ORIGIN = "moz-extension://12acc078-b84b-4db7-bb5d-ca3aab7eaf30"

mcp = FastMCP(
    "pcjr-tools",
    transport_security=TransportSecuritySettings(
        allowed_origins=[ALLOWED_BDS_ORIGIN],
        allowed_hosts=["127.0.0.1:8765", "localhost:8765"],
    ),
)

try:
    MANSTORE = MANUAL.ManualStore(MANUAL_FILE, PAGES_JSONL)
except Exception as exc:
    print(f"ERROR: cannot load manual strip {MANUAL_FILE}: {exc}", file=sys.stderr)
    sys.exit(1)

# The BIOS listing is gitignored and may be absent. Degrade gracefully
# rather than refuse startup: bios_grep then reports a clear error.
try:
    BIOSSTORE = BIOS.BiosStore(BIOS_FILE)
    BIOS_ERR = None
except Exception as exc:
    BIOSSTORE = None
    BIOS_ERR = f"cannot load BIOS listing {BIOS_FILE}: {exc}"
    print(f"WARNING: {BIOS_ERR} (bios_grep will report this)", file=sys.stderr)

# --- search_ref -------------------------------------------------------------

@mcp.tool()
def search_ref(
    mode: str,
    query: Optional[str] = None,
    context: int = 3,
    max_pages: int = 1,
    start: Optional[int] = None,
    end: Optional[int] = None,
    max_matches: int = 50,
    raw: bool = False,
    verbose: Optional[bool] = None,
) -> str:
    """Search the IBM PCjr Technical Reference strip (prose; Appendix A excluded).

    mode:
        query  Ranked prose search. Needs 'query'.
               Optional: context (default 3), max_pages (default 1).
        grep   Exhaustive line-attributed hits across pages. Needs 'query'.
               Optional: context (default 3), max_matches (default 50).
        peek   Raw page body by 1-based page index. Needs 'start' >= 1.
               Optional: end.
        stats  Diagnostic page counts. Optional: verbose (omit or true).

    raw=true disables OCR hex normalization (default on for hex tokens).
    Page results carry pages.jsonl axes/regions metadata under 'meta' when present.
    """
    try:
        if mode == "query":
            if not query:
                return json.dumps({"error": "mode=query requires 'query'"})
            return json.dumps(
                MANSTORE.query(query, int(context), int(max_pages), raw), indent=2
            )
        if mode == "grep":
            if not query:
                return json.dumps({"error": "mode=grep requires 'query'"})
            return json.dumps(
                MANSTORE.grep(query, int(context), int(max_matches), raw), indent=2
            )
        if mode == "peek":
            if start is None or start < 1:
                return json.dumps(
                    {"error": "mode=peek requires 'start' >= 1 (1-based page index)"}
                )
            return json.dumps(MANSTORE.peek(start, end), indent=2)
        if mode == "stats":
            return json.dumps(MANSTORE.stats(bool(verbose)), indent=2)
        return json.dumps({"error": "mode must be one of query|grep|peek|stats"})
    except Exception as exc:
        return json.dumps({"error": str(exc)})

# --- grep_repo --------------------------------------------------------------

@mcp.tool()
def grep_repo(
    mode: str,
    query: Optional[str] = None,
    context: int = 2,
    literal: bool = False,
    path: Optional[str] = None,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    max_matches: int = 50,
) -> str:
    """Read-only repo tool over the PyCJr repo.

    mode:
        facts          Fact-layer grep (facts.md, sessions/, docs/).
                       Needs 'query'. Optional: context, max_matches.
        all            Whole-repo grep (text files only, hidden refused).
                       Needs 'query'. Optional: context, max_matches.
        files          Substring discovery of root-relative paths.
                       Needs 'query'. Optional: max_matches.
        ls             Directory listing. Optional: path (default repo root).
        read           Full file by root-relative path. Needs 'path'.
                       Optional: start_line, end_line (1-based).
        facts_headings Heading index of facts.md (line, date, name, status).
        stats          Fact-layer file/line counts.
        roots          Which fact-layer roots exist.
    """
    try:
        return json.dumps(
            GREP.dispatch(
                mode=mode,
                query=query,
                context=context,
                literal=literal,
                path=path,
                start_line=start_line,
                end_line=end_line,
                max_matches=max_matches,
            ),
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)})

# --- bios_grep --------------------------------------------------------------

@mcp.tool()
def bios_grep(
    mode: str,
    query: Optional[str] = None,
    context: int = 3,
    start: Optional[int] = None,
    end: Optional[int] = None,
    max_matches: int = 50,
    raw: bool = False,
) -> str:
    """Grep the flat BIOS listing (refs/ibm_pcjr-bios.lst).

    mode:
        grep   Line-attributed hits. Needs 'query'.
               Optional: context (default 3), max_matches (default 50).
        peek   Raw lines by 1-based line number. Needs 'start' >= 1.
               Optional: end.
        stats  Line count of the listing.

    raw=true disables OCR hex normalization (default on for hex tokens).
    """
    if BIOSSTORE is None:
        return json.dumps({"error": BIOS_ERR})
    try:
        if mode == "grep":
            if not query:
                return json.dumps({"error": "mode=grep requires 'query'"})
            return json.dumps(
                BIOSSTORE.grep(query, int(context), int(max_matches), raw), indent=2
            )
        if mode == "peek":
            if start is None or start < 1:
                return json.dumps(
                    {"error": "mode=peek requires 'start' >= 1 (1-based line number)"}
                )
            return json.dumps(BIOSSTORE.peek(start, end), indent=2)
        if mode == "stats":
            return json.dumps(BIOSSTORE.stats(), indent=2)
        return json.dumps({"error": "mode must be one of grep|peek|stats"})
    except Exception as exc:
        return json.dumps({"error": str(exc)})

# --- jr ---------------------------------------------------------------------

@mcp.tool()
def jr(
    command: str,
    # file inputs (legacy)
    src: Optional[str] = None,
    binfile: Optional[str] = None,
    bas: Optional[str] = None,
    bin: Optional[str] = None,
    out: Optional[str] = None,
    # inline inputs (new)
    asm_text: Optional[str] = None,
    bin_hex: Optional[str] = None,
    bas_text: Optional[str] = None,
    stage: Optional[int] = None,
    result: Optional[int] = None,
    ceiling: Optional[int] = None,
    shape: Optional[str] = None,
    only: Optional[list[str]] = None,
    skip: Optional[list[str]] = None,
    strict: bool = False,
    uasm: Optional[str] = None,
    keep: bool = False,
) -> str:
    """PCjr bridge byte pipeline with inline or file inputs.

    Prefer inline inputs (asm_text, bin_hex, bas_text) for development;
    use file inputs only when persistence is required.
    All inline inputs are strings without 0x/&H prefixes.
    """
    try:
        if command == "build":
            if asm_text is None:
                if not src:
                    return "ERROR: command=build requires 'src' or 'asm_text'"
                with open(src, 'r') as f:
                    asm_text = f.read()
            res = JR.build(
                asm_text,
                stage=stage if stage is not None else 6,
                result=result,
                ceiling=ceiling if ceiling is not None else 180,
                shape=shape or "bridge",
                only=only,
                skip=skip,
                strict=strict,
                uasm=uasm or "uasm",
            )
            # Return artifacts inline; optionally write if src given.
            if src:
                base = os.path.splitext(src)[0]
                with open(base + ".bin", 'wb') as f:
                    f.write(bytes.fromhex(res["bin_hex"]))
                with open(base + ".data", 'w') as f:
                    f.write(res["data_block"])
                with open(base + ".bas", 'w') as f:
                    f.write(res["bas_source"])
            return json.dumps(res, indent=2)

        elif command == "lint":
            if bin_hex is None:
                if not binfile:
                    return "ERROR: command=lint requires 'binfile' or 'bin_hex'"
                with open(binfile, 'rb') as f:
                    bin_hex = f.read().hex().upper()
            res = JR.lint(
                bin_hex,
                stage=stage if stage is not None else 6,
                result=result,
                ceiling=ceiling if ceiling is not None else 180,
                shape=shape or "bridge",
                only=only,
                skip=skip,
                strict=strict,
            )
            return json.dumps(res, indent=2)

        elif command == "verify":
            if bas_text is None and bas:
                with open(bas, 'r') as f:
                    bas_text = f.read()
            if bin_hex is None and bin:
                with open(bin, 'rb') as f:
                    bin_hex = f.read().hex().upper()
            if bas_text is None or bin_hex is None:
                return "ERROR: command=verify requires ('bas' or 'bas_text') and ('bin' or 'bin_hex')"
            res = JR.verify(bas_text, bin_hex)
            return json.dumps(res, indent=2)

        elif command == "golden":
            if bas_text is None:
                if not bas:
                    return "ERROR: command=golden requires 'bas' or 'bas_text'"
                with open(bas, 'r') as f:
                    bas_text = f.read()
            hex_out = JR.golden(bas_text)
            if out:
                with open(out, 'wb') as f:
                    f.write(bytes.fromhex(hex_out))
                return f"golden: wrote {len(hex_out)//2} bytes to {out}"
            return hex_out

        elif command == "dis":
            if bin_hex is None:
                if not binfile:
                    return "ERROR: command=dis requires 'binfile' or 'bin_hex'"
                with open(binfile, 'rb') as f:
                    bin_hex = f.read().hex().upper()
            return JR.dis(bin_hex)

        elif command == "data":
            if bin_hex is None:
                if not binfile:
                    return "ERROR: command=data requires 'binfile' or 'bin_hex'"
                with open(binfile, 'rb') as f:
                    bin_hex = f.read().hex().upper()
            return JR.data(bin_hex)

        elif command == "parse":
            if bas_text is None:
                if not bas:
                    return "ERROR: command=parse requires 'bas' or 'bas_text'"
                with open(bas, 'r') as f:
                    bas_text = f.read()
            hex_out = JR.parse(bas_text)
            if out:
                with open(out, 'wb') as f:
                    f.write(bytes.fromhex(hex_out))
                return f"parse: wrote {len(hex_out)//2} bytes to {out}"
            return hex_out

        else:
            return f"ERROR: unknown command '{command}'"

    except JR.JrError as exc:
        return f"ERROR (exit {exc.exit_code}):\n{exc}"
    except FileNotFoundError as exc:
        return f"ERROR: file not found: {exc}"
    except Exception as exc:
        return f"ERROR: {exc}"

def main() -> None:
    print("pcjr-tools MCP server")
    print(f"  manual strip:    {MANUAL_FILE}")
    print(f"  pages jsonl:     {PAGES_JSONL}")
    print(f"  bios listing:    {BIOS_FILE}")
    print(f"  repo grep:       {os.path.join(REF_DIR, 'pcjr_repo_grep.py')}")
    print(f"  manual store:    {os.path.join(REF_DIR, 'pcjr_manual.py')}")
    print(f"  bios store:      {os.path.join(REF_DIR, 'pcjr_bios.py')}")
    print(f"  jr module:       {os.path.join(JR_TOOLS_DIR, 'jr.py')}")
    print(f"  pages loaded:    {len(MANSTORE.pages)}")
    print(f"  endpoint:        http://{HOST}:{PORT_REF}/mcp")
    print("Press Ctrl+C to stop.")

    import uvicorn

    try:
        app = mcp.streamable_http_app()
        print("transport: streamable-http (/mcp)")
    except AttributeError:
        app = mcp.sse_app()
        print("transport: sse fallback (may not work with BDS)")

    uvicorn.run(app, host=HOST, port=PORT_REF)

if __name__ == "__main__":
    main()
