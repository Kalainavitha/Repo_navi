import { useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import type { Member, MemberAllocations } from '../types'
import { Fact, ModalShell } from './ui'

const statusStyle: Record<string, string> = {
  Pending: 'bg-slate-100 text-slate-600',
  'In Progress': 'bg-[#EAF2EC] text-[#245C43]',
  Blocked: 'bg-amber-100 text-amber-800',
  Completed: 'bg-[#123D2B] text-white',
}
const statusText: Record<string, string> = { Pending: 'Yet to start', 'In Progress': 'In process', Blocked: 'Halted', Completed: 'Completed' }

function shortDate(value: string | null) {
  if (!value) return '—'
  const parsed = new Date(`${value}T00:00:00`)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function MemberAllocationsModal({ member, onClose }: { member: Member; onClose: () => void }) {
  const [data, setData] = useState<MemberAllocations | null>(null)
  const [error, setError] = useState('')
  const [openProject, setOpenProject] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    apiFetch<MemberAllocations>(`/api/team-members/${member.id}/allocations`)
      .then((result) => { if (!cancelled) setData(result) })
      .catch((loadError) => { if (!cancelled) setError(loadError instanceof Error ? loadError.message : 'Unable to load allocations.') })
    return () => { cancelled = true }
  }, [member.id])

  const totals = data?.totals
  const done = totals && totals.assigned_hours ? Math.round((100 * totals.completed_hours) / totals.assigned_hours) : 0

  return (
    <ModalShell
      wide
      title={`${member.name} · Allocations`}
      subtitle={`${member.role}${member.additional_role ? ` · ${member.additional_role}` : ''} · ${member.hours_per_day}h/day`}
      onClose={onClose}
      footer={<button type="button" onClick={onClose} className="rounded-xl bg-[#123D2B] px-4 py-2 text-sm font-semibold text-white hover:bg-[#0B2B20]">Close</button>}
    >
      {error ? <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
      {!data && !error ? <div role="status" className="p-4 text-sm text-[#6B776E]">Loading allocations…</div> : null}

      {data ? (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Fact label="Projects" value={totals?.project_count ?? 0} />
            <Fact label="Tasks" value={totals?.task_count ?? 0} />
            <Fact label="Allocated hours" value={`${totals?.assigned_hours ?? 0}h`} />
            <Fact label="Hours remaining" value={`${totals?.remaining_hours ?? 0}h`} />
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between text-xs text-[#6B776E]">
              <span>Work completed</span>
              <span>{done}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-[#EAF2EC]">
              <div className="h-full rounded-full bg-[#245C43]" style={{ width: `${done}%` }} />
            </div>
            <p className="mt-1 text-[11px] text-[#6B776E]">Capacity: {data.daily_capacity}h per working day · {data.weekly_capacity}h per week</p>
          </div>

          <section aria-label="Project allocations">
            <h4 className="mb-2 text-sm font-semibold text-[#18251D]">By project</h4>
            {data.projects.length ? (
              <div className="space-y-2">
                {data.projects.map((project) => {
                  const expanded = openProject === project.project_id
                  return (
                    <div key={project.project_id} className="rounded-xl border border-[#DCE5DE] bg-[#F7F9F7]">
                      <button
                        type="button"
                        aria-expanded={expanded}
                        onClick={() => setOpenProject(expanded ? null : project.project_id)}
                        className="w-full p-3 text-left"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="font-semibold text-[#18251D]">{project.name}</div>
                            <div className="text-xs text-[#6B776E]">{project.status} · {shortDate(project.first_date)} → {shortDate(project.last_date)} · {project.task_count} task(s)</div>
                          </div>
                          <div className="shrink-0 text-right">
                            <div className="text-lg font-bold text-[#0B2B20]">{project.assigned_hours}h</div>
                            <div className="text-[11px] text-[#6B776E]">{project.remaining_hours}h left · {project.share_percent}% of load</div>
                          </div>
                        </div>
                        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white">
                          <div className="h-full rounded-full bg-[#367653]" style={{ width: `${project.share_percent}%` }} />
                        </div>
                      </button>
                      {expanded ? (
                        <ul className="space-y-1 border-t border-[#DCE5DE] bg-white p-3">
                          {project.tasks.map((task) => (
                            <li key={task.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                              <span className="min-w-0 flex-1 truncate text-[#18251D]">{task.title}</span>
                              <span className="text-xs text-[#6B776E]">{shortDate(task.start_date)} → {shortDate(task.end_date)}</span>
                              <span className="text-xs font-medium text-[#18251D]">{task.hours}h</span>
                              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${statusStyle[task.status] ?? statusStyle.Pending}`}>{statusText[task.status] ?? task.status}</span>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] p-4 text-sm text-[#6B776E]">Not assigned to any active project yet.</p>
            )}
          </section>

          <section aria-label="Weekly load">
            <h4 className="mb-2 text-sm font-semibold text-[#18251D]">Weekly hours vs capacity</h4>
            {data.weekly.length ? (
              <ul className="space-y-1.5">
                {data.weekly.map((week) => {
                  const ratio = week.capacity_hours ? week.hours / week.capacity_hours : 0
                  const over = ratio > 1
                  return (
                    <li key={week.week} className="grid grid-cols-[72px_minmax(0,1fr)_88px] items-center gap-2 text-xs">
                      <span className="text-[#6B776E]">Wk {shortDate(week.week)}</span>
                      <div className="h-2.5 overflow-hidden rounded-full bg-[#EAF2EC]" title={week.by_project.map((item) => `${item.name}: ${item.hours}h`).join('\n')}>
                        <div className={`h-full rounded-full ${over ? 'bg-red-500' : ratio > 0.85 ? 'bg-amber-500' : 'bg-[#367653]'}`} style={{ width: `${Math.min(100, Math.round(ratio * 100))}%` }} />
                      </div>
                      <span className={`text-right font-medium ${over ? 'text-red-600' : 'text-[#18251D]'}`}>{week.hours}/{week.capacity_hours}h</span>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="text-sm text-[#6B776E]">No scheduled hours yet.</p>
            )}
          </section>
        </div>
      ) : null}
    </ModalShell>
  )
}
