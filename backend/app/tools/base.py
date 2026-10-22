from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    kind: str = "text"  # text | money | datetime | status | list


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
    # Per-tool behavior switches (see README "Per-tool differences").
    overdue_filter: bool = False          # enables ?overdue=true and the "Pending over 48h" count
    value_field: str | None = None        # numeric field summed into "Pending value" (None = hidden)
    requester_field: str = "customer"     # data field used as the actor of the seeded "submitted" event

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
            "features": {"overdue_filter": self.overdue_filter, "value_summary": self.value_field is not None},
            "actions": [
                {"key": a.key, "label": a.label, "to_status": a.to_status,
                 "from_statuses": list(a.from_statuses), "requires_reason": a.requires_reason}
                for a in self.actions
            ],
        }
