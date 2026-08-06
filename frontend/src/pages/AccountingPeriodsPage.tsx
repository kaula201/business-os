import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarRange, ChevronLeft, ChevronRight, History, LockKeyhole, ShieldCheck, Unlock } from 'lucide-react'
import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { api } from '../services/api'
import { useAuthStore } from '../store/authStore'

interface AccountingPeriod {
  id: string
  year: number
  month: number
  start_date: string
  end_date: string
  status: 'open' | 'closed'
  close_reason: string | null
  closed_at: string | null
  reopened_at: string | null
}

interface PeriodEvent {
  id: string
  action: 'closed' | 'reopened'
  reason: string
  created_at: string
}

const months = [
  'იანვარი', 'თებერვალი', 'მარტი', 'აპრილი', 'მაისი', 'ივნისი',
  'ივლისი', 'აგვისტო', 'სექტემბერი', 'ოქტომბერი', 'ნოემბერი', 'დეკემბერი',
]
const errorText = (error: any) => error?.response?.data?.detail || 'ოპერაცია ვერ შესრულდა'
const formatDateTime = (value: string | null) => value
  ? new Intl.DateTimeFormat('ka-GE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
  : '—'

type ActionState = { type: 'close' | 'reopen'; month: number } | null

export default function AccountingPeriodsPage() {
  const { t } = useTranslation()
  const currentYear = new Date().getFullYear()
  const [year, setYear] = useState(currentYear)
  const [action, setAction] = useState<ActionState>(null)
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [historyPeriod, setHistoryPeriod] = useState<AccountingPeriod | null>(null)
  const user = useAuthStore((state) => state.user)
  const queryClient = useQueryClient()

  const periodsQuery = useQuery({
    queryKey: ['accounting-periods', year],
    queryFn: () => api.get(`/accounting-periods?year=${year}`).then((response) => response.data.data as AccountingPeriod[]),
  })
  const periods = periodsQuery.data || []
  const periodByMonth = useMemo(
    () => new Map(periods.map((period) => [period.month, period])),
    [periods],
  )
  const closedCount = periods.filter((period) => period.status === 'closed').length

  const historyQuery = useQuery({
    queryKey: ['accounting-period-history', historyPeriod?.id],
    queryFn: () => api.get(`/accounting-periods/${historyPeriod!.id}/history`).then((response) => response.data.data as PeriodEvent[]),
    enabled: Boolean(historyPeriod),
  })

  const periodMutation = useMutation({
    mutationFn: ({ type, month, reason }: { type: 'close' | 'reopen'; month: number; reason: string }) =>
      api.post(`/accounting-periods/${year}/${month}/${type}`, { reason }),
    onSuccess: () => {
      setAction(null)
      setReason('')
      setError('')
      queryClient.invalidateQueries({ queryKey: ['accounting-periods', year] })
    },
    onError: (mutationError) => setError(errorText(mutationError)),
  })

  const openAction = (type: 'close' | 'reopen', month: number) => {
    setAction({ type, month })
    setReason('')
    setError('')
  }
  const submitAction = () => {
    if (!action || reason.trim().length < 3) return
    periodMutation.mutate({ ...action, reason: reason.trim() })
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-brandgray-900 dark:text-gray-100">
            <CalendarRange className="text-primary-600 dark:text-primary-400" />
            {t('სააღრიცხვო პერიოდები')}
          </h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">
            {t('დახურეთ დასრულებული თვეები და დაიცავით ფინანსური მონაცემები შემდგომი ცვლილებებისგან')}
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-xl border border-brandgray-200 bg-white p-1 shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <button className="rounded-lg p-2 hover:bg-brandgray-50 dark:hover:bg-dark-100" onClick={() => setYear((value) => value - 1)} aria-label={t('წინა წელი')}><ChevronLeft size={18} /></button>
          <span className="min-w-20 text-center text-lg font-semibold">{year}</span>
          <button className="rounded-lg p-2 hover:bg-brandgray-50 dark:hover:bg-dark-100" onClick={() => setYear((value) => value + 1)} aria-label={t('შემდეგი წელი')}><ChevronRight size={18} /></button>
        </div>
      </header>

      <section className="grid gap-4 sm:grid-cols-3">
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50"><p className="text-sm text-brandgray-500 dark:text-gray-400">{t('წელი')}</p><p className="mt-1 text-2xl font-semibold">{year}</p></div>
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50"><p className="text-sm text-brandgray-500 dark:text-gray-400">{t('დახურული თვე')}</p><p className="mt-1 text-2xl font-semibold text-amber-700 dark:text-amber-300">{closedCount}</p></div>
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50"><p className="text-sm text-brandgray-500 dark:text-gray-400">{t('ღია თვე')}</p><p className="mt-1 text-2xl font-semibold text-emerald-700 dark:text-emerald-300">{12 - closedCount}</p></div>
      </section>

      {periodsQuery.isLoading ? (
        <div className="card p-10 text-center text-brandgray-500 dark:bg-dark-200 dark:text-gray-400">{t('პერიოდები იტვირთება...')}</div>
      ) : (
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {months.map((monthName, index) => {
            const month = index + 1
            const period = periodByMonth.get(month)
            const isClosed = period?.status === 'closed'
            return (
              <article key={month} className={`card overflow-hidden p-0 dark:bg-dark-200 dark:border-dark-50 ${isClosed ? 'ring-1 ring-amber-300/60 dark:ring-amber-700/50' : ''}`}>
                <div className="flex items-start justify-between gap-3 p-5">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wider text-brandgray-400">{year}-{String(month).padStart(2, '0')}</p>
                    <h2 className="mt-1 text-lg font-semibold text-brandgray-900 dark:text-gray-100">{monthName}</h2>
                  </div>
                  <span className={`badge ${isClosed ? 'badge-yellow' : 'badge-green'}`}>{isClosed ? 'დახურული' : 'ღია'}</span>
                </div>
                <div className="min-h-20 border-y border-brandgray-100 bg-brandgray-50/50 px-5 py-3 text-sm dark:border-dark-50 dark:bg-dark-300/40">
                  {isClosed ? <><p className="line-clamp-2 text-brandgray-700 dark:text-gray-300">{period?.close_reason}</p><p className="mt-1 text-xs text-brandgray-400">{formatDateTime(period?.closed_at || null)}</p></> : <p className="text-brandgray-500 dark:text-gray-400">{t('ფინანსური ოპერაციები ნებადართულია')}</p>}
                </div>
                <div className="flex items-center justify-between gap-2 p-4">
                  {period && <button className="btn-secondary flex items-center gap-1.5 px-3 py-1.5 text-xs" onClick={() => setHistoryPeriod(period)}><History size={14} />{t('ისტორია')}</button>}
                  <div className="ml-auto">
                    {isClosed && user?.role === 'admin' ? (
                      <button className="btn-secondary flex items-center gap-1.5 px-3 py-1.5 text-xs" onClick={() => openAction('reopen', month)}><Unlock size={14} />{t('გახსნა')}</button>
                    ) : !isClosed ? (
                      <button className="btn-primary flex items-center gap-1.5 px-3 py-1.5 text-xs" onClick={() => openAction('close', month)}><LockKeyhole size={14} />{t('დახურვა')}</button>
                    ) : null}
                  </div>
                </div>
              </article>
            )
          })}
        </section>
      )}

      <div className="flex items-start gap-3 rounded-xl border border-primary-200 bg-primary-50 p-4 text-sm text-primary-900 dark:border-primary-800/60 dark:bg-primary-900/20 dark:text-primary-200">
        <ShieldCheck className="mt-0.5 shrink-0" size={19} />
        <p>{t('დახურულ პერიოდში იბლოკება GL posting, სალაროს ოპერაციები, ხარჯები, ძირითადი საშუალებები, ანალიტიკური ჩანაწერები და საბანკო statement import.')}</p>
      </div>

      <Modal open={Boolean(action)} onClose={() => setAction(null)} title={action?.type === 'close' ? `${months[(action?.month || 1) - 1]} — პერიოდის დახურვა` : `${months[(action?.month || 1) - 1]} — პერიოდის გახსნა`}>
        <div className="space-y-4">
          <p className="text-sm text-brandgray-600 dark:text-gray-300">
            {action?.type === 'close' ? 'დახურვის შემდეგ ამ თვის ფინანსური ცვლილებები დაიბლოკება.' : 'ხელახლა გახსნის შემდეგ ამ თვის ფინანსური ცვლილებები კვლავ შესაძლებელი იქნება.'}
          </p>
          <FormField label={t('მიზეზი')} required><textarea className="input" rows={4} value={reason} onChange={(event) => setReason(event.target.value)} placeholder={t('მიუთითეთ მოქმედების მიზეზი')} /></FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setAction(null)}>{t('გაუქმება')}</button><button className="btn-primary" disabled={reason.trim().length < 3 || periodMutation.isPending} onClick={submitAction}>{periodMutation.isPending ? 'მუშავდება...' : action?.type === 'close' ? 'პერიოდის დახურვა' : 'პერიოდის გახსნა'}</button></div>
        </div>
      </Modal>

      <Modal open={Boolean(historyPeriod)} onClose={() => setHistoryPeriod(null)} title={`${historyPeriod ? months[historyPeriod.month - 1] : ''} — ცვლილებების ისტორია`}>
        <div className="space-y-3">
          {historyQuery.isLoading && <p className="text-sm text-brandgray-500">{t('ისტორია იტვირთება...')}</p>}
          {(historyQuery.data || []).map((event) => (
            <div key={event.id} className="rounded-xl border border-brandgray-200 p-4 dark:border-dark-50">
              <div className="flex items-center justify-between gap-3"><span className={`badge ${event.action === 'closed' ? 'badge-yellow' : 'badge-green'}`}>{event.action === 'closed' ? 'დაიხურა' : 'გაიხსნა'}</span><span className="text-xs text-brandgray-400">{formatDateTime(event.created_at)}</span></div>
              <p className="mt-2 text-sm text-brandgray-700 dark:text-gray-300">{event.reason}</p>
            </div>
          ))}
          {!historyQuery.isLoading && !historyQuery.data?.length && <p className="text-sm text-brandgray-500">{t('ცვლილებების ისტორია არ არის.')}</p>}
        </div>
      </Modal>
    </div>
  )
}
