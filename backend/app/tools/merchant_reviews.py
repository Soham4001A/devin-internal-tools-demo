"""Merchant Reviews (onboarding operations review mock).

All seed records are wholly fictional synthetic data. This is an internal operations
review queue only; it is NOT KYC/KYB verification or a compliance determination.
"""
from .base import Action, Column, ToolConfig

# (ref, merchant_name, business_category, owner, missing_documents, hours_ago, status, decision_reason)
_SEED = [
    ("MR-2001", "Saltmarsh Ceramics Studio", "Handmade goods", "Priya Raman",
     ["Proof of business address"], 3, "pending", None),
    ("MR-2002", "Quillfeather Bookbinders", "Books & stationery", "Diego Alvarez",
     [], 9, "pending", None),
    ("MR-2003", "Tidewater Kayak Rentals", "Recreation rentals", "Sana Qureshi",
     ["Liability insurance certificate", "Bank account letter"], 27, "pending", None),
    ("MR-2004", "Emberly Candle Co.", "Home fragrance", "Priya Raman",
     ["Product catalog"], 55, "pending", None),
    ("MR-2005", "Northgate Mobile Detailing", "Automotive services", "Diego Alvarez",
     ["Business registration extract", "Refund policy page"], 80, "pending", None),
    ("MR-2006", "Fernhollow Plant Nursery", "Garden & plants", "Sana Qureshi",
     [], 40, "approved", "All requested documents received; storefront and policies match application."),
    ("MR-2007", "Brassbell Music Lessons", "Education services", "Priya Raman",
     [], 72, "approved", "Website, pricing and cancellation terms reviewed; nothing outstanding."),
    ("MR-2008", "Velvet Comet Novelties", "Novelty retail", "Diego Alvarez",
     ["Bank account letter", "Proof of business address", "Product catalog"], 150, "rejected",
     "Applicant did not respond to three document requests within 10 business days."),
]


def _seed() -> list[dict]:
    out = []
    for ref, name, category, owner, missing, hrs, status, dreason in _SEED:
        out.append({
            "ref": ref,
            "status": status,
            "hours_ago": hrs,
            "data": {"merchant_name": name, "business_category": category, "owner": owner,
                     "missing_documents": missing},
            "decision": None if status == "pending" else {
                "action": "approve" if status == "approved" else "reject",
                "actor": owner, "reason": dreason, "hours_after_submit": min(8, hrs / 2)},
        })
    return out


MERCHANT_REVIEWS = ToolConfig(
    key="merchant_reviews",
    name="Merchant Reviews",
    record_label="Merchant review",
    statuses=("pending", "approved", "rejected"),
    columns=(
        Column("ref", "Case"),
        Column("merchant_name", "Merchant"),
        Column("business_category", "Business category"),
        Column("submitted_at", "Submitted", "datetime"),
        Column("owner", "Owner"),
        Column("missing_documents", "Missing documents", "list"),
        Column("status", "Review status", "status"),
    ),
    detail_fields=(
        Column("merchant_name", "Merchant"),
        Column("business_category", "Business category"),
        Column("owner", "Owner"),
        Column("submitted_at", "Submitted", "datetime"),
        Column("missing_documents", "Missing documents", "list"),
    ),
    search_fields=("ref", "merchant_name", "business_category", "owner", "missing_documents"),
    actions=(
        Action("approve", "Approve", "approved", ("pending",)),
        Action("reject", "Reject", "rejected", ("pending",)),
    ),
    seed=_seed,
    overdue_filter=False,
    value_field=None,
    requester_field="merchant_name",
)
