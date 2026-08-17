import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck, History, GitBranch, KeyRound, Copy, Eye, Plus, Trash2 } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { securityApi, fieldAccessApi } from '../services/api'

const tabs = [
  { id: '2fa', label: '2FA', icon: ShieldCheck },
  { id: 'history', label: 'შესვლის ისტორია', icon: History },
  { id: 'steps', label: 'Approval Steps', icon: GitBranch },
  { id: 'fields', label: 'Field Access', icon: Eye },
]

export default function SecurityPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState('2fa')
  const [secret, setSecret] = useState('')
  const [error, setError] = useState('')

  const { data: twoFa } = useQuery({ queryKey: ['sec-2fa'], queryFn: () => securityApi.twoFaStatus().then(r => r.data.data) })
  const { data: history } = useQuery({ queryKey: ['sec-history'], queryFn: () => securityApi.loginHistory().then(r => r.data.data) })
  const { data: fieldRules } = useQuery({ queryKey: ['sec-fields'], queryFn: () => fieldAccessApi.list().then(r => r.data.data) })

  const [fieldForm, setFieldForm] = useState({ module: 'clients', role: 'employee', field: '', can_view: true, can_edit: false })
  const [fieldOpen, setFieldOpen] = useState(false)

  const createFieldRule = useMutation({
    mutationFn: () => fieldAccessApi.create(fieldForm),
    onSuccess: () => { setFieldOpen(false); setFieldForm({ module: 'clients', role: 'employee', field: '', can_view: true, can_edit: false }); qc.invalidateQueries({ queryKey: ['sec-fields'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const removeFieldRule = useMutation({
    mutationFn: (id: string) => fieldAccessApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sec-fields'] }),
  })

  const setup2fa = useMutation({
    mutationFn: () => securityApi.twoFaSetup(),
    onSuccess: (r: any) => { setSecret(r.data.data.secret); qc.invalidateQueries({ queryKey: ['sec-2fa'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const disable2fa = useMutation({
    mutationFn: () => securityApi.twoFaDisable(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sec-2fa'] }),
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('უსაფრთხოება')}</h1>
        <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('2FA, შესვლის ისტორია, მრავალსაფეხურიანი approvals')}</p>
      </div>

      <div className="flex gap-1 border-b border-brandgray-100 dark:border-dark-50">
        {tabs.map(tabItem => (
          <button key={tabItem.id} onClick={() => setTab(tabItem.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === tabItem.id ? 'border-primary-600 text-primary-700 dark:border-primary-400 dark:text-primary-300' : 'border-transparent text-brandgray-500 hover:text-brandgray-700 dark:text-gray-400'
            }`}>
            <tabItem.icon size={18} /> {t(tabItem.label)}
          </button>
        ))}
      </div>

      {tab === '2fa' && (
        <div className="max-w-xl rounded-xl border bg-white p-6 shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="flex items-center gap-3">
            <KeyRound className="text-primary-600" size={28} />
            <div>
              <h3 className="font-semibold text-brandgray-900 dark:text-gray-100">{t('ორფაქტორიანი ავთენტიფიკაცია')}</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">{t('TOTP — Google Authenticator / Authy')}</p>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-3">
            <span className={`rounded-full px-3 py-1 text-xs font-medium ${twoFa?.enabled ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
              {twoFa?.enabled ? t('ჩართულია') : t('გამორთულია')}
            </span>
            {twoFa?.enabled ? (
              <button onClick={() => disable2fa.mutate()} className="btn btn-secondary text-sm">{t('გამორთვა')}</button>
            ) : (
              <button onClick={() => setup2fa.mutate()} className="btn btn-primary text-sm">{t('ჩართვა')}</button>
            )}
          </div>
          {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
        </div>
      )}

      {tab === 'history' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('IP მისამართი')}</th>
                  <th className="px-4 py-3">{t('მოწყობილობა')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3">{t('თარიღი')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(history || []).length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('ისტორია ცარიელია')}</td></tr>
                ) : (history || []).map((h: any) => (
                  <tr key={h.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono text-xs text-gray-700 dark:text-gray-300">{h.ip_address || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{h.user_agent ? h.user_agent.slice(0, 50) : '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${h.success ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400'}`}>
                        {h.success ? t('წარმატებული') : t('წარუმატებელი')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{new Date(h.created_at).toLocaleString('ka-GE')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'steps' && (
        <div className="rounded-xl border bg-white p-6 shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <h3 className="font-semibold text-brandgray-900 dark:text-gray-100 mb-2">{t('მრავალსაფეხურიანი approvals')}</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            {t('Approval Steps განყოფილება Approvals მოდულშია — აქ ნახავთ ლოგიკას: ყველა step-ის დამტკიცების შემდეგ request დამტკიცდება, ნებისმიერი უარყოფა — უარყოფს მთლიანად.')}
          </p>
          <div className="flex items-center gap-2 rounded-lg bg-gray-50 dark:bg-dark-100 p-3 text-sm text-gray-600 dark:text-gray-400">
            <GitBranch size={16} />
            <span>manager → admin → approved</span>
          </div>
        </div>
      )}

      {tab === 'fields' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500 dark:text-gray-400">{t('ველების დონის წვდომა — რომელ როლს რომელი ველი უჩანს')}</p>
            <button onClick={() => setFieldOpen(true)} className="btn btn-primary flex items-center gap-2 text-sm">
              <Plus size={16} /> {t('ახალი წესი')}
            </button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                  <tr>
                    <th className="px-4 py-3">{t('მოდული')}</th>
                    <th className="px-4 py-3">{t('როლი')}</th>
                    <th className="px-4 py-3">{t('ველი')}</th>
                    <th className="px-4 py-3">{t('ნახვა')}</th>
                    <th className="px-4 py-3">{t('რედაქტირება')}</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y dark:divide-dark-50">
                  {(fieldRules || []).length === 0 ? (
                    <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('წესები არ არის')}</td></tr>
                  ) : (fieldRules || []).map((r: any) => (
                    <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                      <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{r.module}</td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.role}</td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.field}</td>
                      <td className="px-4 py-3">{r.can_view ? '✓' : '—'}</td>
                      <td className="px-4 py-3">{r.can_edit ? '✓' : '—'}</td>
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => removeFieldRule.mutate(r.id)} className="text-red-500 hover:text-red-700"><Trash2 size={18} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Field access create modal */}
      <Modal open={fieldOpen} onClose={() => setFieldOpen(false)} title={t('ახალი წესი')}>
        <div className="space-y-4">
          <FormField label={t('მოდული')}>
            <select value={fieldForm.module} onChange={e => setFieldForm({ ...fieldForm, module: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="clients">clients</option>
              <option value="orders">orders</option>
              <option value="invoices">invoices</option>
              <option value="inventory">inventory</option>
              <option value="hr">hr</option>
            </select>
          </FormField>
          <FormField label={t('როლი')}>
            <select value={fieldForm.role} onChange={e => setFieldForm({ ...fieldForm, role: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="admin">admin</option>
              <option value="manager">manager</option>
              <option value="employee">employee</option>
              <option value="accountant">accountant</option>
            </select>
          </FormField>
          <FormField label={t('ველი')} required>
            <input value={fieldForm.field} onChange={e => setFieldForm({ ...fieldForm, field: e.target.value })}
              placeholder="credit_limit" className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
              <input type="checkbox" checked={fieldForm.can_view} onChange={e => setFieldForm({ ...fieldForm, can_view: e.target.checked })} /> {t('ნახვა')}
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
              <input type="checkbox" checked={fieldForm.can_edit} onChange={e => setFieldForm({ ...fieldForm, can_edit: e.target.checked })} /> {t('რედაქტირება')}
            </label>
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createFieldRule.mutate()} disabled={!fieldForm.field || createFieldRule.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შექმნა')}
          </button>
        </div>
      </Modal>

      {/* 2FA secret modal */}
      <Modal open={!!secret} onClose={() => setSecret('')} title={t('2FA ჩართულია')}>
        <div className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">{t('დაამატეთ ეს secret თქვენს Authenticator აპში:')}</p>
          <div className="flex items-center gap-2 rounded-lg border border-gray-200 dark:border-dark-50 p-3">
            <code className="flex-1 break-all text-xs font-mono text-gray-800 dark:text-gray-200">{secret}</code>
            <button onClick={() => { navigator.clipboard?.writeText(secret); setSecret('') }} className="text-primary-600 hover:text-primary-700"><Copy size={16} /></button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
