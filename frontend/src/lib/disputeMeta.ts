import type { DisputeStatus } from '@/types'

/**
 * Shared presentation metadata for dispute statuses.
 * Kept in a plain module (not a page component file) so React Fast Refresh
 * stays happy and other pages can import it without a page→page dependency.
 */
export const disputeStatusMeta: Record<DisputeStatus, { color: string; label: string }> = {
  open: { color: 'blue', label: 'Обсуждение' },
  in_mediation: { color: 'gold', label: 'Арбитраж' },
  resolved: { color: 'green', label: 'Решён' },
  cancelled: { color: 'default', label: 'Отменён' },
}
