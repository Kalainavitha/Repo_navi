import type { Risk, RiskSeverity } from '../types'

export const severityStyles: Record<string, { badge: string; dot: string }> = {
  High: { badge: 'bg-red-100 text-red-700', dot: 'bg-red-500' },
  Medium: { badge: 'bg-amber-100 text-amber-800', dot: 'bg-amber-500' },
  Low: { badge: 'bg-[#EAF2EC] text-[#245C43]', dot: 'bg-[#367653]' },
}

const order: Record<RiskSeverity, number> = { High: 0, Medium: 1, Low: 2 }

// Older saved plans stored risks as plain strings; show them as medium-severity notes.
export function normalizeRisks(raw: unknown): Risk[] {
  if (!Array.isArray(raw)) return []
  return raw
    .map((item): Risk | null => {
      if (typeof item === 'string') return { type: 'note', severity: 'Medium', message: item }
      if (item && typeof item === 'object' && 'message' in item) return item as Risk
      return null
    })
    .filter((item): item is Risk => item !== null)
    .sort((a, b) => order[a.severity] - order[b.severity])
}
