"""Refunds review tool. All seed records are wholly fictional synthetic data."""
from .base import Action, Column, ToolConfig

# (ref, customer, merchant, amount_usd, reason, owner, hours_ago, status, decision_reason)
_SEED = [
    ("RF-1001", "Avery Lindqvist", "Northwind Coffee Roasters", 18.50, "Duplicate charge", "Priya Raman", 2, "pending", None),
    ("RF-1002", "Jonah Okafor", "Brightline Fitness Club", 79.00, "Cancelled membership still billed", "Diego Alvarez", 7, "pending", None),
    ("RF-1003", "Mei Tanaka", "Lumen Electronics Outlet", 1249.99, "Item not received", "Priya Raman", 30, "pending", None),
    ("RF-1004", "Rafael Moreno", "Harbor & Pine Furniture", 642.10, "Damaged on arrival", "Sana Qureshi", 53, "pending", None),
    ("RF-1005", "Elise Fontaine", "Skyward Travel Desk", 2310.00, "Flight cancelled by carrier", "Diego Alvarez", 61, "pending", None),
    ("RF-1006", "Tobias Reinholt", "Copperleaf Grocers", 46.27, "Charged after order cancellation", "Sana Qureshi", 76, "pending", None),
    ("RF-1007", "Naledi Mokoena", "Pixelforge Game Store", 59.99, "Unauthorized in-app purchase", "Priya Raman", 98, "pending", None),
    ("RF-1008", "Owen Gallagher", "Meridian Car Rentals", 318.45, "Overcharged fuel fee", "Diego Alvarez", 20, "approved", "Fuel receipt confirms tank was returned full."),
    ("RF-1009", "Ines Carvalho", "Bluebird Streaming", 14.99, "Subscription renewed after cancel", "Sana Qureshi", 44, "approved", "Cancellation logged before renewal date."),
    ("RF-1010", "Kwame Asante", "Atlas Office Supply", 205.00, "Wrong item shipped", "Priya Raman", 70, "rejected", "Merchant shows correct SKU delivered; customer asked to open return."),
    ("RF-1011", "Freya Halvorsen", "Juniper Home Cleaning", 120.00, "Service not performed", "Diego Alvarez", 120, "approved", "Merchant confirmed missed appointment."),
    ("RF-1012", "Luca Bianchi", "Orbit Mobile Accessories", 33.80, "Changed mind after purchase", "Sana Qureshi", 15, "rejected", "Outside merchant's 14-day return window; not a billing error."),
]


def _seed() -> list[dict]:
    out = []
    for ref, cust, merch, amt, reason, owner, hrs, status, dreason in _SEED:
        out.append({
            "ref": ref,
            "status": status,
            "hours_ago": hrs,
            "data": {"customer": cust, "merchant": merch, "amount_usd": amt,
                     "reason": reason, "owner": owner},
            "decision": None if status == "pending" else {
                "action": "approve" if status == "approved" else "reject",
                "actor": owner, "reason": dreason, "hours_after_submit": min(6, hrs / 2)},
        })
    return out


REFUNDS = ToolConfig(
    key="refunds",
    name="Refunds Review",
    record_label="Refund request",
    statuses=("pending", "approved", "rejected"),
    columns=(
        Column("ref", "Request"),
        Column("customer", "Customer"),
        Column("merchant", "Merchant"),
        Column("amount_usd", "Amount (USD)", "money"),
        Column("reason", "Reason"),
        Column("owner", "Owner"),
        Column("submitted_at", "Submitted", "datetime"),
        Column("status", "Status", "status"),
    ),
    detail_fields=(
        Column("customer", "Customer"),
        Column("merchant", "Merchant"),
        Column("amount_usd", "Amount (USD)", "money"),
        Column("reason", "Customer reason"),
        Column("owner", "Owner"),
        Column("submitted_at", "Submitted", "datetime"),
    ),
    search_fields=("ref", "customer", "merchant", "reason", "owner"),
    actions=(
        Action("approve", "Approve", "approved", ("pending",)),
        Action("reject", "Reject", "rejected", ("pending",)),
    ),
    seed=_seed,
)
