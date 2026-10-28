import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { apiFetch } from '../lib/api'
import type { TeamWorkload } from '../types'

const palette = ['#123D2B', '#367653', '#7FB394', '#B7D5C2', '#D97706', '#0EA5E9', '#8B5CF6', '#EC4899']
const axis = { fontSize: 11, fill: '#6B776E' }

// `refreshKey` changes whenever the team or the saved plans change, so the chart stays current.
export function TeamWorkloadChart({ refreshKey }: { refreshKey: string }) {
  const [state, setState] = useState<{ key: string; data: TeamWorkload | null; failed: boolean } | null>(null)

  useEffect(() => {
    let cancelled = false
    apiFetch<TeamWorkload>('/api/team-workload')
      .then((data) => { if (!cancelled) setState({ key: refreshKey, data, failed: false }) })
      .catch(() => { if (!cancelled) setState({ key: refreshKey, data: null, failed: true }) })
    return () => { cancelled = true }
  }, [refreshKey])

  const data = state?.data ?? null
  const rows = useMemo(
    () => (data?.members ?? []).map((member) => {
      const row: Record<string, string | number> = {
        label: `${member.name} · ${member.hours_per_day}h/day`,
        total: member.total_hours,
      }
      member.by_project.forEach((entry) => { row[`p${entry.project_id}`] = entry.hours })
      return row
    }),
    [data],
  )
  const projects = data?.projects ?? []
  const hasHours = (data?.members ?? []).some((member) => member.total_hours > 0)
  const height = Math.max(170, rows.length * 46 + 40)

  return (
    <section aria-label="Team workload" className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-[#18251D]">Work across projects</h3>
          <p className="text-xs text-[#6B776E]">Planned hours per person on each active project, with their daily working hours.</p>
        </div>
      </div>

      {!state ? (
        <div role="status" className="h-40 animate-pulse rounded-xl bg-[#F1F5F2]" />
      ) : state.failed ? (
        <p role="alert" className="text-sm text-red-600">The team workload could not be loaded.</p>
      ) : !rows.length || !hasHours ? (
        <div className="rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] p-5 text-center text-sm text-[#6B776E]">
          No tasks are assigned yet. Generate a plan to see who is working on what.
        </div>
      ) : (
        <>
          <div style={{ height }} className="w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                <CartesianGrid strokeDasharray="4 4" stroke="#DCE5DE" horizontal={false} />
                <XAxis type="number" tick={axis} tickLine={false} unit="h" />
                <YAxis type="category" dataKey="label" width={170} tick={axis} tickLine={false} />
                <Tooltip formatter={(value) => `${value}h`} cursor={{ fill: 'rgba(36,92,67,0.06)' }} />
                {projects.map((project, index) => (
                  <Bar key={project.id} dataKey={`p${project.id}`} name={project.name} stackId="hours" fill={palette[index % palette.length]} radius={index === projects.length - 1 ? [0, 6, 6, 0] : 0} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[#6B776E]" aria-label="Projects">
            {projects.map((project, index) => (
              <li key={project.id} className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: palette[index % palette.length] }} />
                {project.name}
              </li>
            ))}
          </ul>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {(data?.members ?? []).map((member) => (
              <div key={member.id} className="rounded-lg bg-[#F7F9F7] px-3 py-2 text-xs text-[#6B776E]">
                <div className="font-semibold text-[#18251D]">{member.name}</div>
                <div>{member.total_hours}h planned across {member.by_project.length} project{member.by_project.length === 1 ? '' : 's'} · {member.weekly_hours}h/week available</div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
