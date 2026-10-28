import { NavLink } from 'react-router-dom'
import { AlertTriangle, ArrowUpRight, CheckCircle2, FolderKanban, Plus, Users } from 'lucide-react'
import type { DashboardData, Member } from '../../types'
import { SeverityBadge } from '../ui'
import { CalendarCard } from './CalendarCard'
import { UpcomingDeadlines } from './UpcomingDeadlines'

type Props = {
  dashboard: DashboardData | null
  loading: boolean
  todayLabel: string
  members: Member[]
  onOpenProject: (projectId: number) => void
  onCreatePlan: () => void
}

const panel = 'min-w-0 rounded-2xl border border-[#DCE5DE] bg-white p-4 shadow-sm'

function greeting() {
  const hour = new Date().getHours()
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
}

function Empty({ children }: { children: string }) {
  return <div className="rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] p-4 text-sm text-[#6B776E]">{children}</div>
}

export function HomeDashboard({ dashboard, loading, todayLabel, members, onOpenProject, onCreatePlan }: Props) {
  const metrics = dashboard?.metrics
  const overdue = metrics?.overdue_tasks ?? 0
  const leads = members.filter((member) => member.is_lead)
  const noProjects = !loading && (metrics?.total_projects ?? 0) === 0

  const kpis = [
    { label: 'Total Projects', count: metrics?.total_projects, note: 'All plans created', to: '/generated-plan', icon: FolderKanban, tone: 'from-[#123D2B] to-[#245C43]' },
    { label: 'Team Members', count: metrics?.team_members, note: leads.length ? `${leads.length} team lead${leads.length > 1 ? 's' : ''}` : 'Available to plan', to: '/team-info', icon: Users, tone: 'from-[#367653] to-[#5E9B78]' },
  ]

  return (
    <div className="space-y-4">
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#0B2B20] via-[#123D2B] to-[#245C43] px-5 py-4 text-white shadow-md md:px-6 md:py-5">
        <div className="pointer-events-none absolute -right-10 -top-12 h-40 w-40 rounded-full bg-white/5" />
        <div className="relative flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#CFE4D7]">{todayLabel}</div>
            <h2 className="mt-1 text-xl font-bold md:text-2xl">{greeting()}! Welcome to GenPlan 👋</h2>
            <p className="mt-0.5 text-sm text-[#CFE4D7]">Let's make today a productive one.</p>
            <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-[#CFE4D7]">
              {loading ? 'Loading your portfolio…' : `${metrics?.total_projects ?? 0} project${(metrics?.total_projects ?? 0) === 1 ? '' : 's'} in your portfolio`}
              {!loading ? (
                overdue ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-400/20 px-2 py-0.5 text-xs font-semibold text-amber-200"><AlertTriangle size={12} /> {overdue} overdue</span>
                ) : (metrics?.total_projects ?? 0) > 0 ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-white/10 px-2 py-0.5 text-xs font-semibold text-[#CFE4D7]"><CheckCircle2 size={12} /> Nothing overdue</span>
                ) : null
              ) : null}
            </p>
          </div>
          <button type="button" onClick={onCreatePlan} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-[#123D2B] shadow-sm transition hover:bg-[#EAF2EC]">
            <Plus size={16} /> Create a plan
          </button>
        </div>
      </section>

      <section aria-label="Key numbers" className="grid gap-3 sm:grid-cols-2">
        {kpis.map(({ label, count, note, to, icon: Icon, tone }) => (
          <NavLink key={label} to={to} className="group relative overflow-hidden rounded-xl border border-[#DCE5DE] bg-white p-4 shadow-sm transition hover:border-[#245C43] hover:shadow-md">
            <div className={`absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r ${tone}`} />
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#6B776E]">{label}</div>
                {loading ? (
                  <div className="mt-2 h-7 w-12 animate-pulse rounded bg-[#E8EFEA]" aria-label="Loading" />
                ) : (
                  <div className="mt-1 text-3xl font-bold leading-none tracking-tight text-[#0B2B20]">{count ?? 0}</div>
                )}
                <div className="mt-1.5 text-xs text-[#245C43]">{note}</div>
              </div>
              <span className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br ${tone} text-white`}>
                <Icon size={18} />
              </span>
            </div>
            <ArrowUpRight size={13} className="absolute bottom-2.5 right-2.5 text-[#C7D8CD] transition group-hover:text-[#123D2B]" />
          </NavLink>
        ))}
      </section>

      <div className="grid items-stretch gap-4 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
        <CalendarCard onOpenProject={onOpenProject} />
        <UpcomingDeadlines items={dashboard?.upcoming_deadlines ?? []} loading={loading} onOpenProject={onOpenProject} />
      </div>

      <section className={panel}>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-semibold text-[#18251D]">Recent Projects</h3>
          <NavLink to="/generated-plan" className="text-sm font-medium text-[#123D2B] hover:underline">View all</NavLink>
        </div>
        {noProjects ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] px-4 py-8 text-center">
            <span className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-[#EAF2EC] text-[#123D2B]"><FolderKanban size={20} /></span>
            <p className="font-semibold text-[#18251D]">No projects yet</p>
            <p className="max-w-sm text-sm text-[#6B776E]">Create your first plan from a user-story document and GenPlan will split the work across your team.</p>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {loading ? <div role="status" className="p-3 text-sm text-[#6B776E]">Loading saved projects…</div> : dashboard?.recent_projects.length ? dashboard.recent_projects.map((item) => (
              <button key={item.id} type="button" onClick={() => onOpenProject(item.id)} className="rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-3 text-left transition hover:border-[#245C43] hover:bg-white">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate font-medium text-[#18251D]">{item.name}</div>
                    <div className="text-xs text-[#6B776E]">{item.project_type} · {item.task_count} tasks{item.deadline ? ` · due ${item.deadline}` : ''}</div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="rounded-full bg-[#EAF2EC] px-2 py-0.5 text-xs font-medium text-[#123D2B]">{item.status}</span>
                    {item.risk_level && item.risk_level !== 'Low' ? <SeverityBadge level={item.risk_level} /> : null}
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white"><div className="h-full rounded-full bg-[#367653]" style={{ width: `${item.progress_percent}%` }} /></div>
                  <span className="text-xs font-medium text-[#245C43]">{item.progress_percent}%</span>
                </div>
              </button>
            )) : <div className="md:col-span-2"><Empty>No saved projects yet.</Empty></div>}
          </div>
        )}
      </section>
    </div>
  )
}
