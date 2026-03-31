# Artemis
> Minimal Model Context Protocol for live NT4 robot connection.

Exposes topics for LLM model reading and publishing of single or batched/timestamped values over network table connection to robot.
Publishing limited to subtables under tuning table prefix (cli option ``--tuning-prefix=<prefix>``)

### Uses:
- Control system tuning
- Live debugging of mechanical systems
- Performance/limiting factor identification

### Usage
```
uv venv
uv add "mcp[cli]" pyntcore
claude mcp add artemis -- uv run --directory <your artemis dir> python artemis.py <your team number> 
```
