interface SummaryMetricProps {
  label: string;
  value: number;
  tone?: "default" | "critical" | "accent";
  helper?: string;
}

export function SummaryMetric({ label, value, tone = "default", helper }: SummaryMetricProps) {
  return (
    <div className={`metric-card metric-${tone}`}>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      {helper ? <span className="metric-helper">{helper}</span> : null}
    </div>
  );
}
