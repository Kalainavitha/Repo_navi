import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App'

const lead = { id: 'L1', name: 'Lena Lead', role: 'Project Manager', skills: ['planning'], experience: 9, hours_per_day: 8, allocation: 100, available_from: null, available_until: null, leave_dates: [], is_lead: true }
const dev = { id: 'D1', name: 'Dev Dan', role: 'Backend Developer', skills: ['python'], experience: 3, hours_per_day: 8, allocation: 100, available_from: null, available_until: null, leave_dates: [], is_lead: false }

const emptyDashboard = {
  metrics: { total_projects: 0, active_projects: 0, completed_projects: 0, team_members: 0, tasks_in_progress: 0, overdue_tasks: 0 },
  project_status: [], task_progress: [], team_workload: [], project_timeline: [], recent_projects: [], upcoming_deadlines: [],
}

function planFixture() {
  const tasks = [
    {
      id: 'P7-TSK-001', title: 'Build backend logic: Sign in', description: 'Implement the server-side logic, data handling and validation needed so users can sign in.',
      summary: 'Server-side logic so users can sign in.', summary_source: 'task', story_ids: ['ST-001'], category: 'Backend', effort_hours: 8, remaining_hours: 8,
      priority: 'High', required_skills: [], assignee_id: 'D1', assignee_name: 'Dev Dan', dependencies: [], status: 'Pending',
      acceptance_criteria: ['Endpoints implemented with validation'], rationale: 'Dev Dan (3 yrs) was chosen for this task.',
      risk_level: 'Medium', risk_note: 'High-priority task on a member with 3 years of experience.', start_date: '2026-11-02', end_date: '2026-11-03',
    },
    {
      id: 'P7-TSK-002', title: 'Build screens: Dashboard', description: 'Build the screens and interactions that let users see a dashboard.',
      summary: 'User-facing screens so users can see a dashboard.', summary_source: 'task', story_ids: ['ST-002'], category: 'UI/Frontend', effort_hours: 6, remaining_hours: 6,
      priority: 'Medium', required_skills: [], assignee_id: 'D1', assignee_name: 'Dev Dan', dependencies: [], status: 'Pending',
      start_date: '2026-11-04', end_date: '2026-11-04',
    },
  ]
  const plan = {
    id: 7, project_id: 7, name: 'Billing Portal', project_type: 'Web Application', start_date: '2026-11-02', deadline: '2026-12-18', status: 'Active', stories: [], tasks,
    summary: {
      task_count: 2, progress_percent: 0, risk_level: 'High', risk_score: 14,
      risks: [{ type: 'deadline', severity: 'High', message: 'The plan finishes 3 day(s) after the deadline (2026-12-18).' }],
    },
  }
  const project = {
    id: 7, name: 'Billing Portal', description: 'PROJECT-WIDE DESCRIPTION that must not appear in task popups.', project_type: 'Web Application',
    start_date: '2026-11-02', deadline: '2026-12-18', status: 'Active', archived: false, has_plan: true, members: [lead, dev], plan,
  }
  return { plan, project }
}

function stubApi(extra: (url: string) => Response | undefined = () => undefined, options: { withPlan?: boolean } = {}) {
  const { project } = planFixture()
  const withPlan = options.withPlan ?? true
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    const custom = extra(url)
    if (custom) return custom
    if (url.endsWith('/api/team-members')) return new Response(JSON.stringify([lead, dev]), { status: 200 })
    if (url.endsWith('/api/projects?archived=true')) return new Response('[]', { status: 200 })
    if (url.endsWith('/api/projects')) return new Response(JSON.stringify(withPlan ? [project] : []), { status: 200 })
    if (url.endsWith('/api/projects/7')) return new Response(JSON.stringify(project), { status: 200 })
    if (url.endsWith('/api/dashboard')) return new Response(JSON.stringify(emptyDashboard), { status: 200 })
    if (url.includes('/api/calendar')) return new Response(JSON.stringify({ month: '', events: [] }), { status: 200 })
    return new Response('{}', { status: 200 })
  }))
}

function memberCard(name: string) {
  const match = screen.getAllByText(name).map((element) => element.closest('div[class*="cursor-pointer"]')).find(Boolean)
  if (!match) throw new Error(`No team card found for ${name}`)
  return match as HTMLElement
}

describe('GenPlan features', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the Edit button on every task for everyone, with no sign-in step', async () => {
    window.history.pushState({}, '', '/generated-plan')
    stubApi()
    render(<App />)
    await screen.findAllByText('Build backend logic: Sign in')

    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Edit' }).length).toBe(2))
    expect(screen.queryByLabelText('Signed in as')).not.toBeInTheDocument()
    expect(screen.queryByText(/Signed in as/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Only a Team Lead can reassign/)).not.toBeInTheDocument()
  })

  it('reassigns a task without any user header', async () => {
    window.history.pushState({}, '', '/generated-plan')
    const patches: { url: string; headers: Record<string, string>; body: Record<string, unknown> }[] = []
    stubApi((url) => (url.includes('/api/tasks/') ? new Response('{}', { status: 200 }) : undefined))
    const original = globalThis.fetch as unknown as (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'PATCH') patches.push({ url: String(input), headers: (init.headers ?? {}) as Record<string, string>, body: JSON.parse(String(init.body)) })
      return original(input, init)
    }))
    render(<App />)
    await screen.findAllByText('Build backend logic: Sign in')
    fireEvent.click((await screen.findAllByRole('button', { name: 'Edit' }))[0])
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getAllByRole('combobox')[0], { target: { value: 'L1' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(patches.length).toBeGreaterThan(0))
    expect(patches[0].body).toEqual({ assignee_id: 'L1' })
    expect(patches[0].headers).not.toHaveProperty('X-Acting-Member-Id')
  })

  it('opens a short task summary instead of the project description', async () => {
    window.history.pushState({}, '', '/generated-plan')
    stubApi()
    render(<App />)
    await screen.findAllByText('Build backend logic: Sign in')

    fireEvent.click(screen.getAllByRole('button', { name: 'View' })[0])
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Server-side logic so users can sign in.')).toBeInTheDocument()
    expect(within(dialog).getByText('Endpoints implemented with validation')).toBeInTheDocument()
    expect(within(dialog).getByText(/Why this person/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Medium risk/)).toBeInTheDocument()
    expect(dialog).not.toHaveTextContent('PROJECT-WIDE DESCRIPTION')

    fireEvent.click(within(dialog).getAllByRole('button', { name: 'Close' }).at(-1)!)
    fireEvent.click(screen.getAllByRole('button', { name: 'View' })[1])
    const second = await screen.findByRole('dialog')
    expect(within(second).getByText('User-facing screens so users can see a dashboard.')).toBeInTheDocument()
    expect(second).not.toHaveTextContent('Server-side logic so users can sign in.')
  })

  it('does not repeat the long story text for tasks from an older plan', async () => {
    window.history.pushState({}, '', '/generated-plan')
    const { project } = planFixture()
    const longStory = 'REPEATED STORY TEXT As a logged-in user, I want to see a dashboard. '.repeat(30)
    const oldTask = { ...project.plan.tasks[0], summary: 'Backend work for “Sign in”.', summary_source: 'derived', description: longStory, acceptance_criteria: ['SHOULD NOT SHOW'], rationale: undefined }
    const oldProject = { ...project, plan: { ...project.plan, tasks: [oldTask] } }
    stubApi((url) => (url.endsWith('/api/projects/7') ? new Response(JSON.stringify(oldProject), { status: 200 }) : undefined))
    render(<App />)
    await screen.findAllByText(/Build backend logic: Sign in/)
    fireEvent.click(screen.getAllByRole('button', { name: 'View' })[0])
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/Backend work for/)).toBeInTheDocument()
    expect(dialog).not.toHaveTextContent('REPEATED STORY TEXT')
    expect(dialog).not.toHaveTextContent('SHOULD NOT SHOW')
  })

  it('regenerates a plan after confirmation', async () => {
    window.history.pushState({}, '', '/generated-plan')
    const calls: string[] = []
    stubApi((url) => {
      if (url.endsWith('/api/projects/7/generate-plan')) {
        calls.push(url)
        return new Response('{}', { status: 200 })
      }
      return undefined
    })
    const confirm = vi.spyOn(window, 'confirm')
    render(<App />)
    await screen.findAllByText('Build backend logic: Sign in')

    confirm.mockReturnValueOnce(false)
    fireEvent.click(screen.getByRole('button', { name: 'Regenerate Plan' }))
    expect(calls).toHaveLength(0)

    confirm.mockReturnValueOnce(true)
    fireEvent.click(screen.getByRole('button', { name: 'Regenerate Plan' }))
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(await screen.findByText('Plan regenerated')).toBeInTheDocument()
    confirm.mockRestore()
  })

  it('lets anyone mark a task in progress or completed, even without being a team lead', async () => {
    window.history.pushState({}, '', '/generated-plan')
    const patches: { url: string; body: Record<string, unknown> }[] = []
    stubApi((url) => (url.includes('/api/tasks/') ? new Response('{}', { status: 200 }) : undefined))
    const original = globalThis.fetch as unknown as (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'PATCH') patches.push({ url: String(input), body: JSON.parse(String(init.body)) })
      return original(input, init)
    }))
    render(<App />)
    await screen.findAllByText('Build backend logic: Sign in')
    // status can be changed without opening the Edit dialog

    const select = screen.getByLabelText('Status of Build backend logic: Sign in')
    expect(select).toHaveValue('Pending')
    expect(within(select).getAllByRole('option').map((option) => option.textContent)).toEqual(['Yet to start', 'In process', 'Halted', 'Completed'])

    fireEvent.change(select, { target: { value: 'In Progress' } })
    await waitFor(() => expect(patches).toHaveLength(1))
    expect(patches[0].url).toMatch(/\/api\/tasks\/P7-TSK-001$/)
    expect(patches[0].body).toEqual({ status: 'In Progress' })

    fireEvent.change(screen.getByLabelText('Status of Build screens: Dashboard'), { target: { value: 'Completed' } })
    await waitFor(() => expect(patches).toHaveLength(2))
    expect(patches[1].body).toEqual({ status: 'Completed' })
  })

  it('offers the status control in the task popup and disables it on archived plans', async () => {
    window.history.pushState({}, '', '/generated-plan')
    stubApi()
    const view = render(<App />)
    await screen.findAllByText('Build backend logic: Sign in')
    fireEvent.click(screen.getAllByRole('button', { name: 'View' })[0])
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByLabelText('Status of Build backend logic: Sign in')).toBeEnabled()
    view.unmount()

    const { project } = planFixture()
    const archived = { ...project, archived: true, plan: { ...project.plan, archived: true } }
    stubApi((url) => (url.endsWith('/api/projects/7') ? new Response(JSON.stringify(archived), { status: 200 }) : url.endsWith('/api/projects') ? new Response('[]', { status: 200 }) : url.endsWith('/api/projects?archived=true') ? new Response(JSON.stringify([archived]), { status: 200 }) : undefined))
    window.history.pushState({}, '', '/generated-plan?project_id=7')
    render(<App />)
    const locked = await screen.findAllByLabelText('Status of Build backend logic: Sign in')
    expect(locked[0]).toBeDisabled()
  })

  it('lists plan risks with their severity', async () => {
    window.history.pushState({}, '', '/generated-plan')
    stubApi()
    render(<App />)
    const panel = await screen.findByRole('region', { name: 'Plan risks' })
    expect(within(panel).getByText(/The plan finishes 3 day\(s\) after the deadline/)).toBeInTheDocument()
    expect(within(panel).getByText('High overall')).toBeInTheDocument()
    expect(within(panel).getByText('14')).toBeInTheDocument()
  })

  it('shows a member\'s project allocations and hours from the Team Info page', async () => {
    window.history.pushState({}, '', '/team-info')
    stubApi((url) => {
      if (url.endsWith('/api/team-members/D1/allocations')) {
        return new Response(JSON.stringify({
          member: dev, daily_capacity: 8, weekly_capacity: 40,
          totals: { project_count: 2, task_count: 3, assigned_hours: 26, remaining_hours: 20, completed_hours: 6 },
          projects: [
            { project_id: 7, name: 'Billing Portal', status: 'Active', start_date: '2026-11-02', deadline: '2026-12-18', task_count: 2, assigned_hours: 14, remaining_hours: 14, completed_hours: 0, share_percent: 54, first_date: '2026-11-02', last_date: '2026-11-04', tasks: [{ id: 'P7-TSK-001', title: 'Build backend logic: Sign in', status: 'Pending', priority: 'High', hours: 8, remaining_hours: 8, start_date: '2026-11-02', end_date: '2026-11-03' }] },
            { project_id: 8, name: 'Warehouse App', status: 'Active', start_date: '2026-11-09', deadline: null, task_count: 1, assigned_hours: 12, remaining_hours: 6, completed_hours: 6, share_percent: 46, first_date: '2026-11-09', last_date: '2026-11-11', tasks: [] },
          ],
          weekly: [{ week: '2026-11-02', hours: 44, capacity_hours: 40, by_project: [{ name: 'Billing Portal', hours: 44 }] }],
        }), { status: 200 })
      }
      return undefined
    })
    render(<App />)
    await screen.findAllByText('Dev Dan')
    fireEvent.click(within(memberCard('Dev Dan')).getByRole('button', { name: /Allocations/ }))

    const dialog = await screen.findByRole('dialog')
    expect(await within(dialog).findByText('Billing Portal')).toBeInTheDocument()
    expect(within(dialog).getByText('Warehouse App')).toBeInTheDocument()
    expect(within(dialog).getByText('26h')).toBeInTheDocument()
    expect(within(dialog).getByText('44/40h')).toBeInTheDocument()

    fireEvent.click(within(dialog).getByRole('button', { name: /Billing Portal/ }))
    expect(within(dialog).getByText('Build backend logic: Sign in')).toBeInTheDocument()
  })

  it('creates a member with optional email, an additional role and no allocation, notes or extra skills', async () => {
    window.history.pushState({}, '', '/team-info')
    const bodies: Record<string, unknown>[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (init?.method === 'POST' && url.endsWith('/api/team-members')) {
        bodies.push(JSON.parse(String(init.body)))
        return new Response(JSON.stringify({ ...dev, id: 'N1', name: 'New Person' }), { status: 201 })
      }
      if (url.endsWith('/api/team-members')) return new Response(JSON.stringify([lead, dev]), { status: 200 })
      if (url.endsWith('/api/team-workload')) return new Response(JSON.stringify({ projects: [], members: [] }), { status: 200 })
      if (url.includes('/api/projects')) return new Response('[]', { status: 200 })
      if (url.endsWith('/api/dashboard')) return new Response(JSON.stringify(emptyDashboard), { status: 200 })
      return new Response('{}', { status: 200 })
    }))
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Add Member/ }))
    const dialogHost = document.body

    // removed fields
    expect(within(dialogHost).queryByText(/Allocation Percentage/)).not.toBeInTheDocument()
    expect(within(dialogHost).queryByText('Additional Skills')).not.toBeInTheDocument()
    expect(within(dialogHost).queryByText('Additional Information')).not.toBeInTheDocument()
    expect(within(dialogHost).queryByText('Notes')).not.toBeInTheDocument()
    expect(within(dialogHost).queryByRole('checkbox', { name: /Team Lead/ })).not.toBeInTheDocument()
    // email is optional
    expect(within(dialogHost).getByText('Email Address (optional)')).toBeInTheDocument()

    const nameInput = document.querySelector('input[type="text"]') as HTMLInputElement
    fireEvent.change(nameInput, { target: { value: 'New Person' } })
    const selects = Array.from(document.querySelectorAll('select')) as HTMLSelectElement[]
    const roleSelect = selects.find((select) => Array.from(select.options).some((option) => option.value === 'Team Lead') && !Array.from(select.options).some((option) => option.value === ''))!
    const extraRole = selects.find((select) => Array.from(select.options).some((option) => option.text === 'None'))!
    expect(Array.from(roleSelect.options).map((option) => option.value)).toContain('Team Lead')
    fireEvent.change(extraRole, { target: { value: 'Team Lead' } })

    fireEvent.click(screen.getByRole('button', { name: 'Save Member' }))
    await waitFor(() => expect(bodies.length).toBe(1))
    expect(bodies[0].email).toBeNull()
    expect(bodies[0].additional_role).toBe('Team Lead')
    expect(bodies[0]).not.toHaveProperty('allocation')
    expect(bodies[0]).not.toHaveProperty('notes')
    expect(bodies[0]).not.toHaveProperty('is_lead')
  })

  it('still validates an email when one is typed', async () => {
    window.history.pushState({}, '', '/team-info')
    stubApi()
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Add Member/ }))
    fireEvent.change(document.querySelector('input[type="text"]') as HTMLInputElement, { target: { value: 'Typo Tim' } })
    fireEvent.change(document.querySelector('input[type="email"]') as HTMLInputElement, { target: { value: 'not-an-email' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Member' }))
    expect(await screen.findByText(/Enter a valid email address/)).toBeInTheDocument()
  })

  it('shows each person\'s hours per project and working hours in the Team Info chart', async () => {
    window.history.pushState({}, '', '/team-info')
    stubApi((url) => {
      if (url.endsWith('/api/team-workload')) {
        return new Response(JSON.stringify({
          projects: [{ id: 7, name: 'Billing Portal' }, { id: 8, name: 'Warehouse App' }],
          members: [
            { id: 'D1', name: 'Dev Dan', role: 'Backend Developer', is_lead: false, hours_per_day: 8, weekly_hours: 40, total_hours: 26, by_project: [{ project_id: 7, name: 'Billing Portal', hours: 14, completed_hours: 0 }, { project_id: 8, name: 'Warehouse App', hours: 12, completed_hours: 0 }] },
            { id: 'L1', name: 'Lena Lead', role: 'Team Lead', is_lead: true, hours_per_day: 6, weekly_hours: 30, total_hours: 0, by_project: [] },
          ],
        }), { status: 200 })
      }
      return undefined
    })
    render(<App />)
    const chart = await screen.findByRole('region', { name: 'Team workload' })
    const projects = await within(chart).findByRole('list', { name: 'Projects' })
    expect(within(projects).getByText('Billing Portal')).toBeInTheDocument()
    expect(within(projects).getByText('Warehouse App')).toBeInTheDocument()
    expect(within(chart).getByText(/26h planned across 2 projects/)).toBeInTheDocument()
    expect(within(chart).getByText(/30h\/week available/)).toBeInTheDocument()
  })

  it('shows the active projects count on the Generated Plan page', async () => {
    window.history.pushState({}, '', '/generated-plan')
    stubApi((url) => {
      if (url.endsWith('/api/dashboard')) {
        return new Response(JSON.stringify({ ...emptyDashboard, metrics: { ...emptyDashboard.metrics, total_projects: 4, active_projects: 3 } }), { status: 200 })
      }
      return undefined
    })
    render(<App />)
    await screen.findAllByText('Build backend logic: Sign in')
    expect(screen.getByText('Active Projects')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('Active projects count')).toHaveTextContent('3'))
  })

  it('renders a compact dashboard with one create button and no tasks-in-progress card', async () => {
    window.history.pushState({}, '', '/')
    const dashboard = {
      ...emptyDashboard,
      metrics: { total_projects: 5, active_projects: 3, completed_projects: 1, team_members: 4, tasks_in_progress: 6, overdue_tasks: 2 },
      project_status: [{ name: 'Active', value: 3 }, { name: 'Completed', value: 1 }],
      task_progress: [{ name: 'Pending', value: 7 }],
      team_workload: [{ id: 'D1', name: 'Dev Dan', hours: 21.6, allocation: 100 }],
      recent_projects: [{ id: 7, name: 'Billing Portal', status: 'Active', deadline: '2026-12-18', project_type: 'Web Application', task_count: 12, progress_percent: 40, risk_level: 'High' }],
      upcoming_deadlines: [{ id: 7, name: 'Billing Portal', deadline: '2026-12-18', status: 'Active' }],
    }
    stubApi((url) => {
      if (url.endsWith('/api/dashboard')) return new Response(JSON.stringify(dashboard), { status: 200 })
      const match = url.match(/\/api\/calendar\?month=(\d{4}-\d{2})/)
      if (match) {
        return new Response(JSON.stringify({ month: match[1], events: [{ date: `${match[1]}-15`, type: 'deadline', title: 'Billing Portal deadline', project_id: 7, project_name: 'Billing Portal', status: 'Active' }] }), { status: 200 })
      }
      return undefined
    })
    render(<App />)

    const keyNumbers = await screen.findByRole('region', { name: 'Key numbers' })
    await waitFor(() => expect(within(keyNumbers).getByText('5')).toBeInTheDocument())
    expect(within(keyNumbers).getByText('Total Projects')).toBeInTheDocument()
    expect(within(keyNumbers).queryByText('Active Projects')).not.toBeInTheDocument()
    expect(within(keyNumbers).getByText('Team Members')).toBeInTheDocument()
    expect(within(keyNumbers).queryByText('Tasks in Progress')).not.toBeInTheDocument()
    expect(screen.queryByText(/tasks? in progress/i)).not.toBeInTheDocument()

    // exactly one create button in the page content (the sidebar link is navigation)
    const main = screen.getByRole('main')
    expect(within(main).getAllByRole('button', { name: /create/i })).toHaveLength(1)
    expect(within(main).getByRole('button', { name: /create a plan/i })).toBeInTheDocument()

    // calendar loads events and stays navigable
    const calendar = screen.getByRole('region', { name: 'Calendar' })
    fireEvent.click(await within(calendar).findByRole('gridcell', { name: /-15, 1 event/ }))
    expect(await within(calendar).findByText('Billing Portal deadline')).toBeInTheDocument()
    fireEvent.click(within(calendar).getByRole('button', { name: 'Next month' }))
    await waitFor(() => expect(within(calendar).getByRole('gridcell', { name: /-15, 1 event/ })).toBeInTheDocument())

    // recent project shows its risk level
    expect(screen.getByText('High risk')).toBeInTheDocument()
    expect(screen.getByText(/2 overdue/)).toBeInTheDocument()
  })

  it('greets everyone with a general welcome, never by name', async () => {
    window.history.pushState({}, '', '/')
    stubApi()
    render(<App />)
    expect(await screen.findByText(/Welcome to GenPlan/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: /Welcome to GenPlan/ })).not.toHaveTextContent(/Lena|aishu|Dan/i)
  })

  it('has no Insights chart card on the home page', async () => {
    window.history.pushState({}, '', '/')
    stubApi()
    render(<App />)
    await screen.findByRole('region', { name: 'Upcoming deadlines' })
    expect(screen.queryByText('Insights')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Charts' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab')).not.toBeInTheDocument()
  })

  it('shows upcoming deadlines beside the calendar: 5 visible, 10 per page, the 11th on the next page', async () => {
    window.history.pushState({}, '', '/')
    const deadlines = Array.from({ length: 12 }, (_, index) => ({
      id: 100 + index, name: `Project ${String(index + 1).padStart(2, '0')}`, deadline: `2027-01-${String(index + 1).padStart(2, '0')}`, status: 'Active',
    }))
    stubApi((url) => (url.endsWith('/api/dashboard')
      ? new Response(JSON.stringify({ ...emptyDashboard, metrics: { ...emptyDashboard.metrics, total_projects: 12, active_projects: 12 }, upcoming_deadlines: deadlines }), { status: 200 })
      : undefined))
    render(<App />)

    const windowEl = await screen.findByRole('region', { name: 'Upcoming deadlines' })
    const calendar = screen.getByRole('region', { name: 'Calendar' })
    // same row as the calendar, everything inside one window
    expect(windowEl.parentElement).toBe(calendar.parentElement)

    const list = await within(windowEl).findByRole('list', { name: 'Upcoming deadlines list' })
    // a page holds 10 rows, but the window is only tall enough for 5 (5 x 44px rows + 4 x 8px gaps)
    expect(within(list).getAllByRole('listitem')).toHaveLength(10)
    expect(list).toHaveStyle({ maxHeight: '252px' })
    expect(within(list).getByText('Project 10')).toBeInTheDocument()
    expect(within(list).queryByText('Project 11')).not.toBeInTheDocument()
    expect(within(windowEl).getByText('Page 1 of 2')).toBeInTheDocument()
    expect(within(windowEl).getByRole('button', { name: 'Previous page' })).toBeDisabled()

    fireEvent.click(within(windowEl).getByRole('button', { name: 'Next page' }))
    const second = within(windowEl).getByRole('list', { name: 'Upcoming deadlines list' })
    expect(within(second).getAllByRole('listitem')).toHaveLength(2)
    expect(within(second).getByText('Project 11')).toBeInTheDocument()
    expect(within(second).getByText('Project 12')).toBeInTheDocument()
    expect(within(windowEl).getByText('Page 2 of 2')).toBeInTheDocument()
    expect(within(windowEl).getByRole('button', { name: 'Next page' })).toBeDisabled()

    fireEvent.click(within(windowEl).getByRole('button', { name: 'Previous page' }))
    expect(within(within(windowEl).getByRole('list', { name: 'Upcoming deadlines list' })).getAllByRole('listitem')).toHaveLength(10)
  })

  it('opens a project from the deadlines window and hides paging when there is only one page', async () => {
    window.history.pushState({}, '', '/')
    const deadlines = [{ id: 7, name: 'Billing Portal', deadline: '2027-02-01', status: 'Active' }]
    stubApi((url) => (url.endsWith('/api/dashboard')
      ? new Response(JSON.stringify({ ...emptyDashboard, upcoming_deadlines: deadlines }), { status: 200 })
      : undefined))
    render(<App />)
    const windowEl = await screen.findByRole('region', { name: 'Upcoming deadlines' })
    expect(await within(windowEl).findByText('Billing Portal')).toBeInTheDocument()
    expect(within(windowEl).queryByRole('button', { name: 'Next page' })).not.toBeInTheDocument()
    expect(within(windowEl).getByText('Page 1 of 1')).toBeInTheDocument()
    fireEvent.click(within(windowEl).getByRole('button', { name: /Billing Portal/ }))
    expect(await screen.findByRole('heading', { name: 'Generated Plan' })).toBeInTheDocument()
  })

  it('stretches the deadlines window to the calendar height and keeps the pager at the bottom', async () => {
    window.history.pushState({}, '', '/')
    const deadlines = [
      { id: 1, name: 'Login', deadline: '2027-01-12', status: 'Active' },
      { id: 2, name: 'test', deadline: '2027-02-01', status: 'Active' },
    ]
    stubApi((url) => (url.endsWith('/api/dashboard')
      ? new Response(JSON.stringify({ ...emptyDashboard, upcoming_deadlines: deadlines }), { status: 200 })
      : undefined))
    render(<App />)
    const windowEl = await screen.findByRole('region', { name: 'Upcoming deadlines' })
    const calendar = screen.getByRole('region', { name: 'Calendar' })
    // both cards sit in a stretching grid row, so the shorter one takes the taller one's height
    expect(windowEl.parentElement).toBe(calendar.parentElement)
    expect(calendar.parentElement).toHaveClass('items-stretch')
    expect(windowEl).toHaveClass('h-full')
    // with only two deadlines the rest stays empty and the counter is pushed to the bottom
    expect(await within(windowEl).findByText('Page 1 of 1')).toHaveAttribute('aria-live', 'polite')
    expect(within(windowEl).getByText('Page 1 of 1').parentElement).toHaveClass('mt-auto')
  })

  it('shows an empty state when there are no upcoming deadlines', async () => {
    window.history.pushState({}, '', '/')
    stubApi()
    render(<App />)
    const windowEl = await screen.findByRole('region', { name: 'Upcoming deadlines' })
    expect(await within(windowEl).findByText('No upcoming deadlines.')).toBeInTheDocument()
    expect(within(windowEl).queryByRole('button', { name: 'Next page' })).not.toBeInTheDocument()
  })

  it('has a slim top bar with a create button only outside the home page', async () => {
    window.history.pushState({}, '', '/team-info')
    stubApi()
    const { unmount } = render(<App />)
    const bar = (await screen.findByRole('navigation', { name: 'Breadcrumb' })).closest('header') as HTMLElement
    expect(within(bar).getByText('Team Info')).toBeInTheDocument()
    expect(within(bar).getByRole('button', { name: /create plan/i })).toBeInTheDocument()
    unmount()

    window.history.pushState({}, '', '/')
    render(<App />)
    const homeBar = (await screen.findByRole('navigation', { name: 'Breadcrumb' })).closest('header') as HTMLElement
    expect(within(homeBar).queryByRole('button')).not.toBeInTheDocument()
  })
})
