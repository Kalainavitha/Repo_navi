import { AlertTriangle, ShieldCheck } from 'lucide-react'
import type { RiskSeverity } from '../types'
import { normalizeRisks, severityStyles } from './severity'

export function RiskPanel({ summary }: { summary?: Record<string, unknown> }) {
  const risks = normalizeRisks(summary?.risks)
  const level = (summary?.risk_level as RiskSeverity | undefined) ?? (risks[0]?.severity ?? 'Low')
  const score = typeof summary?.risk_score === 'number' ? (summary.risk_score as number) : undefined
  const projected = typeof summary?.projected_completion === 'string' ? (summary.projected_completion as string) : null
  const buffered = typeof summary?.buffered_completion === 'string' ? (summary.buffered_completion as string) : null
  const tone = level === 'High' ? 'border-red-200 bg-red-50' : level === 'Medium' ? 'border-amber-200 bg-amber-50' : 'border-[#CFE4D7] bg-[#F1F8F3]'
  const Icon = risks.length ? AlertTriangle : ShieldCheck

  return (
    <section aria-label="Plan risks" className={`rounded-xl border p-4 ${tone}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon size={18} className={level === 'High' ? 'text-red-600' : level === 'Medium' ? 'text-amber-600' : 'text-[#245C43]'} />
          <h3 className="text-sm font-semibold text-[#18251D]">Plan risks</h3>
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${(severityStyles[level] ?? severityStyles.Low).badge}`}>{level} overall</span>
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-[#6B776E]">
          {score !== undefined ? <span>Risk score <strong className="text-[#18251D]">{score}</strong>/100</span> : null}
          {projected ? <span>Planned finish <strong className="text-[#18251D]">{projected}</strong></span> : null}
          {buffered ? <span>With buffer <strong className="text-[#18251D]">{buffered}</strong></span> : null}
        </div>
      </div>
      {risks.length ? (
        <ul className="mt-3 space-y-2">
          {risks.map((risk, index) => (
            <li key={`${risk.type}-${index}`} className="flex items-start gap-2 rounded-lg bg-white/70 px-3 py-2 text-sm text-[#18251D]">
              <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${(severityStyles[risk.severity] ?? severityStyles.Low).dot}`} />
              <span className="min-w-0 flex-1">{risk.message}</span>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${(severityStyles[risk.severity] ?? severityStyles.Low).badge}`}>{risk.severity}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-[#245C43]">No risks were detected for this plan.</p>
      )}
    </section>
  )
}
