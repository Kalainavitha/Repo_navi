import { useEffect, useState } from 'react'
import { GraduationCap } from 'lucide-react'
import { apiFetch } from '../lib/api'
import type { EstimateAccuracy } from '../types'

// A ratio of 1.0 means "as planned". The bar shows how far a person's real time is from the plan.
function RatioBar({ ratio }: { ratio: number }) {
  const clamped = Math.max(0.5, Math.min(2, ratio))
  const offset = ((clamped - 0.5) / 1.5) * 100
  const slow = ratio > 1.05
  const fast = ratio < 0.95
  return (
    <div className="relative h-2 rounded-full bg-[#EAF2EC]" role="img" aria-label={`Takes ${Math.round(ratio * 100)}% of the planned time`}>
      <span className="absolute left-1/3 top-[-2px] h-3 w-px bg-[#6B776E]" title="As planned" />
      <span className={`absolute top-[-1px] h-2.5 w-2.5 -translate-x-1/2 rounded-full ${slow ? 'bg-amber-500' : fast ? 'bg-[#367653]' : 'bg-[#123D2B]'}`} style={{ left: `${offset}%` }} />
    </div>
  )
}

// `refreshKey` changes when tasks are updated, so the card learns from the latest completions.
export function EstimateCoachCard({ refreshKey }: { refreshKey: string }) {
  const [state, setState] = useState<{ key: string; data: EstimateAccuracy | null; failed: boolean } | null>(null)

  useEffect(() => {
    let cancelled = false
    apiFetch<EstimateAccuracy>('/api/estimate-accuracy')
      .then((data) => { if (!cancelled) setState({ key: refreshKey, data, failed: false }) })
      .catch(() => { if (!cancelled) setState({ key: refreshKey, data: null, failed: true }) })
    return () => { cancelled = true }
  }, [refreshKey])

  const data = state?.data ?? null
  const members = data?.members ?? []
  const learnedCount = members.filter((member) => member.learned).length

  return (
    <section aria-label="Estimate coach" className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-[#EAF2EC] text-[#123D2B]"><GraduationCap size={16} /></span>
          <div>
            <h3 className="text-base font-semibold text-[#18251D]">Estimate Coach</h3>
            <p className="text-xs text-[#6B776E]">Learns how long each person really takes and corrects new plans automatically.</p>
          </div>
        </div>
        {data ? <span className="rounded-full bg-[#F1F5F2] px-2 py-0.5 text-xs font-semibold text-[#245C43]">{learnedCount} of {members.length} learned</span> : null}
      </div>

      {!state ? (
        <div role="status" aria-label="Loading estimate accuracy" className="h-24 animate-pulse rounded-xl bg-[#F1F5F2]" />
      ) : state.failed || !data ? (
        <p role="alert" className="text-sm text-red-600">The estimate accuracy could not be loaded.</p>
      ) : (data.samples ?? 0) === 0 ? (
        <div className="rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] p-5 text-center text-sm text-[#6B776E]">
          Nothing to learn from yet. Mark tasks <span className="font-semibold text-[#18251D]">In process</span> and then <span className="font-semibold text-[#18251D]">Completed</span>; after {data.min_samples ?? 3} finished tasks per person, GenPlan starts correcting their estimates.
        </div>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {members.map((member) => (
            <li key={member.id} className="rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate font-semibold text-[#18251D]">{member.name}</div>
                  <div className="text-[11px] uppercase tracking-wide text-[#245C43]">{member.role}</div>
                </div>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${member.learned ? 'bg-[#123D2B] text-white' : 'bg-white text-[#6B776E]'}`}>
                  {member.learned ? (member.applied_factor && member.applied_factor !== 1 ? `Applied x${member.applied_factor}` : 'Accurate') : `${member.samples}/${data.min_samples ?? 3} tasks`}
                </span>
              </div>
              <div className="mt-3">{member.avg_ratio !== null ? <RatioBar ratio={member.avg_ratio} /> : <div className="h-2 rounded-full bg-[#EAF2EC]" />}</div>
              <p className="mt-2 text-xs text-[#6B776E]">{member.label}</p>
              {member.by_phase.length ? (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {member.by_phase.map((phase) => (
                    <li key={phase.phase} className="rounded-full bg-white px-2 py-0.5 text-[10px] text-[#6B776E]" title={`${phase.samples} completed task(s)`}>
                      {phase.phase} <span className="font-semibold text-[#18251D]">x{phase.ratio}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-[11px] text-[#6B776E]">Duration is measured from In process to Completed, so it works best when statuses are updated promptly.</p>
    </section>
  )
}
