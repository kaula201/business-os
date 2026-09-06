import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, Building2, Pencil, Plus, Search, ShieldAlert, GitBranch, Landmark, Coins, ClipboardCheck } from 'lucide-react'

import ConfirmDialog from '../components/ui/ConfirmDialog'
import DataTable from '../components/ui/DataTable'
import FormField from '../components/ui/FormField'
import Modal from '../components/ui/Modal'
import { suppliersApi } from '../services/api'
import type { Supplier, SupplierCreate } from '../types'

const emptySupplier: SupplierCreate = {
  code: '',
  name: '',
  identification_code: '',
  is_vat_payer: false,
  contact_name: '',
  phone: '',
  email: '',
  address: '',
  bank_account: '',
  payment_terms_days: 0,
  notes: '',
}

export default function SuppliersPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [page, setPage] = useState(1)
  const [showInactive, setShowInactive] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Supplier | null>(null)
  const [archiveTarget, setArchiveTarget] = useState<Supplier | null>(null)
  const [form, setForm] = useState<SupplierCreate>(emptySupplier)
  const [formError, setFormError] = useState('')
  // Supplier 2.0
  const [advFor, setAdvFor] = useState<Supplier | null>(null)
  const [advData, setAdvData] = useState<any>(null)
  const [advError, setAdvError] = useState('')
  const [riskForm, setRiskForm] = useState({ risk_level: 'low', risk_score: '', is_blacklisted: false, blacklist_reason: '' })
  const [curForm, setCurForm] = useState({ currency: 'GEL', payment_terms_days: '0', exchange_rate_policy: 'daily', fixed_rate: '', is_default: false })

  // Debounce: search იგზავნება server-ზე მხოლოდ აკრეფის შეწყვეტის შემდეგ
  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput); setPage(1) }, 400)
    return () => clearTimeout(t)
  }, [searchInput])

  const { data, isLoading } = useQuery({
    queryKey: ['suppliers', search, showInactive, page],
    queryFn: () => suppliersApi.list({ search: search || undefined, include_inactive: showInactive, page, page_size: 20 }).then((r) => r.data.data),
  })

  const suppliers: Supplier[] = data?.items || []
  const suppliersTotal = data?.total || 0
  const suppliersTotalPages = Math.max(1, Math.ceil(suppliersTotal / 20))

  const saveMutation = useMutation({
    mutationFn: () => editing
      ? suppliersApi.update(editing.id, form)
      : suppliersApi.create(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] })
      closeModal()
    },
    onError: (error: any) => setFormError(error.response?.data?.detail || t('მომწოდებლის შენახვა ვერ მოხერხდა')),
  })

  const archiveMutation = useMutation({
    mutationFn: (id: string) => suppliersApi.archive(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] })
      setArchiveTarget(null)
    },
    onError: (error: any) => {
      setFormError(error.response?.data?.detail || t('მომწოდებლის დეაქტივაცია ვერ მოხერხდა'))
      setArchiveTarget(null)
    },
  })

  // Supplier 2.0 mutations
  const riskMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: any }) => suppliersApi.setRisk(id, payload),
    onSuccess: () => { loadAdv(advFor); queryClient.invalidateQueries({ queryKey: ['suppliers'] }) },
    onError: (e: any) => setAdvError(e.response?.data?.detail || 'რისკის განახლება ვერ მოხერხდა'),
  })
  const curMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: any }) => suppliersApi.upsertCurrencyTerm(id, payload),
    onSuccess: () => { loadAdv(advFor); setCurForm({ currency: 'GEL', payment_terms_days: '0', exchange_rate_policy: 'daily', fixed_rate: '', is_default: false }) },
    onError: (e: any) => setAdvError(e.response?.data?.detail || 'ვალუტის პირობები ვერ შეინახა'),
  })
  const onboardingMutation = useMutation({
    mutationFn: (id: string) => suppliersApi.startOnboarding(id),
    onSuccess: () => loadAdv(advFor),
    onError: (e: any) => setAdvError(e.response?.data?.detail || 'Onboarding ვერ დაიწყო'),
  })
  const stepMutation = useMutation({
    mutationFn: ({ id, stepId }: { id: string; stepId: string }) => suppliersApi.completeOnboardingStep(id, stepId),
    onSuccess: () => loadAdv(advFor),
    onError: (e: any) => setAdvError(e.response?.data?.detail || 'Onboarding step ვერ დასრულდა'),
  })
  const bankApproveMutation = useMutation({
    mutationFn: (bankId: string) => suppliersApi.approveBankDetail(bankId),
    onSuccess: () => loadAdv(advFor),
    onError: (e: any) => setAdvError(e.response?.data?.detail || 'საბანკო ანგარიში ვერ დამტკიცდა'),
  })

  async function loadAdv(supplier: Supplier | null) {
    if (!supplier) return
    setAdvError('')
    try {
      const [onb, risk, cur] = await Promise.all([
        suppliersApi.getOnboarding(supplier.id).then((r: any) => r.data.data),
        suppliersApi.listRiskEvents(supplier.id).then((r: any) => r.data.data),
        suppliersApi.listCurrencyTerms(supplier.id).then((r: any) => r.data.data),
      ])
      setAdvData({ onboarding: onb, riskEvents: risk, currencyTerms: cur })
    } catch (e: any) {
      setAdvError(e.response?.data?.detail || 'მონაცემების ჩატვირთვა ვერ მოხერხდა')
    }
  }

  function openCreate() {
    setEditing(null)
    setForm({ ...emptySupplier })
    setFormError('')
    setModalOpen(true)
  }

  function openEdit(supplier: Supplier) {
    setEditing(supplier)
    setForm({
      code: supplier.code,
      name: supplier.name,
      identification_code: supplier.identification_code || '',
      is_vat_payer: supplier.is_vat_payer,
      contact_name: supplier.contact_name || '',
      phone: supplier.phone || '',
      email: supplier.email || '',
      address: supplier.address || '',
      bank_account: supplier.bank_account || '',
      payment_terms_days: supplier.payment_terms_days,
      notes: supplier.notes || '',
    })
    setFormError('')
    setModalOpen(true)
  }

  function closeModal() {
    setModalOpen(false)
    setEditing(null)
    setForm({ ...emptySupplier })
    setFormError('')
  }

  function submit(event: React.FormEvent) {
    event.preventDefault()
    setFormError('')
    saveMutation.mutate()
  }

  const columns = [
    {
      key: 'name', label: 'მომწოდებელი', render: (supplier: Supplier) => (
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <Building2 size={18} />
          </div>
          <div>
            <p className="font-medium text-gray-900 dark:text-gray-100">{supplier.name}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">{supplier.code}</p>
          </div>
        </div>
      ),
    },
    { key: 'identification_code', label: 'საიდენტიფიკაციო', render: (supplier: Supplier) => supplier.identification_code || '—' },
    { key: 'contact', label: 'კონტაქტი', hideOnMobile: true, render: (supplier: Supplier) => (
      <div><p>{supplier.contact_name || '—'}</p><p className="text-xs text-gray-500 dark:text-gray-400">{supplier.phone || supplier.email || ''}</p></div>
    ) },
    { key: 'terms', label: 'გადახდის ვადა', hideOnMobile: true, render: (supplier: Supplier) => `${supplier.payment_terms_days} დღე` },
    { key: 'status', label: 'სტატუსი', render: (supplier: Supplier) => (
      <span className={`badge ${supplier.is_active ? 'badge-green' : 'badge-gray'}`}>{supplier.is_active ? t('აქტიური') : t('არააქტიური')}</span>
    ) },
    { key: 'actions', label: '', render: (supplier: Supplier) => (
      <div className="flex justify-end gap-1">
        <button className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-100 text-gray-500 dark:text-gray-400" title={t('მოწინავე მართვა')} onClick={(e) => { e.stopPropagation(); setAdvFor(supplier); setAdvData(null); setAdvError(''); loadAdv(supplier) }}>
          <GitBranch size={18} />
        </button>
        <button className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 text-gray-500 dark:text-gray-400" title={t('რედაქტირება')} onClick={(e) => { e.stopPropagation(); openEdit(supplier) }}>
          <Pencil size={18} />
        </button>
        {supplier.is_active && (
          <button className="p-2 rounded-lg hover:bg-red-50 text-red-500" title={t('დეაქტივაცია')} onClick={(e) => { e.stopPropagation(); setArchiveTarget(supplier) }}>
            <Archive size={16} />
          </button>
        )}
      </div>
    ) },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('მომწოდებლები')}</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{t('შესყიდვების პარტნიორები და გადახდის პირობები')}</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={openCreate}><Plus size={18} /> {t('ახალი მომწოდებელი')}</button>
      </div>

      {formError && !modalOpen && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{formError}</div>}

      <div className="card flex flex-col sm:flex-row gap-3 items-center">
        <div className="relative flex-1 w-full">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <input className="input pl-10" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder={t('სახელი, კოდი ან საიდენტიფიკაციო ნომერი')} />
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} /> {t('არააქტიურების ჩვენება')}
        </label>
      </div>

      <DataTable columns={columns} data={suppliers} isLoading={isLoading} emptyMessage={t('მომწოდებელი ჯერ არ არის დამატებული')} page={page} totalPages={suppliersTotalPages} total={suppliersTotal} onPageChange={setPage} />

      <Modal open={modalOpen} onClose={closeModal} title={editing ? t('მომწოდებლის რედაქტირება') : t('ახალი მომწოდებელი')} size="lg">
        <form onSubmit={submit} className="space-y-5">
          {formError && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{formError}</div>}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FormField label={t('კოდი')} required><input className="input" required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></FormField>
            <FormField label={t('დასახელება')} required><input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></FormField>
            <FormField label={t('საიდენტიფიკაციო კოდი')}><input className="input" value={form.identification_code || ''} onChange={(e) => setForm({ ...form, identification_code: e.target.value })} /></FormField>
            <FormField label={t('გადახდის ვადა (დღე)')}><input type="number" min="0" className="input" value={form.payment_terms_days || 0} onChange={(e) => setForm({ ...form, payment_terms_days: Number(e.target.value) })} /></FormField>
            <FormField label={t('საკონტაქტო პირი')}><input className="input" value={form.contact_name || ''} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} /></FormField>
            <FormField label={t('ტელეფონი')}><input className="input" value={form.phone || ''} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></FormField>
            <FormField label={t('ელფოსტა')}><input type="email" className="input" value={form.email || ''} onChange={(e) => setForm({ ...form, email: e.target.value })} /></FormField>
            <FormField label={t('საბანკო ანგარიში')}><input className="input" value={form.bank_account || ''} onChange={(e) => setForm({ ...form, bank_account: e.target.value })} /></FormField>
          </div>
          <FormField label={t('მისამართი')}><input className="input" value={form.address || ''} onChange={(e) => setForm({ ...form, address: e.target.value })} /></FormField>
          <FormField label={t('შენიშვნა')}><textarea className="input min-h-20" value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></FormField>
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300"><input type="checkbox" checked={form.is_vat_payer || false} onChange={(e) => setForm({ ...form, is_vat_payer: e.target.checked })} /> {t('დღგ-ის გადამხდელი')}</label>
          <div className="flex justify-end gap-3 pt-4 border-t"><button type="button" className="btn-secondary" onClick={closeModal}>{t('გაუქმება')}</button><button className="btn-primary" disabled={saveMutation.isPending}>{saveMutation.isPending ? t('ინახება...') : t('შენახვა')}</button></div>
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(archiveTarget)}
        onClose={() => setArchiveTarget(null)}
        onConfirm={() => archiveTarget && archiveMutation.mutate(archiveTarget.id)}
        title={t('მომწოდებლის დეაქტივაცია')}
        message={`${archiveTarget?.name || ''} აღარ გამოჩნდება ახალი შესყიდვის შეკვეთის შექმნისას. ისტორია შენარჩუნდება.`}
        confirmLabel="დეაქტივაცია"
        loading={archiveMutation.isPending}
      />

      {/* Supplier 2.0 advanced management modal */}
      <Modal open={Boolean(advFor)} onClose={() => setAdvFor(null)} title={`${advFor?.name || ''} — ${t('მოწინავე მართვა')}`} size="xl">
        {advFor && (
          <div className="space-y-5">
            {advError && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{advError}</div>}

            {/* Risk / blacklist */}
            <div className="rounded-xl border border-brandgray-200 dark:border-dark-50 p-4">
              <h3 className="font-semibold flex items-center gap-2 mb-3"><ShieldAlert size={17} /> {t('რისკი / Blacklist')}</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t('რისკის დონე')}</label>
                  <select className="input" value={riskForm.risk_level} onChange={e => setRiskForm({ ...riskForm, risk_level: e.target.value })}>
                    <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t('ქულა (0-100)')}</label>
                  <input type="number" min="0" max="100" className="input" value={riskForm.risk_score} onChange={e => setRiskForm({ ...riskForm, risk_score: e.target.value })} />
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2 text-sm pb-2">
                    <input type="checkbox" checked={riskForm.is_blacklisted} onChange={e => setRiskForm({ ...riskForm, is_blacklisted: e.target.checked })} /> {t('Blacklist')}
                  </label>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t('მიზეზი')}</label>
                  <input className="input" value={riskForm.blacklist_reason} onChange={e => setRiskForm({ ...riskForm, blacklist_reason: e.target.value })} />
                </div>
              </div>
              <button className="btn-primary text-sm mt-3" disabled={riskMutation.isPending}
                onClick={() => riskMutation.mutate({ id: advFor.id, payload: { risk_level: riskForm.risk_level, risk_score: riskForm.risk_score ? Number(riskForm.risk_score) : undefined, is_blacklisted: riskForm.is_blacklisted, blacklist_reason: riskForm.blacklist_reason || undefined } })}>
                {t('შენახვა')}
              </button>
              {advData?.riskEvents?.length > 0 && (
                <div className="mt-3 space-y-1">
                  {advData.riskEvents.map((e: any) => (
                    <div key={e.id} className="flex justify-between text-xs p-2 bg-gray-50 dark:bg-dark-100 rounded-lg">
                      <span className="font-medium">{e.event_type}</span><span>{e.risk_level || ''} {e.description ? `— ${e.description}` : ''}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Multi-currency terms */}
            <div className="rounded-xl border border-brandgray-200 dark:border-dark-50 p-4">
              <h3 className="font-semibold flex items-center gap-2 mb-3"><Coins size={17} /> {t('მრავალვალუტიანი პირობები')}</h3>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t('ვალუტა')}</label>
                  <select className="input" value={curForm.currency} onChange={e => setCurForm({ ...curForm, currency: e.target.value })}>
                    <option value="GEL">GEL</option><option value="USD">USD</option><option value="EUR">EUR</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t('გადახდის დღეები')}</label>
                  <input type="number" min="0" className="input" value={curForm.payment_terms_days} onChange={e => setCurForm({ ...curForm, payment_terms_days: e.target.value })} />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t('კურსის პოლიტიკა')}</label>
                  <select className="input" value={curForm.exchange_rate_policy} onChange={e => setCurForm({ ...curForm, exchange_rate_policy: e.target.value })}>
                    <option value="daily">Daily</option><option value="fixed">Fixed</option><option value="invoice">Invoice</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t('ფიქსირებული კურსი')}</label>
                  <input type="number" step="0.000001" className="input" value={curForm.fixed_rate} onChange={e => setCurForm({ ...curForm, fixed_rate: e.target.value })} />
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2 text-sm pb-2">
                    <input type="checkbox" checked={curForm.is_default} onChange={e => setCurForm({ ...curForm, is_default: e.target.checked })} /> {t('დეფოლტი')}
                  </label>
                </div>
              </div>
              <button className="btn-primary text-sm mt-3" disabled={curMutation.isPending}
                onClick={() => curMutation.mutate({ id: advFor.id, payload: { currency: curForm.currency, payment_terms_days: Number(curForm.payment_terms_days), exchange_rate_policy: curForm.exchange_rate_policy, fixed_rate: curForm.fixed_rate ? Number(curForm.fixed_rate) : undefined, is_default: curForm.is_default } })}>
                {t('პირობების დამატება')}
              </button>
              {advData?.currencyTerms?.length > 0 && (
                <div className="mt-3 space-y-1">
                  {advData.currencyTerms.map((c: any) => (
                    <div key={c.id} className="flex justify-between text-sm p-2 bg-gray-50 dark:bg-dark-100 rounded-lg">
                      <span className="font-semibold">{c.currency} {c.is_default ? '(default)' : ''}</span>
                      <span>{c.payment_terms_days} დღე — {c.exchange_rate_policy}{c.fixed_rate ? ` @ ${c.fixed_rate}` : ''}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Onboarding workflow */}
            <div className="rounded-xl border border-brandgray-200 dark:border-dark-50 p-4">
              <h3 className="font-semibold flex items-center gap-2 mb-3"><ClipboardCheck size={17} /> {t('Onboarding workflow')} <span className="badge badge-blue">{advData?.onboarding?.onboarding_status || advFor.onboarding_status || 'pending'}</span></h3>
              {!advData?.onboarding?.steps?.length ? (
                <button className="btn-secondary text-sm" onClick={() => onboardingMutation.mutate(advFor.id)}>{t('Onboarding-ის დაწყება')}</button>
              ) : (
                <div className="space-y-2">
                  {advData.onboarding.steps.map((s: any) => (
                    <div key={s.id} className="flex items-center justify-between p-2 border-b dark:border-dark-50">
                      <span className="text-sm">{s.step_name}</span>
                      <div className="flex items-center gap-2">
                        <span className={`badge ${s.status === 'done' ? 'badge-green' : 'badge-gray'}`}>{s.status}</span>
                        {s.status !== 'done' && (
                          <button className="text-xs font-medium text-primary-600 hover:text-primary-700" onClick={() => stepMutation.mutate({ id: advFor.id, stepId: s.id })}>
                            {t('დასრულება')}
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Bank approval */}
            <div className="rounded-xl border border-brandgray-200 dark:border-dark-50 p-4">
              <h3 className="font-semibold flex items-center gap-2 mb-3"><Landmark size={17} /> {t('საბანკო ანგარიშები')}</h3>
              {advFor.bank_details?.length ? advFor.bank_details.map((b: any) => (
                <div key={b.id} className="flex items-center justify-between p-2 border-b dark:border-dark-50">
                  <div>
                    <p className="text-sm font-medium">{b.bank_name} — {b.iban_masked}</p>
                    <p className="text-xs text-gray-500">{b.currency} {b.is_primary ? '· primary' : ''}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`badge ${b.approval_status === 'approved' ? 'badge-green' : 'badge-amber'}`}>{b.approval_status}</span>
                    {b.approval_status !== 'approved' && (
                      <button className="text-xs font-medium text-emerald-600 hover:text-emerald-700" onClick={() => bankApproveMutation.mutate(b.id)}>
                        {t('დამტკიცება')}
                      </button>
                    )}
                  </div>
                </div>
              )) : <p className="text-sm text-gray-500">{t('საბანკო ანგარიში არ არის')}</p>}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
