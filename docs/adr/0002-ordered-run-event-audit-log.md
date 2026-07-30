# Keep an ordered audit event log for every run

Each processing run stores its summary and terminal state in `agent_runs`, while ordered execution facts are appended to `run_events`. This replaces the insufficient `tool_called` flag and makes tool inputs and outputs, validation retries, failures, and the specialist's decision demonstrable without logging credentials or other secrets.
