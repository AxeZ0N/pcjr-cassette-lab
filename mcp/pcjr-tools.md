# pcjr-tools — Server Ops + Tool Surface (v6)

Server: `pcjr-tools` at `http://localhost:8765/mcp` (loopback bind).

## Tools

| Tool | Mode / command | Purpose |
|---|---|---|
| `search_ref` | `query` \| `peek` \| `stats` | Manual strip search |
| `grep_repo` | `query` \| `read` \| `grep_all` \| `stats` \| `roots` | Read-only repo search (stdlib, no git) |
| `jr` | `build` \| `lint` \| `verify` \| `golden` \| `dis` \| `data` \| `parse` | Bridge byte pipeline (UASM + NDISASM) |

### search_ref

```

mode: query   query, context(3), max_pages(1)
mode: peek    start, end (1-based; start>=1)
mode: stats   verbose (omit or true; never false)

```

### jr

```

command: build    asm_text (or src); stage(6), result(auto), ceiling(180), strict
command: lint     bin_hex (or binfile); stage, result, ceiling, strict
command: verify   bas, bin
command: golden   bas [--out F]
command: dis      bin_hex (or binfile)   -> ndisasm -b 16
command: data     bin_hex (or binfile)   -> DATA lines + -1
command: parse    bas_text (or bas)      -> hex

```

Inline inputs (`asm_text`, `bin_hex`, `bas_text`) are preferred for
development; file inputs only for persistence. Inline strings carry no
`0x`/`&H` prefixes. `build` requires the UASM segment wrapper (see
`docs/jr_tool_spec.md` section 3.3). Zero-arg hazard: every `jr` call
MUST include `command`.

### grep_repo

Schema:

```json
{
  "mode": "query",
  "query": "carrier_high_us|burst_us",
  "context": 2,
  "literal": false
}
```

- `query` — regex search over `facts.md`, `sessions/`, `docs/`
  (case-insensitive; `|` works).
- `read` — full file by root-relative path, whole repo (text only;
  hidden/absolute/`../`/symlink escapes refused). Args: `path`.
- `grep_all` — regex search across whole repo (text only). Args:
  `query`; capped by `max_matches` (default 50).
- `stats` — file/line counts per root.
- `roots` — which roots exist.
- Zero-arg hazard: every `grep_repo` call MUST include `mode`.

## Registration (already wired)

Server v8 registers `search_ref`, `grep_repo`, and `jr` in
`mcp/pcjr_tools_server.py`. `jr` is imported from
`refs/jr-tools/jr.py`; UASM and NDISASM are expected on PATH.

If you rebuild the server from scratch:

```
import pcjr_repo_grep as GREP
import jr as JR

@mcp.tool()
def grep_repo(mode: str, query: Optional[str] = None,
              context: int = 2, literal: bool = False) -> str:
    ...
```

Then restart:

```
bin/start_pcjr_mcp.sh
```

Self-test:

```
bin/grep_selftest.sh
python3 mcp/test_mcp_jr_smoke.py
```

## Security posture (do not weaken)

- `grep_repo` query mode: fixed roots `facts.md`, `sessions/`, `docs/`.
  Whole-repo `read`/`grep_all` refuse hidden paths, absolute paths,
  `../`, and symlink escapes. No git binary, no subprocess, stdlib only.
- Writes NEVER go through the server. Writes are user-owned via
  `bin/jr-commit.sh` and `bin/migrate_repo.py`.

## Paste-first fallback

When the server is down, the assistant asks you to run and paste:

```
git grep -n -i -E -C2 "carrier_high_us|burst_us|gap2" -- facts.md sessions docs
```

For the manual strip, when the server is down, run the ref tool and paste
the output:

```
python3 refs/pcjr_ref_tool.py refs/deepseek_reference.txt query "<term>" --context 3 --max-pages 1
python3 refs/pcjr_ref_tool.py refs/deepseek_reference.txt peek 30 35
python3 refs/pcjr_ref_tool.py refs/deepseek_reference.txt stats --verbose
```
