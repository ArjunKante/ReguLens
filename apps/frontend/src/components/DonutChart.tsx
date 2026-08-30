export interface DonutChartDatum {
  key: string;
  label: string;
  count: number;
  /** A CSS color (var(--status-...) so it matches StatusBadge's palette). */
  color: string;
}

interface DonutChartProps {
  data: DonutChartDatum[];
  total: number;
  size?: number;
}

const RADIUS = 42;
const STROKE = 16;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** A dependency-free SVG donut chart (no charting library exists in this
 * project yet — see package.json — so this stays a small, purpose-built
 * component rather than pulling one in for a single chart). Segments are
 * plain stroked circle arcs via stroke-dasharray, in the same status colors
 * StatusBadge already uses, so the chart and the badges/legend always agree
 * visually. Renders a neutral empty ring when there is nothing to show
 * (e.g. a completed inspection with zero evaluated rules) rather than
 * fabricating a full circle. */
export function DonutChart({ data, total, size = 168 }: DonutChartProps) {
  const nonZero = data.filter((d) => d.count > 0);
  let offset = 0;

  return (
    <div
      className="donut-chart"
      role="img"
      aria-label={
        total > 0
          ? `Rule evaluation distribution: ${nonZero.map((d) => `${d.label} ${d.count}`).join(", ")}, total ${total}`
          : "No rules evaluated"
      }
    >
      <svg viewBox="0 0 100 100" width={size} height={size}>
        <circle cx="50" cy="50" r={RADIUS} fill="none" stroke="var(--color-border)" strokeWidth={STROKE} opacity={total > 0 ? 0.25 : 1} />
        {total > 0 &&
          nonZero.map((d) => {
            const fraction = d.count / total;
            const dash = fraction * CIRCUMFERENCE;
            const el = (
              <circle
                key={d.key}
                cx="50"
                cy="50"
                r={RADIUS}
                fill="none"
                stroke={d.color}
                strokeWidth={STROKE}
                strokeDasharray={`${dash} ${CIRCUMFERENCE - dash}`}
                strokeDashoffset={-offset}
                transform="rotate(-90 50 50)"
              />
            );
            offset += dash;
            return el;
          })}
      </svg>
      <div className="donut-chart__center">
        <span className="donut-chart__total">{total}</span>
        <span className="donut-chart__total-label">Total Rules</span>
      </div>
    </div>
  );
}
