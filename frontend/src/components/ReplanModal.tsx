import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowRight, CheckCircle2 } from 'lucide-react'
import { apiFetch } from '../lib/api'
import type { Impact } from '../types'
import { Fact, ModalShell } from './ui'

function niceDate(value: string | null) {
  if (!value) return '-'
  const parsed = new Date(`${value}T00:00:00`)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}

// Shows what slips if the unfinished work is re-scheduled from today, and lets the user save that re-plan.
export function ReplanModal({ projectId, onClose, onApplied }: { projectId: number; onClose: () => void; onApplied: () => void | Promise<void> }) {
  const [impact, setImpact] = useState<Impact | null>(null)
  const [error, setError] = useState('')
  const [applying, setApplying] = useState(false)

  useEffect(() => {
    let cancelled = false
    apiFetch<Impact>(`/api/projects/${projectId}/impact`)
      .then((data) => { if (!cancelled) setImpact(data) })
      .catch((loadError) => { if (!cancelled) setError(loadError instanceof Error ? loadError.message : 'Unable to analyse the delay.') })
    return () => { cancelled = true }
  }, [projectId])

  const apply = async () => {
    setApplying(true)
    setError('')
    try {
      await apiFetch(`/api/projects/${projectId}/replan`, { method: 'POST' })
      await onApplied()
      onClose()
    } catch (applyError) {
      setError(applyError instanceof Error ? applyError.message : 'The re-plan could not be saved.')
    } finally {
      setApplying(false)
    }
  }

  const slip = impact?.slip_days ?? 0
  const deadlineWorse = impact ? impact.deadline_ok === false : false

  return (
    <ModalShell
      wide
      title="Re-plan from today"
      subtitle="Delay impact"
      onClose={() => { if (!applying) onClose() }}
      footer={
        <>
          <button type="button" disabled={applying} onClick={onClose} className="rounded-xl border border-[#DCE5DE] bg-white px-4 py-2 text-sm font-medium text-[#18251D] disabled:opacity-50">Cancel</button>
          <button
            type="button"
            disabled={applying || !impact || !impact.needs_replan}
            onClick={() => void apply()}
            className="rounded-xl bg-[#123D2B] px-4 py-2 text-sm font-semibold text-white hover:bg-[#0B2B20] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {applying ? 'Applying…' : 'Apply re-plan'}
          </button>
        </>
      }
    >
      {error ? <div role="alert" className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
      {!impact && !error ? <div role="status" className="p-4 text-sm text-[#6B776E]">Analysing the plan…</div> : null}

      {impact ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Fact label="Overdue tasks" value={impact.overdue.length} />
            <Fact label="Halted tasks" value={impact.blocked.length} />
            <Fact label="Finish now" value={niceDate(impact.original_finish)} />
            <Fact label="Finish after re-plan" value={niceDate(impact.replanned_finish)} />
          </div>

          {impact.needs_replan ? (
            <div className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${deadlineWorse ? 'border-red-200 bg-red-50 text-red-700' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <span>
                {slip > 0 ? `The finish date slips by ${slip} day${slip === 1 ? '' : 's'}. ` : 'The finish date does not change. '}
                {impact.deadline ? (impact.deadline_ok ? `It still meets the deadline (${niceDate(impact.deadline)}).` : `It misses the deadline (${niceDate(impact.deadline)}).`) : ''}
              </span>
            </div>
          ) : (
            <div className="flex items-start gap-2 rounded-lg border border-[#CFE4D7] bg-[#F1F8F3] px-3 py-2 text-sm text-[#245C43]">
              <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
              <span>Everything is on schedule. There is nothing to re-plan.</span>
            </div>
          )}

          {impact.shifted_tasks.length ? (
            <section aria-label="Tasks that move">
              <h4 className="mb-2 text-sm font-semibold text-[#18251D]">{impact.shifted_tasks.length} task{impact.shifted_tasks.length === 1 ? '' : 's'} move{impact.shifted_tasks.length === 1 ? 's' : ''}{impact.people_affected.length ? ` · affects ${impact.people_affected.join(', ')}` : ''}</h4>
              <ul className="max-h-56 space-y-1.5 overflow-y-auto pr-1">
                {impact.shifted_tasks.map((task) => (
                  <li key={task.id} className="rounded-lg border border-[#DCE5DE] bg-[#F7F9F7] px-3 py-2 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate font-medium text-[#18251D]">{task.title}</span>
                      <span className="shrink-0 text-xs text-[#6B776E]">{task.assignee_name}</span>
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-[#6B776E]">
                      <span>{niceDate(task.old_end)}</span><ArrowRight size={12} /><span className="font-semibold text-[#18251D]">{niceDate(task.new_end)}</span>
                      <span className={task.delta_days > 0 ? 'text-amber-700' : 'text-[#245C43]'}>({task.delta_days > 0 ? '+' : ''}{task.delta_days} days)</span>
                      {task.status === 'Blocked' ? <span className="rounded-full bg-amber-100 px-1.5 text-[10px] font-semibold text-amber-800">Halted</span> : null}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <p className="text-xs text-[#6B776E]">Applying keeps completed tasks and who does what, and only changes the dates and daily hours of unfinished work.</p>
        </div>
      ) : null}
    </ModalShell>
  )
}
