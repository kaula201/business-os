import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShoppingCart, Plus, Send, Trash2, Package, Tag, Truck, RotateCcw, FileText, MapPin } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { ecommerceApi, emailMarketingApi } from '../services/api'
import { fmtDate } from '../lib/format'

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function EcommercePage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'campaigns' | 'promotions' | 'shipping' | 'returns' | 'content'>('campaigns')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: '', subject: '', body: '', audience: '' })
  // eCommerce 2.0 forms
  const [promoForm, setPromoForm] = useState({ code: '', name: '', discount_type: 'percent', discount_value: '', min_subtotal: '0', max_uses: '0' })
  const [shipForm, setShipForm] = useState({ name: '', zone: 'default', flat_rate: '', free_above: '', weight_rate: '0' })
  const [contentForm, setContentForm] = useState({ slug: '', title: '', body: '', seo_title: '', seo_description: '', is_published: true })
  const [trackForm, setTrackForm] = useState({ order_id: '', status: 'shipped', carrier: '', tracking_number: '', note: '' })
  const [returnForm, setReturnForm] = useState({ order_id: '', reason: '' })

  const { data: campaigns } = useQuery({
    queryKey: ['email-campaigns'],
    queryFn: () => emailMarketingApi.list().then(r => r.data.data.items),
  })
  const { data: promotions } = useQuery({
    queryKey: ['ecom-promotions'],
    queryFn: () => ecommerceApi.listPromotions().then(r => r.data.data),
  })
  const { data: shippingRules } = useQuery({
    queryKey: ['ecom-shipping'],
    queryFn: () => ecommerceApi.listShippingRules().then(r => r.data.data),
  })
  const { data: returns } = useQuery({
    queryKey: ['ecom-returns'],
    queryFn: () => ecommerceApi.listReturns().then(r => r.data.data),
  })
  const { data: contentPages } = useQuery({
    queryKey: ['ecom-content'],
    queryFn: () => ecommerceApi.listContentPages().then(r => r.data.data),
  })
  const { data: orders } = useQuery({
    queryKey: ['ecom-orders'],
    queryFn: () => ecommerceApi.orders().then(r => r.data.data),
  })

  const createCampaign = useMutation({
    mutationFn: () => emailMarketingApi.create({
      name: form.name, subject: form.subject, body: form.body,
      audience: { emails: form.audience.split(',').map((e: string) => e.trim()).filter(Boolean) },
    }),
    onSuccess: () => { setOpen(false); setForm({ name: '', subject: '', body: '', audience: '' }); qc.invalidateQueries({ queryKey: ['email-campaigns'] }) },
  })
  const sendCampaign = useMutation({
    mutationFn: (id: string) => emailMarketingApi.send(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['email-campaigns'] }),
  })
  const removeCampaign = useMutation({
    mutationFn: (id: string) => emailMarketingApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['email-campaigns'] }),
  })
  // eCommerce 2.0
  const createPromo = useMutation({
    mutationFn: () => ecommerceApi.createPromotion({
      code: promoForm.code, name: promoForm.name, discount_type: promoForm.discount_type,
      discount_value: Number(promoForm.discount_value), min_subtotal: Number(promoForm.min_subtotal || 0),
      max_uses: Number(promoForm.max_uses || 0),
    }),
    onSuccess: () => { setPromoForm({ code: '', name: '', discount_type: 'percent', discount_value: '', min_subtotal: '0', max_uses: '0' }); qc.invalidateQueries({ queryKey: ['ecom-promotions'] }) },
  })
  const createShip = useMutation({
    mutationFn: () => ecommerceApi.createShippingRule({
      name: shipForm.name, zone: shipForm.zone, flat_rate: Number(shipForm.flat_rate || 0),
      free_above: shipForm.free_above ? Number(shipForm.free_above) : null, weight_rate: Number(shipForm.weight_rate || 0),
    }),
    onSuccess: () => { setShipForm({ name: '', zone: 'default', flat_rate: '', free_above: '', weight_rate: '0' }); qc.invalidateQueries({ queryKey: ['ecom-shipping'] }) },
  })
  const addTrack = useMutation({
    mutationFn: () => ecommerceApi.addTracking(trackForm.order_id, {
      status: trackForm.status, carrier: trackForm.carrier || null,
      tracking_number: trackForm.tracking_number || null, note: trackForm.note || null,
    }),
    onSuccess: () => { setTrackForm({ order_id: '', status: 'shipped', carrier: '', tracking_number: '', note: '' }); qc.invalidateQueries({ queryKey: ['ecom-orders'] }) },
  })
  const requestReturn = useMutation({
    mutationFn: () => ecommerceApi.requestReturn(returnForm.order_id, { reason: returnForm.reason }),
    onSuccess: () => { setReturnForm({ order_id: '', reason: '' }); qc.invalidateQueries({ queryKey: ['ecom-returns'] }) },
  })
  const approveReturn = useMutation({
    mutationFn: (id: string) => ecommerceApi.approveReturn(id, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ecom-returns'] }),
  })
  const createContent = useMutation({
    mutationFn: () => ecommerceApi.createContentPage(contentForm),
    onSuccess: () => { setContentForm({ slug: '', title: '', body: '', seo_title: '', seo_description: '', is_published: true }); qc.invalidateQueries({ queryKey: ['ecom-content'] }) },
  })

  const tabs = [
    { id: 'campaigns' as const, label: t('ელ. მარკეტინგი'), icon: Send },
    { id: 'promotions' as const, label: t('პრომოციები'), icon: Tag },
    { id: 'shipping' as const, label: t('მიწოდება'), icon: Truck },
    { id: 'returns' as const, label: t('დაბრუნებები'), icon: RotateCcw },
    { id: 'content' as const, label: t('კონტენტი (SEO)'), icon: FileText },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('eCommerce')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('მარკეტინგი, პრომოციები, მიწოდება, დაბრუნებები, SEO')}</p>
        </div>
        {tab === 'campaigns' && (
          <button onClick={() => setOpen(true)} className="btn btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('ახალი კამპანია')}
          </button>
        )}
      </div>

      <div className="flex gap-1 rounded-lg bg-brandgray-100 p-1 w-fit dark:bg-dark-100">
        {tabs.map(tb => (
          <button key={tb.id} onClick={() => setTab(tb.id)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium ${tab === tb.id ? 'bg-white shadow-sm text-gray-900 dark:bg-dark-200 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'}`}>
            <tb.icon size={14} className="inline mr-1 -mt-0.5" />{tb.label}
          </button>
        ))}
      </div>

      {tab === 'campaigns' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('თემა')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3">{t('გაგზავნილია')}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(campaigns || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('კამპანიები არ არის')}</td></tr>
                ) : (campaigns || []).map((c: any) => (
                  <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{c.name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{c.subject}</td>
                    <td className="px-4 py-3">
                      <span className={`badge ${c.status === 'sent' ? 'badge-success' : 'badge-warning'}`}>{t(c.status === 'sent' ? 'გაგზავნილი' : 'მონახაზი')}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{c.sent_at ? fmtDate(new Date(c.sent_at)) : '—'}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {c.status !== 'sent' && (
                          <button onClick={() => sendCampaign.mutate(c.id)} className="btn btn-sm btn-primary flex items-center gap-1" title={t('გაგზავნა')}><Send size={14} /></button>
                        )}
                        <button onClick={() => removeCampaign.mutate(c.id)} className="btn btn-sm btn-danger flex items-center gap-1" title={t('წაშლა')}><Trash2 size={14} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'promotions' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-gray-200 dark:border-dark-50 p-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('ახალი პრომოცია')}</h3>
            <div className="mt-3 grid gap-2 sm:grid-cols-6">
              <input className={inputCls} placeholder={t('კოდი')} value={promoForm.code} onChange={e => setPromoForm({ ...promoForm, code: e.target.value })} />
              <input className={inputCls} placeholder={t('სახელი')} value={promoForm.name} onChange={e => setPromoForm({ ...promoForm, name: e.target.value })} />
              <select className={inputCls} value={promoForm.discount_type} onChange={e => setPromoForm({ ...promoForm, discount_type: e.target.value })}>
                <option value="percent">%</option><option value="fixed">₾</option>
              </select>
              <input type="number" className={inputCls} placeholder={t('ფასდაკლება')} value={promoForm.discount_value} onChange={e => setPromoForm({ ...promoForm, discount_value: e.target.value })} />
              <input type="number" className={inputCls} placeholder={t('მინ. თანხა')} value={promoForm.min_subtotal} onChange={e => setPromoForm({ ...promoForm, min_subtotal: e.target.value })} />
              <button onClick={() => createPromo.mutate()} disabled={!promoForm.code || !promoForm.discount_value} className="px-3 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">{t('შექმნა')}</button>
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr><th className="px-4 py-3">{t('კოდი')}</th><th className="px-4 py-3">{t('სახელი')}</th><th className="px-4 py-3">{t('ფასდაკლება')}</th><th className="px-4 py-3">{t('გამოყენება')}</th><th className="px-4 py-3">{t('სტატუსი')}</th></tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(promotions || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('პრომოციები არ არის')}</td></tr>
                ) : (promotions || []).map((p: any) => (
                  <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono font-semibold text-primary-700 dark:text-primary-400">{p.code}</td>
                    <td className="px-4 py-3">{p.name}</td>
                    <td className="px-4 py-3">{p.discount_type === 'percent' ? `${p.discount_value}%` : `${p.discount_value} ₾`}</td>
                    <td className="px-4 py-3 text-gray-500">{p.used_count}{p.max_uses ? ` / ${p.max_uses}` : ''}</td>
                    <td className="px-4 py-3">{p.is_active ? <span className="badge badge-success">{t('აქტიური')}</span> : <span className="badge">{t('გამორთული')}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'shipping' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-gray-200 dark:border-dark-50 p-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('ახალი მიწოდების წესი')}</h3>
            <div className="mt-3 grid gap-2 sm:grid-cols-6">
              <input className={inputCls} placeholder={t('სახელი')} value={shipForm.name} onChange={e => setShipForm({ ...shipForm, name: e.target.value })} />
              <input className={inputCls} placeholder={t('ზონა')} value={shipForm.zone} onChange={e => setShipForm({ ...shipForm, zone: e.target.value })} />
              <input type="number" className={inputCls} placeholder={t('ფიქსირებული')} value={shipForm.flat_rate} onChange={e => setShipForm({ ...shipForm, flat_rate: e.target.value })} />
              <input type="number" className={inputCls} placeholder={t('უფასო თუ >')} value={shipForm.free_above} onChange={e => setShipForm({ ...shipForm, free_above: e.target.value })} />
              <input type="number" className={inputCls} placeholder={t('კგ-ის ტარიფი')} value={shipForm.weight_rate} onChange={e => setShipForm({ ...shipForm, weight_rate: e.target.value })} />
              <button onClick={() => createShip.mutate()} disabled={!shipForm.name} className="px-3 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">{t('შექმნა')}</button>
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr><th className="px-4 py-3">{t('სახელი')}</th><th className="px-4 py-3">{t('ზონა')}</th><th className="px-4 py-3">{t('ფიქსირებული')}</th><th className="px-4 py-3">{t('უფასო თუ >')}</th><th className="px-4 py-3">{t('კგ-ის ტარიფი')}</th></tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(shippingRules || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('მიწოდების წესები არ არის')}</td></tr>
                ) : (shippingRules || []).map((r: any) => (
                  <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium">{r.name}</td>
                    <td className="px-4 py-3 text-gray-500">{r.zone}</td>
                    <td className="px-4 py-3">{r.flat_rate} ₾</td>
                    <td className="px-4 py-3">{r.free_above ? `${r.free_above} ₾` : '—'}</td>
                    <td className="px-4 py-3">{r.weight_rate} ₾/კგ</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'returns' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-gray-200 dark:border-dark-50 p-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('დაბრუნების მოთხოვნა')}</h3>
            <div className="mt-3 grid gap-2 sm:grid-cols-4">
              <select className={inputCls} value={returnForm.order_id} onChange={e => setReturnForm({ ...returnForm, order_id: e.target.value })}>
                <option value="">{t('შეკვეთა')}</option>
                {(orders || []).map((o: any) => <option key={o.id} value={o.id}>{o.order_number}</option>)}
              </select>
              <input className={inputCls} placeholder={t('მიზეზი')} value={returnForm.reason} onChange={e => setReturnForm({ ...returnForm, reason: e.target.value })} />
              <button onClick={() => requestReturn.mutate()} disabled={!returnForm.order_id || !returnForm.reason} className="px-3 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">{t('მოთხოვნა')}</button>
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr><th className="px-4 py-3">{t('შეკვეთა')}</th><th className="px-4 py-3">{t('მიზეზი')}</th><th className="px-4 py-3">{t('სტატუსი')}</th><th className="px-4 py-3">{t('თანხა')}</th><th className="px-4 py-3"></th></tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(returns || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('დაბრუნებები არ არის')}</td></tr>
                ) : (returns || []).map((r: any) => (
                  <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono text-xs">{r.order_id.slice(0, 8)}...</td>
                    <td className="px-4 py-3">{r.reason}</td>
                    <td className="px-4 py-3">
                      <span className={`badge ${r.status === 'refunded' ? 'badge-success' : r.status === 'requested' ? 'badge-warning' : 'badge-danger'}`}>{t(r.status)}</span>
                    </td>
                    <td className="px-4 py-3">{r.refund_amount ? `${r.refund_amount} ₾` : '—'}</td>
                    <td className="px-4 py-3">
                      {r.status === 'requested' && (
                        <button onClick={() => approveReturn.mutate(r.id)} className="btn btn-sm btn-primary">{t('დამტკიცება')}</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'content' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-gray-200 dark:border-dark-50 p-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('ახალი გვერდი (SEO)')}</h3>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <input className={inputCls} placeholder={t('Slug')} value={contentForm.slug} onChange={e => setContentForm({ ...contentForm, slug: e.target.value })} />
              <input className={inputCls} placeholder={t('სათაური')} value={contentForm.title} onChange={e => setContentForm({ ...contentForm, title: e.target.value })} />
              <textarea className={`${inputCls} min-h-[80px]`} placeholder={t('შინაარსი')} value={contentForm.body} onChange={e => setContentForm({ ...contentForm, body: e.target.value })} />
              <div className="space-y-2">
                <input className={inputCls} placeholder={t('SEO სათაური')} value={contentForm.seo_title} onChange={e => setContentForm({ ...contentForm, seo_title: e.target.value })} />
                <input className={inputCls} placeholder={t('SEO აღწერა')} value={contentForm.seo_description} onChange={e => setContentForm({ ...contentForm, seo_description: e.target.value })} />
              </div>
            </div>
            <button onClick={() => createContent.mutate()} disabled={!contentForm.slug || !contentForm.title} className="mt-3 px-3 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">{t('შექმნა')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr><th className="px-4 py-3">{t('Slug')}</th><th className="px-4 py-3">{t('სათაური')}</th><th className="px-4 py-3">{t('SEO სათაური')}</th><th className="px-4 py-3">{t('სტატუსი')}</th></tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(contentPages || []).length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('გვერდები არ არის')}</td></tr>
                ) : (contentPages || []).map((p: any) => (
                  <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono text-primary-700 dark:text-primary-400">{p.slug}</td>
                    <td className="px-4 py-3 font-medium">{p.title}</td>
                    <td className="px-4 py-3 text-gray-500">{p.seo_title || '—'}</td>
                    <td className="px-4 py-3">{p.is_published ? <span className="badge badge-success">{t('გამოქვეყნებული')}</span> : <span className="badge">{t('მონახაზი')}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი კამპანია')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')}>
            <input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          </FormField>
          <FormField label={t('თემა')}>
            <input className="input" value={form.subject} onChange={e => setForm({ ...form, subject: e.target.value })} />
          </FormField>
          <FormField label={t('შინაარსი')}>
            <textarea className="input min-h-[100px]" value={form.body} onChange={e => setForm({ ...form, body: e.target.value })} />
          </FormField>
          <FormField label={t('მიმღებები (ელფოსტები, მძიმით გამოყოფილი)')}>
            <input className="input" value={form.audience} onChange={e => setForm({ ...form, audience: e.target.value })} placeholder="a@test.ge, b@test.ge" />
          </FormField>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setOpen(false)}>{t('გაუქმება')}</button>
            <button className="btn btn-primary" onClick={() => createCampaign.mutate()} disabled={!form.name || !form.subject}>{t('შექმნა')}</button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
