import { useEffect, useState } from 'react'
import { Gauge } from 'lucide-react'
import { apiFetch } from '../lib/api'
import type { Forecast } from '../types'

function niceDate(value: string | null) {
  if (!value) return '-'
  const parsed = new Date(`${value}T00:00:00`)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

type Tone = { stroke: string; text: string; badge: string; label: string }

function toneFor(probability: number | null): Tone {
  if (probability === null) return { stroke: '#94A3B8', text: 'text-slate-500', badge: 'bg-slate-100 text-slate-600', label: 'No deadline set' }
  if (probability >= 0.8) return { stroke: '#367653', text: 'text-[#245C43]', badge: 'bg-[#EAF2EC] text-[#245C43]', label: 'Likely on time' }
  if (probability >= 0.5) return { stroke: '#D97706', text: 'text-amber-700', badge: 'bg-amber-50 text-amber-800', label: 'Coin flip' }
  return { stroke: '#DC2626', text: 'text-red-600', badge: 'bg-red-100 text-red-700', label: 'Needs attention' }
}

export function ForecastCard({ projectId, refreshKey, onRequestReplan }: { projectId: number; refreshKey: string; onRequestReplan: () => void }) {
  const [state, setState] = useState<{ key: string; data: Forecast | null; failed: boolean } | null>(null)

  useEffect(() => {
    let cancelled = false
    apiFetch<Forecast>(`/api/projects/${projectId}/forecast`)
      .then((data) => { if (!cancelled) setState({ key: refreshKey, data, failed: false }) })
      .catch(() => { if (!cancelled) setState({ key: refreshKey, data: null, failed: true }) })
    return () => { cancelled = true }
  }, [projectId, refreshKey])

  const data = state?.data ?? null
  const probability = data?.probability_on_time ?? null
  const histogram = data?.histogram ?? []
  const threats = data?.critical_tasks ?? []
  const confidence = (data?.confidence ?? 'Low').toLowerCase()
  const tone = toneFor(probability)
  const percent = probability === null ? 0 : Math.round(probability * 100)
  const circumference = 2 * Math.PI * 42
  const peak = Math.max(1, ...histogram.map((bucket) => bucket.count))

  return (
    <section aria-label="On-time forecast" className="rounded-xl border border-[#DCE5DE] bg-white p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-[#EAF2EC] text-[#123D2B]"><Gauge size={16} /></span>
          <div>
            <h3 className="text-sm font-semibold text-[#18251D]">On-time forecast</h3>
            <p className="text-[11px] text-[#6B776E]">Runs the remaining work {data?.runs || 300} times with realistic overruns</p>
          </div>
        </div>
        {data ? <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${tone.badge}`}>{tone.label}</span> : null}
      </div>

      {!state ? (
        <div role="status" aria-label="Loading forecast" className="h-28 animate-pulse rounded-xl bg-[#F1F5F2]" />
      ) : state.failed || !data ? (
        <p role="alert" className="text-sm text-red-600">The forecast could not be calculated.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-[130px_minmax(0,1fr)_minmax(0,1fr)] md:items-center">
          <div className="relative mx-auto h-[110px] w-[110px]">
            <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90" aria-hidden="true">
              <circle cx="50" cy="50" r="42" fill="none" stroke="#EEF3EF" strokeWidth="10" />
              <circle cx="50" cy="50" r="42" fill="none" stroke={tone.stroke} strokeWidth="10" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - percent / 100)} />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className={`text-2xl font-bold ${tone.text}`} aria-label="On-time probability">{probability === null ? '-' : `${percent}%`}</span>
              <span className="text-[10px] text-[#6B776E]">{probability === null ? 'no deadline' : `by ${niceDate(data.deadline)}`}</span>
            </div>
          </div>

          <div className="min-w-0 space-y-2 text-sm">
            <div className="rounded-lg bg-[#F7F9F7] px-3 py-2">
              <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#6B776E]">Most likely finish</div>
              <div className="font-semibold text-[#18251D]">{niceDate(data.p50)}</div>
            </div>
            <div className="rounded-lg bg-[#F7F9F7] px-3 py-2">
              <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#6B776E]">Safe date (85% sure)</div>
              <div className="font-semibold text-[#18251D]">{niceDate(data.p85)}</div>
            </div>
            <p className="text-[11px] text-[#6B776E]">Range {niceDate(data.earliest)} to {niceDate(data.latest)} · confidence {confidence}</p>
          </div>

          <div className="min-w-0">
            {histogram.length ? (
              <div className="mb-3 flex h-12 items-end gap-0.5" role="img" aria-label="Spread of simulated finish dates">
                {histogram.map((bucket) => (
                  <span
                    key={bucket.date}
                    title={`${niceDate(bucket.date)}: ${bucket.count} of ${data.runs} runs`}
                    className="min-w-[3px] flex-1 rounded-t bg-[#A9C6B3]"
                    style={{ height: `${Math.max(8, Math.round((bucket.count / peak) * 100))}%`, background: data.deadline && bucket.date > data.deadline ? '#F2B8B5' : undefined }}
                  />
                ))}
              </div>
            ) : null}
            {threats.length ? (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#6B776E]">Biggest threats</div>
                <ul className="space-y-1">
                  {threats.slice(0, 3).map((task) => (
                    <li key={task.id} className="flex items-center justify-between gap-2 text-xs text-[#18251D]">
                      <span className="min-w-0 truncate">{task.title}</span>
                      <span className="shrink-0 text-[#6B776E]">{Math.round(task.share * 100)}% of runs</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : <p className="text-xs text-[#6B776E]">All remaining work is finished.</p>}
          </div>
        </div>
      )}

      {data && probability !== null && probability < 0.7 ? (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <span>The odds are below 70%. Re-planning from today may recover time.</span>
          <button type="button" onClick={onRequestReplan} className="rounded-md bg-amber-600 px-2.5 py-1 font-semibold text-white hover:bg-amber-700">Review re-plan</button>
        </div>
      ) : null}
    </section>
  )
}
