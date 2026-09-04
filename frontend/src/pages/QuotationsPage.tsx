import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Check, FileText, History, PenLine, Plus, ShieldCheck, X, Link2 } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { clientsApi, productsApi, salesToolsApi } from '../services/api'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

interface Quotation {
  id: string
  client_id: string
  client_name: string | null
  quotation_number: string
  quotation_date: string
  valid_until: string | null
  status: string
  currency: string
  subtotal: number
  vat_amount: number
  total: number
  discount_percent: number
  items: { id: string; description: string; quantity: number; unit_price: number; line_total: number; is_optional?: boolean; config?: any }[]
  version_number?: number
  approval_required?: boolean
  approval_request_id?: string | null
  signed_at?: string | null
  signed_by?: string | null
  signature_hash?: string | null
  portal_token?: string | null
}

function money(v: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)
}

const statusLabels: Record<string, string> = {
  draft: 'პროექტი', sent: 'გაგზავნილი', accepted: 'მიღებული',
  rejected: 'უარყოფილი', expired: 'ვადაგასული', converted: 'კონვერტირებული',
}
const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600 dark:bg-dark-100 dark:text-gray-400',
  sent: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  accepted: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  rejected: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  expired: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  converted: 'bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
}

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function QuotationsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [detail, setDetail] = useState<Quotation | null>(null)
  const [detailTab, setDetailTab] = useState<'overview' | 'versions'>('overview')
  const [signerName, setSignerName] = useState('')
  const [portalLink, setPortalLink] = useState('')
  const [form, setForm] = useState({
    client_id: '', quotation_date: new Date().toISOString().slice(0, 10),
    valid_until: '', notes: '',
  })
  const [lines, setLines] = useState([{ product_id: '', description: '', quantity: '1', unit_price: '', is_optional: false }])

  const { data, isLoading } = useQuery({
    queryKey: ['quotations'],
    queryFn: () => salesToolsApi.listQuotations({ page_size: 100 }).then(r => r.data.data),
  })
  const items: Quotation[] = data?.items || []

  const { data: clients } = useQuery({
    queryKey: ['clients-all'],
    queryFn: () => clientsApi.list({ page_size: 100 }).then(r => r.data.data.items),
  })
  const { data: products } = useQuery({
    queryKey: ['products-all-q'],
    queryFn: () => productsApi.list({ page_size: 100 }).then(r => r.data.data.items),
  })

  const create = useMutation({
    mutationFn: () => salesToolsApi.createQuotation({
      client_id: form.client_id, quotation_date: form.quotation_date,
      valid_until: form.valid_until || null, notes: form.notes || null,
      items: lines.map(l => ({
        product_id: l.product_id || null,
        description: l.description || '—',
        quantity: Number(l.quantity), unit_price: Number(l.unit_price),
      })),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['quotations'] }); setOpen(false) },
  })

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => salesToolsApi.updateQuotationStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quotations'] }),
  })

  const convert = useMutation({
    mutationFn: (id: string) => salesToolsApi.convertQuotation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quotations'] }),
  })

  const remove = useMutation({
    mutationFn: (id: string) => salesToolsApi.deleteQuotation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quotations'] }),
  })

  // Quotation 2.0
  const { data: versions } = useQuery({
    queryKey: ['quotation-versions', detail?.id],
    queryFn: () => detail ? salesToolsApi.listQuotationVersions(detail.id).then(r => r.data.data) : [],
    enabled: !!detail && detailTab === 'versions',
  })
  const requestApproval = useMutation({
    mutationFn: (id: string) => salesToolsApi.requestApproval(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quotations'] }),
  })
  const sign = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => salesToolsApi.signQuotation(id, { signer_name: name, method: 'manual' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['quotations'] }); setSignerName('') },
  })
  const portal = useMutation({
    mutationFn: (id: string) => salesToolsApi.generatePortalToken(id),
    onSuccess: (r: any) => setPortalLink(`${window.location.origin}${r.data.data.portal_url}`),
  })

  const columns = [
    { key: 'quotation_number', label: 'ნომერი', priority: true, render: (q: Quotation) => (
      <span className="font-mono font-semibold text-gray-900 dark:text-gray-100">{q.quotation_number}</span>) },
    { key: 'client_name', label: 'კლიენტი', render: (q: Quotation) => q.client_name || '—' },
    { key: 'quotation_date', label: 'თარიღი', render: (q: Quotation) => fmtDate(new Date(q.quotation_date)) },
    { key: 'total', label: 'ჯამი', render: (q: Quotation) => <span className="font-semibold">{money(q.total)}</span> },
    { key: 'status', label: 'სტატუსი', render: (q: Quotation) => (
      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColors[q.status] || statusColors.draft}`}>
        {t(statusLabels[q.status] || q.status)}
      </span>) },
    { key: 'actions', label: '', render: (q: Quotation) => (
      <div className="flex gap-1">
        {q.status === 'draft' && (
          <button onClick={() => setStatus.mutate({ id: q.id, status: 'sent' })}
            className="p-1.5 rounded-md text-gray-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30" title={t('გაგზავნა')}>
            <Check size={15} />
          </button>
        )}
        {q.status === 'accepted' && (
          <button onClick={() => convert.mutate(q.id)}
            className="p-1.5 rounded-md text-gray-400 hover:text-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900/30" title={t('კონვერტაცია შეკვეთაში')}>
            <ArrowRight size={15} />
          </button>
        )}
        {q.status === 'draft' && (
          <button onClick={() => remove.mutate(q.id)}
            className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30" title={t('წაშლა')}>
            <X size={15} />
          </button>
        )}
      </div>) },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('კომერციული შემოთავაზებები')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('Quotation — შეკვეთად კონვერტირებადი წინადადებები')}</p>
        </div>
        <button onClick={() => setOpen(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
          <Plus size={15} /> {t('ახალი შემოთავაზება')}
        </button>
      </div>

      <DataTable columns={columns} data={items} isLoading={isLoading}
        emptyMessage={t('შემოთავაზებები არ არის')} onRowClick={q => setDetail(q)} />

      {/* Create modal */}
      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი კომერციული შემოთავაზება')}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('კლიენტი')}</label>
              <select className={inputCls} value={form.client_id} onChange={e => setForm({ ...form, client_id: e.target.value })}>
                <option value="">—</option>
                {(clients || []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('თარიღი')}</label>
              <input type="date" className={inputCls} value={form.quotation_date} onChange={e => setForm({ ...form, quotation_date: e.target.value })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მოქმედების ვადა')}</label>
              <input type="date" className={inputCls} value={form.valid_until} onChange={e => setForm({ ...form, valid_until: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('შენიშვნა')}</label>
              <input className={inputCls} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
            </div>
          </div>

          <div className="space-y-2">
            <div className="grid grid-cols-[1fr_1.4fr_70px_100px] gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              <span>{t('პროდუქტი')}</span><span>{t('აღწერა')}</span><span>{t('რაოდენობა')}</span><span>{t('ფასი')}</span>
            </div>
            {lines.map((l, idx) => (
              <div key={idx} className="grid grid-cols-[1fr_1.4fr_70px_100px] gap-2 items-center">
                <select className={inputCls} value={l.product_id} onChange={e => {
                  const p = (products || []).find((x: any) => x.id === e.target.value)
                  const nl = [...lines]; nl[idx] = { ...l, product_id: e.target.value, description: p?.name || '', unit_price: p?.sale_price ? String(p.sale_price) : l.unit_price }; setLines(nl)
                }}>
                  <option value="">—</option>
                  {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.sku || p.code} — {p.name}</option>)}
                </select>
                <input className={inputCls} value={l.description} onChange={e => { const nl = [...lines]; nl[idx] = { ...l, description: e.target.value }; setLines(nl) }} />
                <input type="number" min="0" step="0.001" className={inputCls} value={l.quantity} onChange={e => { const nl = [...lines]; nl[idx] = { ...l, quantity: e.target.value }; setLines(nl) }} />
                <input type="number" min="0" step="0.01" className={inputCls} value={l.unit_price} onChange={e => { const nl = [...lines]; nl[idx] = { ...l, unit_price: e.target.value }; setLines(nl) }} />
              </div>
            ))}
            <button onClick={() => setLines([...lines, { product_id: '', description: '', quantity: '1', unit_price: '', is_optional: false }])}
              className="text-sm text-primary-700 hover:text-primary-800 font-medium dark:text-primary-400">
              + {t('სტრიქონის დამატება')}
            </button>
          </div>

          <button onClick={() => create.mutate()} disabled={create.isPending || !form.client_id || lines.some(l => !l.quantity || !l.unit_price)}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            <FileText size={15} className="inline mr-1.5 -mt-0.5" />{t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* Detail modal */}
      <Modal open={!!detail} onClose={() => { setDetail(null); setDetailTab('overview'); setPortalLink('') }} title={detail ? `${detail.quotation_number} — ${detail.client_name || ''}` : ''}>
        {detail && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColors[detail.status]}`}>{t(statusLabels[detail.status] || detail.status)}</span>
                {detail.version_number && <span className="text-xs text-gray-400">v{detail.version_number}</span>}
                {detail.approval_required && <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">{t('დამტკიცება საჭიროა')}</span>}
                {detail.signed_at && <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">✍ {detail.signed_by}</span>}
              </div>
              <span className="text-sm text-brandgray-500 dark:text-gray-400">{fmtDate(new Date(detail.quotation_date))}</span>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-gray-200 dark:border-dark-50 pb-2">
              <button onClick={() => setDetailTab('overview')} className={`px-3 py-1.5 text-sm rounded-lg ${detailTab === 'overview' ? 'bg-primary-600 text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-100'}`}>{t('მიმოხილვა')}</button>
              <button onClick={() => setDetailTab('versions')} className={`px-3 py-1.5 text-sm rounded-lg flex items-center gap-1.5 ${detailTab === 'versions' ? 'bg-primary-600 text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-100'}`}>
                <History size={14} /> {t('ვერსიები')}
              </button>
            </div>

            {detailTab === 'overview' && (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-dark-50 text-left text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        <th className="py-2 pr-4">{t('აღწერა')}</th>
                        <th className="py-2 pr-4 text-right">{t('რაოდენობა')}</th>
                        <th className="py-2 pr-4 text-right">{t('ფასი')}</th>
                        <th className="py-2 text-right">{t('ჯამი')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.items.map((i, idx) => (
                        <tr key={idx} className="border-b border-gray-100 dark:border-dark-50">
                          <td className="py-2 pr-4">
                            {i.description}
                            {i.is_optional && <span className="ml-2 text-xs font-medium px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 dark:bg-dark-100 dark:text-gray-400">{t('ოფციონალური')}</span>}
                            {i.config && <span className="ml-1 text-xs text-gray-400">({JSON.stringify(i.config)})</span>}
                          </td>
                          <td className="py-2 pr-4 text-right">{i.quantity}</td>
                          <td className="py-2 pr-4 text-right">{money(i.unit_price)}</td>
                          <td className="py-2 text-right font-semibold">{money(i.line_total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex justify-between text-sm text-brandgray-600 dark:text-gray-400">
                  <span>{t('ქვეჯამი')}</span><span className="font-semibold">{money(detail.subtotal)}</span>
                </div>
                <div className="flex justify-between text-sm text-brandgray-600 dark:text-gray-400">
                  <span>{t('დღგ 18%')}</span><span className="font-semibold">{money(detail.vat_amount)}</span>
                </div>
                <div className="flex justify-between font-bold text-gray-900 dark:text-gray-100">
                  <span>{t('სულ')}</span><span>{money(detail.total)}</span>
                </div>

                {/* Quotation 2.0 actions */}
                <div className="flex flex-wrap gap-2 pt-3 border-t border-gray-200 dark:border-dark-50">
                  {detail.status === 'sent' && !detail.signed_at && (
                    <>
                      <div className="flex items-center gap-2">
                        <input value={signerName} onChange={e => setSignerName(e.target.value)} placeholder={t('ხელმომწერის სახელი')} className={inputCls + ' !w-44'} />
                        <button onClick={() => signerName && sign.mutate({ id: detail.id, name: signerName })} disabled={!signerName || sign.isPending}
                          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50">
                          <PenLine size={15} /> {t('ხელმოწერა')}
                        </button>
                      </div>
                      <button onClick={() => portal.mutate(detail.id)} disabled={portal.isPending}
                        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border border-gray-200 dark:border-dark-50 text-gray-600 dark:text-gray-400 hover:text-primary-600">
                        <Link2 size={15} /> {t('Portal ბმული')}
                      </button>
                    </>
                  )}
                  {detail.status === 'draft' && !detail.approval_required && (
                    <button onClick={() => requestApproval.mutate(detail.id)} disabled={requestApproval.isPending}
                      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50">
                      <ShieldCheck size={15} /> {t('დამტკიცების მოთხოვნა')}
                    </button>
                  )}
                  {portalLink && (
                    <div className="w-full text-xs bg-gray-50 dark:bg-dark-100 rounded-lg p-2 break-all">
                      <span className="text-gray-500 dark:text-gray-400">{t('კლიენტის ბმული:')}</span>{' '}
                      <a href={portalLink} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline">{portalLink}</a>
                    </div>
                  )}
                </div>
              </>
            )}

            {detailTab === 'versions' && (
              <div className="space-y-2 max-h-[320px] overflow-y-auto">
                {(versions || []).map((v: any) => (
                  <div key={v.id} className="border border-gray-100 dark:border-dark-50 rounded-lg p-3 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-gray-900 dark:text-gray-100">v{v.version_number}</span>
                      <span className="text-xs text-gray-400">{fmtDateTime(new Date(v.created_at))}</span>
                    </div>
                    <div className="mt-1 flex gap-4 text-xs text-gray-500 dark:text-gray-400">
                      <span>{t('ჯამი')}: <b>{money(v.total)}</b></span>
                      <span>{t('ფასდაკლება')}: {v.discount_percent}%</span>
                      <span>{t('სტატუსი')}: {t(statusLabels[v.status] || v.status)}</span>
                    </div>
                    {v.change_reason && <p className="mt-1 text-xs text-gray-400">{t('მიზეზი')}: {v.change_reason}</p>}
                    <p className="mt-1 text-xs text-gray-400">{v.items_snapshot.length} {t('სტრიქონი')}</p>
                  </div>
                ))}
                {(versions || []).length === 0 && <p className="text-sm text-gray-400 py-4 text-center">{t('ვერსიები არ არის')}</p>}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
