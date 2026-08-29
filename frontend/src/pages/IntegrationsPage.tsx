import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Key, Webhook as WebhookIcon, Globe, Plus, Trash2, Copy, RefreshCw, ShieldCheck } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { apiKeysApi, integrationsApi } from '../services/api'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

const tabs = [
  { id: 'keys', label: 'API Keys', icon: Key },
  { id: 'webhooks', label: 'Webhooks', icon: WebhookIcon },
  { id: 'rs', label: 'RS.ge / Sandbox', icon: Globe },
  { id: 'counterparties', label: 'კონტრაგენტები', icon: ShieldCheck },
]

export default function IntegrationsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState('keys')
  const [error, setError] = useState('')
  const [newKey, setNewKey] = useState('')
  const [keyForm, setKeyForm] = useState({ name: '', scopes: 'read', allowed_ips: '', rate_limit_per_minute: 120, expires_at: '' })
  const [keyOpen, setKeyOpen] = useState(false)
  const [hookForm, setHookForm] = useState({ name: '', url: '', events: 'invoice.created', retry_max: 3, retry_backoff_seconds: 60 })
  const [hookOpen, setHookOpen] = useState(false)

  const { data: keys } = useQuery({ queryKey: ['int-keys'], queryFn: () => integrationsApi.apiKeys().then(r => r.data.data) })
  const { data: hooks } = useQuery({ queryKey: ['int-hooks'], queryFn: () => integrationsApi.webhooks().then(r => r.data.data) })
  const { data: rsStatus } = useQuery({ queryKey: ['int-rs'], queryFn: () => integrationsApi.rsStatus().then(r => r.data.data) })
  const { data: checks } = useQuery({ queryKey: ['int-counterparties'], queryFn: () => integrationsApi.counterpartyChecks().then(r => r.data.data) })
  const [codeInput, setCodeInput] = useState('')
  const [verifyResult, setVerifyResult] = useState<any>(null)
  const verify = useMutation({
    mutationFn: () => integrationsApi.verifyCounterparty({ identification_code: codeInput.trim() }),
    onSuccess: (r: any) => {
      setVerifyResult(r.data.data)
      qc.invalidateQueries({ queryKey: ['int-counterparties'] })
    },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  const createKey = useMutation({
    mutationFn: () => integrationsApi.createApiKey({
      ...keyForm,
      allowed_ips: keyForm.allowed_ips ? keyForm.allowed_ips.split(',').map((s: string) => s.trim()).filter(Boolean) : undefined,
      expires_at: keyForm.expires_at ? new Date(keyForm.expires_at).toISOString() : undefined,
    }),
    onSuccess: (r: any) => { setNewKey(r.data.data.key); setKeyOpen(false); setKeyForm({ name: '', scopes: 'read', allowed_ips: '', rate_limit_per_minute: 120, expires_at: '' }); qc.invalidateQueries({ queryKey: ['int-keys'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const removeKey = useMutation({
    mutationFn: (id: string) => integrationsApi.removeApiKey(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['int-keys'] }),
  })
  const createHook = useMutation({
    mutationFn: () => integrationsApi.createWebhook(hookForm),
    onSuccess: () => { setHookOpen(false); setHookForm({ name: '', url: '', events: 'invoice.created', retry_max: 3, retry_backoff_seconds: 60 }); qc.invalidateQueries({ queryKey: ['int-hooks'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const removeHook = useMutation({
    mutationFn: (id: string) => integrationsApi.removeWebhook(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['int-hooks'] }),
  })

  const copy = (v: string) => { navigator.clipboard?.writeText(v); setNewKey('') }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('ინტეგრაციები')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('API Keys, Webhooks, RS.ge')}</p>
        </div>
        <button onClick={() => { setNewKey(''); tab === 'keys' ? setKeyOpen(true) : setHookOpen(true) }} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {tab === 'keys' ? t('ახალი API Key') : t('ახალი Webhook')}
        </button>
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

      {tab === 'keys' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('პრეფიქსი')}</th>
                  <th className="px-4 py-3">{t('უფლებები')}</th>
                  <th className="px-4 py-3">{t('აქტიური')}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(keys || []).length === 0 ? (
                  <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('API Keys არ არის')}</td></tr>
                ) : (keys || []).map((k: any) => (
                  <tr key={k.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{k.name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-600 dark:text-gray-400">{k.key_prefix}...</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{k.scopes}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{k.expires_at ? fmtDate(new Date(k.expires_at)) : '—'}</td>
                    <td className="px-4 py-3">{k.is_active ? '✓' : '—'}</td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <button onClick={() => apiKeysApi.rotate(k.id).then(r => {
                        alert(`${t('ახალი გასაღები')}: ${r.data.data.key}`)
                        qc.invalidateQueries({ queryKey: ['int-keys'] })
                      })} className="text-amber-500 hover:text-amber-700 mr-2" title={t('როტაცია')}><RefreshCw size={16} /></button>
                      <button onClick={() => removeKey.mutate(k.id)} className="text-red-500 hover:text-red-700"><Trash2 size={18} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'webhooks' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('URL')}</th>
                  <th className="px-4 py-3">{t('მოვლენები')}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(hooks || []).length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('Webhooks არ არის')}</td></tr>
                ) : (hooks || []).map((w: any) => (
                  <tr key={w.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{w.name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-600 dark:text-gray-400">{w.url}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{w.events}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => removeHook.mutate(w.id)} className="text-red-500 hover:text-red-700"><Trash2 size={18} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'rs' && (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border bg-white p-5 shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <h3 className="font-semibold text-brandgray-900 dark:text-gray-100 mb-3">{t('RS.ge SOAP')}</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">{t('კონფიგურირებული')}</span><span>{rsStatus?.configured ? '✓' : '—'}</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">{t('მიუწვდომია')}</span><span>{rsStatus?.reachable ? '✓' : '—'}</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">{t('ავთენტიფიცირებული')}</span><span>{rsStatus?.authenticated ? '✓' : '—'}</span></div>
              {rsStatus?.server_time && <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">{t('სერვერის დრო')}</span><span className="font-mono text-xs">{rsStatus.server_time}</span></div>}
            </div>
          </div>
          <div className="rounded-xl border bg-white p-5 shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <h3 className="font-semibold text-brandgray-900 dark:text-gray-100 mb-3">{t('Sandbox')}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">{t('Sandbox რეჟიმი საშუალებას გაძლევთ ტესტირება გააკეთოთ API-ით რეალური მონაცემების გარეშე. API Keys განყოფილებაში შექმენით key და გამოიყენეთ X-API-Key header-ით.')}</p>
          </div>
        </div>
      )}

      {tab === 'counterparties' && (
        <div className="space-y-4">
          <div className="rounded-xl border bg-white p-5 shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <h3 className="font-semibold text-brandgray-900 dark:text-gray-100 mb-3">{t('კონტრაგენტის გადამოწმება')}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              {t('შეამოწმეთ კონტრაგენტი SRS ღია მონაცემებით — VAT გადამხდელია თუ არა, აქტიური სტატუსი. ყოველი შემოწმება ინახება ისტორიაში.')}
            </p>
            <div className="flex gap-2">
              <input
                value={codeInput}
                onChange={e => setCodeInput(e.target.value)}
                placeholder={t('საიდენტიფიკაციო კოდი')}
                className="w-full max-w-xs rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200"
              />
              <button
                onClick={() => verify.mutate()}
                disabled={verify.isPending || codeInput.trim().length < 7}
                className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {verify.isPending ? t('მუშავდება...') : t('შემოწმება')}
              </button>
            </div>
            {verifyResult && (
              <div className={`mt-4 rounded-lg border p-3 text-sm ${verifyResult.status === 'verified' ? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/40 dark:bg-emerald-900/10 dark:text-emerald-300' : verifyResult.status === 'not_found' ? 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/10 dark:text-amber-300' : 'border-gray-200 bg-gray-50 text-gray-700 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-300'}`}>
                <div className="font-medium">
                  {verifyResult.status === 'verified' ? '✓ ' + t('კონტრაგენტი დადასტურდა') : verifyResult.status === 'not_found' ? t('კონტრაგენტი ვერ მოიძებნა') : t('SRS ღია მონაცემები მიუწვდომელია')}
                </div>
                {verifyResult.entity_name && <div className="mt-1">{verifyResult.entity_name}</div>}
                {verifyResult.is_vat_payer != null && (
                  <div className="mt-1">{t('VAT გადამხდელი')}: {verifyResult.is_vat_payer ? t('დიახ') : t('არა')}</div>
                )}
                <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{fmtDateTime(verifyResult.checked_at)}</div>
              </div>
            )}
          </div>

          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <div className="px-5 py-3.5 border-b border-brandgray-100 dark:border-dark-50">
              <h3 className="font-semibold text-brandgray-900 dark:text-gray-100">{t('შემოწმების ისტორია')}</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                  <tr>
                    <th className="px-4 py-3">{t('კოდი')}</th>
                    <th className="px-4 py-3">{t('დასახელება')}</th>
                    <th className="px-4 py-3">{t('სტატუსი')}</th>
                    <th className="px-4 py-3">{t('VAT')}</th>
                    <th className="px-4 py-3">{t('თარიღი')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-dark-50">
                  {(checks || []).map((c: any) => (
                    <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                      <td className="px-4 py-3 font-mono text-xs">{c.identification_code}</td>
                      <td className="px-4 py-3">{c.entity_name || '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`badge ${c.status === 'verified' ? 'badge-green' : c.status === 'not_found' ? 'badge-amber' : 'badge-gray'}`}>
                          {c.status === 'verified' ? t('დადასტურდა') : c.status === 'not_found' ? t('ვერ მოიძებნა') : t('მიუწვდომელია')}
                        </span>
                      </td>
                      <td className="px-4 py-3">{c.is_vat_payer == null ? '—' : c.is_vat_payer ? t('დიახ') : t('არა')}</td>
                      <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">{fmtDateTime(c.checked_at)}</td>
                    </tr>
                  ))}
                  {!checks?.length && (
                    <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">{t('შემოწმებები არ არის')}</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* New key modal */}
      <Modal open={keyOpen} onClose={() => setKeyOpen(false)} title={t('ახალი API Key')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')} required>
            <input value={keyForm.name} onChange={e => setKeyForm({ ...keyForm, name: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('უფლებები')}>
            <select value={keyForm.scopes} onChange={e => setKeyForm({ ...keyForm, scopes: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="read">read</option>
              <option value="write">write</option>
              <option value="admin">admin</option>
              <option value="*">* (ყველა)</option>
              <option value="sales.read,projects.read">sales.read, projects.read</option>
              <option value="inventory.write,pos.read">inventory.write, pos.read</option>
            </select>
          </FormField>
          <FormField label={t('დაშვებული IP-ები (მძიმით)')}>
            <input value={keyForm.allowed_ips} onChange={e => setKeyForm({ ...keyForm, allowed_ips: e.target.value })}
              placeholder="203.0.113.5, 10.0.0.0/8" className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <div className="grid grid-cols-2 gap-3">
            <FormField label={t('Rate limit (წთ)')}>
              <input type="number" min={1} value={keyForm.rate_limit_per_minute} onChange={e => setKeyForm({ ...keyForm, rate_limit_per_minute: Number(e.target.value) || 120 })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('ვადა (არასავალდებულო)')}>
              <input type="date" value={keyForm.expires_at} onChange={e => setKeyForm({ ...keyForm, expires_at: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createKey.mutate()} disabled={!keyForm.name || createKey.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შექმნა')}
          </button>
        </div>
      </Modal>

      {/* New key result */}
      <Modal open={!!newKey} onClose={() => setNewKey('')} title={t('API Key შეიქმნა')}>
        <div className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">{t('შეინახეთ key — ის მხოლოდ ერთხელ ჩანს!')}</p>
          <div className="flex items-center gap-2 rounded-lg border border-gray-200 dark:border-dark-50 p-3">
            <code className="flex-1 break-all text-xs font-mono text-gray-800 dark:text-gray-200">{newKey}</code>
            <button onClick={() => copy(newKey)} className="text-primary-600 hover:text-primary-700"><Copy size={16} /></button>
          </div>
        </div>
      </Modal>

      {/* New webhook modal */}
      <Modal open={hookOpen} onClose={() => setHookOpen(false)} title={t('ახალი Webhook')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')} required>
            <input value={hookForm.name} onChange={e => setHookForm({ ...hookForm, name: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('URL')} required>
            <input value={hookForm.url} onChange={e => setHookForm({ ...hookForm, url: e.target.value })}
              placeholder="https://example.com/hook" className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('მოვლენები')}>
            <input value={hookForm.events} onChange={e => setHookForm({ ...hookForm, events: e.target.value })}
              placeholder="invoice.created, client.created" className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <div className="grid grid-cols-2 gap-3">
            <FormField label={t('Retry max')}>
              <input type="number" min={1} value={hookForm.retry_max} onChange={e => setHookForm({ ...hookForm, retry_max: Number(e.target.value) || 3 })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('Backoff (წმ)')}>
              <input type="number" min={1} value={hookForm.retry_backoff_seconds} onChange={e => setHookForm({ ...hookForm, retry_backoff_seconds: Number(e.target.value) || 60 })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createHook.mutate()} disabled={!hookForm.name || !hookForm.url || createHook.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შექმნა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
