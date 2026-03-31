# Artemis
> Minimal Model Context Protocol for live NT4 robot connection.

Exposes topics for model reading and publishing single or batched/timestamped values.
Publishing limited to subtables under tuning table prefix (cli option ``--tuning-prefix=<prefix>``)

### Uses:
- Control system tuning
- Live debugging of mechanical systems
- Performance/limiting factor identification

### Usage
```
uv venv
uv add "mcp[cli]" pyntcore
uv run artemis.py <team number>
```
