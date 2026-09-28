import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, FolderTree, Plus, Search, Download, Archive, Tag, Clock, ChevronDown, ChevronRight } from 'lucide-react'

import Modal from '../components/ui/Modal'
import { api } from '../services/api'
import type { ApiResponse, PaginatedResponse } from '../types'

interface DocumentCategory {
  id: string; code: string; name: string; is_active: boolean
}

interface Document {
  id: string; title: string; description: string | null
  category_id: string | null; category_name: string | null
  document_type: string; filename: string; file_size: number
  mime_type: string; tags: string | null; is_template: boolean
  is_archived: boolean; version: number
  created_at: string; updated_at: string
}

const typeLabels: Record<string, string> = {
  contract: 'ხელშეკრულება', invoice_received: 'შემოსული ინვოისი',
  report: 'ანგარიში', template: 'თარგი', hr_document: 'HR დოკუმენტი', other: 'სხვა',
}

const fmtSize = (bytes: number) => bytes > 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : bytes > 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${bytes} B`

export default function DocumentsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ title: '', description: '', category_id: '', document_type: 'other', tags: '' })
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['documents', search],
    queryFn: () => api.get('/documents/', { params: { search: search || undefined, page_size: 100 } }).then(r => r.data.data),
  })
  const { data: catData } = useQuery({
    queryKey: ['doc-categories'],
    queryFn: () => api.get('/documents/categories').then(r => r.data.data),
  })

  const docs: Document[] = data?.items || []
  const categories: DocumentCategory[] = catData || []

  const createMutation = useMutation({
    mutationFn: (fd: FormData) => api.post('/documents/upload', fd),
    onSuccess: () => { setShowModal(false); resetForm(); queryClient.invalidateQueries({ queryKey: ['documents'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  const archiveMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/documents/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
  })

  function resetForm() { setForm({ title: '', description: '', category_id: '', document_type: 'other', tags: '' }); setFile(null); setError('') }

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!file) { setError(t('ფაილი *')); return }
    const fd = new FormData()
    fd.append('title', form.title)
    fd.append('document_type', form.document_type)
    if (form.description) fd.append('description', form.description)
    if (form.category_id) fd.append('category_id', form.category_id)
    if (form.tags) fd.append('tags', form.tags)
    fd.append('file', file)
    createMutation.mutate(fd)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('დოკუმენტები')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('დოკუმენტების საცავი, თარგები, არქივი')}</p>
        </div>
        <button onClick={() => { resetForm(); setShowModal(true) }} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t('დოკუმენტის დამატება')}
        </button>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative min-w-64 flex-1">
          <Search className="absolute left-3 top-2.5 text-gray-400 dark:text-gray-500" size={18} />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder={t('ძებნა სათაურით, თეგებით...')}
            className="w-full rounded-lg border py-2 pl-10 pr-3 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('სათაური')}</th>
                <th className="px-4 py-3">{t('კატეგორია')}</th>
                <th className="px-4 py-3">{t('ტიპი')}</th>
                <th className="px-4 py-3">{t('ფაილი')}</th>
                <th className="px-4 py-3">{t('თეგები')}</th>
                <th className="px-4 py-3 text-right">{t('ვერსია')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {isLoading ? (
                <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
              ) : docs.length === 0 ? (
                <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('დოკუმენტები არ მოიძებნა')}</td></tr>
              ) : docs.map(doc => (
                <tr key={doc.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FileText size={16} className="text-primary-500 shrink-0" />
                      <span className="font-medium text-brandgray-900 dark:text-gray-100">{doc.title}</span>
                    </div>
                    {doc.description && <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{doc.description}</div>}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{doc.category_name || '—'}</td>
                  <td className="px-4 py-3"><span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs dark:bg-dark-100 dark:text-gray-400">{typeLabels[doc.document_type] || doc.document_type}</span></td>
                  <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">{doc.filename}<br/>{fmtSize(doc.file_size)}</td>
                  <td className="px-4 py-3">{doc.tags && <span className="text-xs text-gray-500 dark:text-gray-400">{doc.tags}</span>}</td>
                  <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400">v{doc.version}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => archiveMutation.mutate(doc.id)} className="text-red-500 hover:text-red-700 text-xs" title={t('დარქივება')}><Archive size={16} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={showModal} onClose={() => setShowModal(false)} title={t('ახალი დოკუმენტი')} size="lg">
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('სათაური *')}</label>
              <input required value={form.title} onChange={e => setForm({ ...form, title: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('კატეგორია')}</label>
              <select value={form.category_id} onChange={e => setForm({ ...form, category_id: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                <option value="">{t('აირჩიეთ')}</option>
                {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ტიპი')}</label>
              <select value={form.document_type} onChange={e => setForm({ ...form, document_type: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                {Object.entries(typeLabels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ფაილი *')}</label>
              <input required type="file" onChange={e => setFile(e.target.files?.[0] || null)}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('აღწერა')}</label>
              <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={2}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('თეგები (მძიმით გამოყოფილი)')}</label>
              <input value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </div>
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button type="submit" disabled={createMutation.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {createMutation.isPending ? t('ინახება...') : t('დოკუმენტის დამატება')}
          </button>
        </form>
      </Modal>
    </div>
  )
}
