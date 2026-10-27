type MetricCardProps = {
  label: string
  value: string
  subtext?: string
}

export function MetricCard({ label, value, subtext }: MetricCardProps) {
  return (
    <div className="metric-card">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#6b776e]">{label}</p>
      <div className="mt-3 text-3xl font-bold tracking-tight text-[#0b2b20]">{value}</div>
      {subtext ? <div className="mt-2 text-xs text-[#6b776e]">{subtext}</div> : null}
    </div>
  )
}
