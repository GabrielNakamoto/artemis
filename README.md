# Artemis
> Minimal Model Context Protocol for FRC live NT4 connection or wpilogs


## Artemis - NT4 live connection
- Exposes topics for LLM model reading and publishing of single or batched/timestamped values over network table connection to robot.
- Publishing limited to subtables under tuning table prefix (cli option ``--tuning-prefix=<prefix>``)

## Apollo - .wpilog file
> See simple [example conversation](./turret-controls-review-claude-apollo.txt) reviewing turret control systems tuning from a competition wpilog with claude using a local apollo MCP server
- Rudimentary mcp wrapper for .wpilog parsing

### Uses
- Control system tuning
- Live debugging of mechanical systems
- Performance/limiting factor identification
- log reviews

### Usage
```
uv venv
uv add "mcp[cli]" pyntcore
claude mcp add --transport stdio artemis --scope user -- uv run --directory <your artemis dir> python artemis.py <your team number> 
claude mcp add --transport stdio apollo --scope user -- uv run --directory <your apollo dir> python apollo.py
```

### Todo
- lots of performance improvements/make it easier for LLM to parse important info
    [x] quantizing/downsampling
[x] let model search entries by time range
[x] cache read entries for apollo
