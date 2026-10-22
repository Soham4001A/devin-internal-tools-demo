from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    kind: str = "text"  # text | money | datetime | status


@dataclass(frozen=True)
class Action:
    key: str          # e.g. "approve"
    label: str        # e.g. "Approve"
    to_status: str    # resulting status
    from_statuses: tuple[str, ...]
    requires_reason: bool = True


@dataclass(frozen=True)
class ToolConfig:
    key: str
    name: str
    record_label: str
    statuses: tuple[str, ...]
    columns: tuple[Column, ...]
    detail_fields: tuple[Column, ...]
    search_fields: tuple[str, ...]
    actions: tuple[Action, ...]
    # Returns list of (ref, status, submitted_offset_hours, data, decision|None)
    seed: Callable[[], list[dict]] = field(default=lambda: [])

    def action(self, key: str) -> Action | None:
        return next((a for a in self.actions if a.key == key), None)

    def public(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "record_label": self.record_label,
            "statuses": list(self.statuses),
            "columns": [c.__dict__ for c in self.columns],
            "detail_fields": [c.__dict__ for c in self.detail_fields],
            "actions": [
                {"key": a.key, "label": a.label, "to_status": a.to_status,
                 "from_statuses": list(a.from_statuses), "requires_reason": a.requires_reason}
                for a in self.actions
            ],
        }
