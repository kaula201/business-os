import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Trash2 } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { glApi } from '../services/api'
import type { JournalEntry, JournalEntryLine, JournalEntrySummary } from '../types'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

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
  manual: 'ხელით ჩანაწერი',
  recurring: 'განმეორებადი',
  exchange_difference: 'საკურსო სხვაობა',
  test: 'ტესტი',
}

interface DraftLine {
  key: string
  account_id: string
  debit: string
  credit: string
  note: string
}

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function JournalEntriesPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState({ entry_date: new Date().toISOString().slice(0, 10), description: '' })
  const [lines, setLines] = useState<DraftLine[]>([
    { key: crypto.randomUUID(), account_id: '', debit: '', credit: '', note: '' },
    { key: crypto.randomUUID(), account_id: '', debit: '', credit: '', note: '' },
  ])
  const [error, setError] = useState<string | null>(null)

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

  const { data: accounts } = useQuery({
    queryKey: ['gl-accounts-all-je'],
    queryFn: () => glApi.listAccounts({ page_size: 100 }).then(r => r.data.data.items),
  })

  const entries: JournalEntrySummary[] = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.max(1, Math.ceil(total / 20))

  const create = useMutation({
    mutationFn: () => glApi.createJournalEntry({
      entry_date: form.entry_date,
      description: form.description,
      lines: lines.map(l => ({
        gl_account_id: l.account_id,
        debit_amount: l.debit ? Number(l.debit) : 0,
        credit_amount: l.credit ? Number(l.credit) : 0,
        description: l.note || undefined,
      })),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gl-journal-entries'] })
      setCreateOpen(false)
      setError(null)
      setForm({ entry_date: new Date().toISOString().slice(0, 10), description: '' })
      setLines([
        { key: crypto.randomUUID(), account_id: '', debit: '', credit: '', note: '' },
        { key: crypto.randomUUID(), account_id: '', debit: '', credit: '', note: '' },
      ])
    },
    onError: (e: any) => setError(e?.response?.data?.detail || t('შეცდომა ჩანაწერის შექმნისას')),
  })

  const updateLine = (key: string, patch: Partial<DraftLine>) => {
    setLines(prev => prev.map(l => l.key === key ? { ...l, ...patch } : l))
  }

  const addLine = () => setLines(prev => [...prev, { key: crypto.randomUUID(), account_id: '', debit: '', credit: '', note: '' }])
  const removeLine = (key: string) => setLines(prev => prev.length > 2 ? prev.filter(l => l.key !== key) : prev)

  const totalDebit = lines.reduce((s, l) => s + (Number(l.debit) || 0), 0)
  const totalCredit = lines.reduce((s, l) => s + (Number(l.credit) || 0), 0)
  const balanced = Math.abs(totalDebit - totalCredit) < 0.005

  const columns = [
    { key: 'entry_number', label: 'ნომერი', render: (e: JournalEntrySummary) => <span className="font-mono font-semibold text-gray-900 dark:text-gray-100">{e.entry_number}</span> },
    { key: 'entry_date', label: 'თარიღი', render: (e: JournalEntrySummary) => fmtDate(new Date(e.entry_date)) },
    { key: 'description', label: 'აღწერა', render: (e: JournalEntrySummary) => <span className="text-gray-900 dark:text-gray-100">{e.description}</span> },
    { key: 'reference_type', label: 'წყარო', render: (e: JournalEntrySummary) => (
      <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">{t(refTypes[e.reference_type] || e.reference_type)}</span>
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
        <button onClick={() => setCreateOpen(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
          <Plus size={15} /> {t('ახალი ხელით ჩანაწერი')}
        </button>
      </div>

      <div className="card">
        <div className="relative max-w-xl">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" size={18} />
          <input value={searchInput} onChange={e => setSearchInput(e.target.value)} className="input pl-10" placeholder={t('თარიღით ძებნა (YYYY-MM-DD)...')} />
        </div>
      </div>

      <DataTable columns={columns} data={entries} isLoading={isLoading} emptyMessage={t('საჟურნალო ჩანაწერები ჯერ არ არის')} onRowClick={e => setSelectedId(e.id)} page={page} totalPages={totalPages} total={total} onPageChange={setPage} />

      {/* Detail modal */}
      <Modal open={!!selectedId} onClose={() => setSelectedId(null)} title={selected ? `ჩანაწერი ${selected.entry_number}` : ''}>
        {detailLoading ? <p className="text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</p> : selected && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="text-gray-500 dark:text-gray-400">{t('თარიღი:')}</span> <span className="font-medium">{fmtDate(new Date(selected.entry_date))}</span></div>
              <div><span className="text-gray-500 dark:text-gray-400">{t('წყარო:')}</span> <span className="font-medium">{t(refTypes[selected.reference_type] || selected.reference_type)}</span></div>
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

      {/* Create manual entry modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title={t('ახალი ხელით ჩანაწერი')}>
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('თარიღი')}</label>
              <input type="date" className={inputCls} value={form.entry_date} onChange={e => setForm({ ...form, entry_date: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('აღწერა')}</label>
              <input className={inputCls} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder={t('მაგ: ბანკის საკომისიო')} />
            </div>
          </div>

          <div className="space-y-2">
            <div className="grid grid-cols-[1fr_120px_120px_1fr_32px] gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              <span>{t('ანგარიში')}</span><span className="text-right">{t('დებეტი')}</span><span className="text-right">{t('კრედიტი')}</span><span>{t('აღწერა')}</span><span />
            </div>
            {lines.map(l => (
              <div key={l.key} className="grid grid-cols-[1fr_120px_120px_1fr_32px] gap-2 items-center">
                <select className={inputCls} value={l.account_id} onChange={e => updateLine(l.key, { account_id: e.target.value })}>
                  <option value="">—</option>
                  {(accounts || []).map((a: any) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
                </select>
                <input type="number" step="0.01" min="0" className={inputCls + ' text-right'} value={l.debit} onChange={e => updateLine(l.key, { debit: e.target.value })} placeholder="0.00" />
                <input type="number" step="0.01" min="0" className={inputCls + ' text-right'} value={l.credit} onChange={e => updateLine(l.key, { credit: e.target.value })} placeholder="0.00" />
                <input className={inputCls} value={l.note} onChange={e => updateLine(l.key, { note: e.target.value })} placeholder={t('კომენტარი')} />
                <button onClick={() => removeLine(l.key)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30" title={t('წაშლა')}>
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
            <button onClick={addLine} className="text-sm text-primary-700 hover:text-primary-800 font-medium dark:text-primary-400">
              + {t('სტრიქონის დამატება')}
            </button>
          </div>

          <div className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium ${balanced ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300' : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-300'}`}>
            <span>{balanced ? t('ბალანსი იყრის თავს') : t('ბალანსი არ იყრის თავს')}</span>
            <span className="font-mono">{money(totalDebit)} = {money(totalCredit)}</span>
          </div>

          {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}

          <button onClick={() => create.mutate()} disabled={create.isPending || !balanced || !form.description || lines.some(l => !l.account_id || (!l.debit && !l.credit))}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {create.isPending ? '…' : t('ჩაწერა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
