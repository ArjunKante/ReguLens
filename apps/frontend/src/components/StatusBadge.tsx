interface Props {
  status: string | null | undefined;
}

export function StatusBadge({ status }: Props) {
  if (!status) return <span className="badge badge-NOT_APPLICABLE">—</span>;
  return <span className={`badge badge-${status}`}>{status.replaceAll("_", " ")}</span>;
}
