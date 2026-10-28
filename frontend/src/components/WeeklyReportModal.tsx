import { useEffect, useState } from 'react'
import { ChevronDown, ChevronLeft, ChevronRight, ClipboardCopy, Download, FileSpreadsheet, FileText } from 'lucide-react'
import { apiFetch, downloadFile } from '../lib/api'
import type { ReportTask, WeeklyReport } from '../types'
import { ModalShell } from './ui'

const statusTone: Record<string, string> = {
  'On track': 'bg-[#EAF2EC] text-[#245C43]',
  'At risk': 'bg-amber-100 text-amber-800',
  Late: 'bg-red-100 text-red-700',
}

function isoDay(date: Date) {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function shiftWeek(day: string, weeks: number) {
  const parsed = new Date(`${day}T00:00:00`)
  parsed.setDate(parsed.getDate() + weeks * 7)
  return isoDay(parsed)
}

function shortDate(value: string | null) {
  if (!value) return ''
  const parsed = new Date(`${value}T00:00:00`)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function Section({ title, tasks, empty, flag }: { title: string; tasks: ReportTask[]; empty: string; flag?: string }) {
  return (
    <section aria-label={title}>
      <h4 className="mb-1.5 text-sm font-semibold text-[#18251D]">{title}</h4>
      {tasks.length ? (
        <ul className="space-y-1">
          {tasks.map((task) => (
            <li key={task.id} className="flex items-center justify-between gap-2 rounded-lg bg-[#F7F9F7] px-3 py-1.5 text-sm">
              <span className="min-w-0 truncate text-[#18251D]">{flag ? <span className="mr-1.5 rounded bg-amber-100 px-1 text-[10px] font-semibold text-amber-800">{flag}</span> : null}{task.title}</span>
              <span className="shrink-0 text-xs text-[#6B776E]">{task.assignee_name}{task.end_date ? ` · due ${shortDate(task.end_date)}` : ''}</span>
            </li>
          ))}
        </ul>
      ) : <p className="text-xs text-[#6B776E]">{empty}</p>}
    </section>
  )
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    const area = document.createElement('textarea')
    area.value = text
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand('copy')
    area.remove()
    return ok
  }
}

const downloadFormats = [
  { id: 'docx', label: 'Word document', ext: '.docx', icon: FileText },
  { id: 'pdf', label: 'PDF', ext: '.pdf', icon: FileText },
  { id: 'csv', label: 'CSV (Excel)', ext: '.csv', icon: FileSpreadsheet },
] as const

export function WeeklyReportModal({ projectId, onClose }: { projectId: number; onClose: () => void }) {
  const [day, setDay] = useState(() => isoDay(new Date()))
  const [state, setState] = useState<{ day: string; report: WeeklyReport | null; error: string } | null>(null)
  const [copied, setCopied] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [downloading, setDownloading] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState('')

  useEffect(() => {
    let cancelled = false
    apiFetch<WeeklyReport>(`/api/projects/${projectId}/report?week=${day}`)
      .then((report) => { if (!cancelled) setState({ day, report, error: '' }) })
      .catch((loadError) => { if (!cancelled) setState({ day, report: null, error: loadError instanceof Error ? loadError.message : 'Unable to build the report.' }) })
    return () => { cancelled = true }
  }, [projectId, day])

  const loading = !state || state.day !== day
  const report = !loading ? state.report : null

  const copy = async () => {
    if (!report) return
    setCopied(await copyText(report.markdown))
    window.setTimeout(() => setCopied(false), 2000)
  }

  const download = async (format: string) => {
    if (!report || downloading) return
    setMenuOpen(false)
    setDownloadError('')
    setDownloading(format)
    try {
      const { blob, filename } = await downloadFile(`/api/projects/${projectId}/report/export?format=${format}&week=${day}`)
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(link.href)
    } catch (downloadFailure) {
      setDownloadError(downloadFailure instanceof Error ? downloadFailure.message : 'The file could not be downloaded.')
    } finally {
      setDownloading(null)
    }
  }

  return (
    <ModalShell
      wide
      title="Weekly status report"
      subtitle={report?.project ?? 'Report'}
      onClose={onClose}
      footer={
        <>
          <div className="relative">
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              disabled={!report || downloading !== null}
              onClick={() => setMenuOpen((open) => !open)}
              onKeyDown={(event) => { if (event.key === 'Escape') setMenuOpen(false) }}
              className="inline-flex items-center gap-1.5 rounded-xl border border-[#DCE5DE] bg-white px-4 py-2 text-sm font-medium text-[#18251D] disabled:opacity-50"
            >
              <Download size={14} /> {downloading ? 'Preparing…' : 'Download'} <ChevronDown size={14} />
            </button>
            {menuOpen ? (
              <div role="menu" aria-label="Choose a file format" className="absolute bottom-full right-0 z-10 mb-2 w-52 overflow-hidden rounded-xl border border-[#DCE5DE] bg-white shadow-lg">
                {downloadFormats.map(({ id, label, ext, icon: Icon }) => (
                  <button
                    key={id}
                    type="button"
                    role="menuitem"
                    onClick={() => void download(id)}
                    className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm text-[#18251D] hover:bg-[#F1F8F3]"
                  >
                    <Icon size={15} className="text-[#245C43]" />
                    <span className="flex-1">{label}</span>
                    <span className="text-xs text-[#6B776E]">{ext}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <button type="button" disabled={!report} onClick={() => void copy()} className="inline-flex items-center gap-1.5 rounded-xl bg-[#123D2B] px-4 py-2 text-sm font-semibold text-white hover:bg-[#0B2B20] disabled:opacity-50"><ClipboardCopy size={14} /> {copied ? 'Copied!' : 'Copy text'}</button>
        </>
      }
    >
      <div className="mb-4 flex items-center justify-between gap-2">
        <button type="button" aria-label="Previous week" onClick={() => setDay(shiftWeek(day, -1))} className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[#DCE5DE] hover:bg-[#F7F9F7]"><ChevronLeft size={16} /></button>
        <div className="text-center">
          <div className="text-sm font-semibold text-[#18251D]">{report?.week_label ?? 'Loading…'}</div>
          <button type="button" onClick={() => setDay(isoDay(new Date()))} className="text-[11px] font-medium text-[#245C43] hover:underline">This week</button>
        </div>
        <button type="button" aria-label="Next week" onClick={() => setDay(shiftWeek(day, 1))} className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[#DCE5DE] hover:bg-[#F7F9F7]"><ChevronRight size={16} /></button>
      </div>

      {downloadError ? <div role="alert" className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{downloadError}</div> : null}
      {loading ? <div role="status" className="p-4 text-sm text-[#6B776E]">Building the report…</div> : null}
      {!loading && state.error ? <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{state.error}</div> : null}

      {report ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-[#DCE5DE] bg-[#F7F9F7] p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusTone[report.status] ?? statusTone['On track']}`}>{report.status}</span>
              <span className="text-xs text-[#6B776E]">{report.status_reasons.join('; ')}</span>
            </div>
            <div className="mt-3 flex items-center gap-2">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-white"><div className="h-full rounded-full bg-[#367653]" style={{ width: `${report.progress.percent}%` }} /></div>
              <span className="text-xs font-semibold text-[#245C43]">{report.progress.percent}%</span>
            </div>
            <p className="mt-1.5 text-xs text-[#6B776E]">{report.progress.done} of {report.progress.total} tasks done · {report.progress.hours_done}h of {report.progress.hours_total}h · {report.progress.hours_remaining}h remaining</p>
            {report.forecast ? <p className="mt-1 text-xs text-[#6B776E]">Forecast: {report.forecast}</p> : null}
          </div>

          <Section title="Completed this week" tasks={report.completed_this_week} empty="Nothing completed this week." />
          <Section title="In progress" tasks={report.in_progress} empty="Nothing in progress." />
          <Section
            title="Blocked or overdue"
            tasks={[...report.blocked, ...report.overdue.filter((task) => !report.blocked.some((blocked) => blocked.id === task.id))]}
            empty="None."
          />

          <section aria-label={`Next week (${report.next_week_label})`}>
            <h4 className="mb-1.5 text-sm font-semibold text-[#18251D]">Next week <span className="font-normal text-[#6B776E]">({report.next_week_label})</span></h4>
            {report.next_week.length ? (
              <ul className="space-y-1">
                {report.next_week.map((person) => (
                  <li key={person.name} className="rounded-lg bg-[#F7F9F7] px-3 py-1.5 text-sm">
                    <span className="font-medium text-[#18251D]">{person.name}</span> <span className="text-xs text-[#6B776E]">{person.hours}h · {person.tasks.slice(0, 3).join('; ')}{person.tasks.length > 3 ? '…' : ''}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-xs text-[#6B776E]">No work is scheduled.</p>}
          </section>

          <section aria-label="Top risks">
            <h4 className="mb-1.5 text-sm font-semibold text-[#18251D]">Top risks</h4>
            {report.risks.length ? (
              <ul className="space-y-1">
                {report.risks.map((risk) => (
                  <li key={risk.message} className="flex items-start gap-2 rounded-lg bg-[#F7F9F7] px-3 py-1.5 text-sm text-[#18251D]">
                    <span className={`mt-0.5 shrink-0 rounded-full px-1.5 text-[10px] font-semibold ${risk.severity === 'High' ? 'bg-red-100 text-red-700' : risk.severity === 'Medium' ? 'bg-amber-100 text-amber-800' : 'bg-[#EAF2EC] text-[#245C43]'}`}>{risk.severity}</span>
                    <span>{risk.message}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-xs text-[#6B776E]">No significant risks.</p>}
          </section>
        </div>
      ) : null}
    </ModalShell>
  )
}
