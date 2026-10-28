export type ProjectType =
  | 'Web Application'
  | 'Mobile Application'
  | 'Desktop Application'
  | 'API or Backend System'
  | 'AI/ML Application'
  | 'Data Engineering Platform'
  | 'E-commerce Platform'
  | 'Enterprise Software'
  | 'Cloud Migration'
  | 'DevOps or Infrastructure'
  | 'Cybersecurity Project'
  | 'IoT Application'
  | 'Other'

export type Member = {
  id: string
  name: string
  role: string
  skills: string[]
  experience: number
  hours_per_day: number
  allocation: number
  working_days?: string[]
  available_from: string | null
  available_until: string | null
  leave_dates: string[]
  email?: string
  notes?: string
  hourly_rate?: number
  is_lead?: boolean
  additional_role?: string | null
}

export type Story = {
  id: string
  title: string
  description: string
  acceptance_criteria?: string[]
  priority: string
  dependencies?: string[]
}

export type Task = {
  id: string
  title: string
  description: string
  summary?: string // Short, task-specific summary
  summary_source?: 'task' | 'derived' // 'derived' = old plan, regenerate it for better text
  story_ids: string[]
  category: string
  phase?: string
  effort_hours: number
  remaining_hours: number
  priority: 'High' | 'Medium' | 'Low' | string // Tightened to ensure priority levels match requirements
  required_skills: string[]
  assignee_id: string | null
  assignee_name?: string | null
  dependencies: string[]
  start_date?: string | null
  end_date?: string | null
  status: string
  acceptance_criteria?: string[]
  source_story?: string
  uncertain?: boolean
  rationale?: string
  manually_edited?: boolean
  warning?: string | null
  risk_level?: RiskSeverity
  risk_note?: string | null
  started_at?: string | null
  completed_at?: string | null
  daily_allocations?: { date: string; hours: number }[]
}

export type RiskSeverity = 'High' | 'Medium' | 'Low'

export type Risk = {
  type: string
  severity: RiskSeverity
  message: string
  task_id?: string | null
  member_id?: string | null
}

export type PlanSummary = {
  task_count?: number
  estimated_hours?: number
  projected_completion?: string | null
  buffered_completion?: string | null
  deadline_feasible?: boolean
  risk_level?: RiskSeverity
  risk_score?: number
  risks?: (Risk | string)[]
  warnings?: string[]
  [key: string]: unknown
}

export type Forecast = {
  runs: number
  remaining_tasks: number
  probability_on_time: number | null
  p50: string | null
  p85: string | null
  p95: string | null
  earliest: string | null
  latest: string | null
  histogram: { date: string; count: number }[]
  critical_tasks: { id: string; title: string; share: number }[]
  confidence: 'High' | 'Medium' | 'Low'
  deadline: string | null
}

export type ImpactTask = { id: string; title: string; end_date: string | null; assignee_name: string | null }

export type Impact = {
  today: string
  overdue: ImpactTask[]
  blocked: ImpactTask[]
  original_finish: string | null
  replanned_finish: string | null
  slip_days: number
  deadline: string | null
  deadline_ok: boolean | null
  deadline_ok_before: boolean | null
  shifted_tasks: {
    id: string
    title: string
    status: string
    assignee_name: string | null
    old_start: string | null
    new_start: string | null
    old_end: string
    new_end: string
    delta_days: number
  }[]
  people_affected: string[]
  needs_replan: boolean
  unfinished_tasks: number
}

export type EstimateAccuracy = {
  samples: number
  min_samples: number
  members: {
    id: string
    name: string
    role: string
    samples: number
    avg_ratio: number | null
    applied_factor: number | null
    learned: boolean
    label: string
    by_phase: { phase: string; samples: number; ratio: number; applied_factor: number }[]
  }[]
}

export type ReportTask = { id: string; title: string; assignee_name: string | null; end_date: string | null; status: string; priority?: string | null }

export type WeeklyReport = {
  project: string
  week_start: string
  week_end: string
  week_label: string
  next_week_label: string
  status: 'On track' | 'At risk' | 'Late'
  status_reasons: string[]
  progress: { done: number; total: number; percent: number; hours_done: number; hours_total: number; hours_remaining: number }
  completed_this_week: ReportTask[]
  in_progress: ReportTask[]
  blocked: ReportTask[]
  overdue: ReportTask[]
  next_week: { name: string; hours: number; tasks: string[] }[]
  risks: { severity: string; message: string }[]
  forecast: string | null
  deadline: string | null
  markdown: string
}

export type TeamWorkload = {
  projects: { id: number; name: string }[]
  members: {
    id: string
    name: string
    role: string
    additional_role?: string | null
    is_lead: boolean
    hours_per_day: number
    weekly_hours: number
    total_hours: number
    by_project: { project_id: number; name: string; hours: number; completed_hours: number }[]
  }[]
}

export type MemberAllocations = {
  member: Member
  daily_capacity: number
  weekly_capacity: number
  totals: { project_count: number; task_count: number; assigned_hours: number; remaining_hours: number; completed_hours: number }
  projects: {
    project_id: number
    name: string
    status: string
    start_date: string | null
    deadline: string | null
    task_count: number
    assigned_hours: number
    remaining_hours: number
    completed_hours: number
    share_percent: number
    first_date: string | null
    last_date: string | null
    tasks: { id: string; title: string; status: string; priority: string; hours: number; remaining_hours: number; start_date: string | null; end_date: string | null }[]
  }[]
  weekly: { week: string; hours: number; capacity_hours: number; by_project: { name: string; hours: number }[] }[]
}

export type CalendarEvent = {
  date: string
  type: 'project_start' | 'deadline' | 'task_due'
  title: string
  project_id: number
  project_name: string
  status: string
  priority?: string
  assignee_name?: string | null
}

export type DailyWorkload = {
  date: string
  member_id: string
  member_name: string
  capacity_hours: number
  allocated_hours: number
  remaining_hours: number
  tasks: {
    id: string
    title: string
    start_date: string | null
    end_date: string | null
    effort_hours: number
    allocated_hours: number
    status: string
  }[]
}

export type ProjectFormState = {
  name: string
  description: string
  project_type: string
  start_date: string
  deadline: string
  priority: string
  complexity: string
  working_days: string[]
  hours_per_day: number
  holidays: string[]
  timezone: string
  buffer_percent: number
  members: Member[]
}

export type SavedProject = {
  id: number
  name: string
  description: string
  project_type: string
  start_date: string
  deadline: string | null
  status: string
  archived: boolean
  has_plan: boolean
  // Ensure members are fully typed so Team Info can map them
  members?: Member[]
  plan?: { 
    tasks: Task[]; 
    stories?: Story[]; 
    daily_workload?: DailyWorkload[]; 
    summary: Record<string, number | string | boolean> 
  } | null
}

export type DashboardData = {
  metrics: {
    total_projects: number
    active_projects: number
    completed_projects: number
    team_members: number
    tasks_in_progress: number
    overdue_tasks: number
  }
  project_status: { name: string; value: number }[]
  task_progress: { name: string; value: number }[]
  team_workload: { id: string; name: string; hours: number; allocation: number }[]
  project_timeline: { week: string; planned: number; completed: number }[]
  recent_projects: {
    id: number
    name: string
    status: string
    deadline: string | null
    project_type: string
    task_count: number
    progress_percent: number
    risk_level?: RiskSeverity
  }[]
  upcoming_deadlines: { id: number; name: string; deadline: string; status: string }[]
}