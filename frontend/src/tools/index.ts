/** Client-side per-tool presentation. Server config (columns/statuses/actions) comes from /api/tools/{key}. */
export type ToolUi = { key: string; navLabel: string; title: string; subtitle: string; searchPlaceholder: string };

export const TOOL_UIS: ToolUi[] = [
  {
    key: "refunds",
    navLabel: "Refunds Review",
    title: "Refunds review queue",
    subtitle: "Review customer refund requests and record an approve/reject decision.",
    searchPlaceholder: "Search request, customer, merchant, reason, owner…",
  },
  // Next module example: { key: "merchant_reviews", navLabel: "Merchant Reviews", ... }
];
