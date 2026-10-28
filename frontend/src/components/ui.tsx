import type { ReactNode } from 'react'
import { severityStyles } from './severity'

export function ModalShell({ title, subtitle, onClose, children, footer, wide = false }: { title: string; subtitle?: string; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0B2B20]/40 p-4 backdrop-blur-[2px]" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
        className={`w-full ${wide ? 'max-w-3xl' : 'max-w-lg'} overflow-hidden rounded-2xl border border-[#DCE5DE] bg-white shadow-2xl`}
      >
        <div className="flex items-start justify-between gap-3 border-b border-[#DCE5DE] px-5 py-4">
          <div className="min-w-0">
            {subtitle ? <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#245C43]">{subtitle}</div> : null}
            <h3 className="mt-1 text-lg font-bold text-[#18251D]">{title}</h3>
          </div>
          <button type="button" aria-label="Close" onClick={onClose} className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[#DCE5DE] text-sm text-[#18251D] hover:bg-[#F7F9F7]">✕</button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer ? <div className="flex justify-end gap-2 border-t border-[#DCE5DE] px-5 py-3">{footer}</div> : null}
      </div>
    </div>
  )
}

export function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-lg bg-[#F7F9F7] p-2">
      <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#6B776E]">{label}</div>
      <div className="mt-0.5 text-sm font-medium text-[#18251D]">{value}</div>
    </div>
  )
}

export function SeverityBadge({ level }: { level?: string | null }) {
  const style = severityStyles[level ?? 'Low'] ?? severityStyles.Low
  return <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${style.badge}`}>{level ?? 'Low'} risk</span>
}
