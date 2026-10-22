const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
export const money = (v: unknown) => (typeof v === "number" ? usd.format(v) : "—");
export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
export function age(iso: string, now = Date.now()) {
  const h = Math.max(0, (now - new Date(iso).getTime()) / 36e5);
  if (h < 1) return `${Math.round(h * 60)}m ago`;
  if (h < 48) return `${Math.floor(h)}h ago`;
  return `${Math.floor(h / 24)}d ${Math.floor(h % 24)}h ago`;
}
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
export function cell(kind: string, v: unknown) {
  if (kind === "money") return money(v);
  if (kind === "datetime" && typeof v === "string") return dateTime(v);
  if (kind === "list" && Array.isArray(v)) return v.length ? v.join(", ") : "None";
  return v == null || v === "" ? "—" : String(v);
}
