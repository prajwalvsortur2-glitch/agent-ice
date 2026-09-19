"""Agent layer — the UNTRUSTED decision maker.

The agent plans and *proposes* tool calls. It has no authority to execute a
protected tool. Every proposal goes through Agent ICE.
""" 