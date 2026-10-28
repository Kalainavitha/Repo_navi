import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App'

const dev = { id: 'D1', name: 'Dev Dan', role: 'Backend Developer', skills: ['python'], experience: 3, hours_per_day: 8, allocation: 100, available_from: null, available_until: null, leave_dates: [] }

const emptyDashboard = {
  metrics: { total_projects: 1, active_projects: 1, completed_projects: 0, team_members: 1, tasks_in_progress: 0, overdue_tasks: 0 },
  project_status: [], task_progress: [], team_workload: [], project_timeline: [], recent_projects: [], upcoming_deadlines: [],
}

const baseTask = {
  description: '', summary: 'Short summary.', summary_source: 'task', story_ids: [], category: 'Backend', effort_hours: 8, remaining_hours: 8,
  priority: 'High', required_skills: [], assignee_id: 'D1', assignee_name: 'Dev Dan', dependencies: [], acceptance_criteria: [],
}

function projectWith(tasks: object[]) {
  const plan = {
    id: 7, project_id: 7, name: 'Billing Portal', project_type: 'Web Application', start_date: '2026-11-02', deadline: '2026-12-18',
    status: 'Active', stories: [], tasks, summary: { task_count: tasks.length, progress_percent: 0 },
  }
  return { id: 7, name: 'Billing Portal', description: 'x', project_type: 'Web Application', start_date: '2026-11-02', deadline: '2026-12-18', status: 'Active', archived: false, has_plan: true, members: [dev], plan }
}

const forecast = (overrides: object = {}) => ({
  runs: 300, remaining_tasks: 4, probability_on_time: 0.72, p50: '2026-12-14', p85: '2026-12-19', p95: '2026-12-22',
  earliest: '2026-12-09', latest: '2026-12-26', histogram: [{ date: '2026-12-12', count: 40 }, { date: '2026-12-14', count: 90 }, { date: '2026-12-21', count: 20 }],
  critical_tasks: [{ id: 'P7-TSK-002', title: 'Build secure backend', share: 0.8 }], confidence: 'Medium', deadline: '2026-12-18', ...overrides,
})

function stub(project: ReturnType<typeof projectWith>, extra: (url: string, init?: RequestInit) => Response | undefined = () => undefined) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const custom = extra(url, init)
    if (custom) return custom
    if (url.endsWith('/api/team-members')) return new Response(JSON.stringify([dev]), { status: 200 })
    if (url.endsWith('/api/projects?archived=true')) return new Response('[]', { status: 200 })
    if (url.endsWith('/api/projects')) return new Response(JSON.stringify([project]), { status: 200 })
    if (url.endsWith('/api/projects/7')) return new Response(JSON.stringify(project), { status: 200 })
    if (url.endsWith('/api/dashboard')) return new Response(JSON.stringify(emptyDashboard), { status: 200 })
    if (url.includes('/forecast')) return new Response(JSON.stringify(forecast()), { status: 200 })
    if (url.endsWith('/api/team-workload')) return new Response(JSON.stringify({ projects: [], members: [] }), { status: 200 })
    if (url.endsWith('/api/estimate-accuracy')) return new Response(JSON.stringify({ samples: 0, min_samples: 3, members: [] }), { status: 200 })
    return new Response('{}', { status: 200 })
  }))
}

const onTime = [{ ...baseTask, id: 'P7-TSK-001', title: 'Build backend', status: 'Pending', start_date: '2099-01-05', end_date: '2099-01-06' }]
const late = [
  { ...baseTask, id: 'P7-TSK-001', title: 'Build backend', status: 'Pending', start_date: '2026-01-05', end_date: '2026-01-06' },
  { ...baseTask, id: 'P7-TSK-002', title: 'Write tests', status: 'Blocked', start_date: '2099-01-05', end_date: '2099-01-06' },
]

describe('Smart tools', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the on-time forecast with the odds, the likely and safe dates and the biggest threat', async () => {
    window.history.pushState({}, '', '/generated-plan')
    stub(projectWith(onTime))
    render(<App />)
    const card = await screen.findByRole('region', { name: 'On-time forecast' })
    expect(await within(card).findByLabelText('On-time probability')).toHaveTextContent('72%')
    expect(within(card).getByText('Coin flip')).toBeInTheDocument()
    expect(within(card).getByText('Most likely finish')).toBeInTheDocument()
    expect(within(card).getByText('Safe date (85% sure)')).toBeInTheDocument()
    expect(within(card).getByText('Build secure backend')).toBeInTheDocument()
    expect(within(card).getByText('80% of runs')).toBeInTheDocument()
    expect(within(card).getByRole('img', { name: 'Spread of simulated finish dates' })).toBeInTheDocument()
    // 72% is above the 70% line: no warning banner
    expect(within(card).queryByText(/odds are below 70%/)).not.toBeInTheDocument()
  })

  it('warns and offers a re-plan when the odds are poor, and says so when there is no deadline', async () => {
    window.history.pushState({}, '', '/generated-plan')
    const quiet = {
      today: '2026-11-12', overdue: [], blocked: [], original_finish: '2099-01-06', replanned_finish: '2099-01-06', slip_days: 0, deadline: '2099-12-31',
      deadline_ok: true, deadline_ok_before: true, shifted_tasks: [], people_affected: [], needs_replan: false, unfinished_tasks: 1,
    }
    stub(projectWith(onTime), (url) => {
      if (url.includes('/forecast')) return new Response(JSON.stringify(forecast({ probability_on_time: 0.31 })), { status: 200 })
      if (url.includes('/impact')) return new Response(JSON.stringify(quiet), { status: 200 })
      return undefined
    })
    const first = render(<App />)
    const card = await screen.findByRole('region', { name: 'On-time forecast' })
    expect(await within(card).findByText('Needs attention')).toBeInTheDocument()
    expect(within(card).getByLabelText('On-time probability')).toHaveTextContent('31%')
    fireEvent.click(within(card).getByRole('button', { name: 'Review re-plan' }))
    expect(await screen.findByRole('dialog', { name: 'Re-plan from today' })).toBeInTheDocument()
    first.unmount()

    stub(projectWith(onTime), (url) => (url.includes('/forecast') ? new Response(JSON.stringify(forecast({ probability_on_time: null, deadline: null })), { status: 200 }) : undefined))
    render(<App />)
    const noDeadline = await screen.findByRole('region', { name: 'On-time forecast' })
    expect(await within(noDeadline).findByText('No deadline set')).toBeInTheDocument()
    expect(within(noDeadline).getByLabelText('On-time probability')).toHaveTextContent('-')
  })

  it('counts late and halted tasks on the Re-plan button and shows the impact before applying', async () => {
    window.history.pushState({}, '', '/generated-plan')
    const applied: string[] = []
    const impact = {
      today: '2026-11-12', overdue: [{ id: 'P7-TSK-001', title: 'Build backend', end_date: '2026-01-06', assignee_name: 'Dev Dan' }],
      blocked: [{ id: 'P7-TSK-002', title: 'Write tests', end_date: '2099-01-06', assignee_name: 'Dev Dan' }],
      original_finish: '2026-11-12', replanned_finish: '2026-11-20', slip_days: 8, deadline: '2026-12-18', deadline_ok: true, deadline_ok_before: true,
      shifted_tasks: [{ id: 'P7-TSK-001', title: 'Build backend', status: 'Pending', assignee_name: 'Dev Dan', old_start: '2026-11-04', new_start: '2026-11-12', old_end: '2026-11-06', new_end: '2026-11-16', delta_days: 10 }],
      people_affected: ['Dev Dan'], needs_replan: true, unfinished_tasks: 2,
    }
    stub(projectWith(late), (url, init) => {
      if (url.includes('/impact')) return new Response(JSON.stringify(impact), { status: 200 })
      if (url.includes('/replan') && init?.method === 'POST') { applied.push(url); return new Response('{}', { status: 200 }) }
      return undefined
    })
    render(<App />)
    await screen.findAllByText('Build backend')
    const button = await screen.findByRole('button', { name: /Re-plan from today/ })
    expect(within(button).getByText('2 late')).toBeInTheDocument()

    fireEvent.click(button)
    const dialog = await screen.findByRole('dialog', { name: 'Re-plan from today' })
    expect(await within(dialog).findByText(/slips by 8 days/)).toBeInTheDocument()
    expect(within(dialog).getByText(/still meets the deadline/)).toBeInTheDocument()
    const moves = within(dialog).getByRole('region', { name: 'Tasks that move' })
    expect(within(moves).getByText('Build backend')).toBeInTheDocument()
    expect(within(moves).getByText('(+10 days)')).toBeInTheDocument()

    fireEvent.click(within(dialog).getByRole('button', { name: 'Apply re-plan' }))
    await waitFor(() => expect(applied).toHaveLength(1))
    expect(applied[0]).toMatch(/\/api\/projects\/7\/replan$/)
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Re-plan from today' })).not.toBeInTheDocument())
  })

  it('has nothing to apply when the plan is on schedule', async () => {
    window.history.pushState({}, '', '/generated-plan')
    stub(projectWith(onTime), (url) => (url.includes('/impact')
      ? new Response(JSON.stringify({
        today: '2026-11-12', overdue: [], blocked: [], original_finish: '2099-01-06', replanned_finish: '2099-01-06', slip_days: 0, deadline: '2099-12-31',
        deadline_ok: true, deadline_ok_before: true, shifted_tasks: [], people_affected: [], needs_replan: false, unfinished_tasks: 1,
      }), { status: 200 })
      : undefined))
    render(<App />)
    await screen.findAllByText('Build backend')
    expect(within(await screen.findByRole('button', { name: /Re-plan from today/ })).queryByText(/late/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Re-plan from today/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Re-plan from today' })
    expect(await within(dialog).findByText(/nothing to re-plan/i)).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Apply re-plan' })).toBeDisabled()
  })

  it('builds a weekly report, moves between weeks, and copies the text', async () => {
    window.history.pushState({}, '', '/generated-plan')
    const weeks: string[] = []
    const report = (label: string) => ({
      project: 'Billing Portal', week_start: '2026-11-09', week_end: '2026-11-15', week_label: label, next_week_label: 'Mon 16 Nov - Sun 22 Nov',
      status: 'At risk', status_reasons: ['1 task(s) are halted'], progress: { done: 1, total: 4, percent: 25, hours_done: 8, hours_total: 32, hours_remaining: 24 },
      completed_this_week: [{ id: 'a', title: 'Design the schema', assignee_name: 'Dev Dan', end_date: '2026-11-10', status: 'Completed' }],
      in_progress: [], blocked: [{ id: 'b', title: 'Integrate payments', assignee_name: 'Dev Dan', end_date: '2026-11-12', status: 'Blocked' }], overdue: [],
      next_week: [{ name: 'Dev Dan', hours: 16, tasks: ['Build screens'] }], risks: [{ severity: 'High', message: 'Payments vendor is late' }],
      forecast: '72% chance of finishing by Fri 18 Dec.', deadline: '2026-12-18', markdown: '# Weekly status: Billing Portal\n',
    })
    stub(projectWith(onTime), (url) => {
      if (!url.includes('/report')) return undefined
      weeks.push(new URL(url).searchParams.get('week') ?? '')
      return new Response(JSON.stringify(report(weeks.length === 1 ? 'Mon 9 Nov - Sun 15 Nov 2026' : 'Mon 16 Nov - Sun 22 Nov 2026')), { status: 200 })
    })
    const writeText = vi.fn(async () => undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })

    render(<App />)
    await screen.findAllByText('Build backend')
    fireEvent.click(screen.getByRole('button', { name: /Weekly report/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Weekly status report' })
    expect(await within(dialog).findByText('Mon 9 Nov - Sun 15 Nov 2026')).toBeInTheDocument()
    expect(within(dialog).getByText('At risk')).toBeInTheDocument()
    expect(within(dialog).getByText('Design the schema')).toBeInTheDocument()
    expect(within(dialog).getByText('Integrate payments')).toBeInTheDocument()
    expect(within(dialog).getByText('Payments vendor is late')).toBeInTheDocument()
    expect(within(dialog).getByText(/Forecast: 72% chance/)).toBeInTheDocument()

    fireEvent.click(within(dialog).getByRole('button', { name: 'Copy text' }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('# Weekly status: Billing Portal\n'))
    expect(await within(dialog).findByRole('button', { name: 'Copied!' })).toBeInTheDocument()

    fireEvent.click(within(dialog).getByRole('button', { name: 'Next week' }))
    expect(await within(dialog).findByText('Mon 16 Nov - Sun 22 Nov 2026')).toBeInTheDocument()
    expect(weeks).toHaveLength(2)
    const days = weeks.map((week) => new Date(`${week}T00:00:00`).getTime())
    expect(days[1] - days[0]).toBe(7 * 86_400_000)
  })

  it('lets you choose Word, PDF or CSV when downloading the weekly report', async () => {
    window.history.pushState({}, '', '/generated-plan')
    const requested: string[] = []
    const report = {
      project: 'Billing Portal', week_start: '2026-11-09', week_end: '2026-11-15', week_label: 'Mon 9 Nov - Sun 15 Nov 2026', next_week_label: 'Mon 16 Nov - Sun 22 Nov',
      status: 'On track', status_reasons: ['no overdue or halted work'], progress: { done: 0, total: 1, percent: 0, hours_done: 0, hours_total: 8, hours_remaining: 8 },
      completed_this_week: [], in_progress: [], blocked: [], overdue: [], next_week: [], risks: [], forecast: null, deadline: '2026-12-18', markdown: '# Weekly status',
    }
    stub(projectWith(onTime), (url) => {
      if (url.includes('/report/export')) {
        requested.push(url)
        const format = new URL(url).searchParams.get('format')
        return new Response(new Blob(['file-bytes']), { status: 200, headers: { 'Content-Disposition': `attachment; filename="weekly-report-billing-portal-2026-11-09.${format}"` } })
      }
      if (url.includes('/report')) return new Response(JSON.stringify(report), { status: 200 })
      return undefined
    })
    const createUrl = vi.fn(() => 'blob:fake')
    const revokeUrl = vi.fn()
    Object.defineProperty(URL, 'createObjectURL', { value: createUrl, configurable: true })
    Object.defineProperty(URL, 'revokeObjectURL', { value: revokeUrl, configurable: true })
    const saved: string[] = []
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { saved.push(this.download) })

    render(<App />)
    await screen.findAllByText('Build backend')
    fireEvent.click(screen.getByRole('button', { name: /Weekly report/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Weekly status report' })
    await within(dialog).findByText('Mon 9 Nov - Sun 15 Nov 2026')

    // the old single ".md" button is gone; a format menu replaces it
    expect(within(dialog).queryByRole('button', { name: /\.md/ })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('menu')).not.toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: /Download/ }))
    const menu = within(dialog).getByRole('menu', { name: 'Choose a file format' })
    expect(within(menu).getAllByRole('menuitem').map((item) => item.textContent)).toEqual(['Word document.docx', 'PDF.pdf', 'CSV (Excel).csv'])

    const formats = ['docx', 'pdf', 'csv']
    for (const [index, format] of formats.entries()) {
      if (!within(dialog).queryByRole('menu')) fireEvent.click(within(dialog).getByRole('button', { name: /Download/ }))
      fireEvent.click(within(within(dialog).getByRole('menu')).getAllByRole('menuitem')[index])
      await waitFor(() => expect(saved).toHaveLength(index + 1))
      const url = new URL(requested.at(-1) as string)
      expect(url.pathname).toBe('/api/projects/7/report/export')
      expect(url.searchParams.get('format')).toBe(format)
      expect(url.searchParams.get('week')).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      expect(saved.at(-1)).toBe(`weekly-report-billing-portal-2026-11-09.${format}`)
      await waitFor(() => expect(within(dialog).queryByRole('menu')).not.toBeInTheDocument())
    }
    expect(createUrl).toHaveBeenCalledTimes(3)
    click.mockRestore()
  })

  it('shows a clear message when a download fails', async () => {
    window.history.pushState({}, '', '/generated-plan')
    const report = {
      project: 'Billing Portal', week_start: '2026-11-09', week_end: '2026-11-15', week_label: 'Mon 9 Nov - Sun 15 Nov 2026', next_week_label: 'x',
      status: 'On track', status_reasons: [], progress: { done: 0, total: 1, percent: 0, hours_done: 0, hours_total: 8, hours_remaining: 8 },
      completed_this_week: [], in_progress: [], blocked: [], overdue: [], next_week: [], risks: [], forecast: null, deadline: null, markdown: '',
    }
    stub(projectWith(onTime), (url) => {
      if (url.includes('/report/export')) return new Response(JSON.stringify({ detail: 'Could not build the PDF.' }), { status: 500 })
      if (url.includes('/report')) return new Response(JSON.stringify(report), { status: 200 })
      return undefined
    })
    render(<App />)
    await screen.findAllByText('Build backend')
    fireEvent.click(screen.getByRole('button', { name: /Weekly report/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Weekly status report' })
    await within(dialog).findByText('Mon 9 Nov - Sun 15 Nov 2026')
    fireEvent.click(within(dialog).getByRole('button', { name: /Download/ }))
    fireEvent.click(within(within(dialog).getByRole('menu')).getByRole('menuitem', { name: /PDF/ }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Could not build the PDF.')
  })

  it('offers to assign team members who are not on the project yet, and tells you what happened', async () => {
    window.history.pushState({}, '', '/generated-plan')
    const nancy = { ...dev, id: 'N1', name: 'nancy', role: 'Frontend Developer' }
    const surya = { ...dev, id: 'S1', name: 'surya', role: 'Team Lead' }
    const calls: string[] = []
    let rebalanced = false
    const project = projectWith(onTime)
    stub(project, (url, init) => {
      if (url.endsWith('/api/team-members')) return new Response(JSON.stringify([dev, nancy, surya]), { status: 200 })
      if (url.endsWith('/api/projects/7') && rebalanced) return new Response(JSON.stringify({ ...project, members: [dev, nancy, surya] }), { status: 200 })
      if (url.endsWith('/api/projects/7/rebalance') && init?.method === 'POST') {
        calls.push(url)
        rebalanced = true
        return new Response(JSON.stringify({ added_members: ['nancy', 'surya'], moved: [{ id: 'a' }, { id: 'b' }, { id: 'c' }], rescheduled: 3 }), { status: 200 })
      }
      return undefined
    })
    render(<App />)
    await screen.findAllByText('Build backend')
    const button = await screen.findByRole('button', { name: /Assign new members \(2\)/ })
    expect(button).toHaveAttribute('title', expect.stringContaining('nancy, surya'))

    fireEvent.click(button)
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(await screen.findByText('nancy, surya joined the project and took 3 tasks')).toBeInTheDocument()
    // once everyone is on the project the button goes away
    await waitFor(() => expect(screen.queryByRole('button', { name: /Assign new members/ })).not.toBeInTheDocument())
  })

  it('does not show the assign button when the whole team is already on the project', async () => {
    window.history.pushState({}, '', '/generated-plan')
    stub(projectWith(onTime))
    render(<App />)
    await screen.findAllByText('Build backend')
    expect(screen.queryByRole('button', { name: /Assign new members/ })).not.toBeInTheDocument()
  })

  it('no longer has a Reload Plan button', async () => {
    window.history.pushState({}, '', '/generated-plan')
    stub(projectWith(onTime))
    render(<App />)
    await screen.findAllByText('Build backend')
    expect(screen.queryByRole('button', { name: /Reload Plan/i })).not.toBeInTheDocument()
    // the other plan buttons are still there
    expect(screen.getByRole('button', { name: /Weekly report/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Regenerate Plan/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Archive Plan/ })).toBeInTheDocument()
  })

  it('shows the Estimate Coach empty state, then what it learned about each person', async () => {
    window.history.pushState({}, '', '/team-info')
    stub(projectWith(onTime))
    const first = render(<App />)
    const coach = await screen.findByRole('region', { name: 'Estimate coach' })
    expect(await within(coach).findByText(/Nothing to learn from yet/)).toBeInTheDocument()
    first.unmount()

    stub(projectWith(onTime), (url) => (url.endsWith('/api/estimate-accuracy')
      ? new Response(JSON.stringify({
        samples: 5, min_samples: 3,
        members: [
          { id: 'D1', name: 'Dev Dan', role: 'Backend Developer', samples: 4, avg_ratio: 1.6, applied_factor: 1.34, learned: true, label: 'Tends to take 34% longer than planned, most on Backend.', by_phase: [{ phase: 'Backend', samples: 3, ratio: 1.7, applied_factor: 1.35 }] },
          { id: 'N1', name: 'New Nia', role: 'QA Engineer', samples: 1, avg_ratio: 1.0, applied_factor: null, learned: false, label: 'Learning: 1 of 3 completed tasks needed before estimates are adjusted.', by_phase: [] },
        ],
      }), { status: 200 })
      : undefined))
    render(<App />)
    const filled = await screen.findByRole('region', { name: 'Estimate coach' })
    expect(await within(filled).findByText('Tends to take 34% longer than planned, most on Backend.')).toBeInTheDocument()
    expect(within(filled).getByText('Applied x1.34')).toBeInTheDocument()
    expect(within(filled).getByText('1/3 tasks')).toBeInTheDocument()
    expect(within(filled).getByText('1 of 2 learned')).toBeInTheDocument()
    expect(within(filled).getByRole('img', { name: 'Takes 160% of the planned time' })).toBeInTheDocument()
    expect(within(filled).getByText('x1.7')).toBeInTheDocument()
  })

  it('keeps working when a smart endpoint fails', async () => {
    window.history.pushState({}, '', '/generated-plan')
    stub(projectWith(onTime), (url) => (url.includes('/forecast') ? new Response('{"detail":"boom"}', { status: 500 }) : undefined))
    render(<App />)
    const card = await screen.findByRole('region', { name: 'On-time forecast' })
    expect(await within(card).findByRole('alert')).toHaveTextContent('could not be calculated')
    // the rest of the plan is still usable
    expect((await screen.findAllByText('Build backend')).length).toBeGreaterThan(0)
  })
})
