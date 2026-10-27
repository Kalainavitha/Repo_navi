import { useEffect, useMemo, useRef, useState, type ChangeEvent, type InputHTMLAttributes, type ReactNode } from 'react'
import { BrowserRouter, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, Archive, CheckCircle2, Clock3, FilePlus2, FileText, FolderKanban, House, Menu, Pencil, Plus, Rocket, Search, Users, Wrench, X } from 'lucide-react'
import { apiFetch, previewDocument, uploadDocument } from './lib/api'
import type { DailyWorkload, DashboardData, Member, ProjectFormState, SavedProject, Story, Task } from './types'

const projectTypes = ['Web Application', 'Mobile Application', 'Desktop Application', 'API or Backend System', 'AI/ML Application', 'Data Engineering Platform', 'E-commerce Platform', 'Enterprise Software', 'Cloud Migration', 'DevOps or Infrastructure', 'Cybersecurity Project', 'IoT Application', 'Other']
const roleOptions = ['Project Manager', 'Frontend Developer', 'Backend Developer', 'QA Engineer', 'Product Manager', 'UX Designer', 'DevOps Engineer', 'Data Engineer', 'Security Engineer', 'Business Analyst']
const workingDaysOptions = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const navItems = [
  { label: 'Home', to: '/', icon: House },
  { label: 'Create Plan', to: '/create-plan', icon: FilePlus2 },
  { label: 'Team Info', to: '/team-info', icon: Users },
  { label: 'Generated Plan', to: '/generated-plan', icon: FolderKanban },
  { label: 'Archive', to: '/archive', icon: Archive },
] as const

const inputClassName = 'w-full rounded-xl border border-[#DCE5DE] bg-white px-3 py-2.5 text-sm text-[#18251D] shadow-sm transition focus:border-[#123D2B] focus:outline-none focus:ring-2 focus:ring-[#123D2B]/10'
const selectClassName = `${inputClassName} appearance-none`
const standardTaskCategories = ['UI/Frontend', 'Backend', 'QA/Testing', 'Integration', 'DevOps/Deployment', 'Documentation', 'Planning & Analysis', 'Other']

function taskCategory(task: Task) {
  const category = (task.category || '').trim().toLowerCase()
  return standardTaskCategories.find((value) => value.toLowerCase() === category) ?? 'Other'
}

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
  experience: string
  primary_skills: string
  additional_skills: string
  skill_proficiency: string
  hours_per_day: string
  working_days: string
  availability_start: string
  availability_end: string
  leave_dates: string
  allocation: string
  notes: string
}

const emptyMemberForm: MemberFormValues = {
  name: '',
  email: '',
  role: 'Frontend Developer',
  experience: '3',
  primary_skills: 'react',
  additional_skills: 'typescript, ui',
  skill_proficiency: 'Intermediate',
  hours_per_day: '8',
  working_days: 'Monday, Tuesday, Wednesday, Thursday, Friday',
  availability_start: '',
  availability_end: '',
  leave_dates: '',
  allocation: '80',
  notes: '',
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

function DateField({ label, required, value, onChange, error }: { label: string; required?: boolean; value: string; onChange: (event: ChangeEvent<HTMLInputElement>) => void; error?: string }) {
  return (
    <FormField label={label} required={required} error={error}>
      <input type="date" value={value} onChange={onChange} className={inputClassName} />
    </FormField>
  )
}

function TextAreaField({ label, required, value, onChange, error }: { label: string; required?: boolean; value: string; onChange: (event: ChangeEvent<HTMLTextAreaElement>) => void; error?: string }) {
  return (
    <FormField label={label} required={required} error={error}>
      <textarea value={value} onChange={onChange} className={`${inputClassName} min-h-[110px] resize-y`} />
    </FormField>
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
  const [sidebarOpen, setSidebarOpen] = useState(true)
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
      setExpandedTaskId(null)
      setPlanFilters({ category: 'All Tasks', member: 'All Members', status: 'All Statuses', sort: 'priority' })
      setError('')
      navigate(`/generated-plan?project_id=${projectId}`)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to open the saved project.')
    }
  }

  const [planFilters, setPlanFilters] = useState({ category: 'All Tasks', member: 'All Members', status: 'All Statuses', sort: 'priority' })
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null)

  const taskChartData = useMemo(() => {
    return dashboard?.task_progress ?? []
  }, [dashboard])

  const filteredPlanTasks = useMemo(() => {
    const tasks = plan?.tasks ?? []

    return [...tasks]
      .filter((task: Task) => {
        const matchesCategory = planFilters.category === 'All Tasks' || taskCategory(task) === planFilters.category
        const matchesMember = planFilters.member === 'All Members' || task.assignee_name === planFilters.member
        const matchesStatus = planFilters.status === 'All Statuses' || task.status === planFilters.status
        return matchesCategory && matchesMember && matchesStatus
      })
      .sort((a, b) => {
        const direction = planFilters.sort === 'priority' ? 1 : -1
        if (planFilters.sort === 'priority') {
          const priorityWeight = { 'Critical': 4, 'High': 3, 'Medium': 2, 'Low': 1 }
          return (priorityWeight[b.priority as keyof typeof priorityWeight] ?? 0) - (priorityWeight[a.priority as keyof typeof priorityWeight] ?? 0)
        }
        if (planFilters.sort === 'effort') return direction * (b.effort_hours - a.effort_hours)
        if (planFilters.sort === 'schedule') return (new Date(a.start_date ?? '2099-01-01').getTime() - new Date(b.start_date ?? '2099-01-01').getTime())
        return 0
      })
  }, [plan, planFilters])

  const dailyWorkflow: DailyWorkload[] = plan?.daily_workload ?? []

  const categoryBreakdown = useMemo(() => {
    const tasks: Task[] = plan?.tasks ?? []
    const categories = [...new Set([...standardTaskCategories, ...tasks.map(taskCategory)])]
    return categories.map((category) => ({
        category,
        count: tasks.filter((task: Task) => taskCategory(task) === category).length,
      }))
  }, [plan])
  const taskCategories = ['All Tasks', ...categoryBreakdown.map((group) => group.category)]

  const filteredMembers = useMemo(() => {
    const query = teamSearch.trim().toLowerCase()
    if (!query) return members
    return members.filter((member) => `${member.name} ${member.role} ${member.skills.join(' ')}`.toLowerCase().includes(query))
  }, [members, teamSearch])

  const stats = useMemo(() => {
    const metrics = dashboard?.metrics
    return {
      totalProjects: metrics?.total_projects ?? 0,
      activeProjects: metrics?.active_projects ?? 0,
      completedProjects: metrics?.completed_projects ?? 0,
      teamMembers: metrics?.team_members ?? 0,
      tasksInProgress: metrics?.tasks_in_progress ?? 0,
      overdueTasks: metrics?.overdue_tasks ?? 0,
    }
  }, [dashboard])

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
      primary_skills: member.skills[0] ?? '',
      additional_skills: member.skills.slice(1).join(', '),
      skill_proficiency: 'Intermediate',
      hours_per_day: String(member.hours_per_day ?? 8),
      working_days: (member.working_days ?? workingDaysOptions.slice(0, 5)).join(', '),
      availability_start: member.available_from ?? '',
      availability_end: member.available_until ?? '',
      leave_dates: member.leave_dates.join(', '),
      allocation: String(member.allocation ?? 100),
      notes: member.notes ?? '',
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
    if (!memberFormValues.email.trim()) errors.email = 'Email address is required.'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(memberFormValues.email)) errors.email = 'Enter a valid email address.'
    if (!memberFormValues.role.trim()) errors.role = 'Role is required.'
    if (!memberFormValues.experience || Number(memberFormValues.experience) < 0) errors.experience = 'Years of experience is required.'
    if (!memberFormValues.primary_skills.trim()) errors.primary_skills = 'Primary skills are required.'
    if (!memberFormValues.hours_per_day || Number(memberFormValues.hours_per_day) <= 0 || Number(memberFormValues.hours_per_day) > 24) errors.hours_per_day = 'Working hours must be between 1 and 24.'
    if (!memberFormValues.allocation || Number(memberFormValues.allocation) <= 0 || Number(memberFormValues.allocation) > 100) errors.allocation = 'Allocation percentage must be greater than 0 and at most 100.'
    if (memberFormValues.availability_start && memberFormValues.availability_end && new Date(memberFormValues.availability_end) < new Date(memberFormValues.availability_start)) errors.availability_end = 'Availability end date must be after the start date.'
    setMemberFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const saveMember = async () => {
    if (!validateMemberForm()) {
      setMemberFeedback('Please correct the highlighted team member fields.')
      return
    }

    const nextSkills = parseSkills(memberFormValues.primary_skills, memberFormValues.additional_skills)
    const newMember = {
      name: memberFormValues.name.trim(),
      role: memberFormValues.role,
      skills: nextSkills,
      experience: Number(memberFormValues.experience),
      hours_per_day: Number(memberFormValues.hours_per_day),
      working_days: memberFormValues.working_days.split(',').map((item) => item.trim()).filter(Boolean),
      allocation: Number(memberFormValues.allocation),
      available_from: memberFormValues.availability_start || null,
      available_until: memberFormValues.availability_end || null,
      leave_dates: memberFormValues.leave_dates.split(',').map((item) => item.trim()).filter(Boolean),
      email: memberFormValues.email,
      notes: memberFormValues.notes,
    }

    try {
      if (editingMemberId) {
        await apiFetch<Member>(`/api/team-members/${editingMemberId}`, { method: 'PATCH', body: JSON.stringify(newMember) })
      } else {
        await apiFetch<Member>('/api/team-members', { method: 'POST', body: JSON.stringify(newMember) })
      }
      await refreshPortfolio()
      setMemberFeedback(editingMemberId ? 'Member updated successfully.' : 'Member added successfully.')
      setTimeout(() => closeMemberForm(), 250)
    } catch (saveError) {
      setMemberFeedback(saveError instanceof Error ? saveError.message : 'The team member could not be saved.')
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

  const projectStatusData = dashboard?.project_status ?? []

  const workloadData = dashboard?.team_workload.map((member) => ({ ...member, name: member.name.split(' ')[0] })) ?? []

  const overviewMetrics = [
    { label: 'Total Projects', value: String(stats.totalProjects), note: 'All plans', link: '/generated-plan', icon: FolderKanban },
    { label: 'Active Projects', value: String(stats.activeProjects), note: 'In motion', link: '/generated-plan', icon: Rocket },
    { label: 'Completed Projects', value: String(stats.completedProjects), note: 'Closed', link: '/generated-plan', icon: CheckCircle2 },
    { label: 'Team Members', value: String(stats.teamMembers), note: 'Available', link: '/team-info', icon: Users },
    { label: 'Tasks in Progress', value: String(stats.tasksInProgress), note: 'Live workload', link: '/generated-plan', icon: Clock3 },
    { label: 'Overdue Tasks', value: String(stats.overdueTasks), note: 'Needs attention', link: '/generated-plan', icon: AlertTriangle },
  ]

  const timelineData = dashboard?.project_timeline ?? []

  return (
    <div className="min-h-screen bg-[#F7F9F7] text-[#18251D]">
      <div className="flex min-h-screen">
        <aside className={`${sidebarOpen ? 'w-72' : 'w-24'} hidden border-r border-[#DCE5DE] bg-[#0B2B20] px-3 py-5 text-white transition-all duration-200 md:block`}>
          <div className={`flex items-center ${sidebarOpen ? 'justify-between' : 'justify-center'} gap-2`}>
            <div className={`flex items-center gap-3 ${sidebarOpen ? 'block' : 'hidden'}`}>
              <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[#EAF2EC] text-[#123D2B]">
                <Rocket size={18} />
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#CFE4D7]">GenPlan</div>
              </div>
            </div>
            <button onClick={() => setSidebarOpen((value) => !value)} className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-white hover:bg-white/10">
              {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
            </button>
          </div>

          <nav className="mt-6 space-y-2">
            {navItems.map(({ label, to, icon: Icon }) => (
              <NavLink
                key={label}
                to={to}
                onClick={() => { if (to === '/create-plan') resetCreatePlanForm() }}
                className={({ isActive }) => `flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium transition ${isActive ? 'bg-[#EAF2EC] text-[#0B2B20]' : 'text-white/80 hover:bg-white/5 hover:text-white'} ${sidebarOpen ? '' : 'justify-center'}`}
                title={label}
              >
                <Icon size={18} />
                {sidebarOpen ? <span>{label}</span> : null}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="flex-1">
          <div className="mx-auto max-w-7xl px-4 py-6 md:px-6 lg:px-8">
            <header className="mb-6 rounded-2xl border border-[#DCE5DE] bg-white p-4 shadow-sm md:p-5">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="flex items-center gap-3">
                  <button onClick={() => setSidebarOpen((value) => !value)} className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] text-[#123D2B] md:hidden">
                    <Menu size={18} />
                  </button>
                  <div className="flex items-center gap-3">
                    <div className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-[#EAF2EC] text-[#123D2B]">
                      <Rocket size={20} />
                    </div>
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#245C43]">GenPlan</div>
                      <h1 className="text-2xl font-bold text-[#18251D] md:text-3xl">Plan smarter. Deliver better.</h1>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="rounded-full border border-[#DCE5DE] bg-[#F7F9F7] px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-[#245C43]">{status}</div>
                  <button onClick={generatePlan} className="inline-flex items-center justify-center rounded-xl bg-[#123D2B] px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[#0B2B20]">
                    <span className="inline-flex items-center gap-2"><Wrench size={16} /> {loading ? 'Generating...' : 'Generate Plan'}</span>
                  </button>
                </div>
              </div>
            </header>

            <Routes>
              <Route path="/" element={
                <>
                  <div className="mb-6 rounded-2xl border border-[#DCE5DE] bg-[#F7F9F7] p-4 shadow-sm">
                    <div className="rounded-2xl border border-[#DCE5DE] bg-[#EAF2EC] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#245C43]">Overview</p>
                          <h2 className="mt-1 text-xl font-bold text-[#18251D]">Portfolio snapshot</h2>
                        </div>
                        <div className="rounded-full border border-[#CFE4D7] bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#123D2B]">
                          {todayLabel}
                        </div>
                      </div>

                      <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                        {overviewMetrics.map(({ label, value, note, link, icon: Icon }) => (
                          <NavLink
                            key={label}
                            to={link}
                            className="group flex items-center gap-3 rounded-xl border border-[#DCE5DE] bg-white px-3 py-3 text-left transition hover:border-[#245C43] hover:bg-[#F1F8F3]"
                          >
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#EAF2EC] text-[#123D2B]">
                              <Icon size={18} />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#6B776E]">{label}</div>
                              <div className="mt-1 text-2xl font-bold text-[#0B2B20]">{portfolioLoading ? '…' : value}</div>
                            </div>
                            <div className="text-right text-[10px] font-medium text-[#245C43]">{note}</div>
                          </NavLink>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="mt-6 grid gap-6 xl:grid-cols-2">
                    <section className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-[#18251D]">Project Status</h3>
                        <span className="text-xs uppercase tracking-[0.12em] text-[#245C43]">Overview</span>
                      </div>
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Tooltip />
                            <Pie data={projectStatusData} dataKey="value" nameKey="name" innerRadius={62} outerRadius={92} paddingAngle={3}>
                              {projectStatusData.map((item, index) => <Cell key={item.name} fill={['#123D2B', '#367653', '#A9C6B3', '#C7D1CA'][index % 4]} />)}
                            </Pie>
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                      {!portfolioLoading && !projectStatusData.some((item) => item.value > 0) ? <p className="-mt-8 text-center text-sm text-[#6B776E]">No saved projects yet.</p> : null}
                    </section>

                    <section className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-[#18251D]">Task Progress</h3>
                        <span className="text-xs uppercase tracking-[0.12em] text-[#245C43]">Status</span>
                      </div>
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={taskChartData}>
                            <CartesianGrid strokeDasharray="4 4" stroke="#DCE5DE" vertical={false} />
                            <XAxis dataKey="name" />
                            <YAxis allowDecimals={false} />
                            <Tooltip />
                            <Bar dataKey="value" fill="#367653" radius={[8,8,0,0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                      {!portfolioLoading && !taskChartData.some((item) => item.value > 0) ? <p className="-mt-8 text-center text-sm text-[#6B776E]">No saved task data yet.</p> : null}
                    </section>

                    <section className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-[#18251D]">Team Workload</h3>
                        <span className="text-xs uppercase tracking-[0.12em] text-[#245C43]">Allocation</span>
                      </div>
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={workloadData} layout="vertical" margin={{ left: 12, right: 12 }}>
                            <CartesianGrid strokeDasharray="4 4" stroke="#DCE5DE" horizontal={false} />
                            <XAxis type="number" />
                            <YAxis type="category" dataKey="name" width={50} />
                            <Tooltip />
                            <Bar dataKey="hours" fill="#245C43" radius={[0,8,8,0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                      {!portfolioLoading && !workloadData.length ? <p className="-mt-8 text-center text-sm text-[#6B776E]">No team members yet.</p> : null}
                    </section>

                    <section className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-[#18251D]">Project Timeline</h3>
                        <span className="text-xs uppercase tracking-[0.12em] text-[#245C43]">Schedule</span>
                      </div>
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={timelineData}>
                            <CartesianGrid strokeDasharray="4 4" stroke="#DCE5DE" vertical={false} />
                            <XAxis dataKey="week" />
                            <YAxis allowDecimals={false} />
                            <Tooltip />
                            <Bar dataKey="planned" fill="#DCE5DE" radius={[8,8,0,0]} />
                            <Bar dataKey="completed" fill="#123D2B" radius={[8,8,0,0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                      {!portfolioLoading && !timelineData.length ? <p className="-mt-8 text-center text-sm text-[#6B776E]">No scheduled task data yet.</p> : null}
                    </section>
                  </div>

                  <div className="mt-6 grid gap-6 xl:grid-cols-3">
                    <section className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm xl:col-span-2">
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-[#18251D]">Recent Projects</h3>
                        <NavLink to="/generated-plan" className="text-sm font-medium text-[#123D2B]">View all</NavLink>
                      </div>
                      <div className="space-y-3">
                        {portfolioLoading ? <div role="status" className="p-3 text-sm text-[#6B776E]">Loading saved projects…</div> : dashboard?.recent_projects.length ? dashboard.recent_projects.map((item) => (
                          <button key={item.id} onClick={() => void openProject(item.id)} className="flex w-full items-center justify-between rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-3 text-left hover:border-[#245C43]">
                            <div>
                              <div className="font-medium text-[#18251D]">{item.name}</div>
                              <div className="text-sm text-[#6B776E]">{item.project_type} · {item.task_count} tasks · {item.progress_percent}% complete</div>
                            </div>
                            <span className="rounded-full bg-[#EAF2EC] px-2.5 py-1 text-xs font-medium text-[#123D2B]">{item.status}</span>
                          </button>
                        )) : <div className="rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] p-4 text-sm text-[#6B776E]">No saved projects yet.</div>}
                      </div>
                    </section>

                    <section className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-[#18251D]">Upcoming Deadlines</h3>
                      </div>
                      <div className="space-y-3">
                        {dashboard?.upcoming_deadlines.length ? dashboard.upcoming_deadlines.map((item) => (
                          <button key={item.id} onClick={() => openProject(item.id)} className="flex w-full items-center justify-between rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-3 text-left">
                            <span className="font-medium text-[#18251D]">{item.name}</span>
                            <span className="text-sm text-[#6B776E]">{item.deadline}</span>
                          </button>
                        )) : <div className="rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] p-4 text-sm text-[#6B776E]">No upcoming deadlines.</div>}
                      </div>
                    </section>

                    <section className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-[#18251D]">Quick Actions</h3>
                      </div>
                      <div className="space-y-3">
                        <NavLink to="/create-plan" onClick={resetCreatePlanForm} className="flex items-center justify-between rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-3 text-sm font-medium text-[#18251D]">Create a plan <Plus size={16} className="text-[#123D2B]" /></NavLink>
                        <NavLink to="/team-info" className="flex items-center justify-between rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-3 text-sm font-medium text-[#18251D]">Add team member <Users size={16} className="text-[#123D2B]" /></NavLink>
                        <button onClick={archivePlan} className="flex w-full items-center justify-between rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-3 text-sm font-medium text-[#18251D]">Archive current plan <Archive size={16} className="text-[#123D2B]" /></button>
                      </div>
                    </section>
                  </div>
                </>
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
                      <div className="space-y-5">
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

                      <div className="space-y-4 rounded-2xl border border-[#DCE5DE] bg-[#F7F9F7] p-4">
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
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#245C43]">Manage team</p>
                      <h2 className="text-2xl font-bold text-[#18251D]">Team Info</h2>
                    </div>
                    <button onClick={openAddMemberForm} className="inline-flex items-center gap-2 rounded-xl bg-[#123D2B] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#0B2B20]">
                      <Plus size={16} /> Add Member
                    </button>
                  </div>

                  <section className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
                    <div className="mb-4 flex items-center gap-2 rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] px-3 py-2">
                      <Search size={16} className="text-[#6B776E]" />
                      <input value={teamSearch} onChange={(e) => setTeamSearch(e.target.value)} placeholder="Search members" className="w-full border-0 bg-transparent text-sm text-[#18251D] placeholder:text-[#6B776E] focus:outline-none" />
                    </div>

                    <div className="space-y-3">
                      {filteredMembers.length ? filteredMembers.map((member) => (
                        <div key={member.id} className="rounded-xl border border-[#DCE5DE] p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="font-semibold text-[#18251D]">{member.name}</div>
                              <div className="text-xs uppercase tracking-wide text-[#245C43]">{member.role}</div>
                            </div>
                            <div className="flex items-center gap-2">
                              <button onClick={() => openEditMemberForm(member)} className="inline-flex items-center gap-1 rounded-lg border border-[#DCE5DE] bg-white px-2 py-1.5 text-xs font-medium text-[#18251D]"><Pencil size={12} /> Edit</button>
                              <button onClick={() => removeMember(member.id)} className="inline-flex items-center gap-1 rounded-lg border border-[#DCE5DE] bg-white px-2 py-1.5 text-xs font-medium text-red-600"><X size={12} /> Delete</button>
                            </div>
                          </div>
                          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-[#6B776E]">
                            <div><span className="font-medium text-[#18251D]">Experience:</span> {member.experience} yrs</div>
                            <div><span className="font-medium text-[#18251D]">Allocation:</span> {member.allocation}%</div>
                            <div><span className="font-medium text-[#18251D]">Hours:</span> {member.hours_per_day}/day</div>
                            <div><span className="font-medium text-[#18251D]">Availability:</span> {member.available_from ?? '—'} to {member.available_until ?? '—'}</div>
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
                  </div>

                  <section className="rounded-2xl border border-[#DCE5DE] bg-white p-5 shadow-sm">
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
                          <div>
                            <div className="text-2xl font-bold text-[#18251D]">{plan.name || project.name}</div>
                            <div className="text-sm text-[#6B776E]">{plan.project_type || project.project_type} · {plan.start_date || project.start_date} to {plan.deadline || project.deadline}</div>
                          </div>
                          <div className="flex gap-2">
                            <button onClick={() => openProject(plan.project_id)} className="rounded-xl border border-[#DCE5DE] bg-white px-3 py-2 text-sm font-medium text-[#18251D]">Reload Plan</button>
                            {plan.archived ? (
                              <button disabled={pendingProjectActionId === plan.project_id} onClick={() => void restoreProject(plan.project_id)} className="rounded-xl bg-[#123D2B] px-3 py-2 text-sm font-medium text-white disabled:opacity-50">{pendingProjectActionId === plan.project_id ? 'Restoring…' : 'Restore Plan'}</button>
                            ) : (
                              <button disabled={pendingProjectActionId === plan.project_id} onClick={() => void archivePlan()} className="rounded-xl bg-[#123D2B] px-3 py-2 text-sm font-medium text-white disabled:opacity-50">{pendingProjectActionId === plan.project_id ? 'Archiving…' : 'Archive Plan'}</button>
                            )}
                          </div>
                        </div>

                        <div className="grid gap-4 md:grid-cols-3">
                          <div className="rounded-xl bg-[#F7F9F7] p-3"><div className="text-xs uppercase tracking-[0.12em] text-[#6B776E]">Status</div><div className="mt-2 text-lg font-semibold text-[#18251D]">{plan.summary?.status || 'In Progress'}</div></div>
                          <div className="rounded-xl bg-[#F7F9F7] p-3"><div className="text-xs uppercase tracking-[0.12em] text-[#6B776E]">Tasks</div><div className="mt-2 text-lg font-semibold text-[#18251D]">{plan.summary?.task_count ?? 0}</div></div>
                          <div className="rounded-xl bg-[#F7F9F7] p-3"><div className="text-xs uppercase tracking-[0.12em] text-[#6B776E]">Progress</div><div className="mt-2 text-lg font-semibold text-[#18251D]">{plan.summary?.progress_percent ?? 0}%</div></div>
                        </div>

                        <div className="space-y-4">
                          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                            <label className="block text-sm text-[#18251D]">
                              <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.14em] text-[#245C43]">Category</span>
                              <select value={planFilters.category} onChange={(event) => setPlanFilters((current) => ({ ...current, category: event.target.value }))} className={selectClassName}>
                                {taskCategories.map((category) => <option key={category} value={category}>{category}</option>)}
                              </select>
                            </label>
                            <label className="block text-sm text-[#18251D]">
                              <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.14em] text-[#245C43]">Member</span>
                              <select value={planFilters.member} onChange={(event) => setPlanFilters((current) => ({ ...current, member: event.target.value }))} className={selectClassName}>
                                {['All Members', ...new Set((plan?.tasks ?? []).map((task: Task) => task.assignee_name).filter(Boolean) as string[])].map((member) => <option key={member} value={member}>{member}</option>)}
                              </select>
                            </label>
                            <label className="block text-sm text-[#18251D]">
                              <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.14em] text-[#245C43]">Sort</span>
                              <select value={planFilters.sort} onChange={(event) => setPlanFilters((current) => ({ ...current, sort: event.target.value }))} className={selectClassName}>
                                <option value="priority">Priority</option>
                                <option value="effort">Effort</option>
                                <option value="schedule">Schedule</option>
                              </select>
                            </label>
                          </div>

                          <div className="flex flex-wrap items-center gap-2">
                            <select value={planFilters.status} onChange={(event) => setPlanFilters((current) => ({ ...current, status: event.target.value }))} className={selectClassName}>
                              {['All Statuses', 'Pending', 'In Progress', 'Completed', 'Blocked'].map((status) => <option key={status} value={status}>{status}</option>)}
                            </select>
                            <button onClick={() => setPlanFilters({ category: 'All Tasks', member: 'All Members', status: 'All Statuses', sort: 'priority' })} className="rounded-xl border border-[#DCE5DE] bg-white px-3 py-2 text-sm font-medium text-[#18251D]">Clear filters</button>
                          </div>

                          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                            {categoryBreakdown.map((group) => (
                              <button key={group.category} type="button" onClick={() => setPlanFilters((current) => ({ ...current, category: current.category === group.category ? 'All Tasks' : group.category }))} aria-pressed={planFilters.category === group.category} className={`rounded-xl border p-3 text-left transition ${planFilters.category === group.category ? 'border-[#123D2B] bg-[#EAF2EC]' : 'border-[#DCE5DE] bg-[#F7F9F7] hover:border-[#245C43]'}`}>
                                <div className="text-xs uppercase tracking-[0.12em] text-[#6B776E]">{group.category}</div>
                                <div className="mt-2 text-xl font-semibold text-[#18251D]">{group.count}</div>
                              </button>
                            ))}
                          </div>

                          <section className="overflow-hidden rounded-xl border border-[#DCE5DE]">
                            <div className="border-b border-[#DCE5DE] bg-[#F7F9F7] px-3 py-2">
                              <h3 className="font-semibold text-[#18251D]">Team Member Workflow / Daily Workload</h3>
                            </div>
                            {dailyWorkflow.some((day) => day.tasks.length > 0) ? (
                              <div className="overflow-x-auto">
                                <table className="min-w-full text-left text-sm">
                                  <thead className="bg-white text-[#18251D]">
                                    <tr>
                                      <th className="px-3 py-2 font-semibold">Workday</th>
                                      <th className="px-3 py-2 font-semibold">Team Member</th>
                                      <th className="px-3 py-2 font-semibold">Scheduled Tasks</th>
                                      <th className="px-3 py-2 font-semibold">Allocated / Capacity</th>
                                      <th className="px-3 py-2 font-semibold">Remaining</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {dailyWorkflow.map((day) => (
                                      <tr key={`${day.date}-${day.member_id}`} className="border-t border-[#DCE5DE] align-top">
                                        <td className="whitespace-nowrap px-3 py-2 font-medium text-[#18251D]">{day.date}</td>
                                        <td className="whitespace-nowrap px-3 py-2 text-[#18251D]">{day.member_name}</td>
                                        <td className="min-w-[280px] px-3 py-2">
                                          {day.tasks.length ? <div className="space-y-2">{day.tasks.map((item) => (
                                            <div key={item.id} className="rounded-lg border border-[#DCE5DE] bg-[#F7F9F7] p-2">
                                              <div className="font-medium text-[#18251D]">{item.id} · {item.title}</div>
                                              <div className="text-xs text-[#6B776E]">{item.start_date || day.date} to {item.end_date || day.date} · {item.allocated_hours}h today / {item.effort_hours}h estimated · {item.status}</div>
                                            </div>
                                          ))}</div> : <span className="text-xs text-[#6B776E]">No tasks scheduled</span>}
                                        </td>
                                        <td className="whitespace-nowrap px-3 py-2 text-[#18251D]">{day.allocated_hours}h / {day.capacity_hours}h</td>
                                        <td className="whitespace-nowrap px-3 py-2 text-[#18251D]">{day.remaining_hours}h</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            ) : <div className="p-4 text-sm text-[#6B776E]">{planMembers.length ? 'No scheduled tasks are assigned to team members.' : 'No team members are assigned to this project.'}</div>}
                          </section>

                          <div className="space-y-3">
                            {filteredPlanTasks.length ? filteredPlanTasks.map((task: Task) => {
                              const isOpen = expandedTaskId === task.id
                              return (
                                <div key={task.id} className="rounded-xl border border-[#DCE5DE] p-3">
                                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                    <button type="button" onClick={() => setExpandedTaskId(isOpen ? null : task.id)} className="flex flex-1 items-center justify-between gap-3 text-left">
                                      <div>
                                        <div className="font-medium text-[#18251D]">{task.id} · {task.title}</div>
                                        <div className="text-sm text-[#6B776E]">{task.category} · {task.assignee_name || 'Unassigned'} · {task.effort_hours}h · {task.priority}</div>
                                      </div>
                                      <span className="text-xs uppercase tracking-[0.12em] text-[#245C43]">{isOpen ? 'Hide' : 'View details'}</span>
                                    </button>
                                    <select value={task.status} onChange={(e) => adjustTaskStatus(task.id, e.target.value)} className="rounded-lg border border-[#DCE5DE] bg-white px-2 py-1 text-sm text-[#18251D]">
                                      <option value="Pending">Pending</option>
                                      <option value="In Progress">In Progress</option>
                                      <option value="Completed">Completed</option>
                                      <option value="Blocked">Blocked</option>
                                    </select>
                                    <select aria-label={`Assign ${task.id}`} value={task.assignee_id ?? ''} onChange={(event) => void adjustTaskAssignment(task.id, event.target.value)} className="rounded-lg border border-[#DCE5DE] bg-white px-2 py-1 text-sm text-[#18251D]">
                                      <option value="">Unassigned</option>
                                      {planMembers.map((member) => <option key={member.id} value={member.id}>{member.name}</option>)}
                                    </select>
                                  </div>

                                  {isOpen ? (
                                    <div className="mt-3 space-y-3 border-t border-[#DCE5DE] pt-3 text-sm text-[#18251D]">
                                      <p><span className="font-semibold text-[#18251D]">Description:</span> {task.description || 'No description available.'}</p>
                                      <p><span className="font-semibold text-[#18251D]">Story:</span> {task.source_story || task.story_ids.join(', ') || 'Project requirement'}</p>
                                      <p><span className="font-semibold text-[#18251D]">Acceptance criteria:</span> {(task.acceptance_criteria ?? []).join('; ') || 'No acceptance criteria specified.'}</p>
                                      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                                        <div><span className="font-semibold text-[#18251D]">Start:</span> {task.start_date || '—'}</div>
                                        <div><span className="font-semibold text-[#18251D]">End:</span> {task.end_date || '—'}</div>
                                        <div><span className="font-semibold text-[#18251D]">Dependencies:</span> {task.dependencies.length ? task.dependencies.join(', ') : 'None'}</div>
                                        <div><span className="font-semibold text-[#18251D]">Assigned:</span> {task.assignee_name || 'Unassigned'}</div>
                                      </div>
                                      {task.warning ? <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800">{task.warning}</div> : null}
                                    </div>
                                  ) : null}
                                </div>
                              )
                            }) : <div className="rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] p-4 text-sm text-[#6B776E]">No tasks match the selected filters.</div>}
                          </div>
                        </div>
                      </div>
                    ) : savedProjects.some((item) => item.has_plan && !item.archived) ? (
                      <div className="space-y-3">
                        <p className="text-sm text-[#6B776E]">Choose a saved project to open its plan.</p>
                        {savedProjects.filter((item) => item.has_plan && !item.archived).map((item) => (
                          <button key={item.id} onClick={() => openProject(item.id)} className="flex w-full items-center justify-between rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-3 text-left hover:border-[#245C43]">
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
                      <div key={item.id} className="mb-3 flex items-center justify-between rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-3 last:mb-0">
                        <div>
                          <div className="font-medium text-[#18251D]">{item.name}</div>
                          <div className="text-sm text-[#6B776E]">{item.status} · {item.deadline || 'No deadline'}</div>
                        </div>
                        <div className="flex gap-2">
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

            {error ? <div className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}
          </div>
        </main>
      </div>

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
                    <TextInput label="Email Address" required type="email" value={memberFormValues.email} onChange={(event) => setMemberFormValues((current) => ({ ...current, email: event.target.value }))} error={memberFormErrors.email} />
                    <SelectField label="Role" required value={memberFormValues.role} onChange={(event) => setMemberFormValues((current) => ({ ...current, role: event.target.value }))} error={memberFormErrors.role}>
                      {roleOptions.map((role) => <option key={role} value={role}>{role}</option>)}
                    </SelectField>
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
                    <div className="md:col-span-2"><TextInput label="Primary Skills" required value={memberFormValues.primary_skills} onChange={(event) => setMemberFormValues((current) => ({ ...current, primary_skills: event.target.value }))} error={memberFormErrors.primary_skills} /></div>
                    <div className="md:col-span-2"><TextInput label="Additional Skills" value={memberFormValues.additional_skills} onChange={(event) => setMemberFormValues((current) => ({ ...current, additional_skills: event.target.value }))} /></div>
                  </div>
                </div>

                <div>
                  <div className="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-[#245C43]">Work Schedule and Availability</div>
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
                    <DateField label="Availability Start Date" value={memberFormValues.availability_start} onChange={(event) => setMemberFormValues((current) => ({ ...current, availability_start: event.target.value }))} error={memberFormErrors.availability_start} />
                    <DateField label="Availability End Date" value={memberFormValues.availability_end} onChange={(event) => setMemberFormValues((current) => ({ ...current, availability_end: event.target.value }))} error={memberFormErrors.availability_end} />
                    <div className="md:col-span-2"><TextInput label="Leave Dates" value={memberFormValues.leave_dates} onChange={(event) => setMemberFormValues((current) => ({ ...current, leave_dates: event.target.value }))} /></div>
                    <TextInput label="Allocation Percentage" required type="number" min="1" max="100" value={memberFormValues.allocation} onChange={(event) => setMemberFormValues((current) => ({ ...current, allocation: event.target.value }))} error={memberFormErrors.allocation} />
                  </div>
                </div>

                <div>
                  <div className="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-[#245C43]">Additional Information</div>
                  <TextAreaField label="Notes" value={memberFormValues.notes} onChange={(event) => setMemberFormValues((current) => ({ ...current, notes: event.target.value }))} />
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
    </div>
  )
}

export default App
