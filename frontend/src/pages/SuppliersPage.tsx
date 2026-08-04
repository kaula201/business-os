import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, Building2, Pencil, Plus, Search } from 'lucide-react'

import ConfirmDialog from '../components/ui/ConfirmDialog'
import DataTable from '../components/ui/DataTable'
import FormField from '../components/ui/FormField'
import Modal from '../components/ui/Modal'
import { suppliersApi } from '../services/api'
import type { Supplier, SupplierCreate } from '../types'

const emptySupplier: SupplierCreate = {
  code: '',
  name: '',
  identification_code: '',
  is_vat_payer: false,
  contact_name: '',
  phone: '',
  email: '',
  address: '',
  bank_account: '',
  payment_terms_days: 0,
  notes: '',
}

export default function SuppliersPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [showInactive, setShowInactive] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Supplier | null>(null)
  const [archiveTarget, setArchiveTarget] = useState<Supplier | null>(null)
  const [form, setForm] = useState<SupplierCreate>(emptySupplier)
  const [formError, setFormError] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['suppliers', search, showInactive],
    queryFn: () => suppliersApi.list({ search: search || undefined, include_inactive: showInactive, page_size: 100 }).then((r) => r.data.data),
  })

  const suppliers: Supplier[] = data?.items || []

  const saveMutation = useMutation({
    mutationFn: () => editing
      ? suppliersApi.update(editing.id, form)
      : suppliersApi.create(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] })
      closeModal()
    },
    onError: (error: any) => setFormError(error.response?.data?.detail || 'მომწოდებლის შენახვა ვერ მოხერხდა'),
  })

  const archiveMutation = useMutation({
    mutationFn: (id: string) => suppliersApi.archive(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] })
      setArchiveTarget(null)
    },
    onError: (error: any) => {
      setFormError(error.response?.data?.detail || 'მომწოდებლის დეაქტივაცია ვერ მოხერხდა')
      setArchiveTarget(null)
    },
  })

  function openCreate() {
    setEditing(null)
    setForm({ ...emptySupplier })
    setFormError('')
    setModalOpen(true)
  }

  function openEdit(supplier: Supplier) {
    setEditing(supplier)
    setForm({
      code: supplier.code,
      name: supplier.name,
      identification_code: supplier.identification_code || '',
      is_vat_payer: supplier.is_vat_payer,
      contact_name: supplier.contact_name || '',
      phone: supplier.phone || '',
      email: supplier.email || '',
      address: supplier.address || '',
      bank_account: supplier.bank_account || '',
      payment_terms_days: supplier.payment_terms_days,
      notes: supplier.notes || '',
    })
    setFormError('')
    setModalOpen(true)
  }

  function closeModal() {
    setModalOpen(false)
    setEditing(null)
    setForm({ ...emptySupplier })
    setFormError('')
  }

  function submit(event: React.FormEvent) {
    event.preventDefault()
    setFormError('')
    saveMutation.mutate()
  }

  const columns = [
    {
      key: 'name', label: 'მომწოდებელი', render: (supplier: Supplier) => (
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <Building2 size={18} />
          </div>
          <div>
            <p className="font-medium text-gray-900 dark:text-gray-100">{supplier.name}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">{supplier.code}</p>
          </div>
        </div>
      ),
    },
    { key: 'identification_code', label: 'საიდენტიფიკაციო', render: (supplier: Supplier) => supplier.identification_code || '—' },
    { key: 'contact', label: 'კონტაქტი', hideOnMobile: true, render: (supplier: Supplier) => (
      <div><p>{supplier.contact_name || '—'}</p><p className="text-xs text-gray-500 dark:text-gray-400">{supplier.phone || supplier.email || ''}</p></div>
    ) },
    { key: 'terms', label: 'გადახდის ვადა', hideOnMobile: true, render: (supplier: Supplier) => `${supplier.payment_terms_days} დღე` },
    { key: 'status', label: 'სტატუსი', render: (supplier: Supplier) => (
      <span className={`badge ${supplier.is_active ? 'badge-green' : 'badge-gray'}`}>{supplier.is_active ? 'აქტიური' : 'არააქტიური'}</span>
    ) },
    { key: 'actions', label: '', render: (supplier: Supplier) => (
      <div className="flex justify-end gap-1">
        <button className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 text-gray-500 dark:text-gray-400" title="რედაქტირება" onClick={(e) => { e.stopPropagation(); openEdit(supplier) }}>
          <Pencil size={16} />
        </button>
        {supplier.is_active && (
          <button className="p-2 rounded-lg hover:bg-red-50 text-red-500" title="დეაქტივაცია" onClick={(e) => { e.stopPropagation(); setArchiveTarget(supplier) }}>
            <Archive size={16} />
          </button>
        )}
      </div>
    ) },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">მომწოდებლები</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">შესყიდვების პარტნიორები და გადახდის პირობები</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={openCreate}><Plus size={18} /> ახალი მომწოდებელი</button>
      </div>

      {formError && !modalOpen && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{formError}</div>}

      <div className="card flex flex-col sm:flex-row gap-3 items-center">
        <div className="relative flex-1 w-full">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input className="input pl-10" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="სახელი, კოდი ან საიდენტიფიკაციო ნომერი" />
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} /> არააქტიურების ჩვენება
        </label>
      </div>

      <DataTable columns={columns} data={suppliers} isLoading={isLoading} emptyMessage="მომწოდებელი ჯერ არ არის დამატებული" />

      <Modal open={modalOpen} onClose={closeModal} title={editing ? 'მომწოდებლის რედაქტირება' : 'ახალი მომწოდებელი'} size="lg">
        <form onSubmit={submit} className="space-y-5">
          {formError && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{formError}</div>}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FormField label="კოდი" required><input className="input" required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></FormField>
            <FormField label="დასახელება" required><input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></FormField>
            <FormField label="საიდენტიფიკაციო კოდი"><input className="input" value={form.identification_code || ''} onChange={(e) => setForm({ ...form, identification_code: e.target.value })} /></FormField>
            <FormField label="გადახდის ვადა (დღე)"><input type="number" min="0" className="input" value={form.payment_terms_days || 0} onChange={(e) => setForm({ ...form, payment_terms_days: Number(e.target.value) })} /></FormField>
            <FormField label="საკონტაქტო პირი"><input className="input" value={form.contact_name || ''} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} /></FormField>
            <FormField label="ტელეფონი"><input className="input" value={form.phone || ''} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></FormField>
            <FormField label="ელფოსტა"><input type="email" className="input" value={form.email || ''} onChange={(e) => setForm({ ...form, email: e.target.value })} /></FormField>
            <FormField label="საბანკო ანგარიში"><input className="input" value={form.bank_account || ''} onChange={(e) => setForm({ ...form, bank_account: e.target.value })} /></FormField>
          </div>
          <FormField label="მისამართი"><input className="input" value={form.address || ''} onChange={(e) => setForm({ ...form, address: e.target.value })} /></FormField>
          <FormField label="შენიშვნა"><textarea className="input min-h-20" value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></FormField>
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300"><input type="checkbox" checked={form.is_vat_payer || false} onChange={(e) => setForm({ ...form, is_vat_payer: e.target.checked })} /> დღგ-ის გადამხდელი</label>
          <div className="flex justify-end gap-3 pt-4 border-t"><button type="button" className="btn-secondary" onClick={closeModal}>გაუქმება</button><button className="btn-primary" disabled={saveMutation.isPending}>{saveMutation.isPending ? 'ინახება...' : 'შენახვა'}</button></div>
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(archiveTarget)}
        onClose={() => setArchiveTarget(null)}
        onConfirm={() => archiveTarget && archiveMutation.mutate(archiveTarget.id)}
        title="მომწოდებლის დეაქტივაცია"
        message={`${archiveTarget?.name || ''} აღარ გამოჩნდება ახალი შესყიდვის შეკვეთის შექმნისას. ისტორია შენარჩუნდება.`}
        confirmLabel="დეაქტივაცია"
        loading={archiveMutation.isPending}
      />
    </div>
  )
}
