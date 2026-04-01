# Artemis
> Minimal Model Context Protocol for FRC live NT4 connection or wpilogs

Exposes topics for LLM model reading and publishing of single or batched/timestamped values over network table connection to robot.
Publishing limited to subtables under tuning table prefix (cli option ``--tuning-prefix=<prefix>``)

**Artemis - NT4 live connection**
**Apollo - .wpilog file**

### Uses:
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
    - quantizing/downsampling
