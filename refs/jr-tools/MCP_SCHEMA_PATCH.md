# Phase 5 — MCP schema change (user-applied)

Edit `mcp/pcjr_tools_server.py` for the `jr` tool schema, then restart
the MCP server.

## jr tool parameter changes

Add:

- `shape`: string, optional (any of `bridge` / `handler` / `iret`)
- `only`: array of strings, optional (rule ids / group names)
- `skip`: array of strings, optional (rule ids / group names)

Remove:

- `rules`: string, optional (retired)

## Schema JSON shape

```json
{
  "type": "object",
  "required": ["command"],
  "properties": {
    "command": {"type": "string"},
    "src": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "binfile": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "bas": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "bin": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "out": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "asm_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "bin_hex": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "bas_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "stage": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
    "shape": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "only": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
    "skip": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
    "result": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
    "ceiling": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
    "strict": {"type": "boolean", "default": false},
    "uasm": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "keep": {"type": "boolean", "default": false}
  }
}
```

## Restart

```
./bin/start_pcjr_mcp.sh restart
```

Then verify with a smoke `jr` call that passes `shape` and `only` and
confirms `rules` is rejected.

