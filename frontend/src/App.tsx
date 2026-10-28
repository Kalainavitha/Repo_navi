import { useEffect, useMemo, useRef, useState, type ChangeEvent, type InputHTMLAttributes, type ReactNode } from 'react'
import { BrowserRouter, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Archive, ClipboardList, Crown, FilePlus2, FileText, FolderKanban, House, Menu, Pencil, Plus, RefreshCw, Rocket, Search, Users, Wrench, X } from 'lucide-react'
import { apiFetch, previewDocument, uploadDocument } from './lib/api'
import type { DashboardData, Member, ProjectFormState, SavedProject, Story, Task } from './types'
import { Fact, ModalShell, SeverityBadge } from './components/ui'
import { RiskPanel } from './components/RiskPanel'
import { MemberAllocationsModal } from './components/MemberAllocationsModal'
import { TeamWorkloadChart } from './components/TeamWorkloadChart'
import { ForecastCard } from './components/ForecastCard'
import { ReplanModal } from './components/ReplanModal'
import { WeeklyReportModal } from './components/WeeklyReportModal'
import { EstimateCoachCard } from './components/EstimateCoachCard'
import { HomeDashboard } from './components/dashboard/HomeDashboard'

const projectTypes = ['Web Application', 'Mobile Application', 'Desktop Application', 'API or Backend System', 'AI/ML Application', 'Data Engineering Platform', 'E-commerce Platform', 'Enterprise Software', 'Cloud Migration', 'DevOps or Infrastructure', 'Cybersecurity Project', 'IoT Application', 'Other']
const roleOptions = ['Team Lead', 'Project Manager', 'Frontend Developer', 'Backend Developer', 'QA Engineer', 'Product Manager', 'UX Designer', 'DevOps Engineer', 'Data Engineer', 'Security Engineer', 'Business Analyst', 'Full-Stack Developer']
const workingDaysOptions = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const navItems = [
  { label: 'Home', to: '/', icon: House },
  { label: 'Create Plan', to: '/create-plan', icon: FilePlus2 },
  { label: 'Team Info', to: '/team-info', icon: Users },
  { label: 'Generated Plan', to: '/generated-plan', icon: FolderKanban },
  { label: 'Archive', to: '/archive', icon: Archive },
] as const

const pageTitles: Record<string, string> = {
  '/': 'Home',
  '/create-plan': 'Create Plan',
  '/team-info': 'Team Info',
  '/generated-plan': 'Generated Plan',
  '/archive': 'Archive',
}

const inputClassName = 'w-full rounded-xl border border-[#DCE5DE] bg-white px-3 py-2.5 text-sm text-[#18251D] shadow-sm transition focus:border-[#123D2B] focus:outline-none focus:ring-2 focus:ring-[#123D2B]/10'
const selectClassName = `${inputClassName} appearance-none`

const defaultForm: ProjectFormState = {
  name: 'Customer Portal Modernization',
  description: 'Modernize the customer portal with login, self-service billing, and notification workflows.',
  project_type: 'Web Application',
  start_date: '2026-11-02',
  deadline: '2026-12-18',
  priority: 'High',
  complexity: 'Medium',
  working_days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
  hours_per_day: 8,
  holidays: ['2026-11-26', '2026-12-25'],
  timezone: 'UTC',
  buffer_percent: 10,
  members: [
    { id: 'PM-1', name: 'Asha Patel', role: 'Project Manager', skills: ['planning', 'risk', 'stakeholder'], experience: 9, hours_per_day: 8, allocation: 100, available_from: '2026-11-02', available_until: '2026-12-18', leave_dates: ['2026-11-20'] },
    { id: 'FE-1', name: 'Lucas Ji', role: 'Frontend Developer', skills: ['react', 'typescript', 'ux'], experience: 6, hours_per_day: 7, allocation: 80, available_from: '2026-11-02', available_until: '2026-12-18', leave_dates: ['2026-12-04'] },
    { id: 'BE-1', name: 'Nora Chen', role: 'Backend Developer', skills: ['python', 'fastapi', 'sql'], experience: 7, hours_per_day: 8, allocation: 90, available_from: '2026-11-02', available_until: '2026-12-18', leave_dates: [] },
    { id: 'QA-1', name: 'Mateo Ruiz', role: 'QA Engineer', skills: ['testing', 'automation', 'quality'], experience: 5, hours_per_day: 6, allocation: 75, available_from: '2026-11-02', available_until: '2026-12-18', leave_dates: ['2026-11-27'] },
  ],
}

const newPlanDefaults: ProjectFormState = {
  ...defaultForm,
  name: '',
  description: '',
  members: [],
}

type MemberFormValues = {
  name: string
  email: string
  role: string
  additional_role: string
  experience: string
  primary_skills: string
  skill_proficiency: string
  hours_per_day: string
  working_days: string
  leave_dates: string
}

const emptyMemberForm: MemberFormValues = {
  name: '',
  email: '',
  role: 'Frontend Developer',
  additional_role: '',
  experience: '3',
  primary_skills: 'react, typescript',
  skill_proficiency: 'Intermediate',
  hours_per_day: '8',
  working_days: 'Monday, Tuesday, Wednesday, Thursday, Friday',
  leave_dates: '',
}

function todayIso() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

// Changes whenever a task's status, date or owner changes, so the smart cards refresh with the plan.
function planSignature(plan: any): string {
  if (!plan) return 'none'
  const tasks = (plan.tasks ?? []) as Task[]
  return `${plan.project_id}:${tasks.map((task) => `${task.status}${task.end_date ?? ''}${task.assignee_id ?? ''}`).join('|')}`
}

function FormField({ label, required = false, children, error }: { label: string; required?: boolean; children: ReactNode; error?: string }) {
  return (
    <div className="space-y-2">
      <label className="block text-sm font-semibold text-[#18251D]">
        <span className="inline-flex items-center gap-1">
          {label}
          {required ? <span className="text-[#123D2B]">*</span> : null}
        </span>
      </label>
      {children}
      {error ? <p className="text-xs font-medium text-red-600">{error}</p> : null}
    </div>
  )
}

function TextInput({ label, required, value, onChange, error, type = 'text', ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; required?: boolean; error?: string }) {
  return (
    <FormField label={label} required={required} error={error}>
      <input type={type} value={value} onChange={onChange} className={inputClassName} {...props} />
    </FormField>
  )
}

function SelectField({ label, required, value, onChange, error, children }: { label: string; required?: boolean; value: string; onChange: (event: ChangeEvent<HTMLSelectElement>) => void; error?: string; children: ReactNode }) {
  return (
    <FormField label={label} required={required} error={error}>
      <select value={value} onChange={onChange} className={selectClassName}>
        {children}
      </select>
    </FormField>
  )
}

const standardTaskCategories = ['UI/Frontend', 'Backend', 'QA/Testing', 'Integration', 'DevOps/Deployment', 'Documentation', 'Planning & Analysis', 'Other']

function taskCategory(task: Task) {
  const category = (task.category || '').trim().toLowerCase()
  return standardTaskCategories.find((value) => value.toLowerCase() === category) ?? 'Other'
}

const statusOptions = [
  { label: 'Yet to start', value: 'Pending' },
  { label: 'In process', value: 'In Progress' },
  { label: 'Halted', value: 'Blocked' },
  { label: 'Completed', value: 'Completed' },
]
const priorityOptions = ['High', 'Medium', 'Low']
const statusSelectTone: Record<string, string> = {
  Pending: 'border-slate-200 bg-slate-50 text-slate-600',
  'In Progress': 'border-[#CFE4D7] bg-[#EAF2EC] text-[#245C43]',
  Blocked: 'border-amber-200 bg-amber-50 text-amber-800',
  Completed: 'border-[#123D2B] bg-[#123D2B] text-white',
}

const statusColors: Record<string, string> = {
  Pending: '#94A3B8',
  'In Progress': '#367653',
  Blocked: '#F59E0B',
  Completed: '#123D2B',
}
const priorityBadge: Record<string, string> = {
  Critical: 'bg-red-100 text-red-700',
  High: 'bg-orange-100 text-orange-700',
  Medium: 'bg-amber-50 text-amber-700',
  Low: 'bg-[#EAF2EC] text-[#245C43]',
}

const fieldClass = 'w-full rounded-xl border border-[#DCE5DE] bg-white px-3 py-2.5 text-sm text-[#18251D] shadow-sm transition focus:border-[#123D2B] focus:outline-none focus:ring-2 focus:ring-[#123D2B]/10 disabled:cursor-not-allowed disabled:bg-[#F7F9F7] disabled:text-[#6B776E]'
const smallFieldClass = 'w-full rounded-lg border border-[#DCE5DE] bg-white px-2 py-2 text-xs text-[#18251D] focus:border-[#123D2B] focus:outline-none focus:ring-2 focus:ring-[#123D2B]/10'
const labelClass = 'mb-1 block text-[11px] font-semibold uppercase tracking-[0.14em] text-[#245C43]'
const boxClass = 'rounded-xl border border-[#DCE5DE] bg-white p-3 shadow-sm'

const statusLabel = (value: string) => statusOptions.find((option) => option.value === value)?.label ?? value

function formatDate(value: string) {
  const parsed = new Date(`${value}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}

function shortSummary(task: Task, max = 110) {
  const text = (task.summary || task.description || '').replace(/\s+/g, ' ').trim()
  if (!text) return task.title
  const first = text.match(/^.*?[.!?](?=\s|$)/)?.[0] ?? text
  return first.length > max ? `${first.slice(0, max - 1).trimEnd()}…` : first
}

type Row = {
  key: string
  date: string
  memberId: string
  memberName: string
  items: { task: Task; hours?: number }[]
}

type GeneratedPlanViewProps = {
  plan: any
  members: Member[]
  onStatusChange: (taskId: string, status: string) => void | Promise<void>
  onAssign: (taskId: string, memberId: string) => void | Promise<void>
  canReassign?: boolean
}

const defaultFilters = { category: 'All Tasks', member: 'All Members', priority: 'All Priorities', status: 'All Statuses' }

function GeneratedPlanView({ plan, members, onStatusChange, onAssign, canReassign = false }: GeneratedPlanViewProps) {
  const [filters, setFilters] = useState(defaultFilters)
  const [summaryTaskId, setSummaryTaskId] = useState<string | null>(null)
  const [editTaskId, setEditTaskId] = useState<string | null>(null)
  const [editAssignee, setEditAssignee] = useState('')
  const [editStatus, setEditStatus] = useState('')
  const [saving, setSaving] = useState(false)
  const [statusBusyId, setStatusBusyId] = useState<string | null>(null)
  const readOnly = Boolean(plan?.archived)

  // Anyone working on the plan can report progress; only reassigning/editing is limited to Team Leads.
  const changeStatus = async (task: Task, next: string) => {
    if (next === task.status || statusBusyId) return
    setStatusBusyId(task.id)
    try {
      await onStatusChange(task.id, next)
    } finally {
      setStatusBusyId(null)
    }
  }

  const statusSelect = (task: Task) => (
    <select
      aria-label={`Status of ${task.title}`}
      value={task.status}
      disabled={readOnly || statusBusyId === task.id}
      onChange={(event) => void changeStatus(task, event.target.value)}
      className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold focus:outline-none focus:ring-2 focus:ring-[#123D2B]/20 disabled:cursor-not-allowed disabled:opacity-60 ${statusSelectTone[task.status] ?? statusSelectTone.Pending}`}
    >
      {statusOptions.map((option) => <option key={option.value} value={option.value} className="bg-white text-[#18251D]">{option.label}</option>)}
    </select>
  )

  const allocatedTasks = useMemo<Task[]>(
    () => ((plan?.tasks ?? []) as Task[]).filter((task) => Boolean(task.assignee_id || task.assignee_name)),
    [plan],
  )
  const taskById = useMemo(() => new Map(allocatedTasks.map((task) => [task.id, task])), [allocatedTasks])
  const memberById = useMemo(() => new Map(members.map((member) => [member.id, member])), [members])

  const categoryStats = useMemo(
    () =>
      standardTaskCategories
        .map((category) => {
          const list = allocatedTasks.filter((task) => taskCategory(task) === category)
          return {
            category,
            count: list.length,
            hours: list.reduce((sum, task) => sum + (task.effort_hours ?? 0), 0),
            people: new Set(list.map((task) => task.assignee_name)).size,
            done: list.filter((task) => task.status === 'Completed').length,
          }
        })
        .filter((item) => item.count > 0),
    [allocatedTasks],
  )

  const memberNames = useMemo(
    () => [...new Set(allocatedTasks.map((task) => task.assignee_name).filter(Boolean) as string[])],
    [allocatedTasks],
  )

  const matches = (task: Task) =>
    (filters.category === 'All Tasks' || taskCategory(task) === filters.category) &&
    (filters.member === 'All Members' || task.assignee_name === filters.member) &&
    (filters.priority === 'All Priorities' || task.priority === filters.priority) &&
    (filters.status === 'All Statuses' || task.status === filters.status)

  const dailyWorkload: any[] = plan?.daily_workload ?? []
  let rows: Row[] = []
  if (dailyWorkload.some((day) => day.tasks?.length)) {
    dailyWorkload.forEach((day) => {
      const items = (day.tasks ?? [])
        .map((item: any) => ({ task: taskById.get(item.id), hours: item.allocated_hours as number | undefined }))
        .filter((entry: { task?: Task }) => entry.task && matches(entry.task)) as { task: Task; hours?: number }[]
      if (items.length) rows.push({ key: `${day.date}-${day.member_id}`, date: day.date, memberId: day.member_id, memberName: day.member_name, items })
    })
  } else {
    const grouped = new Map<string, Row>()
    allocatedTasks.filter(matches).forEach((task) => {
      const date = task.start_date || 'Unscheduled'
      const key = `${date}-${task.assignee_id ?? task.assignee_name}`
      const row = grouped.get(key) ?? { key, date, memberId: task.assignee_id ?? '', memberName: task.assignee_name ?? '', items: [] }
      row.items.push({ task })
      grouped.set(key, row)
    })
    rows = [...grouped.values()]
  }
  rows.sort((a, b) => {
    const left = a.date === 'Unscheduled' ? '~' : a.date
    const right = b.date === 'Unscheduled' ? '~' : b.date
    return left === right ? a.memberName.localeCompare(b.memberName) : left.localeCompare(right)
  })
  const dateGroups = rows.reduce((map, row) => map.set(row.date, [...(map.get(row.date) ?? []), row]), new Map<string, Row[]>())

  const summaryTask = summaryTaskId ? taskById.get(summaryTaskId) : undefined
  const editTask = editTaskId ? taskById.get(editTaskId) : undefined
  const focusMember: Member | undefined = filters.member !== 'All Members' ? members.find((member) => member.name === filters.member) : undefined

  const completed = allocatedTasks.filter((task) => task.status === 'Completed').length
  const progress = allocatedTasks.length ? Math.round((completed / allocatedTasks.length) * 100) : 0
  const filtersActive = Object.entries(filters).some(([key, value]) => value !== (defaultFilters as Record<string, string>)[key])

  const openEdit = (task: Task) => {
    if (!canReassign) return;
    setSummaryTaskId(null)
    setEditAssignee(task.assignee_id ?? '')
    setEditStatus(task.status)
    setEditTaskId(task.id)
  }

  const saveEdit = async () => {
    if (!editTask) return
    setSaving(true)
    try {
      if (editStatus && editStatus !== editTask.status) await onStatusChange(editTask.id, editStatus)
      if (editAssignee && editAssignee !== (editTask.assignee_id ?? '')) await onAssign(editTask.id, editAssignee)
    } finally {
      setSaving(false)
      setEditTaskId(null)
    }
  }

  const stages = (() => {
    const levels = new Map<string, number>()
    const levelOf = (id: string, seen: Set<string>): number => {
      const cached = levels.get(id)
      if (cached !== undefined) return cached
      if (seen.has(id)) return 0
      const deps = (taskById.get(id)?.dependencies ?? []).filter((dep) => taskById.has(dep))
      const nextSeen = new Set(seen).add(id)
      const level = deps.length ? Math.max(...deps.map((dep) => levelOf(dep, nextSeen))) + 1 : 0
      levels.set(id, level)
      return level
    }
    allocatedTasks.forEach((task) => levelOf(task.id, new Set()))
    const max = Math.max(0, ...Array.from(levels.values()))
    return Array.from({ length: max + 1 }, (_, index) => allocatedTasks.filter((task) => levels.get(task.id) === index))
  })()

  return (
    <div className="space-y-4">
      <RiskPanel summary={plan?.summary} />

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-[#F7F9F7] p-3">
          <div className="text-xs uppercase tracking-[0.12em] text-[#6B776E]">Allocated Tasks</div>
          <div className="mt-2 text-lg font-semibold text-[#18251D]">{allocatedTasks.length}</div>
        </div>
        <div className="rounded-xl bg-[#F7F9F7] p-3">
          <div className="text-xs uppercase tracking-[0.12em] text-[#6B776E]">Progress</div>
          <div className="mt-2 text-lg font-semibold text-[#18251D]">{progress}%</div>
        </div>
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-4 sm:flex-row sm:items-end sm:justify-between">
        <label className="block w-full sm:max-w-xs">
          <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.14em] text-[#245C43]">Category</span>
          <select value={filters.category} onChange={(event) => setFilters((current) => ({ ...current, category: event.target.value }))} className={fieldClass}>
            <option value="All Tasks">All Tasks</option>
            {categoryStats.map((item) => (
              <option key={item.category} value={item.category}>{item.category} ({item.count})</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={!filtersActive}
          onClick={() => setFilters(defaultFilters)}
          className="rounded-xl border border-[#DCE5DE] bg-white px-4 py-2.5 text-sm font-medium text-[#18251D] disabled:opacity-50"
        >
          Clear filters
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]">
        <section className="@container min-w-0 rounded-xl border border-[#DCE5DE] bg-white p-4">
          <div className="hidden gap-3 border-b border-[#DCE5DE] pb-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#245C43] @2xl:grid @2xl:grid-cols-[130px_160px_minmax(0,1fr)]">
            <div>Date</div>
            <div>Team Member</div>
            <div>Scheduled Task</div>
          </div>

          {dateGroups.size ? (
            <div className="mt-4 space-y-6">
              {[...dateGroups.entries()].map(([date, dayRows]) => (
                <div key={date} className="gap-3 @2xl:grid @2xl:grid-cols-[130px_minmax(0,1fr)]">
                  <div className="relative mb-3 border-l-2 border-[#CFE4D7] pl-4 @2xl:mb-0">
                    <span className="absolute -left-[7px] top-1 h-3 w-3 rounded-full bg-[#123D2B] ring-4 ring-white" />
                    <div className="text-sm font-semibold text-[#18251D]">{date === 'Unscheduled' ? date : formatDate(date)}</div>
                    <div className="text-xs text-[#6B776E]">{dayRows.reduce((sum, row) => sum + row.items.length, 0)} task(s)</div>
                  </div>

                  <div className="min-w-0 space-y-4">
                    {dayRows.map((row) => (
                      <div key={row.key} className="gap-3 @2xl:grid @2xl:grid-cols-[160px_minmax(0,1fr)]">
                        <div className="mb-2 @2xl:mb-0">
                          <div className="font-medium text-[#18251D]">{row.memberName}</div>
                          <div className="text-xs text-[#6B776E]">{memberById.get(row.memberId)?.role ?? ''}</div>
                        </div>

                        <div className="min-w-0 space-y-2">
                          {row.items.map(({ task, hours }) => (
                            <div
                              key={task.id}
                              style={{ borderLeftColor: statusColors[task.status] ?? '#94A3B8' }}
                              className="flex flex-col gap-2 rounded-xl border border-l-4 border-[#DCE5DE] bg-white p-3 shadow-sm @xl:flex-row @xl:items-center @xl:justify-between"
                            >
                              <div className="min-w-0">
                                <div className="text-xs font-semibold text-[#245C43]">{task.id} · {taskCategory(task)}</div>
                                <div className="truncate font-medium text-[#18251D]">{task.title}</div>
                                <div className="truncate text-sm text-[#6B776E]">{shortSummary(task)}</div>
                              </div>
                              <div className="flex shrink-0 flex-wrap items-center gap-2">
                                <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${priorityBadge[task.priority] ?? 'bg-[#EAF2EC] text-[#245C43]'}`}>{task.priority}</span>
                                {task.risk_level && task.risk_level !== 'Low' ? <SeverityBadge level={task.risk_level} /> : null}
                                {statusSelect(task)}
                                <span className="text-xs text-[#6B776E]">{hours ?? task.effort_hours}h</span>
                                <button
                                  type="button"
                                  onClick={() => setSummaryTaskId(task.id)}
                                  className="rounded-lg bg-[#123D2B] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#0B2B20]"
                                >
                                  View
                                </button>
                                {canReassign && (
                                  <button
                                    type="button"
                                    onClick={() => openEdit(task)}
                                    className="rounded-lg border border-[#DCE5DE] bg-white px-3 py-1.5 text-xs font-semibold text-[#123D2B] hover:bg-[#EAF2EC]"
                                  >
                                    Edit
                                  </button>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] p-6 text-center text-sm text-[#6B776E]">
              No allocated tasks match the selected filters.
            </div>
          )}
        </section>

        <aside className="grid grid-cols-2 content-start gap-3 sm:grid-cols-4 lg:grid-cols-1">
          <div className={boxClass}>
            <label className="block">
              <span className={labelClass}>Member</span>
              <select value={filters.member} onChange={(event) => setFilters((current) => ({ ...current, member: event.target.value }))} className={smallFieldClass}>
                <option value="All Members">All Members</option>
                {memberNames.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </label>
            {focusMember ? (
              <div className="mt-2 space-y-0.5 rounded-lg bg-[#F7F9F7] p-2 text-[11px] text-[#6B776E]">
                <div className="text-xs font-semibold text-[#18251D]">{focusMember.name}</div>
                <div className="uppercase tracking-wide text-[#245C43]">{focusMember.role}</div>
                <div>{focusMember.experience} yrs · {focusMember.hours_per_day}h/day</div>
                <div className="break-words">Skills: {focusMember.skills.join(', ') || 'None'}</div>
              </div>
            ) : (
              <p className="mt-2 text-[11px] text-[#6B776E]">Pick a member to see details.</p>
            )}
          </div>

          <div className={boxClass}>
            <label className="block">
              <span className={labelClass}>Priority</span>
              <select value={filters.priority} onChange={(event) => setFilters((current) => ({ ...current, priority: event.target.value }))} className={smallFieldClass}>
                <option value="All Priorities">All Priorities</option>
                {priorityOptions.map((priority) => <option key={priority} value={priority}>{priority}</option>)}
              </select>
            </label>
          </div>

          <div className={boxClass}>
            <label className="block">
              <span className={labelClass}>Completion Status</span>
              <select value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))} className={smallFieldClass}>
                <option value="All Statuses">All Statuses</option>
                {statusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
          </div>

          <div className={`${boxClass} col-span-2 sm:col-span-4 lg:col-span-1`}>
            <div className={labelClass}>Category Details</div>
            {categoryStats.length ? (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-1">
                {categoryStats.map((item) => (
                  <button
                    key={item.category}
                    type="button"
                    aria-pressed={filters.category === item.category}
                    onClick={() => setFilters((current) => ({ ...current, category: current.category === item.category ? 'All Tasks' : item.category }))}
                    className={`rounded-lg border p-2 text-left text-[11px] transition hover:border-[#245C43] ${filters.category === item.category ? 'border-[#123D2B] bg-[#EAF2EC]' : 'border-[#DCE5DE] bg-[#F7F9F7]'}`}
                  >
                    <div className="text-xs font-semibold text-[#18251D]">{item.category}</div>
                    <div className="mt-0.5 text-[#6B776E]">{item.count} task(s) · {item.hours}h</div>
                    <div className="text-[#6B776E]">{item.people} member(s) · {item.done} done</div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-[#6B776E]">No allocated tasks yet.</p>
            )}
          </div>
        </aside>
      </div>

      <details className="rounded-xl border border-[#DCE5DE] bg-white p-4">
        <summary className="cursor-pointer text-sm font-semibold text-[#18251D]">Task dependency stages</summary>
        <div className="mt-4 space-y-4">
          {stages.map((stage, index) => stage.length ? (
            <div key={`stage-${index}`}>
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#245C43]">Stage {index + 1}</div>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {stage.map((task) => (
                  <div key={task.id} className="rounded-lg border border-[#DCE5DE] bg-[#F7F9F7] p-3 text-sm">
                    <div className="font-semibold text-[#18251D]">{task.id} · {task.title}</div>
                    <div className="mt-1 text-xs text-[#6B776E]">{task.assignee_name} · {task.effort_hours}h · {statusLabel(task.status)}</div>
                    <div className="mt-1 text-[11px] text-[#6B776E]">{task.dependencies.length ? `Depends on: ${task.dependencies.join(', ')}` : 'Starting task'}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null)}
        </div>
      </details>

      {summaryTask ? (
        <ModalShell
          subtitle={`${summaryTask.id} · ${taskCategory(summaryTask)}`}
          title={summaryTask.title}
          onClose={() => setSummaryTaskId(null)}
          footer={
            <>
              {canReassign && (
                <button type="button" onClick={() => openEdit(summaryTask)} className="rounded-xl border border-[#DCE5DE] bg-white px-4 py-2 text-sm font-medium text-[#123D2B] hover:bg-[#EAF2EC]">Edit</button>
              )}
              <button type="button" onClick={() => setSummaryTaskId(null)} className="rounded-xl bg-[#123D2B] px-4 py-2 text-sm font-semibold text-white hover:bg-[#0B2B20]">Close</button>
            </>
          }
        >
          <p className="text-sm font-medium leading-relaxed text-[#18251D]">{shortSummary(summaryTask, 220)}</p>
          {summaryTask.summary_source === 'task' && summaryTask.description && summaryTask.description !== summaryTask.summary ? (
            <p className="mt-2 text-sm leading-relaxed text-[#6B776E]">{summaryTask.description}</p>
          ) : null}
          {summaryTask.summary_source === 'task' && summaryTask.acceptance_criteria?.length ? (
            <div className="mt-3">
              <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#6B776E]">Done when</div>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-[#18251D]">
                {summaryTask.acceptance_criteria.slice(0, 3).map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          ) : null}
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Fact label="Assigned to" value={summaryTask.assignee_name || '—'} />
            <Fact label="Status" value={statusSelect(summaryTask)} />
            <Fact label="Priority" value={summaryTask.priority} />
            <Fact label="Effort" value={`${summaryTask.effort_hours}h`} />
            <Fact label="Start" value={summaryTask.start_date || '—'} />
            <Fact label="End" value={summaryTask.end_date || '—'} />
          </div>
          <div className="mt-2 rounded-lg bg-[#F7F9F7] p-2 text-xs text-[#6B776E]">
            <span className="font-semibold text-[#18251D]">Depends on:</span> {summaryTask.dependencies.length ? summaryTask.dependencies.join(', ') : 'None'}
          </div>
          {summaryTask.rationale ? <div className="mt-2 rounded-lg bg-[#F7F9F7] p-2 text-xs text-[#6B776E]"><span className="font-semibold text-[#18251D]">Why this person:</span> {summaryTask.rationale}</div> : null}
          {summaryTask.risk_note ? (
            <div className={`mt-2 rounded-lg border px-3 py-2 text-xs ${summaryTask.risk_level === 'High' ? 'border-red-200 bg-red-50 text-red-700' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>
              <span className="font-semibold">{summaryTask.risk_level} risk:</span> {summaryTask.risk_note}
            </div>
          ) : null}
          {summaryTask.warning ? <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">{summaryTask.warning}</div> : null}
        </ModalShell>
      ) : null}

      {editTask ? (
        <ModalShell
          subtitle="Edit task"
          title={`${editTask.id} · ${editTask.title}`}
          onClose={() => { if (!saving) setEditTaskId(null) }}
          footer={
            <>
              <button type="button" disabled={saving} onClick={() => setEditTaskId(null)} className="rounded-xl border border-[#DCE5DE] bg-white px-4 py-2 text-sm font-medium text-[#18251D] disabled:opacity-50">Cancel</button>
              <button type="button" disabled={saving} onClick={() => void saveEdit()} className="rounded-xl bg-[#123D2B] px-4 py-2 text-sm font-semibold text-white hover:bg-[#0B2B20] disabled:opacity-50">{saving ? 'Saving…' : 'Save'}</button>
            </>
          }
        >
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.14em] text-[#245C43]">Assigned member</span>
              <select value={editAssignee} onChange={(event) => setEditAssignee(event.target.value)} className={fieldClass}>
                {members.map((member) => <option key={member.id} value={member.id}>{member.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.14em] text-[#245C43]">Completion status</span>
              <select value={editStatus} onChange={(event) => setEditStatus(event.target.value)} className={fieldClass}>
                {statusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
          </div>
        </ModalShell>
      ) : null}
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}

function AppShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const initialProjectId = useRef(Number(new URLSearchParams(location.search).get('project_id')) || undefined)
  const [todayLabel] = useState(() => new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }))
  const [project, setProject] = useState<ProjectFormState>(defaultForm)
  const [members, setMembers] = useState<Member[]>([])
  const [planMembers, setPlanMembers] = useState<Member[]>([])
  const [previewStories, setPreviewStories] = useState<Story[]>([])
  const [previewText, setPreviewText] = useState('')
  const [plan, setPlan] = useState<any | null>(null)
  const [savedProjects, setSavedProjects] = useState<SavedProject[]>([])
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [status, setStatus] = useState('Ready to plan')
  const [loading, setLoading] = useState(false)
  const [portfolioLoading, setPortfolioLoading] = useState(true)
  const [pendingProjectActionId, setPendingProjectActionId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [documentLoading, setDocumentLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const previewRequestId = useRef(0)
  const [teamSearch, setTeamSearch] = useState('')
  const [selectedMember, setSelectedMember] = useState<Member | null>(null)
  const [allocationsMember, setAllocationsMember] = useState<Member | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(() => (typeof window === 'undefined' ? true : window.innerWidth >= 768))
  const [memberFormOpen, setMemberFormOpen] = useState(false)
  const [editingMemberId, setEditingMemberId] = useState<string | null>(null)
  const [memberFormValues, setMemberFormValues] = useState<MemberFormValues>(emptyMemberForm)
  const [memberFormErrors, setMemberFormErrors] = useState<Record<string, string>>({})
  const [memberFeedback, setMemberFeedback] = useState('')
  const archivedPlans = savedProjects.filter((item) => item.archived)
  const portfolioRequestId = useRef(0)


  const refreshPortfolio = async (preferredProjectId?: number) => {
    const requestId = ++portfolioRequestId.current
    setPortfolioLoading(true)
    try {
      const [nextMembers, activeProjects, archivedProjects, nextDashboard] = await Promise.all([
        apiFetch<Member[]>('/api/team-members'),
        apiFetch<SavedProject[]>('/api/projects'),
        apiFetch<SavedProject[]>('/api/projects?archived=true'),
        apiFetch<DashboardData>('/api/dashboard'),
      ])
      if (requestId !== portfolioRequestId.current) return
      const nextProjects = [...activeProjects, ...archivedProjects]
      setMembers(nextMembers)
      setSavedProjects(nextProjects)
      setDashboard(nextDashboard)

      const candidate = preferredProjectId
        ? nextProjects.find((item) => item.id === preferredProjectId)
        : nextProjects.find((item) => item.has_plan && !item.archived)
      if (candidate?.has_plan) {
        const details = await apiFetch<SavedProject>(`/api/projects/${candidate.id}`)
        if (requestId !== portfolioRequestId.current) return
        setPlan(details.plan ?? null)
        setPlanMembers(details.members ?? [])
        setProject((current) => ({
          ...current,
          name: details.name,
          description: details.description,
          project_type: details.project_type,
          start_date: details.start_date,
          deadline: details.deadline ?? '',
        }))
      } else if (preferredProjectId === undefined) {
        setPlan(null)
        setPlanMembers([])
      }
    } finally {
      if (requestId === portfolioRequestId.current) setPortfolioLoading(false)
    }
  }

  useEffect(() => {
    refreshPortfolio(initialProjectId.current).catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load saved GenPlan data.')
    })
  }, [])

  const resetCreatePlanForm = () => {
    previewRequestId.current += 1
    setProject({ ...newPlanDefaults, working_days: [...newPlanDefaults.working_days], holidays: [...newPlanDefaults.holidays] })
    setSelectedFile(null)
    setPreviewStories([])
    setPreviewText('')
    setDocumentLoading(false)
    setError('')
    setStatus('Ready to plan')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const isCreatePage = location.pathname === '/create-plan'
  const isHomePage = location.pathname === '/'
  const pageTitle = pageTitles[location.pathname] ?? 'Page not found'

  useEffect(() => {
    document.title = isHomePage ? 'GenPlan' : `${pageTitle} · GenPlan`
  }, [isHomePage, pageTitle])

  const handleHeaderAction = () => {
    if (isCreatePage) {
      void generatePlan()
      return
    }
    resetCreatePlanForm()
    navigate('/create-plan')
  }

  const [regenerating, setRegenerating] = useState(false)
  const [replanOpen, setReplanOpen] = useState(false)
  const [reportOpen, setReportOpen] = useState(false)
  const [assigningMembers, setAssigningMembers] = useState(false)
  const missingMembers = plan ? members.filter((member) => !planMembers.some((onPlan) => onPlan.id === member.id)) : []
  const lateTaskCount = plan
    ? ((plan.tasks ?? []) as Task[]).filter((task) => task.status === 'Blocked' || (task.status !== 'Completed' && Boolean(task.end_date) && (task.end_date as string) < todayIso())).length
    : 0
  const assignNewMembers = async () => {
    if (!plan?.project_id || assigningMembers) return
    setAssigningMembers(true)
    setError('')
    try {
      const outcome = await apiFetch<{ added_members: string[]; moved: unknown[] }>(`/api/projects/${plan.project_id}/rebalance`, { method: 'POST' })
      await refreshPortfolio(plan.project_id)
      setStatus(
        outcome.added_members.length
          ? `${outcome.added_members.join(', ')} joined the project and took ${outcome.moved.length} task${outcome.moved.length === 1 ? '' : 's'}`
          : 'Everyone is already on this project',
      )
    } catch (assignError) {
      setError(assignError instanceof Error ? assignError.message : 'The new members could not be assigned.')
    } finally {
      setAssigningMembers(false)
    }
  }

  const regeneratePlan = async () => {
    if (!plan?.project_id || regenerating) return
    if (!window.confirm('Regenerate this plan? Tasks are rebuilt from the uploaded stories using the current team and their other projects. Task progress and manual edits will be reset.')) return
    setRegenerating(true)
    setError('')
    try {
      await apiFetch<unknown>(`/api/projects/${plan.project_id}/generate-plan`, { method: 'POST' })
      await refreshPortfolio(plan.project_id)
      setStatus('Plan regenerated')
    } catch (regenerateError) {
      setError(regenerateError instanceof Error ? regenerateError.message : 'The plan could not be regenerated.')
    } finally {
      setRegenerating(false)
    }
  }

  const openProject = async (projectId: number) => {
    try {
      const details = await apiFetch<SavedProject>(`/api/projects/${projectId}`)
      if (!details.plan) throw new Error('This project does not have a generated plan to open.')
      setPlan(details.plan ?? null)
      setPlanMembers(details.members ?? [])
      setProject((current) => ({
        ...current,
        name: details.name,
        description: details.description,
        project_type: details.project_type,
        start_date: details.start_date,
        deadline: details.deadline ?? '',
      }))
      setError('')
      navigate(`/generated-plan?project_id=${projectId}`)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to open the saved project.')
    }
  }

  const filteredMembers = useMemo(() => {
    const query = teamSearch.trim().toLowerCase()
    if (!query) return members
    return members.filter((member) => `${member.name} ${member.role} ${member.skills.join(' ')}`.toLowerCase().includes(query))
  }, [members, teamSearch])

  const handleProjectField = (field: keyof ProjectFormState, value: string | number | string[]) => {
    setProject((current) => ({ ...current, [field]: value }))
  }

  const toggleWorkingDay = (day: string) => {
    setProject((current) => {
      const nextDays = current.working_days.includes(day)
        ? current.working_days.filter((value) => value !== day)
        : [...current.working_days, day]
      return { ...current, working_days: nextDays }
    })
  }

  const openAddMemberForm = () => {
    setEditingMemberId(null)
    setMemberFormValues(emptyMemberForm)
    setMemberFormErrors({})
    setMemberFeedback('')
    setMemberFormOpen(true)
  }

  const openEditMemberForm = (member: Member) => {
    setEditingMemberId(member.id)
    setMemberFormValues({
      name: member.name,
      email: member.email ?? '',
      role: member.role,
      experience: String(member.experience ?? 0),
      additional_role: member.additional_role ?? '',
      primary_skills: member.skills.join(', '),
      skill_proficiency: 'Intermediate',
      hours_per_day: String(member.hours_per_day ?? 8),
      working_days: (member.working_days ?? workingDaysOptions.slice(0, 5)).join(', '),
      leave_dates: member.leave_dates.join(', '),
    })
    setMemberFormErrors({})
    setMemberFeedback('')
    setMemberFormOpen(true)
  }

  const closeMemberForm = () => {
    setMemberFormOpen(false)
    setEditingMemberId(null)
    setMemberFormErrors({})
    setMemberFeedback('')
  }

  const parseSkills = (primary: string, additional: string) => {
    const values = [primary, additional]
      .flatMap((part) => part.split(',').map((item) => item.trim()))
      .filter(Boolean)
    return [...new Set(values)]
  }

  const validateMemberForm = () => {
    const errors: Record<string, string> = {}
    if (!memberFormValues.name.trim()) errors.name = 'Name is required.'
    if (memberFormValues.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(memberFormValues.email.trim())) errors.email = 'Enter a valid email address or leave it empty.'
    if (!memberFormValues.role.trim()) errors.role = 'Role is required.'
    if (!memberFormValues.experience || Number(memberFormValues.experience) < 0) errors.experience = 'Years of experience is required.'
    if (!memberFormValues.primary_skills.trim()) errors.primary_skills = 'Add at least one skill.'
    if (!memberFormValues.hours_per_day || Number(memberFormValues.hours_per_day) <= 0 || Number(memberFormValues.hours_per_day) > 24) errors.hours_per_day = 'Working hours must be between 1 and 24.'
    setMemberFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const saveMember = async () => {
    if (!validateMemberForm()) {
      setMemberFeedback('Please correct the highlighted team member fields.')
      return
    }

    const nextSkills = parseSkills(memberFormValues.primary_skills, '')
    const newMember = {
      name: memberFormValues.name.trim(),
      role: memberFormValues.role,
      skills: nextSkills,
      experience: Number(memberFormValues.experience),
      hours_per_day: Number(memberFormValues.hours_per_day),
      working_days: memberFormValues.working_days.split(',').map((item) => item.trim()).filter(Boolean),
      available_from: null,
      available_until: null,
      leave_dates: memberFormValues.leave_dates.split(',').map((item) => item.trim()).filter(Boolean),
      email: memberFormValues.email.trim() || null,
      additional_role: memberFormValues.additional_role || null,
    }

    try {
      setMemberFeedback('Saving...')
      if (editingMemberId) {
        await apiFetch<Member>(`/api/team-members/${editingMemberId}`, { method: 'PATCH', body: JSON.stringify(newMember) })
      } else {
        await apiFetch<Member>('/api/team-members', { method: 'POST', body: JSON.stringify(newMember) })
      }
      await refreshPortfolio()
      setMemberFeedback(editingMemberId ? 'Member updated successfully.' : 'Member added successfully.')
      setTimeout(() => closeMemberForm(), 250)
    } catch (saveError) {
      console.error("Failed to save member:", saveError)
      const msg = saveError instanceof Error ? saveError.message : 'The team member could not be saved.'
      setMemberFeedback(msg)
    }
  }

  const removeMember = async (memberId: string) => {
    if (!window.confirm('Delete this team member? Members assigned to saved tasks cannot be deleted.')) return
    try {
      await apiFetch<void>(`/api/team-members/${memberId}`, { method: 'DELETE' })
      await refreshPortfolio()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'The team member could not be deleted.')
    }
  }

  const validateSelectedFile = (file: File | null) => {
    if (!file) {
      throw new Error('Select a valid PDF, DOCX, or TXT user story document.')
    }
    const allowedExtensions = ['.pdf', '.docx', '.txt', '.md', '.markdown']
    const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    if (!allowedExtensions.includes(extension)) {
      throw new Error('Only PDF, DOCX, TXT, or Markdown files are supported.')
    }
    if (file.size > 10 * 1024 * 1024) {
      throw new Error('The uploaded file exceeds the 10 MB limit.')
    }
    return file
  }

  const handleDocumentSelection = async (file: File | null) => {
    const requestId = ++previewRequestId.current
    setSelectedFile(null)
    setPreviewStories([])
    setPreviewText('')
    setError('')
    setDocumentLoading(false)
    if (!file) return

    try {
      const validFile = validateSelectedFile(file)
      setSelectedFile(validFile)
      setDocumentLoading(true)
      const result = await previewDocument(validFile)
      if (requestId !== previewRequestId.current) return
      setPreviewStories(result.stories)
      setPreviewText(result.preview)
    } catch (previewError) {
      if (requestId !== previewRequestId.current) return
      setSelectedFile(null)
      setError(previewError instanceof Error ? previewError.message : 'The document could not be processed.')
      if (fileInputRef.current) fileInputRef.current.value = ''
    } finally {
      if (requestId === previewRequestId.current) setDocumentLoading(false)
    }
  }

  const generatePlan = async () => {
    if (!project.name || !project.start_date || members.length === 0) {
      setError('Complete the project details and add at least one team member before generating.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const file = validateSelectedFile(selectedFile)
      const created = await apiFetch<SavedProject>(`/api/projects`, {
        method: 'POST',
        body: JSON.stringify({
          name: project.name,
          description: project.description,
          project_type: project.project_type,
          start_date: project.start_date,
          deadline: project.deadline || null,
          priority: project.priority,
          complexity: project.complexity,
          working_days: project.working_days,
          hours_per_day: project.hours_per_day,
          holidays: project.holidays,
          buffer_percent: project.buffer_percent,
          member_ids: members.map((member) => member.id),
        }),
      })
      await uploadDocument(created.id, file)
      const generated = await apiFetch<any>(`/api/projects/${created.id}/generate-plan`, { method: 'POST' })
      setPlan(generated)
      await refreshPortfolio(created.id)
      resetCreatePlanForm()
      setStatus(`Project plan generated for ${created.name} with ${generated.summary.task_count} tasks.`)
      navigate('/generated-plan')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Plan generation failed'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const adjustTaskStatus = async (taskId: string, nextStatus: string) => {
    try {
      await apiFetch<Task>(`/api/tasks/${taskId}`, { method: 'PATCH', body: JSON.stringify({ status: nextStatus }) })
      if (plan?.project_id) await refreshPortfolio(plan.project_id)
    } catch (taskError) {
      setError(taskError instanceof Error ? taskError.message : 'The task status could not be saved.')
    }
  }

  const adjustTaskAssignment = async (taskId: string, memberId: string) => {
    try {
      await apiFetch<Task>(`/api/tasks/${taskId}`, {
        method: 'PATCH',
        body: JSON.stringify({ assignee_id: memberId || null }),
      })
      if (plan?.project_id) await refreshPortfolio(plan.project_id)
    } catch (assignmentError) {
      setError(assignmentError instanceof Error ? assignmentError.message : 'The task assignment could not be saved.')
    }
  }

  const deleteProject = async (projectId: number) => {
    if (!window.confirm('Permanently delete this project and its saved tasks? This cannot be undone.')) return
    if (pendingProjectActionId === projectId) return
    setPendingProjectActionId(projectId)
    setError('')
    try {
      await apiFetch<void>(`/api/projects/${projectId}`, { method: 'DELETE' })
      if (plan?.project_id === projectId) setPlan(null)
      await refreshPortfolio()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'The project could not be deleted.')
    } finally {
      setPendingProjectActionId(null)
    }
  }

  const archivePlan = async () => {
    if (!plan || pendingProjectActionId === plan.project_id || plan.archived) return
    setPendingProjectActionId(plan.project_id)
    try {
      await apiFetch<SavedProject>(`/api/projects/${plan.project_id}/archive`, { method: 'POST' })
      setPlan(null)
      await refreshPortfolio()
      setStatus('Project archived')
    } catch (archiveError) {
      setError(archiveError instanceof Error ? archiveError.message : 'The project could not be archived.')
    } finally {
      setPendingProjectActionId(null)
    }
  }

  const restoreProject = async (projectId: number) => {
    if (pendingProjectActionId === projectId) return
    setPendingProjectActionId(projectId)
    setError('')
    try {
      await apiFetch<SavedProject>(`/api/projects/${projectId}/restore`, { method: 'POST' })
      await refreshPortfolio(projectId)
      setStatus('Project restored')
      navigate('/generated-plan')
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : 'The project could not be restored.')
    } finally {
      setPendingProjectActionId(null)
    }
  }

  const renderNav = (expanded: boolean) => (
    <nav className="mt-6 space-y-2">
      {navItems.map(({ label, to, icon: Icon }) => (
        <NavLink
          key={label}
          to={to}
          onClick={() => {
            if (to === '/create-plan') resetCreatePlanForm()
            if (window.innerWidth < 768) setSidebarOpen(false)
          }}
          className={({ isActive }) => `flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium transition ${isActive ? 'bg-[#EAF2EC] text-[#0B2B20]' : 'text-white/80 hover:bg-white/5 hover:text-white'} ${expanded ? '' : 'justify-center'}`}
          title={label}
        >
          <Icon size={18} />
          {expanded ? <span>{label}</span> : null}
        </NavLink>
      ))}
    </nav>
  )

  return (
    <div className="app-shell min-h-screen w-full bg-[#F7F9F7] text-[#18251D]">
      <div className="min-h-screen w-full">
        <aside className={`fixed inset-y-0 left-0 z-40 flex flex-col overflow-y-auto bg-[#0B2B20] px-3 py-5 text-white transition-all duration-200 ${sidebarOpen ? 'w-64' : 'w-16 md:w-20'}`}>
          <div className={`flex items-center gap-2 ${sidebarOpen ? 'justify-between' : 'justify-center'}`}>
            {sidebarOpen ? (
              <div className="flex min-w-0 items-center gap-3">
                <div className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#EAF2EC] text-[#123D2B]">
                  <Rocket size={18} />
                </div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#CFE4D7]">GenPlan</div>
              </div>
            ) : null}
            <button
              type="button"
              aria-label={sidebarOpen ? 'Collapse menu' : 'Expand menu'}
              aria-expanded={sidebarOpen}
              onClick={() => setSidebarOpen((value) => !value)}
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-white hover:bg-white/10"
            >
              <Menu size={18} />
            </button>
          </div>
          {renderNav(sidebarOpen)}

        </aside>

        {sidebarOpen ? <div className="fixed inset-0 z-30 bg-[#0B2B20]/40 md:hidden" onClick={() => setSidebarOpen(false)} /> : null}

        <main className={`min-w-0 pl-16 transition-[padding] duration-200 ${sidebarOpen ? 'md:pl-64' : 'md:pl-20'}`}>
          <div className="mx-auto w-full max-w-7xl px-4 py-6 md:px-6 lg:px-8">
            <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-sm">
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-[#EAF2EC] text-[#123D2B]"><Rocket size={14} /></span>
                <span className="font-semibold text-[#6B776E]">GenPlan</span>
                <span className="text-[#A9B8AE]">/</span>
                <span className="truncate font-semibold text-[#18251D]">{pageTitle}</span>
              </nav>
              <div className="flex items-center gap-3">
                <div className="rounded-full border border-[#DCE5DE] bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-[#245C43]">{status}</div>
                {!isHomePage ? (
                  <button type="button" onClick={handleHeaderAction} disabled={loading} className="inline-flex items-center justify-center rounded-xl bg-[#123D2B] px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#0B2B20] disabled:opacity-60">
                    <span className="inline-flex items-center gap-2">
                      {isCreatePage ? <Wrench size={16} /> : <FilePlus2 size={16} />}
                      {isCreatePage ? (loading ? 'Generating...' : 'Generate Plan') : 'Create Plan'}
                    </span>
                  </button>
                ) : null}
              </div>
            </header>

            {error ? <div role="alert" className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}

            <Routes>
              <Route path="/" element={
                <HomeDashboard
                  dashboard={dashboard}
                  loading={portfolioLoading}
                  todayLabel={todayLabel}
                  members={members}
                  onOpenProject={(projectId) => void openProject(projectId)}
                  onCreatePlan={() => { resetCreatePlanForm(); navigate('/create-plan') }}
                />
              } />

              <Route path="/create-plan" element={
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#245C43]">Create Plan</p>
                      <h2 className="text-2xl font-bold text-[#18251D]">Create Plan</h2>
                    </div>
                  </div>

                  <section className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
                    <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
                      <div className="min-w-0 space-y-5">
                        <div className="grid gap-4 md:grid-cols-2">
                          <label className="block text-sm font-medium text-[#18251D]">Project Name<input value={project.name} onChange={(e) => handleProjectField('name', e.target.value)} className={inputClassName} /></label>
                          <label className="block text-sm font-medium text-[#18251D]">Project Type<select value={project.project_type} onChange={(e) => handleProjectField('project_type', e.target.value)} className={selectClassName}>{projectTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select></label>
                          <label className="block text-sm font-medium text-[#18251D] md:col-span-2">Project Description<textarea value={project.description} onChange={(e) => handleProjectField('description', e.target.value)} className={`${inputClassName} min-h-[110px]`} /></label>
                          <label className="block text-sm font-medium text-[#18251D]">Start Date<input type="date" value={project.start_date} onChange={(e) => handleProjectField('start_date', e.target.value)} className={inputClassName} /></label>
                          <label className="block text-sm font-medium text-[#18251D]">Target Completion Date<input type="date" value={project.deadline} onChange={(e) => handleProjectField('deadline', e.target.value)} className={inputClassName} /></label>
                          <label className="block text-sm font-medium text-[#18251D]">Working Hours Per Day<input type="number" value={project.hours_per_day} onChange={(e) => handleProjectField('hours_per_day', Number(e.target.value))} className={inputClassName} /></label>
                          <div className="md:col-span-2">
                            <div className="mb-2 block text-sm font-medium text-[#18251D]">Working Days</div>
                            <div className="flex flex-wrap gap-2">
                              {workingDaysOptions.map((day) => {
                                const selected = project.working_days.includes(day)
                                return (
                                  <button
                                    key={day}
                                    type="button"
                                    onClick={() => toggleWorkingDay(day)}
                                    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${selected ? 'border-[#123D2B] bg-[#123D2B] text-white' : 'border-[#DCE5DE] bg-white text-[#18251D] hover:border-[#123D2B]/40'}`}
                                  >
                                    {day}
                                  </button>
                                )
                              })}
                            </div>
                            <div className="mt-2 text-xs text-[#6B776E]">Selected: {project.working_days.length ? project.working_days.join(', ') : 'None'}</div>
                          </div>
                        </div>
                      </div>

                      <div className="min-w-0 space-y-4 rounded-2xl border border-[#DCE5DE] bg-[#F7F9F7] p-4">
                        <div className="flex items-center gap-2 text-lg font-semibold text-[#18251D]"><FileText size={18} className="text-[#123D2B]" /> Upload User Story Document</div>
                        <div className="rounded-xl border-2 border-dashed border-[#DCE5DE] bg-white p-4">
                          <label className="inline-flex cursor-pointer items-center justify-center rounded-xl bg-[#123D2B] px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-[#0B2B20]">
                            <span>Choose File</span>
                            <input ref={fileInputRef} type="file" accept=".pdf,.docx,.txt,.md,.markdown" onChange={(event) => void handleDocumentSelection(event.target.files?.[0] ?? null)} className="hidden" />
                          </label>
                          {selectedFile ? (
                            <div className="mt-3 flex items-center justify-between gap-3 text-sm text-[#18251D]">
                              <span className="truncate">{selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)</span>
                              <button type="button" onClick={() => { if (fileInputRef.current) fileInputRef.current.value = ''; void handleDocumentSelection(null) }} className="shrink-0 text-xs font-semibold text-[#245C43]">Clear file</button>
                            </div>
                          ) : <div className="mt-3 text-sm text-[#6B776E]">No file selected.</div>}
                        </div>
                        <div className="rounded-xl border border-[#DCE5DE] bg-white p-3 text-sm text-[#6B776E]">
                          {documentLoading ? <div role="status">Processing document…</div> : previewStories.length ? (
                            <>
                              {previewStories.slice(0, 3).map((story) => <div key={story.id} className="mb-2 last:mb-0"><div className="font-medium text-[#18251D]">{story.title}</div><div className="mt-1">{story.description}</div></div>)}
                              {previewText ? <details className="mt-3 border-t border-[#DCE5DE] pt-2"><summary className="cursor-pointer font-medium text-[#245C43]">Extracted document text</summary><p className="mt-2 whitespace-pre-wrap text-xs">{previewText}</p></details> : null}
                            </>
                          ) : 'No story document processed yet.'}
                        </div>
                      </div>
                    </div>

                    <div className="mt-6 flex justify-end">
                      <button onClick={generatePlan} className="inline-flex items-center justify-center rounded-xl bg-[#123D2B] px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[#0B2B20]">
                        <span className="inline-flex items-center gap-2"><Wrench size={16} /> {loading ? 'Generating...' : 'Generate Plan'}</span>
                      </button>
                    </div>
                  </section>
                </div>
              } />

              <Route path="/team-info" element={
                <div className="space-y-6">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#245C43]">Manage team</p>
                      <h2 className="text-2xl font-bold text-[#18251D]">Team Info</h2>
                    </div>
                    <button onClick={openAddMemberForm} className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-[#123D2B] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#0B2B20]">
                      <Plus size={16} /> Add Member
                    </button>
                  </div>

                  <TeamWorkloadChart refreshKey={`${members.map((member) => `${member.id}:${member.hours_per_day}`).join('|')}#${savedProjects.map((item) => `${item.id}:${item.status}:${item.archived}`).join('|')}#${planSignature(plan)}`} />

                  <EstimateCoachCard refreshKey={planSignature(plan)} />

                  <section className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
                    <div className="mb-4 flex items-center gap-2 rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] px-3 py-2">
                      <Search size={16} className="text-[#6B776E]" />
                      <input value={teamSearch} onChange={(e) => setTeamSearch(e.target.value)} placeholder="Search members" className="w-full border-0 bg-transparent text-sm text-[#18251D] placeholder:text-[#6B776E] focus:outline-none" />
                    </div>

                    <div className="space-y-3">
                      {filteredMembers.length ? filteredMembers.map((member) => (
                        <div 
                          key={member.id} 
                          onClick={() => setSelectedMember(member)}
                          className="cursor-pointer rounded-xl border border-[#DCE5DE] p-3 transition hover:border-[#245C43] hover:bg-[#F7F9F7]"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 font-semibold text-[#18251D]">{member.name}{member.is_lead ? <span className="inline-flex items-center gap-1 rounded-full bg-[#123D2B] px-2 py-0.5 text-[10px] font-semibold text-white"><Crown size={10} /> Team Lead</span> : null}</div>
                              <div className="text-xs uppercase tracking-wide text-[#245C43]">{member.role}{member.additional_role ? ` · ${member.additional_role}` : ''}</div>
                            </div>
                            <div className="flex shrink-0 flex-wrap items-center justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                              <button onClick={() => setAllocationsMember(member)} className="inline-flex items-center gap-1 rounded-lg bg-[#123D2B] px-2 py-1.5 text-xs font-medium text-white hover:bg-[#0B2B20]"><FolderKanban size={12} /> Allocations</button>
                              <button onClick={() => openEditMemberForm(member)} className="inline-flex items-center gap-1 rounded-lg border border-[#DCE5DE] bg-white px-2 py-1.5 text-xs font-medium text-[#18251D]"><Pencil size={12} /> Edit</button>
                              <button onClick={() => removeMember(member.id)} className="inline-flex items-center gap-1 rounded-lg border border-[#DCE5DE] bg-white px-2 py-1.5 text-xs font-medium text-red-600"><X size={12} /> Delete</button>
                            </div>
                          </div>
                          <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-[#6B776E] sm:grid-cols-2">
                            <div><span className="font-medium text-[#18251D]">Experience:</span> {member.experience} yrs</div>
                            <div><span className="font-medium text-[#18251D]">Hours:</span> {member.hours_per_day}/day</div>
                          </div>
                          <div className="mt-3 text-xs text-[#6B776E]"><span className="font-medium text-[#18251D]">Skills:</span> {member.skills.join(', ') || 'None'}</div>
                        </div>
                      )) : <div className="rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] p-4 text-sm text-[#6B776E]">No team members found.</div>}
                    </div>
                  </section>
                </div>
              } />

              <Route path="/generated-plan" element={
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#245C43]">Project tracking</p>
                      <h2 className="text-2xl font-bold text-[#18251D]">Generated Plan</h2>
                    </div>
                    <div className="inline-flex items-center gap-3 rounded-xl border border-[#DCE5DE] bg-white px-4 py-2 shadow-sm">
                      <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-[#EAF2EC] text-[#123D2B]"><Rocket size={16} /></span>
                      <div>
                        <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#6B776E]">Active Projects</div>
                        <div className="text-xl font-bold leading-none text-[#0B2B20]" aria-label="Active projects count">{portfolioLoading ? '…' : dashboard?.metrics.active_projects ?? 0}</div>
                      </div>
                    </div>
                  </div>

                  <section className="min-w-0 rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
                    {savedProjects.some((item) => item.has_plan && !item.archived) ? (
                      <div className="mb-5 border-b border-[#DCE5DE] pb-4">
                        <div className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#245C43]">Active Generated Plans</div>
                        <div className="flex flex-wrap gap-2">
                          {savedProjects.filter((item) => item.has_plan && !item.archived).map((item) => (
                            <button key={item.id} onClick={() => void openProject(item.id)} aria-current={plan?.project_id === item.id ? 'page' : undefined} className={`rounded-lg border px-3 py-2 text-sm ${plan?.project_id === item.id ? 'border-[#123D2B] bg-[#EAF2EC] font-semibold text-[#123D2B]' : 'border-[#DCE5DE] bg-white text-[#18251D]'}`}>
                              {item.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {plan ? (
                      <div className="space-y-5">
                        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                          <div className="min-w-0">
                            <div className="text-2xl font-bold text-[#18251D]">{plan.name || project.name}</div>
                            <div className="text-sm text-[#6B776E]">{plan.project_type || project.project_type} · {plan.start_date || project.start_date} to {plan.deadline || project.deadline}</div>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {!plan.archived && missingMembers.length ? (
                              <button type="button" disabled={assigningMembers} onClick={() => void assignNewMembers()} title={`Not on this project yet: ${missingMembers.map((member) => member.name).join(', ')}`} className="inline-flex items-center gap-1.5 rounded-xl border border-[#245C43] bg-[#EAF2EC] px-3 py-2 text-sm font-semibold text-[#123D2B] hover:bg-[#DCEBE1] disabled:opacity-50">
                                <Users size={14} /> {assigningMembers ? 'Assigning…' : `Assign new members (${missingMembers.length})`}
                              </button>
                            ) : null}
                            {!plan.archived ? (
                              <button type="button" onClick={() => setReplanOpen(true)} className="inline-flex items-center gap-1.5 rounded-xl border border-[#DCE5DE] bg-white px-3 py-2 text-sm font-medium text-[#18251D] hover:border-[#245C43]">
                                <RefreshCw size={14} /> Re-plan from today
                                {lateTaskCount ? <span className="rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-bold leading-none text-white">{lateTaskCount} late</span> : null}
                              </button>
                            ) : null}
                            <button type="button" onClick={() => setReportOpen(true)} className="inline-flex items-center gap-1.5 rounded-xl border border-[#DCE5DE] bg-white px-3 py-2 text-sm font-medium text-[#18251D] hover:border-[#245C43]">
                              <ClipboardList size={14} /> Weekly report
                            </button>
                            {!plan.archived ? (
                              <button type="button" disabled={regenerating} onClick={() => void regeneratePlan()} className="rounded-xl border border-[#DCE5DE] bg-white px-3 py-2 text-sm font-medium text-[#18251D] disabled:opacity-50">{regenerating ? 'Regenerating…' : 'Regenerate Plan'}</button>
                            ) : null}
                            {plan.archived ? (
                              <button disabled={pendingProjectActionId === plan.project_id} onClick={() => void restoreProject(plan.project_id)} className="rounded-xl bg-[#123D2B] px-3 py-2 text-sm font-medium text-white disabled:opacity-50">{pendingProjectActionId === plan.project_id ? 'Restoring…' : 'Restore Plan'}</button>
                            ) : (
                              <button disabled={pendingProjectActionId === plan.project_id} onClick={() => void archivePlan()} className="rounded-xl bg-[#123D2B] px-3 py-2 text-sm font-medium text-white disabled:opacity-50">{pendingProjectActionId === plan.project_id ? 'Archiving…' : 'Archive Plan'}</button>
                            )}
                          </div>
                        </div>

                        <ForecastCard projectId={plan.project_id} refreshKey={planSignature(plan)} onRequestReplan={() => setReplanOpen(true)} />

                        <GeneratedPlanView
                          key={plan.project_id}
                          plan={plan}
                          members={planMembers}
                          onStatusChange={adjustTaskStatus}
                          onAssign={adjustTaskAssignment}
                          canReassign={!plan.archived}
                        />
                      </div>
                    ) : savedProjects.some((item) => item.has_plan && !item.archived) ? (
                      <div className="space-y-3">
                        <p className="text-sm text-[#6B776E]">Choose a saved project to open its plan.</p>
                        {savedProjects.filter((item) => item.has_plan && !item.archived).map((item) => (
                          <button key={item.id} onClick={() => openProject(item.id)} className="flex w-full items-center justify-between gap-3 rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-3 text-left hover:border-[#245C43]">
                            <span className="font-medium text-[#18251D]">{item.name}</span>
                            <span className="text-sm text-[#6B776E]">{item.archived ? 'Archived' : item.status}</span>
                          </button>
                        ))}
                      </div>
                    ) : <div className="rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] p-6 text-center text-[#6B776E]">No saved plans yet. Use the Create Plan page to generate one.</div>}
                  </section>
                </div>
              } />

              <Route path="/archive" element={
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#245C43]">Saved history</p>
                      <h2 className="text-2xl font-bold text-[#18251D]">Archive</h2>
                    </div>
                  </div>

                  <section className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
                    {portfolioLoading ? <div role="status" className="p-4 text-sm text-[#6B776E]">Loading archived plans…</div> : archivedPlans.length ? archivedPlans.map((item) => (
                      <div key={item.id} className="mb-3 flex flex-col gap-3 rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-3 last:mb-0 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <div className="font-medium text-[#18251D]">{item.name}</div>
                          <div className="text-sm text-[#6B776E]">{item.status} · {item.deadline || 'No deadline'}</div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button onClick={() => void openProject(item.id)} className="rounded-lg border border-[#DCE5DE] bg-white px-3 py-2 text-sm font-medium text-[#18251D]">Open</button>
                          <button disabled={pendingProjectActionId === item.id} onClick={() => void restoreProject(item.id)} className="rounded-lg bg-[#123D2B] px-3 py-2 text-sm font-medium text-white disabled:opacity-50">{pendingProjectActionId === item.id ? 'Restoring…' : 'Restore'}</button>
                          <button disabled={pendingProjectActionId === item.id} onClick={() => void deleteProject(item.id)} className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-600 disabled:opacity-50">Delete</button>
                        </div>
                      </div>
                    )) : <div className="rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] p-6 text-center text-[#6B776E]">No archived plans.</div>}
                  </section>
                </div>
              } />

              <Route path="*" element={<div className="rounded-2xl border border-[#DCE5DE] bg-white p-10 text-center shadow-sm"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#245C43]">404</p><h2 className="mt-2 text-2xl font-bold text-[#18251D]">Page not found</h2><NavLink to="/" className="mt-4 inline-block rounded-xl bg-[#123D2B] px-4 py-2.5 text-sm font-semibold text-white">Back to Home</NavLink></div>} />
            </Routes>

          </div>
        </main>
      </div>

      {/* Team Member Form Modal */}
      {memberFormOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0B2B20]/35 p-4 backdrop-blur-[2px]">
          <div className="w-full max-w-4xl rounded-2xl border border-[#DCE5DE] bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#DCE5DE] px-5 py-4">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#245C43]">Team Member</div>
                <h2 className="text-xl font-bold text-[#18251D]">{editingMemberId ? 'Edit Team Member' : 'Add Team Member'}</h2>
              </div>
              <button onClick={closeMemberForm} className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#DCE5DE] bg-white text-[#18251D] hover:bg-[#F7F9F7]">
                <X size={18} />
              </button>
            </div>

            <div className="max-h-[75vh] overflow-y-auto px-5 py-5">
              <div className="space-y-6">
                <div>
                  <div className="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-[#245C43]">Personal Information</div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <TextInput label="Name" required value={memberFormValues.name} onChange={(event) => setMemberFormValues((current) => ({ ...current, name: event.target.value }))} error={memberFormErrors.name} />
                    <TextInput label="Email Address (optional)" type="email" value={memberFormValues.email} onChange={(event) => setMemberFormValues((current) => ({ ...current, email: event.target.value }))} error={memberFormErrors.email} />
                    <SelectField label="Role" required value={memberFormValues.role} onChange={(event) => setMemberFormValues((current) => ({ ...current, role: event.target.value }))} error={memberFormErrors.role}>
                      {roleOptions.map((role) => <option key={role} value={role}>{role}</option>)}
                    </SelectField>
                    <SelectField label="Additional Role (optional)" value={memberFormValues.additional_role} onChange={(event) => setMemberFormValues((current) => ({ ...current, additional_role: event.target.value }))}>
                      <option value="">None</option>
                      {roleOptions.filter((role) => role !== memberFormValues.role).map((role) => <option key={role} value={role}>{role}</option>)}
                    </SelectField>
                    <p className="text-xs text-[#6B776E] md:col-span-2">Choosing <span className="font-semibold text-[#18251D]">Team Lead</span> as the role or the additional role lets this person reassign and edit tasks.</p>
                  </div>
                </div>

                <div>
                  <div className="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-[#245C43]">Experience and Skills</div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <TextInput label="Years of Experience" required type="number" min="0" value={memberFormValues.experience} onChange={(event) => setMemberFormValues((current) => ({ ...current, experience: event.target.value }))} error={memberFormErrors.experience} />
                    <SelectField label="Skill Proficiency" value={memberFormValues.skill_proficiency} onChange={(event) => setMemberFormValues((current) => ({ ...current, skill_proficiency: event.target.value }))} error={memberFormErrors.skill_proficiency}>
                      <option value="Beginner">Beginner</option>
                      <option value="Intermediate">Intermediate</option>
                      <option value="Advanced">Advanced</option>
                      <option value="Expert">Expert</option>
                    </SelectField>
                    <div className="md:col-span-2"><TextInput label="Skills (comma separated)" required value={memberFormValues.primary_skills} onChange={(event) => setMemberFormValues((current) => ({ ...current, primary_skills: event.target.value }))} error={memberFormErrors.primary_skills} /></div>
                  </div>
                </div>

                <div>
                  <div className="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-[#245C43]">Work Schedule</div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <TextInput label="Working Hours Per Day" required type="number" min="1" max="24" value={memberFormValues.hours_per_day} onChange={(event) => setMemberFormValues((current) => ({ ...current, hours_per_day: event.target.value }))} error={memberFormErrors.hours_per_day} />
                    <fieldset className="space-y-2">
                      <legend className="text-sm font-semibold text-[#18251D]">Working Days</legend>
                      <div className="flex flex-wrap gap-3">
                        {workingDaysOptions.map((day) => (
                          <label key={day} className="inline-flex items-center gap-2 text-sm text-[#18251D]">
                            <input
                              type="checkbox"
                              checked={memberFormValues.working_days.split(',').map((item) => item.trim()).includes(day)}
                              onChange={(event) => setMemberFormValues((current) => {
                                const selected = current.working_days.split(',').map((item) => item.trim()).filter(Boolean)
                                const nextDays = event.target.checked ? [...selected, day] : selected.filter((item) => item !== day)
                                return { ...current, working_days: workingDaysOptions.filter((item) => nextDays.includes(item)).join(', ') }
                              })}
                              className="accent-[#123D2B]"
                            />
                            {day}
                          </label>
                        ))}
                      </div>
                    </fieldset>
                    <div className="md:col-span-2"><TextInput label="Leave Dates" value={memberFormValues.leave_dates} onChange={(event) => setMemberFormValues((current) => ({ ...current, leave_dates: event.target.value }))} /></div>
                  </div>
                </div>

              </div>

              {memberFeedback ? <div className="mt-5 rounded-xl border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">{memberFeedback}</div> : null}

              <div className="mt-6 flex flex-col-reverse gap-3 border-t border-[#DCE5DE] pt-4 sm:flex-row sm:justify-end">
                <button type="button" onClick={closeMemberForm} className="rounded-xl border border-[#DCE5DE] bg-white px-4 py-2.5 text-sm font-medium text-[#18251D]">Cancel</button>
                <button type="button" onClick={saveMember} className="rounded-xl bg-[#123D2B] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#0B2B20]">Save Member</button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {/* Team Member Details Modal */}
      {selectedMember ? (
        <ModalShell
          title={selectedMember.name}
          subtitle={`${selectedMember.role} · ${selectedMember.experience} yrs exp`}
          onClose={() => setSelectedMember(null)}
        >
          <div className="space-y-6">
            <div>
              <h4 className="mb-2 text-sm font-semibold text-[#18251D]">Project Allocations</h4>
              <button
                type="button"
                onClick={() => { const member = selectedMember; setSelectedMember(null); setAllocationsMember(member) }}
                className="inline-flex items-center gap-2 rounded-xl bg-[#123D2B] px-4 py-2 text-sm font-semibold text-white hover:bg-[#0B2B20]"
              >
                <FolderKanban size={14} /> View projects and hours
              </button>
            </div>

            <div>
              <h4 className="mb-2 text-sm font-semibold text-[#18251D]">Availability</h4>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <Fact label="Hours / Day" value={`${selectedMember.hours_per_day}h`} />
              </div>
            </div>

            <div>
              <h4 className="mb-2 text-sm font-semibold text-[#18251D]">Skills</h4>
              <div className="flex flex-wrap gap-2">
                {selectedMember.skills.length > 0 ? selectedMember.skills.map(skill => (
                  <span key={skill} className="rounded-full bg-[#EAF2EC] px-2 py-1 text-xs font-medium text-[#123D2B]">{skill}</span>
                )) : <span className="text-sm text-[#6B776E]">No skills listed.</span>}
              </div>
            </div>
          </div>
        </ModalShell>
      ) : null}

      {allocationsMember ? <MemberAllocationsModal member={allocationsMember} onClose={() => setAllocationsMember(null)} /> : null}
      {replanOpen && plan ? <ReplanModal projectId={plan.project_id} onClose={() => setReplanOpen(false)} onApplied={() => refreshPortfolio(plan.project_id)} /> : null}
      {reportOpen && plan ? <WeeklyReportModal projectId={plan.project_id} onClose={() => setReportOpen(false)} /> : null}
    </div>
  )
}

export default App