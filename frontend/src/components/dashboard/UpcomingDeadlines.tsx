import { useEffect, useRef, useState } from 'react'
import { CalendarClock, ChevronLeft, ChevronRight } from 'lucide-react'
import type { DashboardData } from '../../types'

type Deadline = DashboardData['upcoming_deadlines'][number]

export const DEADLINES_PER_PAGE = 10 // one page holds 10; the 11th deadline starts page 2
export const DEADLINES_VISIBLE = 5 // five rows are visible at once, the other five need a scroll
const ROW_HEIGHT = 44
const ROW_GAP = 8
const WINDOW_HEIGHT = DEADLINES_VISIBLE * ROW_HEIGHT + (DEADLINES_VISIBLE - 1) * ROW_GAP

function daysUntil(deadline: string) {
  const target = new Date(`${deadline}T00:00:00`)
  if (Number.isNaN(target.getTime())) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - today.getTime()) / 86_400_000)
}

function dueLabel(deadline: string) {
  const days = daysUntil(deadline)
  if (days === null) return ''
  if (days <= 0) return 'Due today'
  if (days === 1) return 'Tomorrow'
  return `In ${days} days`
}

// Everything lives inside this one window: the list (5 rows visible, scroll for the rest of the page) and the paging.
export function UpcomingDeadlines({ items, loading, onOpenProject }: { items: Deadline[]; loading: boolean; onOpenProject: (projectId: number) => void }) {
  const [page, setPage] = useState(0)
  const listRef = useRef<HTMLUListElement | null>(null)

  const pageCount = Math.max(1, Math.ceil(items.length / DEADLINES_PER_PAGE))
  const current = Math.min(page, pageCount - 1)
  const start = current * DEADLINES_PER_PAGE
  const visible = items.slice(start, start + DEADLINES_PER_PAGE)

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = 0
  }, [current])

  return (
    <section aria-label="Upcoming deadlines" className="flex h-full min-w-0 flex-col rounded-2xl border border-[#DCE5DE] bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-[#EAF2EC] text-[#123D2B]"><CalendarClock size={15} /></span>
          <h3 className="text-base font-semibold text-[#18251D]">Upcoming Deadlines</h3>
        </div>
        {items.length ? <span className="rounded-full bg-[#F1F5F2] px-2 py-0.5 text-xs font-semibold text-[#245C43]">{items.length}</span> : null}
      </div>

      {loading ? (
        <div role="status" aria-label="Loading deadlines" className="animate-pulse rounded-xl bg-[#F1F5F2]" style={{ height: WINDOW_HEIGHT }} />
      ) : !items.length ? (
        <div className="flex items-center justify-center rounded-xl border border-dashed border-[#DCE5DE] bg-[#F7F9F7] p-4 text-sm text-[#6B776E]" style={{ height: WINDOW_HEIGHT }}>
          No upcoming deadlines.
        </div>
      ) : (
        <ul
          ref={listRef}
          aria-label="Upcoming deadlines list"
          className="mb-3 space-y-2 overflow-y-auto pr-1"
          style={{ maxHeight: WINDOW_HEIGHT }}
        >
          {visible.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onOpenProject(item.id)}
                className="flex w-full items-center justify-between gap-3 rounded-lg border border-[#DCE5DE] bg-[#F7F9F7] px-3 text-left transition hover:border-[#245C43] hover:bg-white"
                style={{ height: ROW_HEIGHT }}
              >
                <span className="min-w-0 truncate text-sm font-medium text-[#18251D]">{item.name}</span>
                <span className="flex shrink-0 flex-col items-end leading-tight">
                  <span className="text-xs font-semibold text-[#245C43]">{item.deadline}</span>
                  <span className="text-[10px] text-[#6B776E]">{dueLabel(item.deadline)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {!loading && items.length > 0 ? (
        <div className="mt-auto flex items-center justify-between gap-2 border-t border-[#DCE5DE] pt-3 text-xs text-[#6B776E]">
          <span aria-live="polite">Page {current + 1} of {pageCount}</span>
          {pageCount > 1 ? (
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                aria-label="Previous page"
                disabled={current === 0}
                onClick={() => setPage(current - 1)}
                className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[#DCE5DE] hover:bg-[#F7F9F7] disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronLeft size={14} />
              </button>
              <button
                type="button"
                aria-label="Next page"
                disabled={current >= pageCount - 1}
                onClick={() => setPage(current + 1)}
                className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[#DCE5DE] hover:bg-[#F7F9F7] disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
