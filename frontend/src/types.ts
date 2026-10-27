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
  story_ids: string[]
  category: string
  phase?: string
  effort_hours: number
  remaining_hours: number
  priority: string
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
  daily_allocations?: { date: string; hours: number }[]
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
  members?: Member[]
  plan?: { tasks: Task[]; stories?: Story[]; daily_workload?: DailyWorkload[]; summary: Record<string, number | string | boolean> } | null
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
  }[]
  upcoming_deadlines: { id: number; name: string; deadline: string; status: string }[]
}
