import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  Check, CheckCircle2, ChevronRight, Download, Eye, FileSpreadsheet,
  FileText, Pencil, Plus, Printer, Search, ShieldCheck, Trash2,
} from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { invoicesApi } from '../services/api'
import type { CustomerInvoice, CustomerInvoiceDraftUpdate, CustomerInvoiceSummary } from '../types'

function money(value: number, currency = 'GEL') {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency }).format(value)
}

function errorText(error: any) {
  return error?.response?.data?.detail || 'ოპერაცია ვერ შესრულდა'
}

async function saveBlob(request: Promise<any>, filename: string, mime: string) {
  const response = await request
  const url = window.URL.createObjectURL(new Blob([response.data], { type: mime }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
}

function draftFromInvoice(invoice: CustomerInvoice): CustomerInvoiceDraftUpdate {
  return {
    invoice_date: invoice.invoice_date,
    due_date: invoice.due_date,
    currency: invoice.currency,
    seller_name: invoice.seller_name,
    seller_identification_code: invoice.seller_identification_code,
    seller_address: invoice.seller_address || '',
    seller_phone: invoice.seller_phone || '',
    seller_email: invoice.seller_email || '',
    client_name: invoice.client_name,
    client_identification_code: invoice.client_identification_code,
    client_address: invoice.client_address || '',
    notes: invoice.notes || '',
    items: invoice.items.map(item => ({
      product_name: item.product_name,
      quantity: item.quantity,
      unit_price: item.unit_price,
      discount_percent: item.discount_percent,
      vat_rate: item.vat_rate,
    })),
  }
}

function StatusSteps({ issued = false }: { issued?: boolean }) {
  const steps = [
    { label: 'შევსება', done: true },
    { label: 'დადასტურება', done: issued },
    { label: 'ჩამოტვირთვა', done: issued },
  ]
  return (
    <div className="flex items-center rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-dark-50 dark:bg-dark-200">
      {steps.map((step, index) => (
        <div key={step.label} className="flex flex-1 items-center last:flex-none">
          <div className="flex items-center gap-2">
            <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${step.done ? 'bg-primary-500 text-white' : 'bg-gray-100 text-gray-400 dark:bg-dark-100'}`}>
              {step.done ? <Check size={15} /> : index + 1}
            </span>
            <span className={`hidden text-sm sm:inline ${step.done ? 'font-medium text-gray-900' : 'text-gray-400'}`}>{step.label}</span>
          </div>
          {index < steps.length - 1 && <div className={`mx-3 h-px flex-1 ${steps[index + 1].done ? 'bg-primary-300' : 'bg-gray-200 dark:bg-dark-50'}`} />}
        </div>
      ))}
    </div>
  )
}

function PartyCard({ title, name, code, address }: { title: string; name: string; code: string; address?: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50/70 p-4 dark:border-dark-50 dark:bg-dark-100">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</div>
      <div className="font-semibold text-gray-900">{name}</div>
      <div className="mt-1 text-sm text-gray-500">ს/კ {code}</div>
      {address && <div className="mt-2 text-sm text-gray-600">{address}</div>}
    </div>
  )
}

export default function InvoicesPage() {
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') || '')
  const [statusFilter, setStatusFilter] = useState<'all' | 'draft' | 'issued'>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [confirmIssue, setConfirmIssue] = useState(false)
  const [draft, setDraft] = useState<CustomerInvoiceDraftUpdate | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [issuing, setIssuing] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewNumber, setPreviewNumber] = useState('')
  const [previewLoadingId, setPreviewLoadingId] = useState<string | null>(null)

  useEffect(() => () => {
    if (previewUrl) window.URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  const listQuery = useQuery({
    queryKey: ['customer-invoices', search],
    queryFn: () => invoicesApi.list({
      page_size: 100,
      search: search || undefined,
    }).then(response => response.data.data),
  })
  const detailQuery = useQuery<CustomerInvoice>({
    queryKey: ['customer-invoice', selectedId],
    queryFn: () => invoicesApi.get(selectedId!).then(response => response.data.data),
    enabled: !!selectedId,
  })
  const allInvoices: CustomerInvoiceSummary[] = listQuery.data?.items || []
  const invoices = statusFilter === 'all' ? allInvoices : allInvoices.filter(invoice => invoice.status === statusFilter)
  const selected = detailQuery.data
  const draftCount = allInvoices.filter(invoice => invoice.status === 'draft').length
  const issuedInvoices = allInvoices.filter(invoice => invoice.status === 'issued')
  const issuedTotal = issuedInvoices.reduce((sum, invoice) => sum + invoice.total, 0)

  const refresh = async (id?: string) => {
    await queryClient.invalidateQueries({ queryKey: ['customer-invoices'] })
    if (id) await queryClient.invalidateQueries({ queryKey: ['customer-invoice', id] })
  }

  const openEditor = (invoice: CustomerInvoice) => {
    setSelectedId(invoice.id)
    setDraft(draftFromInvoice(invoice))
    setConfirmIssue(false)
    setEditorOpen(true)
    setError('')
    setMessage('')
  }

  const openInvoice = async (invoice: CustomerInvoiceSummary) => {
    setSelectedId(invoice.id)
    if (invoice.status === 'draft') {
      try {
        const response = await invoicesApi.get(invoice.id)
        openEditor(response.data.data)
      } catch (openError) {
        setError(errorText(openError))
      }
    }
  }

  const handlePreview = async (invoice: CustomerInvoiceSummary | CustomerInvoice) => {
    try {
      setError('')
      setPreviewLoadingId(invoice.id)
      const response = await invoicesApi.preview(invoice.id)
      setPreviewNumber(invoice.invoice_number)
      setPreviewUrl(window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' })))
    } catch (previewError) {
      setError(errorText(previewError))
    } finally {
      setPreviewLoadingId(null)
    }
  }

  const handleExport = async (invoice: CustomerInvoiceSummary | CustomerInvoice, format: 'pdf' | 'word' | 'excel') => {
    try {
      setError('')
      if (format === 'pdf') await saveBlob(invoicesApi.download(invoice.id), `${invoice.invoice_number}.pdf`, 'application/pdf')
      if (format === 'word') await saveBlob(invoicesApi.downloadWord(invoice.id), `${invoice.invoice_number}.docx`, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
      if (format === 'excel') await saveBlob(invoicesApi.downloadExcel(invoice.id), `${invoice.invoice_number}.xlsx`, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    } catch (downloadError) {
      setError(errorText(downloadError))
    }
  }

  const saveCurrentDraft = async () => {
    if (!draft || !selected) return null
    setSaving(true)
    setError('')
    try {
      const response = await invoicesApi.updateDraft(selected.id, draft)
      const invoice = response.data.data as CustomerInvoice
      setDraft(draftFromInvoice(invoice))
      setMessage('ცვლილებები შენახულია')
      await refresh(invoice.id)
      return invoice
    } catch (saveError) {
      setError(errorText(saveError))
      return null
    } finally {
      setSaving(false)
    }
  }

  const previewCurrentDraft = async () => {
    const invoice = await saveCurrentDraft()
    if (!invoice) return
    setEditorOpen(false)
    await handlePreview(invoice)
  }

  const issueCurrentDraft = async () => {
    const saved = await saveCurrentDraft()
    if (!saved) return
    setIssuing(true)
    setError('')
    try {
      const response = await invoicesApi.issue(saved.id)
      const invoice = response.data.data as CustomerInvoice
      setEditorOpen(false)
      setConfirmIssue(false)
      setDraft(null)
      setMessage('ინვოისი დადასტურებულია — ჩამოტვირთვა უკვე შესაძლებელია')
      await refresh(invoice.id)
    } catch (issueError) {
      setError(errorText(issueError))
    } finally {
      setIssuing(false)
    }
  }

  const updateItem = (index: number, field: keyof CustomerInvoiceDraftUpdate['items'][number], value: string | number) => {
    if (!draft) return
    setDraft({ ...draft, items: draft.items.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item) })
  }
  const addItem = () => draft && setDraft({ ...draft, items: [...draft.items, { product_name: '', quantity: 1, unit_price: 0, discount_percent: 0, vat_rate: 18 }] })
  const removeItem = (index: number) => draft && draft.items.length > 1 && setDraft({ ...draft, items: draft.items.filter((_, itemIndex) => itemIndex !== index) })

  const draftTotals = useMemo(() => {
    if (!draft) return { subtotal: 0, vat: 0, total: 0 }
    return draft.items.reduce((result, item) => {
      const subtotal = item.quantity * item.unit_price * (1 - item.discount_percent / 100)
      const vat = subtotal * item.vat_rate / 100
      return { subtotal: result.subtotal + subtotal, vat: result.vat + vat, total: result.total + subtotal + vat }
    }, { subtotal: 0, vat: 0, total: 0 })
  }, [draft])

  const validDraft = Boolean(
    draft && draft.seller_name.trim() && draft.seller_identification_code.trim() &&
    draft.client_name.trim() && draft.client_identification_code.trim() && draft.due_date >= draft.invoice_date &&
    draft.items.length && draft.items.every(item => item.product_name.trim() && item.quantity > 0 && item.unit_price >= 0 && item.discount_percent >= 0 && item.discount_percent <= 100 && item.vat_rate >= 0 && item.vat_rate <= 100)
  )

  const columns = [
    { key: 'invoice_number', label: 'ინვოისი', render: (invoice: CustomerInvoiceSummary) => <div><div className="font-mono font-semibold text-gray-900">{invoice.invoice_number}</div><div className="mt-1 text-xs text-gray-500">შეკვეთა {invoice.order_number}</div></div> },
    { key: 'client_name', label: 'მყიდველი', render: (invoice: CustomerInvoiceSummary) => <div><div className="font-medium text-gray-900">{invoice.client_name}</div><div className="text-xs text-gray-500">ს/კ {invoice.client_identification_code}</div></div> },
    { key: 'status', label: 'სტატუსი', render: (invoice: CustomerInvoiceSummary) => <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${invoice.status === 'draft' ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300' : 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'}`}>{invoice.status === 'draft' ? 'მოსამზადებელი' : 'დადასტურებული'}</span> },
    { key: 'invoice_date', label: 'თარიღი', hideOnMobile: true, render: (invoice: CustomerInvoiceSummary) => <div><div>{new Date(invoice.invoice_date).toLocaleDateString('ka-GE')}</div><div className="text-xs text-gray-500">ვადა {new Date(invoice.due_date).toLocaleDateString('ka-GE')}</div></div> },
    { key: 'total', label: 'სულ', className: 'text-right', render: (invoice: CustomerInvoiceSummary) => <span className="font-semibold">{money(invoice.total, invoice.currency)}</span> },
    { key: 'actions', label: '', render: (invoice: CustomerInvoiceSummary) => <div className="flex justify-end"><button onClick={event => { event.stopPropagation(); void openInvoice(invoice) }} className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${invoice.status === 'draft' ? 'bg-primary-50 text-primary-700 hover:bg-primary-100 dark:bg-primary-900/30 dark:text-primary-300' : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-dark-100'}`}>{invoice.status === 'draft' ? <Pencil size={16} /> : <Eye size={16} />}{invoice.status === 'draft' ? 'შევსება' : 'ნახვა'}<ChevronRight size={15} /></button></div> },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><h1 className="text-2xl font-bold text-gray-900">გაყიდვის ინვოისები</h1><p className="mt-1 text-sm text-gray-500">მყიდველისთვის გასაცემი Invoice-ების მომზადება, გადამოწმება და დადასტურება</p></div>
        <div className="flex gap-2"><div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 dark:border-amber-900/50 dark:bg-amber-900/20"><div className="text-xs text-amber-700 dark:text-amber-300">შესავსები</div><div className="text-xl font-bold text-amber-900 dark:text-amber-200">{draftCount}</div></div><div className="rounded-xl border border-primary-100 bg-primary-50 px-4 py-2.5 dark:border-primary-900/50 dark:bg-primary-900/20"><div className="text-xs text-primary-700 dark:text-primary-300">დადასტურებული</div><div className="text-xl font-bold text-primary-900 dark:text-primary-200">{issuedInvoices.length}</div></div></div>
      </div>

      <StatusSteps />
      {message && <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700 dark:border-green-900/50 dark:bg-green-900/20 dark:text-green-300">{message}</div>}
      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">{error}</div>}

      <div className="card flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="relative w-full max-w-xl"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} /><input value={search} onChange={event => setSearch(event.target.value)} className="input pl-10" placeholder="ინვოისის ნომერი, შეკვეთა ან მყიდველი" /></div>
        <div className="flex rounded-lg bg-gray-100 p-1 dark:bg-dark-100">{([['all', 'ყველა'], ['draft', 'შესავსები'], ['issued', 'დადასტურებული']] as const).map(([value, label]) => <button key={value} onClick={() => setStatusFilter(value)} className={`rounded-md px-3 py-2 text-sm transition-colors ${statusFilter === value ? 'bg-white font-medium text-gray-900 shadow-sm dark:bg-dark-200' : 'text-gray-500 hover:text-gray-800'}`}>{label}</button>)}</div>
      </div>
      <DataTable columns={columns} data={invoices} isLoading={listQuery.isLoading} emptyMessage="არჩეული სტატუსით ინვოისი არ მოიძებნა" onRowClick={invoice => void openInvoice(invoice)} />
      {statusFilter === 'all' && issuedInvoices.length > 0 && <div className="text-right text-sm text-gray-500">დადასტურებული ინვოისების ჯამი: <span className="font-semibold text-gray-800">{money(issuedTotal)}</span></div>}

      <Modal open={!!selectedId && !editorOpen && !previewUrl} onClose={() => setSelectedId(null)} title="გაყიდვის ინვოისის ნახვა" size="xl">
        {detailQuery.isLoading && <div className="py-10 text-center text-gray-500">იტვირთება...</div>}
        {selected && <div className="space-y-5">
          <StatusSteps issued={selected.status === 'issued'} />
          <div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex items-center gap-2"><FileText className="text-primary-600" size={22} /><h3 className="font-mono text-xl font-bold">{selected.invoice_number}</h3></div><p className="mt-1 text-sm text-gray-500">შეკვეთა {selected.order_number}</p></div><div className="flex gap-2"><button onClick={() => void handlePreview(selected)} className="btn-secondary flex items-center gap-2"><Eye size={17} /> PDF ნახვა</button>{selected.status === 'draft' && <button onClick={() => openEditor(selected)} className="btn-primary flex items-center gap-2"><Pencil size={17} /> რედაქტირების გაგრძელება</button>}</div></div>
          <div className="grid gap-3 md:grid-cols-2"><PartyCard title="თქვენი კომპანია (გამყიდველი)" name={selected.seller_name} code={selected.seller_identification_code} address={selected.seller_address} /><PartyCard title="კლიენტი (მყიდველი)" name={selected.client_name} code={selected.client_identification_code} address={selected.client_address} /></div>
          <div className="grid grid-cols-2 gap-3 rounded-xl border border-gray-200 p-4 text-sm md:grid-cols-4 dark:border-dark-50"><div><div className="text-gray-500">თარიღი</div><div className="mt-1 font-medium">{new Date(selected.invoice_date).toLocaleDateString('ka-GE')}</div></div><div><div className="text-gray-500">გადახდის ვადა</div><div className="mt-1 font-medium">{new Date(selected.due_date).toLocaleDateString('ka-GE')}</div></div><div><div className="text-gray-500">ვალუტა</div><div className="mt-1 font-medium">{selected.currency}</div></div><div><div className="text-gray-500">საბოლოო თანხა</div><div className="mt-1 text-lg font-bold">{money(selected.total, selected.currency)}</div></div></div>
          <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-dark-50"><table className="w-full text-sm"><thead className="bg-gray-50 dark:bg-dark-100"><tr><th className="px-4 py-3 text-left">დასახელება</th><th className="px-4 py-3 text-right">რაოდენობა</th><th className="px-4 py-3 text-right">ფასი</th><th className="px-4 py-3 text-right">ფასდაკლება</th><th className="px-4 py-3 text-right">დღგ</th><th className="px-4 py-3 text-right">სულ</th></tr></thead><tbody className="divide-y dark:divide-dark-50">{selected.items.map(item => <tr key={item.id}><td className="px-4 py-3 font-medium">{item.product_name}</td><td className="px-4 py-3 text-right">{item.quantity}</td><td className="px-4 py-3 text-right">{money(item.unit_price, selected.currency)}</td><td className="px-4 py-3 text-right">{item.discount_percent}%</td><td className="px-4 py-3 text-right">{item.vat_rate}%</td><td className="px-4 py-3 text-right font-semibold">{money(item.line_total, selected.currency)}</td></tr>)}</tbody></table></div>
          {selected.status === 'issued' && <div className="rounded-xl border border-green-200 bg-green-50 p-4 dark:border-green-900/50 dark:bg-green-900/20"><div className="flex items-center gap-2 font-semibold text-green-800 dark:text-green-300"><ShieldCheck size={19} /> დადასტურებული დოკუმენტი</div><p className="mt-1 text-sm text-green-700 dark:text-green-400">ფინანსური მონაცემები დაფიქსირებულია. აირჩიეთ სასურველი ფორმატი.</p><div className="mt-4 grid gap-2 sm:grid-cols-3"><button onClick={() => void handleExport(selected, 'pdf')} className="btn-primary flex items-center justify-center gap-2"><Download size={17} /> PDF ჩამოტვირთვა</button><button onClick={() => void handleExport(selected, 'word')} className="btn-secondary flex items-center justify-center gap-2"><FileText size={17} /> Word ჩამოტვირთვა</button><button onClick={() => void handleExport(selected, 'excel')} className="btn-secondary flex items-center justify-center gap-2"><FileSpreadsheet size={17} /> Excel ჩამოტვირთვა</button></div></div>}
        </div>}
      </Modal>

      <Modal open={editorOpen && !previewUrl} onClose={() => { setEditorOpen(false); setConfirmIssue(false) }} title={selected ? `${selected.invoice_number} — შევსება` : 'ინვოისის შევსება'} size="full">
        {draft && selected && <div className="space-y-5">
          <StatusSteps />
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
            <div className="space-y-5">
              <section className="rounded-xl border border-gray-200 p-5 dark:border-dark-50"><div className="mb-4"><h3 className="font-semibold text-gray-900">1. ძირითადი ინფორმაცია</h3><p className="mt-1 text-sm text-gray-500">დოკუმენტის თარიღი, გადახდის ვადა და ვალუტა</p></div><div className="grid gap-4 md:grid-cols-3"><FormField label="ინვოისის თარიღი" required><input type="date" className="input" value={draft.invoice_date} onChange={e => setDraft({ ...draft, invoice_date: e.target.value })} /></FormField><FormField label="გადახდის ვადა" required><input type="date" className="input" value={draft.due_date} onChange={e => setDraft({ ...draft, due_date: e.target.value })} /></FormField><FormField label="ვალუტა" required><input className="input uppercase" maxLength={3} value={draft.currency} onChange={e => setDraft({ ...draft, currency: e.target.value.toUpperCase() })} /></FormField></div></section>

              <section className="rounded-xl border border-gray-200 p-5 dark:border-dark-50"><div className="mb-4"><h3 className="font-semibold text-gray-900">2. მხარეები</h3><p className="mt-1 text-sm text-gray-500">შეამოწმეთ გამყიდველისა და მყიდველის იურიდიული მონაცემები</p></div><div className="grid gap-5 md:grid-cols-2"><div className="space-y-3 rounded-lg bg-gray-50 p-4 dark:bg-dark-100"><div className="text-sm font-semibold text-gray-700">გამყიდველი</div><FormField label="დასახელება" required><input className="input" value={draft.seller_name} onChange={e => setDraft({ ...draft, seller_name: e.target.value })} /></FormField><FormField label="საიდენტიფიკაციო კოდი" required><input className="input" value={draft.seller_identification_code} onChange={e => setDraft({ ...draft, seller_identification_code: e.target.value })} /></FormField><FormField label="მისამართი"><input className="input" value={draft.seller_address} onChange={e => setDraft({ ...draft, seller_address: e.target.value })} /></FormField><div className="grid gap-3 sm:grid-cols-2"><FormField label="ტელეფონი"><input className="input" value={draft.seller_phone} onChange={e => setDraft({ ...draft, seller_phone: e.target.value })} /></FormField><FormField label="ელფოსტა"><input className="input" value={draft.seller_email} onChange={e => setDraft({ ...draft, seller_email: e.target.value })} /></FormField></div></div><div className="space-y-3 rounded-lg bg-gray-50 p-4 dark:bg-dark-100"><div className="text-sm font-semibold text-gray-700">მყიდველი</div><FormField label="დასახელება" required><input className="input" value={draft.client_name} onChange={e => setDraft({ ...draft, client_name: e.target.value })} /></FormField><FormField label="საიდენტიფიკაციო კოდი" required><input className="input" value={draft.client_identification_code} onChange={e => setDraft({ ...draft, client_identification_code: e.target.value })} /></FormField><FormField label="მისამართი"><input className="input" value={draft.client_address} onChange={e => setDraft({ ...draft, client_address: e.target.value })} /></FormField></div></div></section>

              <section className="rounded-xl border border-gray-200 p-5 dark:border-dark-50"><div className="mb-4 flex items-start justify-between gap-3"><div><h3 className="font-semibold text-gray-900">3. პოზიციები</h3><p className="mt-1 text-sm text-gray-500">შეცვალეთ დასახელება, რაოდენობა, ფასი, ფასდაკლება ან დღგ</p></div><button className="btn-secondary flex shrink-0 items-center gap-2 text-sm" onClick={addItem}><Plus size={16} /> დამატება</button></div><div className="space-y-3">{draft.items.map((item, index) => <div key={index} className="grid gap-3 rounded-lg border border-gray-200 bg-gray-50/50 p-3 md:grid-cols-[minmax(200px,2fr)_90px_110px_90px_80px_42px] md:items-end dark:border-dark-50 dark:bg-dark-100/50"><FormField label="დასახელება"><input className="input" value={item.product_name} onChange={e => updateItem(index, 'product_name', e.target.value)} /></FormField><FormField label="რაოდენობა"><input className="input" type="number" min="0.001" step="0.001" value={item.quantity} onChange={e => updateItem(index, 'quantity', Number(e.target.value))} /></FormField><FormField label="ფასი"><input className="input" type="number" min="0" step="0.01" value={item.unit_price || ''} onChange={e => updateItem(index, 'unit_price', Number(e.target.value))} /></FormField><FormField label="ფასდ. %"><input className="input" type="number" min="0" max="100" step="0.01" value={item.discount_percent} onChange={e => updateItem(index, 'discount_percent', Number(e.target.value))} /></FormField><FormField label="დღგ %"><input className="input" type="number" min="0" max="100" step="0.01" value={item.vat_rate} onChange={e => updateItem(index, 'vat_rate', Number(e.target.value))} /></FormField><button className="mb-0.5 flex h-10 w-10 items-center justify-center rounded-lg text-red-600 hover:bg-red-50 disabled:opacity-30 dark:hover:bg-red-900/20" disabled={draft.items.length === 1} onClick={() => removeItem(index)} aria-label={`პოზიცია ${index + 1} — წაშლა`}><Trash2 size={18} /></button></div>)}</div></section>

              <section className="rounded-xl border border-gray-200 p-5 dark:border-dark-50"><FormField label="შენიშვნა"><textarea className="input min-h-24" value={draft.notes || ''} onChange={e => setDraft({ ...draft, notes: e.target.value })} placeholder="გადახდის პირობა ან დამატებითი ინფორმაცია" /></FormField></section>
            </div>

            <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start"><div className="rounded-xl border border-primary-200 bg-primary-50 p-5 dark:border-primary-900/50 dark:bg-primary-900/20"><div className="text-sm font-semibold text-primary-900 dark:text-primary-200">ინვოისის ჯამი</div><div className="mt-4 space-y-2 text-sm"><div className="flex justify-between"><span className="text-primary-700 dark:text-primary-300">ქვე-ჯამი</span><span>{money(draftTotals.subtotal, draft.currency)}</span></div><div className="flex justify-between"><span className="text-primary-700 dark:text-primary-300">დღგ</span><span>{money(draftTotals.vat, draft.currency)}</span></div><div className="mt-3 flex justify-between border-t border-primary-200 pt-3 text-lg font-bold dark:border-primary-800"><span>სულ</span><span>{money(draftTotals.total, draft.currency)}</span></div></div></div>
              {!validDraft && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-300">შეავსეთ ყველა სავალდებულო ველი და გადაამოწმეთ პოზიციები.</div>}
              {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">{error}</div>}
              {!confirmIssue ? <div className="space-y-2"><button className="btn-secondary flex w-full items-center justify-center gap-2" disabled={saving || !validDraft} onClick={() => void saveCurrentDraft()}><Pencil size={16} /> {saving ? 'ინახება...' : 'ცვლილებების შენახვა'}</button><button className="btn-secondary flex w-full items-center justify-center gap-2" disabled={saving || !validDraft} onClick={() => void previewCurrentDraft()}><Eye size={16} /> შენახვა და PDF ნახვა</button><button className="btn-primary flex w-full items-center justify-center gap-2" disabled={saving || !validDraft} onClick={() => setConfirmIssue(true)}><CheckCircle2 size={17} /> დადასტურებაზე გადასვლა</button></div> : <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-900/20"><div className="flex items-center gap-2 font-semibold text-amber-900 dark:text-amber-200"><ShieldCheck size={18} /> საბოლოო დადასტურება</div><p className="mt-2 text-sm text-amber-800 dark:text-amber-300">დადასტურების შემდეგ ფინანსური მონაცემები ჩაიკეტება და შეიქმნება დავალიანება და GL გატარება.</p><div className="mt-4 space-y-2"><button className="btn-primary w-full" disabled={issuing || saving} onClick={() => void issueCurrentDraft()}>{issuing ? 'მუშავდება...' : 'დიახ, დაადასტურე'}</button><button className="btn-secondary w-full" disabled={issuing} onClick={() => setConfirmIssue(false)}>უკან დაბრუნება</button></div></div>}
            </aside>
          </div>
        </div>}
      </Modal>

      <Modal open={!!previewUrl} onClose={() => setPreviewUrl(null)} title={`${previewNumber} — PDF გადამოწმება`} size="xl">
        {previewUrl && <div className="space-y-3"><div className="flex items-center justify-between"><p className="text-sm text-gray-500">გადაამოწმეთ დოკუმენტი დადასტურებამდე.</p><button className="btn-secondary flex items-center gap-2" onClick={() => window.open(previewUrl, '_blank')}><Printer size={17} /> სრულ ეკრანზე / ბეჭდვა</button></div><iframe src={previewUrl} title={`${previewNumber} PDF preview`} className="h-[70vh] w-full rounded-lg border border-gray-200 bg-white" /></div>}
      </Modal>
    </div>
  )
}
