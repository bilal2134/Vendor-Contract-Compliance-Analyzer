interface SummaryMetricProps {
  label: string;
  value: number;
}

export function SummaryMetric({ label, value }: SummaryMetricProps) {
  return (
    <div className="metric-card">
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
    </div>
  );
}
