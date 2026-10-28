import { useEffect, useMemo, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight, Flag, Rocket, ListChecks } from 'lucide-react'
import { apiFetch } from '../../lib/api'
import type { CalendarEvent } from '../../types'

const noEvents: CalendarEvent[] = []
const weekdayLabels =['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const eventStyle: Record<CalendarEvent['type'], { dot: string; label: string; chip: string; icon: typeof Flag }> = {
  deadline: { dot: 'bg-red-500', label: 'Deadline', chip: 'bg-red-50 text-red-700', icon: Flag },
  task_due: { dot: 'bg-[#367653]', label: 'Task due', chip: 'bg-[#EAF2EC] text-[#245C43]', icon: ListChecks },
  project_start: { dot: 'bg-sky-500', label: 'Project start', chip: 'bg-sky-50 text-sky-700', icon: Rocket },
}

const pad = (value: number) => String(value).padStart(2, '0')
const dayKey = (year: number, month: number, day: number) => `${year}-${pad(month + 1)}-${pad(day)}`
const monthKey = (year: number, month: number) => `${year}-${pad(month + 1)}`

export function CalendarCard({ onOpenProject }: { onOpenProject?: (projectId: number) => void }) {
  const [today] = useState(() => new Date())
  const todayKey = dayKey(today.getFullYear(), today.getMonth(), today.getDate())
  const [cursor, setCursor] = useState({ year: today.getFullYear(), month: today.getMonth() })
  const [selected, setSelected] = useState(todayKey)
  const [result, setResult] = useState<{ key: string; events: CalendarEvent[]; failed: boolean } | null>(null)
  const requestedKey = monthKey(cursor.year, cursor.month)
  const state: 'loading' | 'ready' | 'error' = !result || result.key !== requestedKey ? 'loading' : result.failed ? 'error' : 'ready'
  const events = result && result.key === requestedKey ? result.events : noEvents

  useEffect(() => {
    let cancelled = false
    apiFetch<{ month: string; events: CalendarEvent[] }>(`/api/calendar?month=${requestedKey}`)
      .then((response) => { if (!cancelled) setResult({ key: requestedKey, events: response.events, failed: false }) })
      .catch(() => { if (!cancelled) setResult({ key: requestedKey, events: [], failed: true }) })
    return () => { cancelled = true }
  }, [requestedKey])

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>()
    events.forEach((event) => map.set(event.date, [...(map.get(event.date) ?? []), event]))
    return map
  }, [events])

  const firstWeekday = new Date(cursor.year, cursor.month, 1).getDay()
  const daysInMonth = new Date(cursor.year, cursor.month + 1, 0).getDate()
  const cells: (number | null)[] = [...Array(firstWeekday).fill(null), ...Array.from({ length: daysInMonth }, (_, index) => index + 1)]
  while (cells.length % 7 !== 0) cells.push(null)

  const monthLabel = new Date(cursor.year, cursor.month, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  const selectedEvents = byDay.get(selected) ?? []
  const selectedLabel = new Date(`${selected}T00:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })

  const shiftMonth = (delta: number) => {
    const next = new Date(cursor.year, cursor.month + delta, 1)
    setCursor({ year: next.getFullYear(), month: next.getMonth() })
  }
  const goToday = () => {
    setCursor({ year: today.getFullYear(), month: today.getMonth() })
    setSelected(todayKey)
  }

  return (
    <section aria-label="Calendar" className="min-w-0 rounded-2xl border border-[#DCE5DE] bg-white p-4 shadow-sm">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-[#EAF2EC] text-[#123D2B]"><CalendarDays size={15} /></span>
          <h3 className="text-base font-semibold text-[#18251D]">{monthLabel}</h3>
        </div>
        <div className="flex items-center gap-1.5">
          <button type="button" onClick={goToday} className="rounded-md border border-[#DCE5DE] bg-white px-2.5 py-1 text-xs font-semibold text-[#123D2B] hover:bg-[#EAF2EC]">Today</button>
          <button type="button" aria-label="Previous month" onClick={() => shiftMonth(-1)} className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[#DCE5DE] hover:bg-[#F7F9F7]"><ChevronLeft size={14} /></button>
          <button type="button" aria-label="Next month" onClick={() => shiftMonth(1)} className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[#DCE5DE] hover:bg-[#F7F9F7]"><ChevronRight size={14} /></button>
        </div>
      </div>

      <div className="grid grid-cols-7 text-center text-[10px] font-semibold uppercase tracking-[0.1em] text-[#6B776E]">
        {weekdayLabels.map((label) => <div key={label} className="py-1">{label}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-0.5" role="grid" aria-busy={state === 'loading'}>
        {cells.map((day, index) => {
          if (day === null) return <div key={`blank-${index}`} className="h-9" />
          const key = dayKey(cursor.year, cursor.month, day)
          const dayEvents = byDay.get(key) ?? []
          const isToday = key === todayKey
          const isSelected = key === selected
          const kinds = [...new Set(dayEvents.map((event) => event.type))]
          return (
            <button
              key={key}
              type="button"
              role="gridcell"
              aria-label={`${key}${dayEvents.length ? `, ${dayEvents.length} event(s)` : ''}`}
              aria-selected={isSelected}
              onClick={() => setSelected(key)}
              className={`flex h-9 flex-col items-center justify-center rounded-md border text-xs transition ${
                isSelected ? 'border-[#123D2B] bg-[#123D2B] text-white' : isToday ? 'border-[#367653] bg-[#EAF2EC] font-bold text-[#123D2B]' : 'border-transparent text-[#18251D] hover:border-[#DCE5DE] hover:bg-[#F7F9F7]'
              }`}
            >
              <span className="leading-none">{day}</span>
              <span className="mt-0.5 flex h-1 items-center gap-0.5">
                {kinds.map((kind) => <span key={kind} className={`h-1 w-1 rounded-full ${isSelected ? 'bg-white' : eventStyle[kind].dot}`} />)}
              </span>
            </button>
          )
        })}
      </div>

      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-[#6B776E]">
        {(Object.keys(eventStyle) as CalendarEvent['type'][]).map((kind) => (
          <span key={kind} className="inline-flex items-center gap-1"><span className={`h-1.5 w-1.5 rounded-full ${eventStyle[kind].dot}`} />{eventStyle[kind].label}</span>
        ))}
      </div>

      <div className="mt-3 border-t border-[#DCE5DE] pt-3">
        <h4 className="text-xs font-semibold text-[#18251D]">{selectedLabel}</h4>
        {state === 'error' ? <p role="alert" className="mt-1.5 text-xs text-red-600">Calendar events could not be loaded.</p> : null}
        {state !== 'error' && !selectedEvents.length ? <p className="mt-1.5 text-xs text-[#6B776E]">{state === 'loading' ? 'Loading…' : 'Nothing scheduled.'}</p> : null}
        <ul className="mt-1.5 max-h-36 space-y-1.5 overflow-y-auto">
          {selectedEvents.map((event, index) => {
            const style = eventStyle[event.type]
            const Icon = style.icon
            return (
              <li key={`${event.type}-${event.project_id}-${index}`}>
                <button type="button" onClick={() => onOpenProject?.(event.project_id)} className="flex w-full items-center gap-2 rounded-lg border border-[#DCE5DE] bg-[#F7F9F7] px-2 py-1.5 text-left hover:border-[#245C43]">
                  <span className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md ${style.chip}`}><Icon size={12} /></span>
                  <span className="min-w-0 flex-1 truncate text-xs font-medium text-[#18251D]">{event.title}</span>
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}
