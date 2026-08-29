import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../store/authStore'
import { api, purchaseApprovalApi, usersApi, companyApi } from '../services/api'
import { Settings, Shield, UserPlus, Mail, User, Clock, SlidersHorizontal, Plug, Search } from 'lucide-react'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import type { User as UserType } from '../types'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

export default function SettingsPage() {
  const { t } = useTranslation()
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'company' | 'users' | 'account' | 'purchasing' | 'integrations'>('account')
  const [inviteModal, setInviteModal] = useState(false)
  const [inviteForm, setInviteForm] = useState({ email: '', full_name: '', role: 'employee' })
  const [managerApprovalLimit, setManagerApprovalLimit] = useState(5000)
  const [approvalMessage, setApprovalMessage] = useState('')
  const [companyForm, setCompanyForm] = useState({ name: '', address: '', phone: '', email: '', website: '', is_vat_payer: true, currency: 'GEL' })
  const [companyMessage, setCompanyMessage] = useState('')
  const [pwForm, setPwForm] = useState({ current_password: '', new_password: '', confirm: '' })
  const [pwMessage, setPwMessage] = useState('')
  const [pwLoading, setPwLoading] = useState(false)
  const [waybillNumber, setWaybillNumber] = useState('')
  const [waybillResult, setWaybillResult] = useState<any>(null)
  const [integrationError, setIntegrationError] = useState('')

  const { data: usersData } = useQuery({
    queryKey: ['users-settings'],
    queryFn: () => usersApi.list({ page_size: 100 }).then(r => r.data.data),
    enabled: user?.role === 'admin',
  })
  const { data: approvalPolicy } = useQuery({
    queryKey: ['purchase-approval-policy'],
    queryFn: () => purchaseApprovalApi.get().then(r => r.data.data),
    enabled: user?.role === 'admin',
  })
  const { data: rsStatus, isLoading: rsStatusLoading, refetch: refetchRsStatus } = useQuery({
    queryKey: ['rs-status'],
    queryFn: () => api.get('/integrations/rs/status').then(r => r.data.data),
    enabled: activeTab === 'integrations' && ['admin', 'accountant'].includes(user?.role || ''),
    retry: false,
  })

  const waybillMutation = useMutation({
    mutationFn: () => api.get(`/integrations/rs/waybills/${encodeURIComponent(waybillNumber)}`),
    onSuccess: (response) => { setWaybillResult(response.data.data); setIntegrationError('') },
    onError: (error: any) => { setWaybillResult(null); setIntegrationError(error?.response?.data?.detail || t('ზედნადების მიღება ვერ მოხერხდა')) },
  })

  useEffect(() => {
    if (approvalPolicy) setManagerApprovalLimit(approvalPolicy.manager_approval_limit)
  }, [approvalPolicy])

  const { data: companyData } = useQuery({
    queryKey: ['my-company'],
    queryFn: () => companyApi.getMyCompany().then(r => r.data.data),
  })

  useEffect(() => {
    if (companyData) {
      setCompanyForm({
        name: companyData.name || '',
        address: companyData.address || '',
        phone: companyData.phone || '',
        email: companyData.email || '',
        website: companyData.website || '',
        is_vat_payer: companyData.is_vat_payer !== false,
        currency: companyData.currency || 'GEL',
      })
    }
  }, [companyData])

  const companyMutation = useMutation({
    mutationFn: () => companyApi.updateMyCompany(companyForm),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-company'] })
      setCompanyMessage('კომპანიის ინფორმაცია შენახულია.')
    },
    onError: (error: any) => setCompanyMessage(error?.response?.data?.detail || t('შენახვა ვერ მოხერხდა')),
  })

  const approvalMutation = useMutation({
    mutationFn: () => purchaseApprovalApi.update(managerApprovalLimit),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-approval-policy'] })
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] })
      queryClient.invalidateQueries({ queryKey: ['purchase-order'] })
      setApprovalMessage('Approval ზღვარი შენახულია.')
    },
    onError: (error: any) => setApprovalMessage(error.response?.data?.detail || t('Approval ზღვრის შენახვა ვერ მოხერხდა.')),
  })

  const users: UserType[] = usersData?.items || []

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await usersApi.invite(inviteForm)
      queryClient.invalidateQueries({ queryKey: ['users-settings'] })
      setInviteModal(false)
      setInviteForm({ email: '', full_name: '', role: 'employee' })
    } catch (err: any) {
      alert(err?.response?.data?.detail || t('მოწვევა ვერ შესრულდა'))
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('პარამეტრები')}</h1>

      <div className="flex gap-2">
        {[
          { id: 'account', label: t('ჩემი ანგარიში'), icon: User },
          { id: 'company', label: t('კომპანია'), icon: Settings },
          ...(user?.role === 'admin' ? [{ id: 'users', label: t('მომხმარებლები'), icon: Shield }] : []),
          ...(user?.role === 'admin' ? [{ id: 'purchasing', label: t('შესყიდვების approval'), icon: SlidersHorizontal }] : []),
          ...(['admin', 'accountant'].includes(user?.role || '') ? [{ id: 'integrations', label: t('ინტეგრაციები'), icon: Plug }] : []),
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab.id ? 'bg-primary-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200 dark:bg-dark-200 dark:text-gray-400 dark:border-dark-50 dark:hover:bg-dark-100 dark:hover:text-gray-200'
            }`}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'account' && (
        <div className="card">
          <h3 className="font-semibold text-gray-900 mb-6 dark:text-gray-100">{t('ჩემი ანგარიში')}</h3>
          <div className="space-y-4">
            <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg dark:bg-dark-100">
              <div className="w-12 h-12 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-xl font-bold dark:bg-primary-900/50 dark:text-primary-300">
                {user?.full_name?.charAt(0) || '?'}
              </div>
              <div>
                <p className="font-medium text-gray-900 dark:text-gray-100">{user?.full_name}</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">{user?.email}</p>
              </div>
              <span className="ml-auto badge badge-blue">{user?.role}</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-3 border border-gray-200 rounded-lg dark:border-dark-50">
                <p className="text-xs text-gray-500 dark:text-gray-400">{t('ელფოსტა')}</p>
                <p className="font-medium dark:text-gray-200">{user?.email}</p>
              </div>
              <div className="p-3 border border-gray-200 rounded-lg dark:border-dark-50">
                <p className="text-xs text-gray-500 dark:text-gray-400">{t('როლი')}</p>
                <p className="font-medium dark:text-gray-200">{user?.role}</p>
              </div>
              <div className="p-3 border border-gray-200 rounded-lg dark:border-dark-50">
                <p className="text-xs text-gray-500 dark:text-gray-400">{t('სტატუსი')}</p>
                <p className="font-medium dark:text-gray-200">{user?.is_active ? t('აქტიური') : t('არააქტიური')}</p>
              </div>
              <div className="p-3 border border-gray-200 rounded-lg dark:border-dark-50">
                <p className="text-xs text-gray-500 dark:text-gray-400">{t('ბოლო შესვლა')}</p>
                <p className="font-medium dark:text-gray-200">—</p>
              </div>
            </div>

            {/* Password Change */}
            <div className="border-t border-gray-200 pt-6 mt-6 dark:border-dark-50">
              <h4 className="font-medium text-gray-900 mb-4 dark:text-gray-100">{t('პაროლის შეცვლა')}</h4>
              <form onSubmit={async (e) => {
                e.preventDefault()
                if (pwForm.new_password !== pwForm.confirm) {
                  setPwMessage('ახალი პაროლები არ ემთხვევა')
                  return
                }
                setPwLoading(true)
                setPwMessage('')
                try {
                  await usersApi.changePassword({
                    current_password: pwForm.current_password,
                    new_password: pwForm.new_password,
                  })
                  setPwMessage('პაროლი წარმატებით შეიცვალა')
                  setPwForm({ current_password: '', new_password: '', confirm: '' })
                } catch (err: any) {
                  setPwMessage(err?.response?.data?.detail || t('შეცდომა'))
                } finally {
                  setPwLoading(false)
                }
              }} className="max-w-sm space-y-3">
                <FormField label={t('მიმდინარე პაროლი')}>
                  <input type="password" value={pwForm.current_password} onChange={(e) => setPwForm({ ...pwForm, current_password: e.target.value })} className="input" required />
                </FormField>
                <FormField label={t('ახალი პაროლი')}>
                  <input type="password" value={pwForm.new_password} onChange={(e) => setPwForm({ ...pwForm, new_password: e.target.value })} className="input" minLength={8} required />
                </FormField>
                <FormField label={t('გაიმეორეთ ახალი პაროლი')}>
                  <input type="password" value={pwForm.confirm} onChange={(e) => setPwForm({ ...pwForm, confirm: e.target.value })} className="input" minLength={8} required />
                </FormField>
                {pwMessage && <p className={`text-sm ${pwMessage.includes('წარმატებით') ? 'text-green-600' : 'text-red-600'}`}>{pwMessage}</p>}
                <button type="submit" className="btn-primary" disabled={pwLoading}>
                  {pwLoading ? t('ინახება...') : t('პაროლის შეცვლა')}
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'company' && (
        <div className="card">
          <h3 className="font-semibold text-gray-900 mb-6 dark:text-gray-100">{t('კომპანიის ინფორმაცია')}</h3>
          <form onSubmit={(e) => { e.preventDefault(); setCompanyMessage(''); companyMutation.mutate() }} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField label={t('კომპანიის სახელი')} required>
                <input type="text" value={companyForm.name} onChange={(e) => setCompanyForm({ ...companyForm, name: e.target.value })} className="input" required />
              </FormField>
              <FormField label={t('ვალუტა')}>
                <input type="text" value={companyForm.currency} onChange={(e) => setCompanyForm({ ...companyForm, currency: e.target.value.toUpperCase() })} className="input" maxLength={3} placeholder="GEL" />
              </FormField>
              <FormField label={t('ტელეფონი')}>
                <input type="tel" value={companyForm.phone} onChange={(e) => setCompanyForm({ ...companyForm, phone: e.target.value })} className="input" placeholder="+995 32 XXX XX XX" />
              </FormField>
              <FormField label={t('ელფოსტა')}>
                <input type="email" value={companyForm.email} onChange={(e) => setCompanyForm({ ...companyForm, email: e.target.value })} className="input" placeholder="info@company.ge" />
              </FormField>
              <FormField label={t('ვებსაიტი')}>
                <input type="url" value={companyForm.website} onChange={(e) => setCompanyForm({ ...companyForm, website: e.target.value })} className="input" placeholder="https://company.ge" />
              </FormField>
              <FormField label={t('დღგ-ს გადამხდელი')}>
                <label className="flex items-center gap-2 mt-2">
                  <input type="checkbox" checked={companyForm.is_vat_payer} onChange={(e) => setCompanyForm({ ...companyForm, is_vat_payer: e.target.checked })} className="rounded" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">{t('დიახ')}</span>
                </label>
              </FormField>
              <div className="md:col-span-2">
                <FormField label={t('მისამართი')}>
                  <input type="text" value={companyForm.address} onChange={(e) => setCompanyForm({ ...companyForm, address: e.target.value })} className="input" placeholder={t('თბილისი, საქართველო')} />
                </FormField>
              </div>
            </div>
            {companyMessage && <p className={`rounded-lg p-3 text-sm ${companyMessage.includes('შენახულია') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>{companyMessage}</p>}
            <div className="flex justify-end border-t border-gray-200 pt-4 dark:border-dark-50">
              <button type="submit" className="btn-primary" disabled={companyMutation.isPending}>
                {companyMutation.isPending ? t('ინახება...') : t('შენახვა')}
              </button>
            </div>
          </form>
        </div>
      )}

      {activeTab === 'purchasing' && user?.role === 'admin' && (
        <div className="card">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-purple-50 p-3 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300"><SlidersHorizontal size={22} /></div>
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('შესყიდვის შეკვეთების დამტკიცება')}</h3>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('განსაზღვრეთ თანხა, რომლის ჩათვლითაც შესყიდვის შეკვეთის დამტკიცება მენეჯერს შეუძლია.')}</p>
            </div>
          </div>
          <form onSubmit={(event) => { event.preventDefault(); setApprovalMessage(''); approvalMutation.mutate() }} className="mt-6 space-y-5">
            <div className="max-w-sm">
              <FormField label={t('Manager approval-ის მაქსიმალური თანხა')} required>
                <div className="relative">
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={managerApprovalLimit}
                    onChange={(event) => setManagerApprovalLimit(Number(event.target.value))}
                    className="input pr-12"
                    required
                  />
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm font-medium text-gray-500 dark:text-gray-400">GEL</span>
                </div>
              </FormField>
            </div>
            <div className="rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm text-blue-800">
              <p><strong>{managerApprovalLimit.toLocaleString('ka-GE')} GEL-მდე:</strong> {t('მენეჯერი ან ადმინისტრატორი.')}</p>
              <p className="mt-1"><strong>{managerApprovalLimit.toLocaleString('ka-GE')} GEL-ზე მეტი:</strong> {t('მხოლოდ ადმინისტრატორი.')}</p>
              <p className="mt-1">{t('თანამშრომელსა და ბუღალტერს შესყიდვის შეკვეთის დამტკიცება არ შეუძლიათ.')}</p>
            </div>
            {approvalMessage && <p className={`rounded-lg p-3 text-sm ${approvalMessage.includes('შენახულია') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>{approvalMessage}</p>}
            <div className="flex justify-end border-t border-gray-200 pt-4 dark:border-dark-50">
              <button type="submit" className="btn-primary" disabled={approvalMutation.isPending}>
                {approvalMutation.isPending ? t('ინახება...') : t('Approval ზღვრის შენახვა')}
              </button>
            </div>
          </form>
        </div>
      )}

      {activeTab === 'integrations' && ['admin', 'accountant'].includes(user?.role || '') && (
        <div className="card space-y-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-blue-50 p-3 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"><Plug size={22} /></div>
              <div><h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('RS.ge — სასაქონლო ზედნადებები')}</h3><p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('Revenue Service-ის ოფიციალური WayBill SOAP სერვისი')}</p></div>
            </div>
            <button className="btn-secondary" onClick={() => refetchRsStatus()} disabled={rsStatusLoading}>{rsStatusLoading ? t('მოწმდება...') : t('კავშირის შემოწმება')}</button>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-gray-200 p-4 dark:border-dark-50"><p className="text-xs text-gray-500 dark:text-gray-400">{t('სერვერი')}</p><p className={`mt-1 font-semibold ${rsStatus?.reachable ? 'text-green-600' : 'text-red-600'}`}>{rsStatusLoading ? 'მოწმდება...' : rsStatus?.reachable ? t('ხელმისაწვდომია') : t('მიუწვდომელია')}</p></div>
            <div className="rounded-lg border border-gray-200 p-4 dark:border-dark-50"><p className="text-xs text-gray-500 dark:text-gray-400">{t('რეკვიზიტები')}</p><p className={`mt-1 font-semibold ${rsStatus?.configured ? 'text-green-600' : 'text-amber-600'}`}>{rsStatus?.configured ? t('დაყენებულია') : t('არ არის დაყენებული')}</p></div>
            <div className="rounded-lg border border-gray-200 p-4 dark:border-dark-50"><p className="text-xs text-gray-500 dark:text-gray-400">{t('ავტორიზაცია')}</p><p className={`mt-1 font-semibold ${rsStatus?.authenticated ? 'text-green-600' : 'text-gray-500'}`}>{rsStatus?.authenticated ? t('წარმატებულია') : t('არ შემოწმებულა')}</p></div>
          </div>

          {!rsStatus?.configured && <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-200">{t('Backend environment-ში დაამატეთ')} <code>RS_SERVICE_USER</code> {t('და')} <code>RS_SERVICE_PASSWORD</code>{t('. მნიშვნელობები UI-ში არ ინახება.')}</div>}
          {rsStatus?.server_time && <p className="text-xs text-gray-500 dark:text-gray-400">RS.ge სერვერის დრო: {rsStatus.server_time}</p>}

          <div className="border-t border-gray-200 pt-5 dark:border-dark-50">
            <h4 className="font-medium text-gray-900 dark:text-gray-100">{t('ზედნადების მოძებნა ნომრით')}</h4>
            <div className="mt-3 flex max-w-xl gap-2"><input className="input" value={waybillNumber} onChange={(e) => setWaybillNumber(e.target.value)} placeholder={t('ზედნადების ნომერი')}/><button className="btn-primary flex items-center gap-2" disabled={!rsStatus?.configured || !waybillNumber.trim() || waybillMutation.isPending} onClick={() => waybillMutation.mutate()}><Search size={16}/>{waybillMutation.isPending ? t('იძებნება...') : t('მოძებნა')}</button></div>
            {integrationError && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{integrationError}</p>}
            {waybillResult && <pre className="mt-4 max-h-96 overflow-auto rounded-lg bg-gray-950 p-4 text-xs text-green-300">{JSON.stringify(waybillResult.data, null, 2)}</pre>}
          </div>
        </div>
      )}

      {activeTab === 'users' && (
        <div className="card">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('მომხმარებლები')}</h3>
            <button onClick={() => setInviteModal(true)} className="btn-primary flex items-center gap-2 text-sm">
              <UserPlus size={16} /> {t('მოწვევა')}
            </button>
          </div>

          <div className="space-y-2">
            {users.map((u: UserType) => (
              <div key={u.id} className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 border border-gray-100 dark:border-dark-50 dark:hover:bg-dark-100">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-sm font-bold">
                    {u.full_name?.charAt(0) || '?'}
                  </div>
                  <div>
                    <p className="font-medium text-sm text-gray-900 dark:text-gray-100">{u.full_name}</p>
                    <p className="text-xs text-gray-500 flex items-center gap-1 dark:text-gray-400"><Mail size={11} /> {u.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="badge badge-blue text-xs">{u.role}</span>
                  {!u.is_active && <span className="badge badge-red text-xs">{t('დეაქტივირებული')}</span>}
                  <span className="text-xs text-gray-400 flex items-center gap-1 dark:text-gray-500"><Clock size={11} /> {fmtDate(new Date(u.created_at))}</span>
                </div>
              </div>
            ))}
            {users.length === 0 && <p className="text-sm text-gray-400 text-center py-8 dark:text-gray-500">{t('მომხმარებლები არ მოიძებნა')}</p>}
          </div>
        </div>
      )}

      <Modal open={inviteModal} onClose={() => setInviteModal(false)} title={t('მომხმარებლის მოწვევა')} size="md">
        <form onSubmit={handleInvite} className="space-y-4">
          <FormField label={t('სახელი')} required>
            <input type="text" value={inviteForm.full_name} onChange={(e) => setInviteForm({ ...inviteForm, full_name: e.target.value })} className="input" required />
          </FormField>
          <FormField label={t('ელფოსტა')} required>
            <input type="email" value={inviteForm.email} onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })} className="input" required />
          </FormField>
          <FormField label={t('როლი')}>
            <Select value={inviteForm.role} onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value })} options={[
              { value: 'admin', label: t('ადმინისტრატორი') },
              { value: 'manager', label: t('მენეჯერი') },
              { value: 'employee', label: t('თანამშრომელი') },
              { value: 'accountant', label: t('ბუღალტერი') },
            ]} />
          </FormField>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-dark-50">
            <button type="button" onClick={() => setInviteModal(false)} className="btn-secondary">{t('გაუქმება')}</button>
            <button type="submit" className="btn-primary">{t('მოწვევა')}</button>
          </div>
        </form>
      </Modal>
    </div>
  )
}