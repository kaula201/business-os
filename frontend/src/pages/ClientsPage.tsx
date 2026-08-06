import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { clientsApi, importApi } from '../services/api'
import { Plus, Search, Building2, User, Phone, Mail, MapPin, Upload, Loader2 } from 'lucide-react'
import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import { StatusBadge, clientStatusMap } from '../components/ui/Badges'
import type { Client, ClientCreate } from '../types'

const CLIENTS_PAGE_SIZE = 20

export default function ClientsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [page, setPage] = useState(1)
  const [modalOpen, setModalOpen] = useState(false)
  const [editClient, setEditClient] = useState<Client | null>(null)
  const [viewClient, setViewClient] = useState<Client | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Client | null>(null)
  const [importModal, setImportModal] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importResult, setImportResult] = useState('')
  const [importLoading, setImportLoading] = useState(false)
  const [form, setForm] = useState<ClientCreate>({
    name: '', client_type: 'legal', identification_code: '',
    is_vat_payer: true, address: '', phone: '', email: '', notes: '',
  })

  // Debounce: search იგზავნება server-ზე მხოლოდ აკრეფის შეწყვეტის შემდეგ
  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput); setPage(1) }, 400)
    return () => clearTimeout(t)
  }, [searchInput])

  const { data, isLoading } = useQuery({
    queryKey: ['clients', search, page],
    queryFn: () => clientsApi.list({ search: search || undefined, page, page_size: CLIENTS_PAGE_SIZE }).then(r => r.data.data),
  })

  const createMutation = useMutation({
    mutationFn: (data: ClientCreate) => clientsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clients'] })
      closeModal()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => clientsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clients'] })
      setDeleteTarget(null)
    },
  })

  const items: Client[] = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.max(1, Math.ceil(total / CLIENTS_PAGE_SIZE))

  function openCreate() {
    setEditClient(null)
    setForm({ name: '', client_type: 'legal', identification_code: '', is_vat_payer: true, address: '', phone: '', email: '', notes: '' })
    setModalOpen(true)
  }

  function openEdit(client: Client) {
    setEditClient(client)
    setForm({
      name: client.name, client_type: client.client_type,
      identification_code: client.identification_code,
      is_vat_payer: client.is_vat_payer, address: client.address || '',
      phone: client.phone || '', email: client.email || '', notes: client.notes || '',
    })
    setModalOpen(true)
  }

  function closeModal() {
    setModalOpen(false)
    setEditClient(null)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (editClient) {
      clientsApi.update(editClient.id, form).then(() => {
        queryClient.invalidateQueries({ queryKey: ['clients'] })
        closeModal()
      })
    } else {
      createMutation.mutate(form)
    }
  }

  const columns = [
    {
      key: 'name', label: 'კლიენტი',
      render: (c: Client) => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-primary-100 text-primary-700 rounded-lg flex items-center justify-center">
            {c.client_type === 'legal' ? <Building2 size={16} /> : <User size={16} />}
          </div>
          <div>
            <span className="font-medium text-gray-900 dark:text-gray-100">{c.name}</span>
            <span className="block text-xs text-gray-400 dark:text-gray-500">{c.identification_code}</span>
          </div>
        </div>
      ),
    },
    { key: 'client_type', label: 'ტიპი', render: (c: Client) => c.client_type === 'legal' ? 'იურ. პირი' : 'ფიზ. პირი', hideOnMobile: true },
    {
      key: 'contact', label: 'საკონტაქტო', hideOnMobile: true,
      render: (c: Client) => (
        <div>
          {c.phone && <span className="block text-xs">{c.phone}</span>}
          {c.email && <span className="block text-xs text-gray-400 dark:text-gray-500">{c.email}</span>}
        </div>
      ),
    },
    {
      key: 'status', label: 'სტატუსი',
      render: (c: Client) => <StatusBadge status={c.status} map={clientStatusMap} />,
    },
    {
      key: 'actions', label: '',
      render: (c: Client) => (
        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
          <button onClick={() => openEdit(c)} className="p-1.5 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 rounded text-gray-500 dark:text-gray-400 hover:text-primary-600">
            ✏️
          </button>
          <button onClick={() => setDeleteTarget(c)} className="p-1.5 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 rounded text-gray-500 dark:text-gray-400 hover:text-red-600">
            🗑️
          </button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('კლიენტების რეესტრი')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('გაყიდვებისა და ფინანსური დოკუმენტებისთვის გამოყენებული ოფიციალური კლიენტები')}</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => { setImportModal(true); setImportFile(null); setImportResult('') }} className="btn-secondary flex items-center gap-2">
            <Upload size={18} /> {t('Excel იმპორტი')}
          </button>
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('ახალი კლიენტი')}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" size={18} />
          <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder={t('ძებნა სახელით, კოდით, ტელეფონით...')} className="input pl-10" />
        </div>
      </div>

      <DataTable columns={columns} data={items} isLoading={isLoading} emptyMessage="კლიენტების რეესტრში ჩანაწერი არ მოიძებნა" onRowClick={(c) => setViewClient(c)} page={page} totalPages={totalPages} total={total} onPageChange={setPage} />

      {/* Create / Edit Modal */}
      <Modal open={modalOpen} onClose={closeModal} title={editClient ? 'კლიენტის რედაქტირება' : 'ახალი კლიენტი'} size="lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FormField label={t('სახელი / კომპანიის სახელი')} required>
              <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" required />
            </FormField>
            <FormField label={t('საიდენტიფიკაციო კოდი')} required>
              <input type="text" value={form.identification_code} onChange={(e) => setForm({ ...form, identification_code: e.target.value })} className="input" required />
            </FormField>
            <FormField label={t('ტიპი')}>
              <Select options={[{ value: 'legal', label: 'იურიდიული პირი' }, { value: 'individual', label: 'ფიზიკური პირი' }]} value={form.client_type} onChange={(e) => setForm({ ...form, client_type: e.target.value as any })} />
            </FormField>
            <FormField label={t('დღგ-ს გადამხდელი')}>
              <Select options={[{ value: 'true', label: 'კი' }, { value: 'false', label: 'არა' }]} value={String(form.is_vat_payer)} onChange={(e) => setForm({ ...form, is_vat_payer: e.target.value === 'true' })} />
            </FormField>
            <FormField label={t('ტელეფონი')}>
              <input type="tel" value={form.phone || ''} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="input" placeholder="+995 5XX XXX XXX" />
            </FormField>
            <FormField label={t('ელფოსტა')}>
              <input type="email" value={form.email || ''} onChange={(e) => setForm({ ...form, email: e.target.value })} className="input" placeholder="info@company.ge" />
            </FormField>
          </div>
          <FormField label={t('მისამართი')}>
            <input type="text" value={form.address || ''} onChange={(e) => setForm({ ...form, address: e.target.value })} className="input" />
          </FormField>
          <FormField label={t('შენიშვნა')}>
            <textarea value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" rows={3} />
          </FormField>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-dark-50">
            <button type="button" onClick={closeModal} className="btn-secondary">{t('გაუქმება')}</button>
            <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'შენახვა...' : editClient ? 'განახლება' : 'დამატება'}
            </button>
          </div>
        </form>
      </Modal>

      {/* View Client Modal */}
      <Modal open={!!viewClient} onClose={() => setViewClient(null)} title={t('ოფიციალური კლიენტის ბარათი')} size="lg">
        {viewClient && (
          <div className="space-y-4">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-14 h-14 bg-primary-100 text-primary-700 rounded-xl flex items-center justify-center">
                {viewClient.client_type === 'legal' ? <Building2 size={28} /> : <User size={28} />}
              </div>
              <div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">{viewClient.name}</h3>
                <StatusBadge status={viewClient.status} map={clientStatusMap} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg"><span className="text-gray-500 dark:text-gray-400">{t('კოდი:')}</span> <span className="font-medium">{viewClient.identification_code}</span></div>
              <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg"><span className="text-gray-500 dark:text-gray-400">{t('ტიპი:')}</span> <span className="font-medium">{viewClient.client_type === 'legal' ? 'იურ. პირი' : 'ფიზ. პირი'}</span></div>
              <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg"><span className="text-gray-500 dark:text-gray-400">{t('დღგ:')}</span> <span className="font-medium">{viewClient.is_vat_payer ? 'გადამხდელი' : 'არ არის'}</span></div>
              <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg"><span className="text-gray-500 dark:text-gray-400">{t('შექმნილი:')}</span> <span className="font-medium">{new Date(viewClient.created_at).toLocaleDateString('ka-GE')}</span></div>
              {viewClient.phone && <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg col-span-1"><Phone size={14} className="inline mr-1" />{viewClient.phone}</div>}
              {viewClient.email && <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg col-span-1"><Mail size={14} className="inline mr-1" />{viewClient.email}</div>}
              {viewClient.address && <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg col-span-2"><MapPin size={14} className="inline mr-1" />{viewClient.address}</div>}
              {viewClient.notes && <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg col-span-2"><span className="text-gray-500 dark:text-gray-400">{t('შენიშვნა:')}</span> {viewClient.notes}</div>}
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-dark-50">
              <button onClick={() => { setViewClient(null); openEdit(viewClient) }} className="btn-primary">{t('რედაქტირება')}</button>
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        title={t('კლიენტის წაშლა')}
        message={`დარწმუნებული ხართ, რომ გსურთ "${deleteTarget?.name}"-ის წაშლა?`}
        confirmLabel="წაშლა"
        loading={deleteMutation.isPending}
      />

      {/* Import Modal */}
      <Modal open={importModal} onClose={() => setImportModal(false)} title={t('კლიენტების Excel იმპორტი')} size="md">
        {importResult ? (
          <div className="text-center py-4">
            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line">{importResult}</p>
            <button onClick={() => { setImportModal(false); queryClient.invalidateQueries({ queryKey: ['clients'] }) }} className="btn-primary mt-6">{t('დახურვა')}</button>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {t('ატვირთეთ Excel ფაილი (.xlsx) კლიენტების სიით. მოსალოდნელი სვეტები:')}
              <code className="block mt-2 text-xs bg-gray-100 dark:bg-dark-100 p-2 rounded">name, identification_code, phone, email, address, notes</code>
            </p>
            <input
              type="file"
              accept=".xlsx,.xls"
              onChange={(e) => setImportFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-gray-500 dark:text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
            />
            {importFile && <p className="text-xs text-gray-400 dark:text-gray-500">არჩეულია: {importFile.name}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <button onClick={() => setImportModal(false)} className="btn-secondary">{t('გაუქმება')}</button>
              <button
                onClick={async () => {
                  if (!importFile) return
                  setImportLoading(true)
                  setImportResult('')
                  try {
                    const res = await importApi.importClients(importFile)
                    setImportResult(res.data.data?.message || 'იმპორტი დასრულდა')
                  } catch (err: any) {
                    setImportResult(err?.response?.data?.detail || 'შეცდომა იმპორტის დროს')
                  } finally {
                    setImportLoading(false)
                  }
                }}
                disabled={!importFile || importLoading}
                className="btn-primary"
              >
                {importLoading ? <><Loader2 size={16} className="animate-spin" /> {t('იტვირთება...')}</> : 'ატვირთვა'}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}