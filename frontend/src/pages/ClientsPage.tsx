import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { clientsApi, importApi } from '../services/api'
import {Plus, Search, Building2, User, Phone, Mail, MapPin, Upload, Loader2, Pencil, Trash2} from 'lucide-react'
import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import { StatusBadge, clientStatusMap } from '../components/ui/Badges'
import type { Client, ClientCreate } from '../types'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

const CLIENTS_PAGE_SIZE = 20

const ADDRESS_TYPE_LABELS: Record<string, string> = { legal: 'იურიდიული', delivery: 'მიწოდების', billing: 'ბილინგის' }
const RELATION_TYPE_LABELS: Record<string, string> = { branch: 'ფილიალი', parent: 'მშობელი', subsidiary: 'შვილობილი', partner: 'პარტნიორი' }
const STATEMENT_TYPE_LABELS: Record<string, string> = { invoice: 'ინვოისი', payment: 'გადახდა', credit_note: 'ნოტა' }

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
  // Client 2.0 — view tabs
  const [viewTab, setViewTab] = useState<'overview' | 'addresses' | 'groups' | 'relations' | 'statement' | 'merge'>('overview')
  const [newAddress, setNewAddress] = useState({ address_type: 'legal', address_line: '', city: '', is_default: false })
  const [newRelation, setNewRelation] = useState({ related_client_id: '', relation_type: 'branch', notes: '' })
  const [newGroup, setNewGroup] = useState({ name: '', color: '#16A6D4' })
  const [mergeTarget, setMergeTarget] = useState('')
  const [mergeSources, setMergeSources] = useState<string[]>([])
  const [form, setForm] = useState<ClientCreate>({
    name: '', client_type: 'legal', identification_code: '',
    is_vat_payer: true, address: '', phone: '', email: '', notes: '', credit_limit: undefined,
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

  // Client 2.0 queries (enabled only when a client is open)
  const { data: addresses } = useQuery({
    queryKey: ['client-addresses', viewClient?.id],
    queryFn: () => viewClient ? clientsApi.listAddresses(viewClient.id).then(r => r.data.data) : [],
    enabled: !!viewClient && viewTab === 'addresses',
  })
  const { data: groups } = useQuery({
    queryKey: ['client-groups'],
    queryFn: () => clientsApi.listGroups().then(r => r.data.data),
  })
  const { data: relations } = useQuery({
    queryKey: ['client-relations', viewClient?.id],
    queryFn: () => viewClient ? clientsApi.listRelations(viewClient.id).then(r => r.data.data) : [],
    enabled: !!viewClient && viewTab === 'relations',
  })
  const { data: statement } = useQuery({
    queryKey: ['client-statement', viewClient?.id],
    queryFn: () => viewClient ? clientsApi.getStatement(viewClient.id).then(r => r.data.data) : null,
    enabled: !!viewClient && viewTab === 'statement',
  })
  const { data: allClients } = useQuery({
    queryKey: ['clients-all'],
    queryFn: () => clientsApi.list({ page_size: 100 }).then(r => r.data.data),
  })

  const addAddressMutation = useMutation({
    mutationFn: (d: any) => viewClient ? clientsApi.createAddress(viewClient.id, d) : Promise.reject(),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['client-addresses'] }); setNewAddress({ address_type: 'legal', address_line: '', city: '', is_default: false }) },
  })
  const addRelationMutation = useMutation({
    mutationFn: (d: any) => viewClient ? clientsApi.createRelation(viewClient.id, d) : Promise.reject(),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['client-relations'] }); setNewRelation({ related_client_id: '', relation_type: 'branch', notes: '' }) },
  })
  const addGroupMutation = useMutation({
    mutationFn: (d: any) => clientsApi.createGroup(d),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['client-groups'] }),
  })
  const mergeMutation = useMutation({
    mutationFn: (d: any) => clientsApi.merge(d),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clients'] })
      setViewClient(null)
      setMergeTarget(''); setMergeSources([])
    },
  })

  function openCreate() {
    setEditClient(null)
    setForm({ name: '', client_type: 'legal', identification_code: '', is_vat_payer: true, address: '', phone: '', email: '', notes: '', credit_limit: undefined })
    setModalOpen(true)
  }

  function openEdit(client: Client) {
    setEditClient(client)
    setForm({
      name: client.name, client_type: client.client_type,
      identification_code: client.identification_code,
      is_vat_payer: client.is_vat_payer, address: client.address || '',
      phone: client.phone || '', email: client.email || '', notes: client.notes || '',
      credit_limit: (client as any).credit_limit ?? undefined,
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
    { key: 'client_type', label: 'ტიპი', render: (c: Client) => c.client_type === 'legal' ? t('იურ. პირი') : t('ფიზ. პირი'), hideOnMobile: true },
    {
      key: 'contact', label: t('საკონტაქტო'), hideOnMobile: true,
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
          <button onClick={() => openEdit(c)} title={t('რედაქტირება')} aria-label={t('რედაქტირება')} className="p-2 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 rounded-lg text-gray-500 dark:text-gray-400 hover:text-primary-600 min-w-[36px] min-h-[36px] flex items-center justify-center">
            <Pencil size={18} />
          </button>
          <button onClick={() => setDeleteTarget(c)} title={t('წაშლა')} aria-label={t('წაშლა')} className="p-2 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 rounded-lg text-gray-500 dark:text-gray-400 hover:text-red-600 min-w-[36px] min-h-[36px] flex items-center justify-center">
            <Trash2 size={18} />
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

      <DataTable columns={columns} data={items} isLoading={isLoading} emptyMessage={t('კლიენტების რეესტრში ჩანაწერი არ მოიძებნა')} onRowClick={(c) => setViewClient(c)} page={page} totalPages={totalPages} total={total} onPageChange={setPage} />

      {/* Create / Edit Modal */}
      <Modal open={modalOpen} onClose={closeModal} title={editClient ? t('კლიენტის რედაქტირება') : t('ახალი კლიენტი')} size="lg">
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
            <FormField label={t('საკრედიტო ლიმიტი (₾)')}>
              <input type="number" min={0} step="0.01" value={form.credit_limit ?? ''} onChange={(e) => setForm({ ...form, credit_limit: e.target.value === '' ? undefined : Number(e.target.value) })} className="input" placeholder="0 = შეუზღუდავი" />
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
              {createMutation.isPending ? 'შენახვა...' : editClient ? t('განახლება') : t('დამატება')}
            </button>
          </div>
        </form>
      </Modal>

      {/* View Client Modal — tabs: overview / addresses / groups / relations / statement / merge */}
      <Modal open={!!viewClient} onClose={() => { setViewClient(null); setViewTab('overview') }} title={t('ოფიციალური კლიენტის ბარათი')} size="lg">
        {viewClient && (
          <div className="space-y-4">
            <div className="flex items-center gap-4 mb-2">
              <div className="w-14 h-14 bg-primary-100 text-primary-700 rounded-xl flex items-center justify-center">
                {viewClient.client_type === 'legal' ? <Building2 size={28} /> : <User size={28} />}
              </div>
              <div className="flex-1">
                <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">{viewClient.name}</h3>
                <StatusBadge status={viewClient.status} map={clientStatusMap} />
              </div>
              {(viewClient as any).credit_limit != null && (
                <div className="text-right text-sm">
                  <span className="text-gray-400 dark:text-gray-500 block">{t('საკრედიტო ლიმიტი')}</span>
                  <span className="font-bold text-gray-900 dark:text-gray-100">{(viewClient as any).credit_limit} ₾</span>
                </div>
              )}
            </div>

            {/* Tabs */}
            <div className="flex flex-wrap gap-1 border-b border-gray-200 dark:border-dark-50 pb-2">
              {(['overview', 'addresses', 'groups', 'relations', 'statement', 'merge'] as const).map(tabKey => (
                <button
                  key={tabKey}
                  onClick={() => setViewTab(tabKey)}
                  className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${viewTab === tabKey ? 'bg-primary-600 text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-100'}`}
                >
                  {t({ overview: 'მიმოხილვა', addresses: 'მისამართები', groups: 'ჯგუფები', relations: 'კავშირები', statement: 'Statement', merge: 'გაერთიანება' }[tabKey])}
                </button>
              ))}
            </div>

            {viewTab === 'overview' && (
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg"><span className="text-gray-500 dark:text-gray-400">{t('კოდი:')}</span> <span className="font-medium">{viewClient.identification_code}</span></div>
                <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg"><span className="text-gray-500 dark:text-gray-400">{t('ტიპი:')}</span> <span className="font-medium">{viewClient.client_type === 'legal' ? t('იურ. პირი') : t('ფიზ. პირი')}</span></div>
                <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg"><span className="text-gray-500 dark:text-gray-400">{t('დღგ:')}</span> <span className="font-medium">{viewClient.is_vat_payer ? t('გადამხდელი') : t('არ არის')}</span></div>
                <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg"><span className="text-gray-500 dark:text-gray-400">{t('შექმნილი:')}</span> <span className="font-medium">{fmtDate(new Date(viewClient.created_at))}</span></div>
                {viewClient.phone && <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg col-span-1"><Phone size={14} className="inline mr-1" />{viewClient.phone}</div>}
                {viewClient.email && <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg col-span-1"><Mail size={14} className="inline mr-1" />{viewClient.email}</div>}
                {viewClient.address && <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg col-span-2"><MapPin size={14} className="inline mr-1" />{viewClient.address}</div>}
                {viewClient.notes && <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg col-span-2"><span className="text-gray-500 dark:text-gray-400">{t('შენიშვნა:')}</span> {viewClient.notes}</div>}
              </div>
            )}

            {viewTab === 'addresses' && (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2 items-end">
                  <select value={newAddress.address_type} onChange={(e) => setNewAddress({ ...newAddress, address_type: e.target.value })} className="input h-9 w-auto text-sm">
                    <option value="legal">{t('იურიდიული')}</option>
                    <option value="delivery">{t('მიწოდების')}</option>
                    <option value="billing">{t('ბილინგის')}</option>
                  </select>
                  <input value={newAddress.address_line} onChange={(e) => setNewAddress({ ...newAddress, address_line: e.target.value })} placeholder={t('მისამართი')} className="input h-9 flex-1 min-w-[180px] text-sm" />
                  <input value={newAddress.city} onChange={(e) => setNewAddress({ ...newAddress, city: e.target.value })} placeholder={t('ქალაქი')} className="input h-9 w-28 text-sm" />
                  <label className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                    <input type="checkbox" checked={newAddress.is_default} onChange={(e) => setNewAddress({ ...newAddress, is_default: e.target.checked })} /> {t('მთავარი')}
                  </label>
                  <button onClick={() => addAddressMutation.mutate(newAddress)} disabled={!newAddress.address_line || addAddressMutation.isPending} className="btn-primary h-9 text-sm">
                    {t('დამატება')}
                  </button>
                </div>
                <div className="divide-y dark:divide-dark-50">
                  {(addresses || []).map((a: any) => (
                    <div key={a.id} className="flex items-center justify-between py-2 text-sm">
                      <div>
                        <span className="badge mr-2">{t(ADDRESS_TYPE_LABELS[a.address_type] || a.address_type)}</span>
                        <span className="text-gray-700 dark:text-gray-300">{a.address_line}{a.city ? `, ${a.city}` : ''}</span>
                        {a.is_default && <span className="ml-2 text-xs text-primary-600">★ {t('მთავარი')}</span>}
                      </div>
                      <button onClick={() => clientsApi.deleteAddress(a.id).then(() => queryClient.invalidateQueries({ queryKey: ['client-addresses'] }))} className="p-1.5 text-gray-400 hover:text-red-600" title={t('წაშლა')}>
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))}
                  {(addresses || []).length === 0 && <p className="text-sm text-gray-400 py-4 text-center">{t('მისამართები არ არის')}</p>}
                </div>
              </div>
            )}

            {viewTab === 'groups' && (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2 items-end">
                  <input value={newGroup.name} onChange={(e) => setNewGroup({ ...newGroup, name: e.target.value })} placeholder={t('ახალი ჯგუფის სახელი')} className="input h-9 flex-1 min-w-[160px] text-sm" />
                  <input type="color" value={newGroup.color} onChange={(e) => setNewGroup({ ...newGroup, color: e.target.value })} className="h-9 w-12 rounded border border-gray-200 dark:border-dark-50" />
                  <button onClick={() => addGroupMutation.mutate(newGroup)} disabled={!newGroup.name} className="btn-primary h-9 text-sm">{t('ჯგუფის შექმნა')}</button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {(groups || []).map((g: any) => (
                    <button
                      key={g.id}
                      onClick={() => {
                        const cur = (viewClient as any).group_ids || []
                        const next = cur.includes(g.id) ? cur.filter((x: string) => x !== g.id) : [...cur, g.id]
                        clientsApi.setClientGroups(viewClient.id, next).then(() => queryClient.invalidateQueries({ queryKey: ['clients'] }))
                      }}
                      className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${(viewClient as any).group_ids?.includes(g.id) ? 'bg-primary-50 text-primary-700 border-primary-200' : 'bg-white dark:bg-dark-200 border-gray-200 dark:border-dark-50 text-gray-600 dark:text-gray-400'}`}
                      style={{ borderLeftColor: g.color, borderLeftWidth: 4 }}
                    >
                      {g.name} <span className="text-xs text-gray-400">({g.client_count})</span>
                    </button>
                  ))}
                  {(groups || []).length === 0 && <p className="text-sm text-gray-400 py-2">{t('ჯგუფები არ არის')}</p>}
                </div>
              </div>
            )}

            {viewTab === 'relations' && (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2 items-end">
                  <select value={newRelation.related_client_id} onChange={(e) => setNewRelation({ ...newRelation, related_client_id: e.target.value })} className="input h-9 flex-1 min-w-[180px] text-sm">
                    <option value="">{t('აირჩიეთ კლიენტი')}</option>
                    {(allClients?.items || []).filter((c: any) => c.id !== viewClient.id).map((c: any) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                  <select value={newRelation.relation_type} onChange={(e) => setNewRelation({ ...newRelation, relation_type: e.target.value })} className="input h-9 w-auto text-sm">
                    <option value="branch">{t('ფილიალი')}</option>
                    <option value="parent">{t('მშობელი')}</option>
                    <option value="subsidiary">{t('შვილობილი')}</option>
                    <option value="partner">{t('პარტნიორი')}</option>
                  </select>
                  <button onClick={() => newRelation.related_client_id && addRelationMutation.mutate(newRelation)} disabled={!newRelation.related_client_id} className="btn-primary h-9 text-sm">{t('დაკავშირება')}</button>
                </div>
                <div className="divide-y dark:divide-dark-50">
                  {(relations || []).map((r: any) => (
                    <div key={r.id} className="flex items-center justify-between py-2 text-sm">
                      <div>
                        <span className="badge mr-2">{t(RELATION_TYPE_LABELS[r.relation_type] || r.relation_type)}</span>
                        <span className="text-gray-700 dark:text-gray-300">{r.related_client_name}</span>
                      </div>
                      <button onClick={() => clientsApi.deleteRelation(r.id).then(() => queryClient.invalidateQueries({ queryKey: ['client-relations'] }))} className="p-1.5 text-gray-400 hover:text-red-600" title={t('წაშლა')}>
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))}
                  {(relations || []).length === 0 && <p className="text-sm text-gray-400 py-4 text-center">{t('კავშირები არ არის')}</p>}
                </div>
              </div>
            )}

            {viewTab === 'statement' && (
              <div className="space-y-3">
                {statement && (
                  <>
                    <div className="grid grid-cols-3 gap-3 text-sm">
                      <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg"><span className="text-gray-500 dark:text-gray-400 block">{t('ინვოისირებული')}</span><span className="font-bold">{statement.total_invoiced} ₾</span></div>
                      <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg"><span className="text-gray-500 dark:text-gray-400 block">{t('გადახდილი')}</span><span className="font-bold text-green-600">{statement.total_paid} ₾</span></div>
                      <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg"><span className="text-gray-500 dark:text-gray-400 block">{t('ნაშთი')}</span><span className={`font-bold ${statement.closing_balance > 0 ? 'text-red-600' : 'text-green-600'}`}>{statement.closing_balance} ₾</span></div>
                    </div>
                    <div className="max-h-[300px] overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="text-xs text-gray-400 dark:text-gray-500 border-b dark:border-dark-50">
                          <tr>
                            <th className="text-left py-2 pr-2">{t('თარიღი')}</th>
                            <th className="text-left py-2 pr-2">{t('ტიპი')}</th>
                            <th className="text-left py-2 pr-2">{t('რეფერენსი')}</th>
                            <th className="text-right py-2 pr-2">{t('დებეტი')}</th>
                            <th className="text-right py-2 pr-2">{t('კრედიტი')}</th>
                            <th className="text-right py-2">{t('ბალანსი')}</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y dark:divide-dark-50">
                          {statement.lines.map((l: any, i: number) => (
                            <tr key={i}>
                              <td className="py-1.5 pr-2 text-gray-500">{fmtDate(new Date(l.date))}</td>
                              <td className="py-1.5 pr-2"><span className="badge">{t(STATEMENT_TYPE_LABELS[l.type] || l.type)}</span></td>
                              <td className="py-1.5 pr-2 text-gray-600 dark:text-gray-400">{l.reference}</td>
                              <td className="py-1.5 pr-2 text-right">{l.debit ? `${l.debit} ₾` : ''}</td>
                              <td className="py-1.5 pr-2 text-right text-green-600">{l.credit ? `${l.credit} ₾` : ''}</td>
                              <td className="py-1.5 text-right font-medium">{l.balance} ₾</td>
                            </tr>
                          ))}
                          {statement.lines.length === 0 && <tr><td colSpan={6} className="py-4 text-center text-gray-400">{t('ოპერაციები არ არის')}</td></tr>}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>
            )}

            {viewTab === 'merge' && (
              <div className="space-y-3">
                <p className="text-sm text-gray-500 dark:text-gray-400">{t('აირჩიეთ დუბლიკატი კლიენტები — მათი შეკვეთები, ინვოისები და მოვალეები გადავა მიმდინარე კლიენტზე, წყაროები კი დარჩება ისტორიაში.')}</p>
                <div className="space-y-1.5 max-h-[220px] overflow-y-auto">
                  {(allClients?.items || []).filter((c: any) => c.id !== viewClient.id).map((c: any) => (
                    <label key={c.id} className="flex items-center gap-2 text-sm p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-dark-100 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={mergeSources.includes(c.id)}
                        onChange={(e) => setMergeSources(prev => e.target.checked ? [...prev, c.id] : prev.filter(x => x !== c.id))}
                      />
                      <span className="text-gray-700 dark:text-gray-300">{c.name}</span>
                      <span className="text-xs text-gray-400">{c.identification_code}</span>
                    </label>
                  ))}
                </div>
                <button
                  onClick={() => mergeMutation.mutate({ source_client_ids: mergeSources, target_client_id: viewClient.id })}
                  disabled={mergeSources.length === 0 || mergeMutation.isPending}
                  className="btn-primary w-full"
                >
                  {mergeMutation.isPending ? t('მიმდინარეობს...') : `${t('გაერთიანება')} (${mergeSources.length})`}
                </button>
              </div>
            )}

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
                    setImportResult(res.data.data?.message || t('იმპორტი დასრულდა'))
                  } catch (err: any) {
                    setImportResult(err?.response?.data?.detail || t('შეცდომა იმპორტის დროს'))
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