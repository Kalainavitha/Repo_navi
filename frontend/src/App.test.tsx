import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'

describe('App', () => {
  it('renders the GenPlan heading', () => {
    window.history.pushState({}, '', '/')
    render(<App />)
    expect(screen.getAllByText(/GenPlan/i).length).toBeGreaterThan(0)
  })

  it('shows the project creation form fields', () => {
    window.history.pushState({}, '', '/create-plan')
    render(<App />)
    expect(screen.getByLabelText(/project name/i)).toBeInTheDocument()
  })

  it('filters saved plan tasks when a category tile is selected', async () => {
    window.history.pushState({}, '', '/generated-plan')
    const savedPlan = {
      id: 41,
      project_id: 41,
      name: 'Filterable Portal',
      project_type: 'Web Application',
      start_date: '2026-10-27',
      deadline: '2026-11-30',
      status: 'Active',
      stories: [],
      summary: { task_count: 6, progress_percent: 0 },
      tasks: [
        { id: 'TSK-1', title: 'Build UI', description: '', story_ids: [], category: 'UI/Frontend', effort_hours: 3, remaining_hours: 3, priority: 'High', required_skills: [], assignee_id: 'M1', assignee_name: 'Mia', dependencies: [], status: 'Pending' },
        { id: 'TSK-2', title: 'Build API', description: '', story_ids: [], category: 'Backend', effort_hours: 4, remaining_hours: 4, priority: 'Medium', required_skills: [], assignee_id: 'M1', assignee_name: 'Mia', dependencies: [], status: 'Pending' },
        { id: 'TSK-3', title: 'Run tests', description: '', story_ids: [], category: 'QA/Testing', effort_hours: 2, remaining_hours: 2, priority: 'Medium', required_skills: [], assignee_id: 'M1', assignee_name: 'Mia', dependencies: [], status: 'Pending' },
        { id: 'TSK-4', title: 'Connect services', description: '', story_ids: [], category: 'Integration', effort_hours: 2, remaining_hours: 2, priority: 'Medium', required_skills: [], assignee_id: 'M1', assignee_name: 'Mia', dependencies: [], status: 'Pending' },
        { id: 'TSK-5', title: 'Deploy release', description: '', story_ids: [], category: 'DevOps/Deployment', effort_hours: 2, remaining_hours: 2, priority: 'Low', required_skills: [], assignee_id: 'M1', assignee_name: 'Mia', dependencies: [], status: 'Pending' },
        { id: 'TSK-6', title: 'Write guide', description: '', story_ids: [], category: 'Documentation', effort_hours: 1, remaining_hours: 1, priority: 'Low', required_skills: [], assignee_id: 'M1', assignee_name: 'Mia', dependencies: [], status: 'Pending' },
      ],
    }
    const savedProject = { id: 41, name: 'Filterable Portal', description: '', project_type: 'Web Application', start_date: '2026-10-27', deadline: '2026-11-30', status: 'Active', archived: false, has_plan: true, plan: savedPlan }
    const dashboard = {
      metrics: { total_projects: 1, active_projects: 1, completed_projects: 0, team_members: 0, tasks_in_progress: 0, overdue_tasks: 0 },
      project_status: [{ name: 'Active', value: 1 }],
      task_progress: [{ name: 'Pending', value: 6 }],
      team_workload: [],
      project_timeline: [],
      recent_projects: [],
      upcoming_deadlines: [],
    }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/team-members')) return new Response('[]', { status: 200 })
      if (url.endsWith('/api/projects')) return new Response(JSON.stringify([savedProject]), { status: 200 })
      if (url.endsWith('/api/projects?archived=true')) return new Response('[]', { status: 200 })
      if (url.endsWith('/api/dashboard')) return new Response(JSON.stringify(dashboard), { status: 200 })
      if (url.endsWith('/api/projects/41')) return new Response(JSON.stringify(savedProject), { status: 200 })
      return new Response('{}', { status: 200 })
    }))

    render(<App />)
    await screen.findAllByText('Build UI')
    expect(screen.getAllByText('Build API').length).toBeGreaterThan(0)
    expect(screen.queryByPlaceholderText(/task or id/i)).not.toBeInTheDocument()
    const categories = [
      ['UI/Frontend', 'Build UI'],
      ['Backend', 'Build API'],
      ['QA/Testing', 'Run tests'],
      ['Integration', 'Connect services'],
      ['DevOps/Deployment', 'Deploy release'],
      ['Documentation', 'Write guide'],
    ]
    for (const [category, expectedTask] of categories) {
      const filter = screen.getAllByRole('button', { name: new RegExp(category) }).find((button) => button.hasAttribute('aria-pressed'))
      expect(filter).toBeDefined()
      fireEvent.click(filter!)
      await waitFor(() => expect(screen.getAllByText(expectedTask).length).toBeGreaterThan(0))
      for (const [, otherTask] of categories.filter(([otherCategory]) => otherCategory !== category)) {
        expect(screen.queryAllByText(otherTask)).toHaveLength(0)
      }
    }
    fireEvent.change(screen.getByLabelText(/Category/), { target: { value: 'All Tasks' } })
    for (const [, expectedTask] of categories) expect(screen.getAllByText(expectedTask).length).toBeGreaterThan(0)
    vi.unstubAllGlobals()
  })

  it('replaces document preview and clears it when starting a fresh plan', async () => {
    window.history.pushState({}, '', '/create-plan')
    const emptyDashboard = {
      metrics: { total_projects: 0, active_projects: 0, completed_projects: 0, team_members: 0, tasks_in_progress: 0, overdue_tasks: 0 },
      project_status: [], task_progress: [], team_workload: [], project_timeline: [], recent_projects: [], upcoming_deadlines: [],
    }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/api/team-members')) return new Response('[]', { status: 200 })
      if (url.endsWith('/api/projects')) return new Response('[]', { status: 200 })
      if (url.endsWith('/api/projects?archived=true')) return new Response('[]', { status: 200 })
      if (url.endsWith('/api/dashboard')) return new Response(JSON.stringify(emptyDashboard), { status: 200 })
      if (url.endsWith('/api/documents/preview')) {
        const body = init?.body
        if (!(body instanceof FormData)) throw new Error('Expected multipart document body')
        const file = body.get('file') as File
        if (file.name === 'broken.txt') return new Response(JSON.stringify({ detail: 'Preview processing failed' }), { status: 422 })
        const title = file.name === 'first.txt' ? 'Reset password' : 'Track delivery'
        return new Response(JSON.stringify({ filename: file.name, stories: [{ id: `ST-${title}`, title, description: title, priority: 'Medium', acceptance_criteria: [] }], preview: title }), { status: 200 })
      }
      return new Response('{}', { status: 200 })
    }))

    const { container } = render(<App />)
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(fileInput, { target: { files: [new File(['first story'], 'first.txt', { type: 'text/plain' })] } })
    expect(await screen.findAllByText('Reset password')).not.toHaveLength(0)

    fireEvent.change(fileInput, { target: { files: [new File(['broken story'], 'broken.txt', { type: 'text/plain' })] } })
    expect(await screen.findByText('Preview processing failed')).toBeInTheDocument()
    fireEvent.change(fileInput, { target: { files: [new File(['second story'], 'second.txt', { type: 'text/plain' })] } })
    expect(await screen.findAllByText('Track delivery')).not.toHaveLength(0)
    expect(screen.queryAllByText('Reset password')).toHaveLength(0)
    expect(screen.queryByText('Preview processing failed')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('link', { name: 'Create Plan' }))
    expect(screen.queryAllByText('Track delivery')).toHaveLength(0)
    expect(screen.getByText('No file selected.')).toBeInTheDocument()
    expect(fileInput.value).toBe('')
    vi.unstubAllGlobals()
  })

  it('opens an archived plan and restores it to the active list', async () => {
    window.history.pushState({}, '', '/archive')
    let restored = false
    const savedPlan = {
      id: 10, project_id: 10, name: 'Archived Portal', project_type: 'Web Application',
      start_date: '2026-10-27', deadline: '2026-11-30', status: 'Active', archived: true,
      stories: [], summary: { task_count: 1, progress_percent: 0 },
      tasks: [{ id: 'P10-TSK-001', title: 'Saved API task', description: 'Persisted detail', story_ids: ['ST-1'], category: 'Backend', effort_hours: 3, remaining_hours: 3, priority: 'High', required_skills: [], assignee_id: 'BE-1', assignee_name: 'Bea', dependencies: [], status: 'In Progress' }],
    }
    const archivedProject = { id: 10, name: 'Archived Portal', description: '', project_type: 'Web Application', start_date: '2026-10-27', deadline: '2026-11-30', status: 'Active', archived: true, has_plan: true, members: [{ id: 'BE-1', name: 'Bea', role: 'Backend Developer', skills: ['python'], experience: 4, hours_per_day: 8, allocation: 100, available_from: null, available_until: null, leave_dates: [] }], plan: savedPlan }
    const dashboard = { metrics: { total_projects: 1, active_projects: 0, completed_projects: 0, team_members: 1, tasks_in_progress: 1, overdue_tasks: 0 }, project_status: [{ name: 'Archived', value: 1 }], task_progress: [{ name: 'In Progress', value: 1 }], team_workload: [], project_timeline: [], recent_projects: [], upcoming_deadlines: [] }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/team-members')) return new Response(JSON.stringify(archivedProject.members), { status: 200 })
      if (url.endsWith('/api/projects?archived=true')) return new Response(JSON.stringify(restored ? [] : [archivedProject]), { status: 200 })
      if (url.endsWith('/api/projects')) return new Response(JSON.stringify(restored ? [{ ...archivedProject, archived: false }] : []), { status: 200 })
      if (url.endsWith('/api/dashboard')) return new Response(JSON.stringify(dashboard), { status: 200 })
      if (url.endsWith('/api/projects/10/restore')) { restored = true; return new Response(JSON.stringify({ ...archivedProject, archived: false }), { status: 200 }) }
      if (url.endsWith('/api/projects/10')) return new Response(JSON.stringify({ ...archivedProject, archived: !restored, plan: { ...savedPlan, archived: !restored } }), { status: 200 })
      return new Response('{}', { status: 200 })
    }))

    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Open' }))
    expect(await screen.findByText('P10-TSK-001 · Saved API task')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Restore Plan' }))
    await screen.findByRole('button', { name: 'Archive Plan' })
    expect(await screen.findByText('Active Generated Plans')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archived Portal' })).toBeInTheDocument()
    expect(restored).toBe(true)
    vi.unstubAllGlobals()
  })
})
