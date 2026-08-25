interface Props {
  confidence: number;
}

export function ConfidenceBar({ confidence }: Props) {
  const pct = Math.round(confidence * 100);
  return (
    <span title={`${pct}% confidence`}>
      {pct}%
      <span className="confidence-bar-track">
        <span className="confidence-bar-fill" style={{ width: `${pct}%` }} />
      </span>
    </span>
  );
}
