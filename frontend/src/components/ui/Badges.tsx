import { useTranslation } from 'react-i18next'
// Status badge configuration maps
export const orderStatusMap: Record<string, { label: string; cls: string }> = {
  new: { label: 'ახალი', cls: 'badge-gray' },
  confirmed: { label: 'დამტკიცებული', cls: 'badge-blue' },
  preparing: { label: 'მზადდება', cls: 'badge-yellow' },
  shipping: { label: 'მიწოდებაში', cls: 'badge-cyan' },
  completed: { label: 'დასრულებული', cls: 'badge-green' },
  cancelled: { label: 'გაუქმებული', cls: 'badge-red' },
  returned: { label: 'დაბრუნებული', cls: 'badge-cyan' },
}

export const taskStatusMap: Record<string, { label: string; cls: string }> = {
  todo: { label: 'საჭიროებს', cls: 'badge-gray' },
  in_progress: { label: 'პროცესში', cls: 'badge-blue' },
  done: { label: 'დასრულებული', cls: 'badge-green' },
  cancelled: { label: 'გაუქმებული', cls: 'badge-red' },
}

export const priorityMap: Record<string, { label: string; cls: string }> = {
  low: { label: 'დაბალი', cls: 'badge-gray' },
  medium: { label: 'საშუალო', cls: 'badge-yellow' },
  high: { label: 'მაღალი', cls: 'badge-red' },
}

export const stockStatusMap: Record<string, { label: string; cls: string }> = {
  good: { label: 'კარგი', cls: 'badge-green' },
  low: { label: 'დაბალი', cls: 'badge-yellow' },
  critical: { label: 'კრიტიკული', cls: 'badge-red' },
}

export const purchaseOrderStatusMap: Record<string, { label: string; cls: string }> = {
  draft: { label: 'მონახაზი', cls: 'badge-gray' },
  approved: { label: 'დამტკიცებული', cls: 'badge-blue' },
  partially_received: { label: 'ნაწილობრივ მიღებული', cls: 'badge-yellow' },
  received: { label: 'სრულად მიღებული', cls: 'badge-green' },
  cancelled: { label: 'გაუქმებული', cls: 'badge-red' },
}

export const supplierInvoiceStatusMap: Record<string, { label: string; cls: string }> = {
  draft: { label: 'მონახაზი', cls: 'badge-gray' },
  approved: { label: 'დამტკიცებული', cls: 'badge-green' },
  cancelled: { label: 'გაუქმებული', cls: 'badge-red' },
}

export const invoiceMatchingStatusMap: Record<string, { label: string; cls: string }> = {
  matched: { label: 'შეჯერებულია', cls: 'badge-green' },
  quantity_mismatch: { label: 'რაოდენობა არ ემთხვევა', cls: 'badge-red' },
  amount_mismatch: { label: 'თანხა არ ემთხვევა', cls: 'badge-yellow' },
  unmatched: { label: 'შეუჯერებელი', cls: 'badge-gray' },
}

export const supplierPayableStatusMap: Record<string, { label: string; cls: string }> = {
  unpaid: { label: 'გადასახდელი', cls: 'badge-gray' },
  partially_paid: { label: 'ნაწილობრივ გადახდილი', cls: 'badge-blue' },
  paid: { label: 'გადახდილი', cls: 'badge-green' },
  overdue: { label: 'ვადაგადაცილებული', cls: 'badge-red' },
}

export const clientStatusMap: Record<string, { label: string; cls: string }> = {
  potential: { label: 'პოტენციური', cls: 'badge-gray' },
  active: { label: 'აქტიური', cls: 'badge-green' },
  inactive: { label: 'არააქტიური', cls: 'badge-red' },
}

export function StatusBadge({ status, map }: { status: string; map: Record<string, { label: string; cls: string }> }) {
  const { t } = useTranslation()
  const s = map[status] || { label: status, cls: 'badge-gray' }
  return <span className={`badge ${s.cls}`}>{t(s.label)}</span>
}