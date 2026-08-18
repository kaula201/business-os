import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Scale, Award, Zap, FileText, Gavel, BarChart3 } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { productsApi, procurementApi, suppliersApi, contractsApi } from '../services/api'

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function ProcurementPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'rfq' | 'compare' | 'pricelist' | 'blanket' | 'scorecard' | 'contracts' | 'tender' | 'analytics'>('rfq')
  const [rfqOpen, setRfqOpen] = useState(false)
  const [priceOpen, setPriceOpen] = useState(false)
  const [blanketOpen, setBlanketOpen] = useState(false)
  const [scoreOpen, setScoreOpen] = useState(false)
  const [contractOpen, setContractOpen] = useState(false)
  const [tenderOpen, setTenderOpen] = useState(false)
  const [responseFor, setResponseFor] = useState<any | null>(null)
  const [compareFor, setCompareFor] = useState<string | null>(null)
  const [tenderCompareFor, setTenderCompareFor] = useState<string | null>(null)
  const [bidFor, setBidFor] = useState<any | null>(null)
  const [trendFor, setTrendFor] = useState<any | null>(null)
  const [replenishResult, setReplenishResult] = useState<any | null>(null)
  const [rfqForm, setRfqForm] = useState({ title: '', product_id: '', quantity: '', required_date: '' })
  const [priceForm, setPriceForm] = useState({ supplier_id: '', product_id: '', price: '', currency: 'GEL' })
  const [blanketForm, setBlanketForm] = useState({ supplier_id: '', title: '', product_id: '', quantity: '', unit_price: '' })
  const [scoreForm, setScoreForm] = useState({ supplier_id: '', period: '', on_time: '', quality: '', price_index: '' })
  const [responseForm, setResponseForm] = useState({ supplier_id: '', unit_price: '', delivery_days: '' })
  const [contractForm, setContractForm] = useState({ title: '', counterparty: '', start_date: '', end_date: '', value: '' })
  const [tenderForm, setTenderForm] = useState({ title: '', product_id: '', quantity: '', budget: '', required_date: '' })
  const [bidForm, setBidForm] = useState({ supplier_id: '', unit_price: '', delivery_days: '' })

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

  const { data: contractsData, isLoading: contractsLoading } = useQuery({
    queryKey: ['proc-contracts'],
    queryFn: () => contractsApi.list({ page_size: 100 }).then(r => r.data.data.items),
  })
  const contracts: any[] = contractsData || []

  const { data: compareData, isLoading: compareLoading } = useQuery({
    queryKey: ['proc-compare', compareFor],
    queryFn: () => compareFor ? procurementApi.rfqComparison(compareFor).then(r => r.data.data) : Promise.resolve([]),
    enabled: !!compareFor,
  })
  const compareRows: any[] = compareData || []

  const { data: tendersData, isLoading: tendersLoading } = useQuery({
    queryKey: ['proc-tenders'],
    queryFn: () => procurementApi.listTenders({ limit: 200 }).then(r => r.data.data),
  })
  const tenders: any[] = tendersData || []

  const { data: analyticsData, isLoading: analyticsLoading } = useQuery({
    queryKey: ['proc-analytics'],
    queryFn: () => procurementApi.vendorAnalytics().then(r => r.data.data),
  })
  const analytics: any[] = analyticsData || []

  const { data: tenderCompareData, isLoading: tenderCompareLoading } = useQuery({
    queryKey: ['proc-tender-compare', tenderCompareFor],
    queryFn: () => tenderCompareFor ? procurementApi.tenderComparison(tenderCompareFor).then(r => r.data.data) : Promise.resolve([]),
    enabled: !!tenderCompareFor,
  })
  const tenderCompareRows: any[] = tenderCompareData || []

  const { data: trendData, isLoading: trendLoading } = useQuery({
    queryKey: ['proc-price-trend', trendFor?.supplier_id],
    queryFn: () => trendFor ? procurementApi.priceTrend({ supplier_id: trendFor.supplier_id, limit: 200 }).then(r => r.data.data) : Promise.resolve([]),
    enabled: !!trendFor,
  })
  const trendRows: any[] = trendData || []

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
    onSuccess: (data) => { setReplenishResult(data.data.data); qc.invalidateQueries({ queryKey: ['proc-rfqs'] }) },
  })

  const autoCalcScore = useMutation({
    mutationFn: () => procurementApi.autoCalculateScorecards(new Date().toISOString().slice(0, 7)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proc-scores'] }),
  })

  const submitResponse = useMutation({
    mutationFn: () => {
      const rfqLineId = responseFor?.lines?.[0]?.id
      return procurementApi.submitRfqResponse(responseFor.id, {
        supplier_id: responseForm.supplier_id,
        delivery_days: responseForm.delivery_days ? Number(responseForm.delivery_days) : null,
        lines: [{ rfq_line_id: rfqLineId, unit_price: Number(responseForm.unit_price), currency: 'GEL' }],
      })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['proc-rfqs'] }); setResponseFor(null); setResponseForm({ supplier_id: '', unit_price: '', delivery_days: '' }) },
  })

  const createContract = useMutation({
    mutationFn: () => contractsApi.create({
      title: contractForm.title, counterparty: contractForm.counterparty,
      start_date: contractForm.start_date || null, end_date: contractForm.end_date || null,
      value: contractForm.value ? Number(contractForm.value) : null,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['proc-contracts'] }); setContractOpen(false); setContractForm({ title: '', counterparty: '', start_date: '', end_date: '', value: '' }) },
  })

  const createTender = useMutation({
    mutationFn: () => procurementApi.createTender({
      title: tenderForm.title,
      required_date: tenderForm.required_date || null,
      budget_amount: tenderForm.budget ? Number(tenderForm.budget) : null,
      lines: [{ product_id: tenderForm.product_id, quantity: Number(tenderForm.quantity) }],
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['proc-tenders'] }); setTenderOpen(false); setTenderForm({ title: '', product_id: '', quantity: '', budget: '', required_date: '' }) },
  })

  const publishTender = useMutation({
    mutationFn: (id: string) => procurementApi.publishTender(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proc-tenders'] }),
  })

  const submitTenderBid = useMutation({
    mutationFn: () => {
      const tenderLineId = bidFor?.lines?.[0]?.id
      return procurementApi.submitTenderBid(bidFor.id, {
        supplier_id: bidForm.supplier_id,
        delivery_days: bidForm.delivery_days ? Number(bidForm.delivery_days) : null,
        lines: [{ tender_line_id: tenderLineId, product_id: bidFor?.lines?.[0]?.product_id, unit_price: Number(bidForm.unit_price), currency: 'GEL' }],
      })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['proc-tenders'] }); setBidFor(null); setBidForm({ supplier_id: '', unit_price: '', delivery_days: '' }) },
  })

  const awardTender = useMutation({
    mutationFn: ({ tenderId, supplierId }: { tenderId: string; supplierId: string }) => procurementApi.awardTender(tenderId, supplierId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proc-tenders'] }),
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
        {r.status !== 'awarded' && r.status !== 'cancelled' && (
          <button onClick={() => { setResponseFor(r); setResponseForm({ supplier_id: '', unit_price: '', delivery_days: '' }) }}
            className="p-1.5 rounded-md text-gray-400 hover:text-blue-700 hover:bg-blue-50 dark:hover:bg-blue-900/30" title={t('შეთავაზების შეტანა')}>
            <FileText size={15} />
          </button>
        )}
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
          <button onClick={() => setTab('contracts')} className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'contracts' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            {t('ხელშეკრულებები')}
          </button>
          <button onClick={() => setTab('tender')} className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'tender' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            <Gavel size={14} className="inline mr-1" /> {t('ტენდერები')}
          </button>
          <button onClick={() => setTab('analytics')} className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'analytics' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            <BarChart3 size={14} className="inline mr-1" /> {t('Vendor ანალიტიკა')}
          </button>
          <button onClick={() => autoReplenish.mutate()} disabled={autoReplenish.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50">
            <Zap size={15} /> {t('ავტო-შევსება')}
          </button>
          <button onClick={() => {
            if (tab === 'rfq') setRfqOpen(true)
            else if (tab === 'pricelist') setPriceOpen(true)
            else if (tab === 'blanket') setBlanketOpen(true)
            else if (tab === 'scorecard') setScoreOpen(true)
            else if (tab === 'tender') setTenderOpen(true)
            else setContractOpen(true)
          }}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700">
            <Plus size={15} /> {tab === 'rfq' ? t('ახალი RFQ') : tab === 'pricelist' ? t('ახალი ფასი') : tab === 'blanket' ? t('ახალი ჩარჩო შეთანხმება') : tab === 'scorecard' ? t('ახალი სკორკარდი') : tab === 'tender' ? t('ახალი ტენდერი') : t('ახალი ხელშეკრულება')}
          </button>
        </div>
      </div>

      {replenishResult && (
        <div className="rounded-lg border border-emerald-200 dark:border-emerald-900/40 bg-emerald-50 dark:bg-emerald-900/10 p-4">
          <h3 className="text-sm font-semibold text-emerald-800 dark:text-emerald-300 mb-2">
            {replenishResult.created ? `${t('შექმნილია')}: ${replenishResult.order_number} (${replenishResult.items?.length || 0} ${t('ხაზი')})` : t('შევსება არ არის საჭირო')}
          </h3>
          {replenishResult.items?.length > 0 && (
            <div className="space-y-1">
              {replenishResult.items.map((it: any, i: number) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span className="font-medium">{productName(it.product_id)}</span>
                  <span className="font-mono">{it.quantity}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

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
            { key: 'actions', label: '', render: (p: any) => (
              <button onClick={() => setTrendFor(p)} className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-700">
                {t('ისტორია')}
              </button>
            ) },
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
        <>
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
          <div className="mt-3">
            <button onClick={() => autoCalcScore.mutate()} disabled={autoCalcScore.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50">
              <Zap size={15} /> {t('ავტომატური გამოთვლა')}
            </button>
          </div>
        </>
      )}

      {tab === 'contracts' && (
        <DataTable
          columns={[
            { key: 'title', label: t('სათაური'), priority: true, render: (c: any) => <span className="font-semibold text-gray-900 dark:text-gray-100">{c.title}</span> },
            { key: 'counterparty', label: t('კონტრაგენტი'), render: (c: any) => <span className="text-sm">{c.counterparty}</span> },
            { key: 'start_date', label: t('დაწყება'), render: (c: any) => c.start_date ? <span className="font-mono text-sm">{new Date(c.start_date).toLocaleDateString('ka-GE')}</span> : '—' },
            { key: 'end_date', label: t('დასრულება'), render: (c: any) => c.end_date ? <span className="font-mono text-sm">{new Date(c.end_date).toLocaleDateString('ka-GE')}</span> : '—' },
            { key: 'value', label: t('თანხა'), render: (c: any) => c.value ? <span className="font-mono font-semibold">{c.value} ₾</span> : '—' },
            { key: 'status', label: t('სტატუსი'), render: (c: any) => statusBadge(c.status) },
          ]}
          data={contracts} isLoading={contractsLoading} emptyMessage={t('ხელშეკრულებები არ არის')} />
      )}

      {tab === 'tender' && (
        <DataTable
          columns={[
            { key: 'tender_number', label: t('ნომერი'), priority: true, render: (r: any) => <span className="font-semibold text-gray-900 dark:text-gray-100 font-mono">{r.tender_number}</span> },
            { key: 'title', label: t('სათაური'), render: (r: any) => <span className="text-sm">{r.title}</span> },
            { key: 'status', label: t('სტატუსი'), render: (r: any) => statusBadge(r.status) },
            { key: 'budget_amount', label: t('ბიუჯეტი'), render: (r: any) => r.budget_amount ? <span className="font-mono font-semibold">{r.budget_amount} {r.currency}</span> : '—' },
            { key: 'bids_count', label: t('შეთავაზებები'), render: (r: any) => <span className="font-mono">{r.bids_count}</span> },
            { key: 'actions', label: '', render: (r: any) => (
              <div className="flex gap-1">
                <button onClick={() => setTenderCompareFor(r.id)} className="p-1.5 rounded-md text-gray-400 hover:text-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900/30" title={t('შედარება')}>
                  <Scale size={15} />
                </button>
                {r.status === 'draft' && (
                  <button onClick={() => publishTender.mutate(r.id)} className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-blue-600 text-white hover:bg-blue-700">{t('გამოქვეყნება')}</button>
                )}
                {(r.status === 'bidding' || r.status === 'evaluating') && (
                  <>
                    <button onClick={() => { setBidFor(r); setBidForm({ supplier_id: '', unit_price: '', delivery_days: '' }) }} className="p-1.5 rounded-md text-gray-400 hover:text-blue-700 hover:bg-blue-50 dark:hover:bg-blue-900/30" title={t('შეთავაზების შეტანა')}>
                      <FileText size={15} />
                    </button>
                    <button onClick={() => { const s = prompt(t('მომწოდებლის ID')); if (s) awardTender.mutate({ tenderId: r.id, supplierId: s }) }} className="p-1.5 rounded-md text-gray-400 hover:text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-900/30" title={t('გადაცემა')}>
                      <Award size={15} />
                    </button>
                  </>
                )}
              </div>) },
          ]}
          data={tenders} isLoading={tendersLoading} emptyMessage={t('ტენდერები არ არის')} />
      )}

      {tab === 'analytics' && (
        <DataTable
          columns={[
            { key: 'supplier_name', label: t('მომწოდებელი'), priority: true, render: (s: any) => <span className="font-semibold text-gray-900 dark:text-gray-100">{s.supplier_name}</span> },
            { key: 'total_spend', label: t('ჯამური ხარჯი'), render: (s: any) => <span className="font-mono font-semibold">{s.total_spend.toLocaleString('ka-GE')} ₾</span> },
            { key: 'invoice_count', label: t('ინვოისები'), render: (s: any) => <span className="font-mono">{s.invoice_count}</span> },
            { key: 'on_time_delivery_rate', label: t('დროულად %'), render: (s: any) => s.on_time_delivery_rate != null ? <span className="font-mono">{s.on_time_delivery_rate}%</span> : '—' },
            { key: 'quality_rate', label: t('ხარისხი %'), render: (s: any) => s.quality_rate != null ? <span className="font-mono">{s.quality_rate}%</span> : '—' },
            { key: 'overall_score', label: t('საერთო'), render: (s: any) => s.overall_score
              ? <span className={`font-mono font-semibold ${s.overall_score >= 80 ? 'text-emerald-600 dark:text-emerald-400' : s.overall_score >= 60 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'}`}>{s.overall_score}</span> : '—' },
          ]}
          data={analytics} isLoading={analyticsLoading} emptyMessage={t('Vendor ანალიტიკა არ არის')} />
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

      <Modal open={!!responseFor} onClose={() => setResponseFor(null)} title={`${t('შეთავაზების შეტანა')} — ${responseFor?.rfq_number || ''}`}>
        {responseFor && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მომწოდებელი')}</label>
              <select className={inputCls} value={responseForm.supplier_id} onChange={e => setResponseForm({ ...responseForm, supplier_id: e.target.value })}>
                <option value="">—</option>
                {(suppliers || []).map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ერთეულის ფასი')}</label>
                <input type="number" step="0.0001" className={inputCls} value={responseForm.unit_price} onChange={e => setResponseForm({ ...responseForm, unit_price: e.target.value })} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მიწოდების დღეები')}</label>
                <input type="number" className={inputCls} value={responseForm.delivery_days} onChange={e => setResponseForm({ ...responseForm, delivery_days: e.target.value })} />
              </div>
            </div>
            <button onClick={() => submitResponse.mutate()} disabled={submitResponse.isPending || !responseForm.supplier_id || !responseForm.unit_price}
              className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
              {t('შენახვა')}
            </button>
          </div>
        )}
      </Modal>

      <Modal open={contractOpen} onClose={() => setContractOpen(false)} title={t('ახალი ხელშეკრულება')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სათაური')}</label>
            <input className={inputCls} value={contractForm.title} onChange={e => setContractForm({ ...contractForm, title: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('კონტრაგენტი')}</label>
            <input className={inputCls} value={contractForm.counterparty} onChange={e => setContractForm({ ...contractForm, counterparty: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დაწყება')}</label>
              <input type="date" className={inputCls} value={contractForm.start_date} onChange={e => setContractForm({ ...contractForm, start_date: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დასრულება')}</label>
              <input type="date" className={inputCls} value={contractForm.end_date} onChange={e => setContractForm({ ...contractForm, end_date: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('თანხა')}</label>
            <input type="number" step="0.01" className={inputCls} value={contractForm.value} onChange={e => setContractForm({ ...contractForm, value: e.target.value })} />
          </div>
          <button onClick={() => createContract.mutate()} disabled={createContract.isPending || !contractForm.title || !contractForm.counterparty}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={tenderOpen} onClose={() => setTenderOpen(false)} title={t('ახალი ტენდერი')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სათაური')}</label>
            <input className={inputCls} value={tenderForm.title} onChange={e => setTenderForm({ ...tenderForm, title: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტი')}</label>
            <select className={inputCls} value={tenderForm.product_id} onChange={e => setTenderForm({ ...tenderForm, product_id: e.target.value })}>
              <option value="">—</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('რაოდენობა')}</label>
              <input type="number" step="0.001" className={inputCls} value={tenderForm.quantity} onChange={e => setTenderForm({ ...tenderForm, quantity: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ბიუჯეტი')}</label>
              <input type="number" step="0.01" className={inputCls} value={tenderForm.budget} onChange={e => setTenderForm({ ...tenderForm, budget: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('საჭიროა')}</label>
            <input type="date" className={inputCls} value={tenderForm.required_date} onChange={e => setTenderForm({ ...tenderForm, required_date: e.target.value })} />
          </div>
          <button onClick={() => createTender.mutate()} disabled={createTender.isPending || !tenderForm.title || !tenderForm.product_id || !tenderForm.quantity}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={!!bidFor} onClose={() => setBidFor(null)} title={`${t('შეთავაზების შეტანა')} — ${bidFor?.tender_number || ''}`}>
        {bidFor && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მომწოდებელი')}</label>
              <select className={inputCls} value={bidForm.supplier_id} onChange={e => setBidForm({ ...bidForm, supplier_id: e.target.value })}>
                <option value="">—</option>
                {(suppliers || []).map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ერთეულის ფასი')}</label>
                <input type="number" step="0.0001" className={inputCls} value={bidForm.unit_price} onChange={e => setBidForm({ ...bidForm, unit_price: e.target.value })} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მიწოდების დღეები')}</label>
                <input type="number" className={inputCls} value={bidForm.delivery_days} onChange={e => setBidForm({ ...bidForm, delivery_days: e.target.value })} />
              </div>
            </div>
            <button onClick={() => submitTenderBid.mutate()} disabled={submitTenderBid.isPending || !bidForm.supplier_id || !bidForm.unit_price}
              className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
              {t('შენახვა')}
            </button>
          </div>
        )}
      </Modal>

      <Modal open={tenderCompareFor !== null} onClose={() => setTenderCompareFor(null)} title={t('ტენდერის შეთავაზებების შედარება')}>
        <div className="space-y-3">
          {tenderCompareLoading ? (
            <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('იტვირთება...')}</p>
          ) : tenderCompareRows.length === 0 ? (
            <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('შეთავაზებები არ არის')}</p>
          ) : (
            tenderCompareRows.map((row: any, i: number) => (
              <div key={i} className={`flex items-center justify-between rounded-lg px-4 py-3 text-sm ${i === 0 ? 'bg-emerald-50 dark:bg-emerald-900/20' : 'bg-brandgray-50 dark:bg-dark-100'}`}>
                <div>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{row.supplier_name}</span>
                  {row.delivery_days && <span className="ml-2 text-xs text-brandgray-500">{row.delivery_days} {t('დღე')}</span>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono font-semibold">{row.total_amount} {row.currency}</span>
                  {i === 0 && <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">✓ {t('საუკეთესო')}</span>}
                </div>
              </div>
            ))
          )}
        </div>
      </Modal>

      <Modal open={!!trendFor} onClose={() => setTrendFor(null)} title={`${t('ფასის ისტორია')} — ${trendFor?.supplier_name || ''}`}>
        <div className="space-y-3">
          {trendLoading ? (
            <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('იტვირთება...')}</p>
          ) : trendRows.length === 0 ? (
            <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('ისტორია არ არის')}</p>
          ) : (
            trendRows.map((row: any, i: number) => (
              <div key={i} className="flex items-center justify-between rounded-lg px-4 py-3 text-sm bg-brandgray-50 dark:bg-dark-100">
                <div>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{row.product_name}</span>
                  <span className="ml-2 text-xs text-brandgray-500">{new Date(row.changed_at).toLocaleDateString('ka-GE')}</span>
                </div>
                <span className="font-mono font-semibold">{row.price} {row.currency}</span>
              </div>
            ))
          )}
        </div>
      </Modal>
    </div>
  )
}
