"""Per-tool configuration registry.

Each tool (e.g. refunds) owns its own labels, statuses, actions and seed
records. Records and history are always scoped by tool key in the database.
"""
from .base import ToolConfig
from .refunds import REFUNDS

TOOLS: dict[str, ToolConfig] = {t.key: t for t in [REFUNDS]}
