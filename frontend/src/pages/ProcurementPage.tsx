import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Scale, Award, Zap, FileText } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { productsApi, procurementApi, suppliersApi } from '../services/api'

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function ProcurementPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'rfq' | 'compare' | 'pricelist' | 'blanket' | 'scorecard'>('rfq')
  const [rfqOpen, setRfqOpen] = useState(false)
  const [priceOpen, setPriceOpen] = useState(false)
  const [blanketOpen, setBlanketOpen] = useState(false)
  const [scoreOpen, setScoreOpen] = useState(false)
  const [compareFor, setCompareFor] = useState<string | null>(null)
  const [rfqForm, setRfqForm] = useState({ title: '', product_id: '', quantity: '', required_date: '' })
  const [priceForm, setPriceForm] = useState({ supplier_id: '', product_id: '', price: '', currency: 'GEL' })
  const [blanketForm, setBlanketForm] = useState({ supplier_id: '', title: '', product_id: '', quantity: '', unit_price: '' })
  const [scoreForm, setScoreForm] = useState({ supplier_id: '', period: '', on_time: '', quality: '', price_index: '' })

  const { data: rfqsData, isLoading: rfqsLoading } = useQuery({
    queryKey: ['proc-rfqs'],
    queryFn: () => procurementApi.listRfqs({ limit: 200 }).then(r => r.data.data),
  })
  const rfqs: any[] = rfqsData || []

  const { data: pricesData, isLoading: pricesLoading } = useQuery({
    queryKey: ['proc-prices'],
    queryFn: () => procurementApi.listPriceLists().then(r => r.data.data),
  })
  const prices: any[] = pricesData || []

  const { data: blanketsData, isLoading: blanketsLoading } = useQuery({
    queryKey: ['proc-blankets'],
    queryFn: () => procurementApi.listBlanketOrders().then(r => r.data.data),
  })
  const blankets: any[] = blanketsData || []

  const { data: scoresData, isLoading: scoresLoading } = useQuery({
    queryKey: ['proc-scores'],
    queryFn: () => procurementApi.listScorecards().then(r => r.data.data),
  })
  const scores: any[] = scoresData || []

  const { data: compareData, isLoading: compareLoading } = useQuery({
    queryKey: ['proc-compare', compareFor],
    queryFn: () => compareFor ? procurementApi.rfqComparison(compareFor).then(r => r.data.data) : Promise.resolve([]),
    enabled: !!compareFor,
  })
  const compareRows: any[] = compareData || []

  const { data: products } = useQuery({
    queryKey: ['products-all-proc'],
    queryFn: () => productsApi.list({ page_size: 200 }).then(r => r.data.data.items),
  })
  const { data: suppliers } = useQuery({
    queryKey: ['suppliers-all-proc'],
    queryFn: () => suppliersApi.list({ page_size: 200 }).then(r => r.data.data.items),
  })

  const productName = (id: string) => (products || []).find((p: any) => p.id === id)?.name || '—'
  const supplierName = (id: string) => (suppliers || []).find((s: any) => s.id === id)?.name || '—'

  const createRfq = useMutation({
    mutationFn: () => procurementApi.createRfq({
      title: rfqForm.title,
      required_date: rfqForm.required_date || null,
      lines: [{ product_id: rfqForm.product_id, quantity: Number(rfqForm.quantity) }],
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['proc-rfqs'] }); setRfqOpen(false); setRfqForm({ title: '', product_id: '', quantity: '', required_date: '' }) },
  })

  const upsertPrice = useMutation({
    mutationFn: () => procurementApi.upsertPriceList({
      supplier_id: priceForm.supplier_id, product_id: priceForm.product_id,
      price: Number(priceForm.price), currency: priceForm.currency,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['proc-prices'] }); setPriceOpen(false); setPriceForm({ supplier_id: '', product_id: '', price: '', currency: 'GEL' }) },
  })

  const createBlanket = useMutation({
    mutationFn: () => procurementApi.createBlanketOrder({
      supplier_id: blanketForm.supplier_id, title: blanketForm.title,
      lines: [{ product_id: blanketForm.product_id, quantity: Number(blanketForm.quantity), unit_price: Number(blanketForm.unit_price) }],
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['proc-blankets'] }); setBlanketOpen(false); setBlanketForm({ supplier_id: '', title: '', product_id: '', quantity: '', unit_price: '' }) },
  })

  const activateBlanket = useMutation({
    mutationFn: (id: string) => procurementApi.activateBlanketOrder(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proc-blankets'] }),
  })

  const upsertScore = useMutation({
    mutationFn: () => procurementApi.upsertScorecard({
      supplier_id: scoreForm.supplier_id, period: scoreForm.period,
      on_time_delivery_rate: scoreForm.on_time ? Number(scoreForm.on_time) : null,
      quality_rate: scoreForm.quality ? Number(scoreForm.quality) : null,
      price_index: scoreForm.price_index ? Number(scoreForm.price_index) : null,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['proc-scores'] }); setScoreOpen(false); setScoreForm({ supplier_id: '', period: '', on_time: '', quality: '', price_index: '' }) },
  })

  const awardRfq = useMutation({
    mutationFn: ({ rfqId, supplierId }: { rfqId: string; supplierId: string }) => procurementApi.awardRfq(rfqId, supplierId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proc-rfqs'] }),
  })

  const autoReplenish = useMutation({
    mutationFn: () => procurementApi.autoReplenish(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proc-rfqs'] }),
  })

  const statusBadge = (status: string) => {
    const map: Record<string, string> = {
      draft: 'bg-gray-100 text-gray-600 dark:bg-dark-100 dark:text-gray-400',
      sent: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
      receiving: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
      awarded: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
      active: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
      cancelled: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300',
    }
    return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${map[status] || 'bg-gray-100 text-gray-500'}`}>{t(status)}</span>
  }

  const rfqColumns = [
    { key: 'rfq_number', label: t('ნომერი'), priority: true, render: (r: any) => <span className="font-semibold text-gray-900 dark:text-gray-100 font-mono">{r.rfq_number}</span> },
    { key: 'title', label: t('სათაური'), render: (r: any) => <span className="text-sm">{r.title}</span> },
    { key: 'status', label: t('სტატუსი'), render: (r: any) => statusBadge(r.status) },
    { key: 'required_date', label: t('საჭიროა'), render: (r: any) => r.required_date ? <span className="font-mono text-sm">{new Date(r.required_date).toLocaleDateString('ka-GE')}</span> : '—' },
    { key: 'responses_count', label: t('შეთავაზებები'), render: (r: any) => <span className="font-mono">{r.responses_count}</span> },
    { key: 'actions', label: '', render: (r: any) => (
      <div className="flex gap-1">
        <button onClick={() => setCompareFor(r.id)} className="p-1.5 rounded-md text-gray-400 hover:text-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900/30" title={t('შედარება')}>
          <Scale size={15} />
        </button>
        {r.status === 'receiving' && (
          <button onClick={() => { const s = prompt(t('მომწოდებლის ID')); if (s) awardRfq.mutate({ rfqId: r.id, supplierId: s }) }}
            className="p-1.5 rounded-md text-gray-400 hover:text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-900/30" title={t('გადაცემა')}>
            <Award size={15} />
          </button>
        )}
      </div>) },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('შესყიდვები — Procurement')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('RFQ, შედარება, vendor ფასები, ჩარჩო შეთანხმებები, სკორკარდები')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setTab('rfq')} className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'rfq' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            <FileText size={14} className="inline mr-1" /> {t('RFQ')}
          </button>
          <button onClick={() => setTab('pricelist')} className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'pricelist' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            {t('Vendor ფასები')}
          </button>
          <button onClick={() => setTab('blanket')} className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'blanket' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            {t('ჩარჩო შეთანხმებები')}
          </button>
          <button onClick={() => setTab('scorecard')} className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'scorecard' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            {t('სკორკარდები')}
          </button>
          <button onClick={() => autoReplenish.mutate()} disabled={autoReplenish.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50">
            <Zap size={15} /> {t('ავტო-შევსება')}
          </button>
          <button onClick={() => {
            if (tab === 'rfq') setRfqOpen(true)
            else if (tab === 'pricelist') setPriceOpen(true)
            else if (tab === 'blanket') setBlanketOpen(true)
            else setScoreOpen(true)
          }}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700">
            <Plus size={15} /> {tab === 'rfq' ? t('ახალი RFQ') : tab === 'pricelist' ? t('ახალი ფასი') : tab === 'blanket' ? t('ახალი ჩარჩო შეთანხმება') : t('ახალი სკორკარდი')}
          </button>
        </div>
      </div>

      {tab === 'rfq' && (
        <DataTable columns={rfqColumns} data={rfqs} isLoading={rfqsLoading} emptyMessage={t('RFQ არ არის')} />
      )}

      {tab === 'pricelist' && (
        <DataTable
          columns={[
            { key: 'supplier_name', label: t('მომწოდებელი'), priority: true, render: (p: any) => <span className="font-semibold text-gray-900 dark:text-gray-100">{p.supplier_name}</span> },
            { key: 'product_name', label: t('პროდუქტი'), render: (p: any) => <span className="text-sm">{p.product_name}</span> },
            { key: 'price', label: t('ფასი'), render: (p: any) => <span className="font-mono font-semibold">{p.price} {p.currency}</span> },
            { key: 'valid_to', label: t('მოქმედებს'), render: (p: any) => p.valid_to ? <span className="font-mono text-sm">{new Date(p.valid_to).toLocaleDateString('ka-GE')}</span> : '—' },
            { key: 'is_active', label: t('სტატუსი'), render: (p: any) => p.is_active ? statusBadge('active') : statusBadge('cancelled') },
          ]}
          data={prices} isLoading={pricesLoading} emptyMessage={t('Vendor ფასები არ არის')} />
      )}

      {tab === 'blanket' && (
        <DataTable
          columns={[
            { key: 'blanket_number', label: t('ნომერი'), priority: true, render: (b: any) => <span className="font-semibold text-gray-900 dark:text-gray-100 font-mono">{b.blanket_number}</span> },
            { key: 'title', label: t('სათაური'), render: (b: any) => <span className="text-sm">{b.title}</span> },
            { key: 'supplier_name', label: t('მომწოდებელი'), render: (b: any) => <span className="text-sm">{b.supplier_name}</span> },
            { key: 'status', label: t('სტატუსი'), render: (b: any) => statusBadge(b.status) },
            { key: 'end_date', label: t('ვადა'), render: (b: any) => b.end_date ? <span className="font-mono text-sm">{new Date(b.end_date).toLocaleDateString('ka-GE')}</span> : '—' },
            { key: 'actions', label: '', render: (b: any) => b.status === 'draft' && (
              <button onClick={() => activateBlanket.mutate(b.id)} className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 text-white hover:bg-emerald-700">
                {t('აქტივაცია')}
              </button>
            ) },
          ]}
          data={blankets} isLoading={blanketsLoading} emptyMessage={t('ჩარჩო შეთანხმებები არ არის')} />
      )}

      {tab === 'scorecard' && (
        <DataTable
          columns={[
            { key: 'supplier_name', label: t('მომწოდებელი'), priority: true, render: (s: any) => <span className="font-semibold text-gray-900 dark:text-gray-100">{s.supplier_name}</span> },
            { key: 'period', label: t('პერიოდი'), render: (s: any) => <span className="font-mono text-sm">{s.period}</span> },
            { key: 'on_time_delivery_rate', label: t('დროულად %'), render: (s: any) => <span className="font-mono">{s.on_time_delivery_rate ?? '—'}</span> },
            { key: 'quality_rate', label: t('ხარისხი %'), render: (s: any) => <span className="font-mono">{s.quality_rate ?? '—'}</span> },
            { key: 'overall_score', label: t('საერთო'), render: (s: any) => s.overall_score
              ? <span className={`font-mono font-semibold ${s.overall_score >= 80 ? 'text-emerald-600 dark:text-emerald-400' : s.overall_score >= 60 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'}`}>{s.overall_score}</span> : '—' },
          ]}
          data={scores} isLoading={scoresLoading} emptyMessage={t('სკორკარდები არ არის')} />
      )}

      <Modal open={compareFor !== null} onClose={() => setCompareFor(null)} title={t('შეთავაზებების შედარება')}>
        <div className="space-y-4">
          {compareLoading ? (
            <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('იტვირთება...')}</p>
          ) : compareRows.length === 0 ? (
            <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('შეთავაზებები არ არის')}</p>
          ) : (
            compareRows.map((row: any, i: number) => (
              <div key={i} className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-gray-900 dark:text-gray-100">{productName(row.product_id)}</span>
                  <span className="text-sm text-brandgray-500 dark:text-gray-400">{t('რაოდენობა')}: {row.quantity}</span>
                </div>
                {row.offers.length === 0 ? (
                  <p className="text-xs text-brandgray-400">{t('შეთავაზებები არ არის')}</p>
                ) : (
                  <div className="space-y-1">
                    {row.offers.map((o: any, j: number) => (
                      <div key={j} className={`flex items-center justify-between rounded-lg px-3 py-1.5 text-sm ${j === 0 ? 'bg-emerald-50 dark:bg-emerald-900/20' : 'bg-brandgray-50 dark:bg-dark-100'}`}>
                        <span className="font-medium">{o.supplier_name}</span>
                        <span className="font-mono font-semibold">{o.unit_price} {o.currency}</span>
                        {o.delivery_days && <span className="text-xs text-brandgray-500">{o.delivery_days} {t('დღე')}</span>}
                        {j === 0 && <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">✓ {t('საუკეთესო')}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </Modal>

      <Modal open={rfqOpen} onClose={() => setRfqOpen(false)} title={t('ახალი RFQ')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სათაური')}</label>
            <input className={inputCls} value={rfqForm.title} onChange={e => setRfqForm({ ...rfqForm, title: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტი')}</label>
            <select className={inputCls} value={rfqForm.product_id} onChange={e => setRfqForm({ ...rfqForm, product_id: e.target.value })}>
              <option value="">—</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('რაოდენობა')}</label>
              <input type="number" step="0.001" className={inputCls} value={rfqForm.quantity} onChange={e => setRfqForm({ ...rfqForm, quantity: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('საჭიროა')}</label>
              <input type="date" className={inputCls} value={rfqForm.required_date} onChange={e => setRfqForm({ ...rfqForm, required_date: e.target.value })} />
            </div>
          </div>
          <button onClick={() => createRfq.mutate()} disabled={createRfq.isPending || !rfqForm.title || !rfqForm.product_id || !rfqForm.quantity}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={priceOpen} onClose={() => setPriceOpen(false)} title={t('ახალი vendor ფასი')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მომწოდებელი')}</label>
            <select className={inputCls} value={priceForm.supplier_id} onChange={e => setPriceForm({ ...priceForm, supplier_id: e.target.value })}>
              <option value="">—</option>
              {(suppliers || []).map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტი')}</label>
            <select className={inputCls} value={priceForm.product_id} onChange={e => setPriceForm({ ...priceForm, product_id: e.target.value })}>
              <option value="">—</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ფასი')}</label>
              <input type="number" step="0.0001" className={inputCls} value={priceForm.price} onChange={e => setPriceForm({ ...priceForm, price: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ვალუტა')}</label>
              <select className={inputCls} value={priceForm.currency} onChange={e => setPriceForm({ ...priceForm, currency: e.target.value })}>
                <option value="GEL">GEL</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </select>
            </div>
          </div>
          <button onClick={() => upsertPrice.mutate()} disabled={upsertPrice.isPending || !priceForm.supplier_id || !priceForm.product_id || !priceForm.price}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={blanketOpen} onClose={() => setBlanketOpen(false)} title={t('ახალი ჩარჩო შეთანხმება')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მომწოდებელი')}</label>
            <select className={inputCls} value={blanketForm.supplier_id} onChange={e => setBlanketForm({ ...blanketForm, supplier_id: e.target.value })}>
              <option value="">—</option>
              {(suppliers || []).map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სათაური')}</label>
            <input className={inputCls} value={blanketForm.title} onChange={e => setBlanketForm({ ...blanketForm, title: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტი')}</label>
            <select className={inputCls} value={blanketForm.product_id} onChange={e => setBlanketForm({ ...blanketForm, product_id: e.target.value })}>
              <option value="">—</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('რაოდენობა')}</label>
              <input type="number" step="0.001" className={inputCls} value={blanketForm.quantity} onChange={e => setBlanketForm({ ...blanketForm, quantity: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ერთეულის ფასი')}</label>
              <input type="number" step="0.0001" className={inputCls} value={blanketForm.unit_price} onChange={e => setBlanketForm({ ...blanketForm, unit_price: e.target.value })} />
            </div>
          </div>
          <button onClick={() => createBlanket.mutate()} disabled={createBlanket.isPending || !blanketForm.supplier_id || !blanketForm.title || !blanketForm.product_id || !blanketForm.quantity || !blanketForm.unit_price}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={scoreOpen} onClose={() => setScoreOpen(false)} title={t('ახალი სკორკარდი')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მომწოდებელი')}</label>
            <select className={inputCls} value={scoreForm.supplier_id} onChange={e => setScoreForm({ ...scoreForm, supplier_id: e.target.value })}>
              <option value="">—</option>
              {(suppliers || []).map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პერიოდი (YYYY-MM)')}</label>
            <input className={inputCls} value={scoreForm.period} onChange={e => setScoreForm({ ...scoreForm, period: e.target.value })} placeholder="2026-08" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დროულად %')}</label>
              <input type="number" step="0.01" className={inputCls} value={scoreForm.on_time} onChange={e => setScoreForm({ ...scoreForm, on_time: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ხარისხი %')}</label>
              <input type="number" step="0.01" className={inputCls} value={scoreForm.quality} onChange={e => setScoreForm({ ...scoreForm, quality: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ფასის ინდექსი')}</label>
              <input type="number" step="0.01" className={inputCls} value={scoreForm.price_index} onChange={e => setScoreForm({ ...scoreForm, price_index: e.target.value })} />
            </div>
          </div>
          <button onClick={() => upsertScore.mutate()} disabled={upsertScore.isPending || !scoreForm.supplier_id || !scoreForm.period}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
