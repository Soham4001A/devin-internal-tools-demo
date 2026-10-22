import { cap } from "../format";
export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${status}`}>{cap(status)}</span>;
}
