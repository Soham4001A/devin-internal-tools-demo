/**
 * Client-side per-tool presentation. Server config (columns/statuses/actions/features) comes from /api/tools/{key};
 * permissions, reason rules and transitions are enforced by the backend only.
 */
export type ToolUi = {
  key: string;
  path: string; // client route, e.g. "/refunds"
  navLabel: string;
  title: string;
  subtitle: string;
  searchPlaceholder: string;
  totalLabel: string;
  banner: string;
  reasonPlaceholder: string;
  decisionFootnote: string;
};

export const TOOL_UIS: ToolUi[] = [
  {
    key: "refunds",
    path: "/refunds",
    navLabel: "Refunds Review",
    title: "Refunds review queue",
    subtitle: "Review customer refund requests and record an approve/reject decision.",
    searchPlaceholder: "Search request, customer, merchant, reason, owner…",
    totalLabel: "Total requests",
    banner: "all customers, merchants and amounts are synthetic. Decisions are recorded here only; no refunds or payments are executed.",
    reasonPlaceholder: "e.g. Duplicate charge confirmed against merchant settlement report",
    decisionFootnote: "Records a decision only. No payment is executed.",
  },
  {
    key: "merchant_reviews",
    path: "/merchant-reviews",
    navLabel: "Merchant Reviews",
    title: "Merchant reviews queue",
    subtitle: "Onboarding operations review of fictional merchant applications. Not KYC/KYB verification or a compliance check.",
    searchPlaceholder: "Search case, merchant, category, owner, missing document…",
    totalLabel: "Total cases",
    banner: "all merchants and cases are fictional. This is an operations review mock only — not identity, KYC/KYB or compliance verification.",
    reasonPlaceholder: "e.g. All requested onboarding documents received and reviewed",
    decisionFootnote: "Records an operations review decision only. Not a KYC/compliance determination.",
  },
];

export const toolForPath = (pathname: string): ToolUi =>
  TOOL_UIS.find((t) => pathname === t.path || pathname.startsWith(`${t.path}/`)) ?? TOOL_UIS[0];
