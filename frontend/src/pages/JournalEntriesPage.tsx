import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { glApi } from '../services/api'
import type { JournalEntry, JournalEntryLine, JournalEntrySummary } from '../types'

function money(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

const refTypes: Record<string, string> = {
  invoice: 'ინვოისი',
  customer_payment: 'კლიენტის გადახდა',
  customer_payment_reversal: 'გადახდის გაუქმება',
  customer_credit_note: 'Credit Note',
  customer_bank_reconciliation: 'საბანკო შეჯერება',
  customer_bank_reconciliation_reversal: 'შეჯერების გაუქმება',
  supplier_invoice: 'მომწოდებლის ინვოისი',
  supplier_payment: 'მომწოდებლის გადახდა',
  supplier_payment_reversal: 'გადახდის გაუქმება',
  supplier_credit_note: 'Supplier Credit Note',
  supplier_bank_reconciliation: 'საბანკო შეჯერება',
  supplier_bank_reconciliation_reversal: 'შეჯერების გაუქმება',
  test: 'ტესტი',
}

export default function JournalEntriesPage() {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => { setSearch(searchInput); setPage(1) }, 400)
    return () => clearTimeout(timer)
  }, [searchInput])

  const { data, isLoading } = useQuery({
    queryKey: ['gl-journal-entries', search, page],
    queryFn: () => glApi.listJournalEntries({ page, page_size: 20, date_from: search || undefined }).then(r => r.data.data),
  })

  const { data: selected, isLoading: detailLoading } = useQuery({
    queryKey: ['gl-journal-entry', selectedId],
    queryFn: () => glApi.getJournalEntry(selectedId!).then(r => r.data.data),
    enabled: !!selectedId,
  })

  const entries: JournalEntrySummary[] = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.max(1, Math.ceil(total / 20))

  const columns = [
    { key: 'entry_number', label: 'ნომერი', render: (e: JournalEntrySummary) => <span className="font-mono font-semibold text-gray-900 dark:text-gray-100">{e.entry_number}</span> },
    { key: 'entry_date', label: 'თარიღი', render: (e: JournalEntrySummary) => new Date(e.entry_date).toLocaleDateString('ka-GE') },
    { key: 'description', label: 'აღწერა', render: (e: JournalEntrySummary) => <span className="text-gray-900 dark:text-gray-100">{e.description}</span> },
    { key: 'reference_type', label: 'წყარო', render: (e: JournalEntrySummary) => (
      <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">{refTypes[e.reference_type] || e.reference_type}</span>
    )},
    { key: 'is_reversal', label: '', render: (e: JournalEntrySummary) => e.is_reversal
      ? <span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">{t('გაუქმება')}</span>
      : null
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('საჟურნალო ჩანაწერები')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('ორმაგი ჩანაწერის პრინციპით შექმნილი GL ჩანაწერები')}</p>
        </div>
      </div>

      <div className="card">
        <div className="relative max-w-xl">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" size={18} />
          <input value={searchInput} onChange={e => setSearchInput(e.target.value)} className="input pl-10" placeholder={t('თარიღით ძებნა (YYYY-MM-DD)...')} />
        </div>
      </div>

      <DataTable columns={columns} data={entries} isLoading={isLoading} emptyMessage={t('საჟურნალო ჩანაწერები ჯერ არ არის')} onRowClick={e => setSelectedId(e.id)} page={page} totalPages={totalPages} total={total} onPageChange={setPage} />

      <Modal open={!!selectedId} onClose={() => setSelectedId(null)} title={selected ? `ჩანაწერი ${selected.entry_number}` : ''}>
        {detailLoading ? <p className="text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</p> : selected && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="text-gray-500 dark:text-gray-400">{t('თარიღი:')}</span> <span className="font-medium">{new Date(selected.entry_date).toLocaleDateString('ka-GE')}</span></div>
              <div><span className="text-gray-500 dark:text-gray-400">{t('წყარო:')}</span> <span className="font-medium">{refTypes[selected.reference_type] || selected.reference_type}</span></div>
              <div className="col-span-2"><span className="text-gray-500 dark:text-gray-400">{t('აღწერა:')}</span> <span className="font-medium">{selected.description}</span></div>
              {selected.is_reversal && <div className="col-span-2"><span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">{t('გაუქმების ჩანაწერი')}</span></div>}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-dark-50 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    <th className="py-2 pr-4">{t('ანგარიში')}</th>
                    <th className="py-2 pr-4 text-right">{t('დებეტი')}</th>
                    <th className="py-2 pr-4 text-right">{t('კრედიტი')}</th>
                    <th className="py-2">{t('აღწერა')}</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.lines.map((line: JournalEntryLine) => (
                    <tr key={line.id} className="border-b border-gray-100 dark:border-dark-50">
                      <td className="py-2 pr-4 font-mono text-gray-900 dark:text-gray-100">{line.gl_account_id.slice(0, 8)}...</td>
                      <td className="py-2 pr-4 text-right font-mono text-green-700">{line.debit_amount > 0 ? money(line.debit_amount) : ''}</td>
                      <td className="py-2 pr-4 text-right font-mono text-red-700">{line.credit_amount > 0 ? money(line.credit_amount) : ''}</td>
                      <td className="py-2 text-gray-600 dark:text-gray-400">{line.description || ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
