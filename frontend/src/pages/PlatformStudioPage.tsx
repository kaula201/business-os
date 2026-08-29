import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  FileText, GitBranch, LayoutTemplate, ListFilter, Plus, Printer, ShieldCheck, Trash2, Upload,
} from 'lucide-react'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import { platformApi } from '../services/api'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

const tabs = [
  { id: 'fields', label: 'Custom Fields', icon: ListFilter },
  { id: 'workflows', label: 'Workflows', icon: GitBranch },
  { id: 'reports', label: 'Reports', icon: FileText },
  { id: 'pdf', label: 'PDF Templates', icon: Printer },
  { id: 'roles', label: 'Custom Roles', icon: ShieldCheck },
  { id: 'imports', label: 'Import Mapping', icon: Upload },
  { id: 'industry', label: 'Industry', icon: LayoutTemplate },
]

const entities = [
  { value: 'client', label: 'კლიენტი' },
  { value: 'supplier', label: 'მომწოდებელი' },
  { value: 'order', label: 'შეკვეთა' },
  { value: 'invoice', label: 'ინვოისი' },
  { value: 'product', label: 'პროდუქტი' },
  { value: 'task', label: 'დავალება' },
  { value: 'project', label: 'პროექტი' },
]

export default function PlatformStudioPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState('fields')
  const [error, setError] = useState('')
  const [pdfPreview, setPdfPreview] = useState<{ filename: string; base64: string } | null>(null)

  // ── queries
  const fieldsQ = useQuery({ queryKey: ['pf-fields'], queryFn: () => platformApi.customFields().then((r: any) => r.data.data) })
  const workflowsQ = useQuery({ queryKey: ['pf-workflows'], queryFn: () => platformApi.workflows().then((r: any) => r.data.data) })
  const reportsQ = useQuery({ queryKey: ['pf-reports'], queryFn: () => platformApi.reports().then((r: any) => r.data.data) })
  const pdfQ = useQuery({ queryKey: ['pf-pdf'], queryFn: () => platformApi.pdfTemplates().then((r: any) => r.data.data) })
  const rolesQ = useQuery({ queryKey: ['pf-roles'], queryFn: () => platformApi.customRoles().then((r: any) => r.data.data) })
  const importsQ = useQuery({ queryKey: ['pf-imports'], queryFn: () => platformApi.importMappings().then((r: any) => r.data.data) })
  const industryQ = useQuery({ queryKey: ['pf-industry'], queryFn: () => platformApi.industryTemplates().then((r: any) => r.data.data) })

  const err = (e: any) => setError(e?.response?.data?.detail || t('შეცდომა'))
  const refetchAll = () => {
    qc.invalidateQueries({ queryKey: ['pf-fields'] })
    qc.invalidateQueries({ queryKey: ['pf-workflows'] })
    qc.invalidateQueries({ queryKey: ['pf-reports'] })
    qc.invalidateQueries({ queryKey: ['pf-pdf'] })
    qc.invalidateQueries({ queryKey: ['pf-roles'] })
    qc.invalidateQueries({ queryKey: ['pf-imports'] })
    qc.invalidateQueries({ queryKey: ['pf-industry'] })
  }

  // ── field mutations
  const [fieldForm, setFieldForm] = useState({ entity_type: 'client', name: '', label_ka: '', field_type: 'text', options: '' })
  const [fieldOpen, setFieldOpen] = useState(false)
  const createField = useMutation({
    mutationFn: () => platformApi.createCustomField({
      ...fieldForm,
      options: fieldForm.field_type === 'select' && fieldForm.options ? fieldForm.options.split(',').map((s: string) => s.trim()).filter(Boolean) : undefined,
    }),
    onSuccess: () => { setFieldOpen(false); setFieldForm({ entity_type: 'client', name: '', label_ka: '', field_type: 'text', options: '' }); refetchAll() },
    onError: err,
  })
  const deleteField = useMutation({ mutationFn: (id: string) => platformApi.deleteCustomField(id), onSuccess: refetchAll, onError: err })

  // ── workflow mutations
  const [wfForm, setWfForm] = useState({ entity_type: 'order', name: '', steps: '' })
  const [wfOpen, setWfOpen] = useState(false)
  const createWorkflow = useMutation({
    mutationFn: () => platformApi.createWorkflow({
      entity_type: wfForm.entity_type, name: wfForm.name,
      steps: wfForm.steps.split('\n').filter(Boolean).map((line: string, i: number) => {
        const [name, from, to, role] = line.split('|').map((s: string) => s.trim())
        return { order: i + 1, name: name || `საფეხური ${i + 1}`, status_from: from || '', status_to: to || '', required_role: role || null }
      }),
    }),
    onSuccess: () => { setWfOpen(false); setWfForm({ entity_type: 'order', name: '', steps: '' }); refetchAll() },
    onError: err,
  })
  const deleteWorkflow = useMutation({ mutationFn: (id: string) => platformApi.deleteWorkflow(id), onSuccess: refetchAll, onError: err })

  // ── report mutations
  const [repForm, setRepForm] = useState({ name: '', entity_type: 'client', columns: '' })
  const [repOpen, setRepOpen] = useState(false)
  const createReport = useMutation({
    mutationFn: () => platformApi.createReport({
      name: repForm.name, entity_type: repForm.entity_type,
      columns: repForm.columns.split(',').filter(Boolean).map((s: string) => { const k = s.trim(); return { key: k, label: k } }),
    }),
    onSuccess: () => { setRepOpen(false); setRepForm({ name: '', entity_type: 'client', columns: '' }); refetchAll() },
    onError: err,
  })

  // ── pdf mutations
  const [pdfForm, setPdfForm] = useState({ name: '', doc_type: 'invoice', title: 'ინვოისი', color: '#2563eb', footer: '' })
  const [pdfOpen, setPdfOpen] = useState(false)
  const createPdf = useMutation({
    mutationFn: () => platformApi.createPdfTemplate({
      name: pdfForm.name, doc_type: pdfForm.doc_type,
      layout: { title: pdfForm.title, color: pdfForm.color, footer: pdfForm.footer || undefined },
    }),
    onSuccess: () => { setPdfOpen(false); setPdfForm({ name: '', doc_type: 'invoice', title: 'ინვოისი', color: '#2563eb', footer: '' }); refetchAll() },
    onError: err,
  })
  const deletePdf = useMutation({ mutationFn: (id: string) => platformApi.deletePdfTemplate(id), onSuccess: refetchAll, onError: err })
  const [previewId, setPreviewId] = useState<string | null>(null)
  const renderPdf = useMutation({
    mutationFn: (id: string) => platformApi.renderPdfTemplate(id, {
      number: 'PREVIEW-001', company_name: 'კომპანია', company_id_code: '000000000',
      client_name: 'კლიენტი', items: [{ name: 'მაგალითი პროდუქტი', qty: 2, price: 50, total: 100 }],
      subtotal: 100, vat: 18, total: 118, date: new Date().toISOString().slice(0, 10),
    }),
    onSuccess: (r: any) => {
      const d = r.data.data
      setPdfPreview({ filename: d.filename, base64: d.pdf_base64 })
    },
    onError: err,
  })

  // ── role mutations
  const [roleForm, setRoleForm] = useState({ name: '', perms: '' })
  const [roleOpen, setRoleOpen] = useState(false)
  const createRole = useMutation({
    mutationFn: () => platformApi.createCustomRole({
      name: roleForm.name,
      permissions: Object.fromEntries(
        roleForm.perms.split('\n').filter(Boolean).map((line: string) => {
          const [mod, access] = line.split('|').map((s: string) => s.trim())
          return [mod, { can_access: access !== 'no', can_create: access === 'full', can_edit: access === 'full', can_delete: false }]
        }),
      ),
    }),
    onSuccess: () => { setRoleOpen(false); setRoleForm({ name: '', perms: '' }); refetchAll() },
    onError: err,
  })
  const deleteRole = useMutation({ mutationFn: (id: string) => platformApi.deleteCustomRole(id), onSuccess: refetchAll, onError: err })

  // ── import mapping
  const [impForm, setImpForm] = useState({ entity_type: 'client', name: '', mapping: '' })
  const [impOpen, setImpOpen] = useState(false)
  const createImport = useMutation({
    mutationFn: () => platformApi.createImportMapping({
      entity_type: impForm.entity_type, name: impForm.name,
      mapping: Object.fromEntries(impForm.mapping.split('\n').filter(Boolean).map((line: string) => {
        const [src, dst] = line.split('→').map((s: string) => s.trim())
        return [src, dst]
      })),
    }),
    onSuccess: () => { setImpOpen(false); setImpForm({ entity_type: 'client', name: '', mapping: '' }); refetchAll() },
    onError: err,
  })
  const deleteImport = useMutation({ mutationFn: (id: string) => platformApi.deleteImportMapping(id), onSuccess: refetchAll, onError: err })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('პლატფორმა — სტუდია')}</h1>
        <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('Custom fields, workflows, reports, PDF, roles — Odoo-ს სტილის კონფიგურაციადი პლატფორმა')}</p>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/10 dark:text-red-300">{error}</div>}

      <div className="flex gap-1 border-b border-brandgray-100 dark:border-dark-50 overflow-x-auto">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${tab === t.id ? 'border-primary-600 text-primary-700 dark:border-primary-400 dark:text-primary-300' : 'border-transparent text-brandgray-500 hover:text-brandgray-700 dark:text-gray-400'}`}>
            <t.icon size={17} /> {t.label}
          </button>
        ))}
      </div>

      {/* Custom Fields */}
      {tab === 'fields' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button className="btn-primary flex items-center gap-2" onClick={() => setFieldOpen(true)}><Plus size={17} /> {t('ახალი ველი')}</button>
          </div>
          <div className="card overflow-hidden dark:bg-dark-200 dark:border-dark-50">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-dark-100 text-left text-xs text-gray-500 dark:text-gray-400">
                  <tr><th className="px-4 py-3">{t('entity')}</th><th className="px-4 py-3">{t('კოდი')}</th><th className="px-4 py-3">{t('დასახელება')}</th><th className="px-4 py-3">{t('ტიპი')}</th><th className="px-4 py-3">{t('სავალდებულო')}</th><th className="px-4 py-3"></th></tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-dark-50">
                  {(fieldsQ.data || []).map((f: any) => (
                    <tr key={f.id}>
                      <td className="px-4 py-3"><span className="badge badge-blue">{f.entity_type}</span></td>
                      <td className="px-4 py-3 font-mono text-xs">{f.name}</td>
                      <td className="px-4 py-3">{f.label_ka}</td>
                      <td className="px-4 py-3">{f.field_type}</td>
                      <td className="px-4 py-3">{f.required ? t('დიახ') : '—'}</td>
                      <td className="px-4 py-3 text-right"><button onClick={() => confirm(t('წავშალოთ?')) && deleteField.mutate(f.id)}><Trash2 size={16} className="text-red-500" /></button></td>
                    </tr>
                  ))}
                  {!fieldsQ.data?.length && <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">{t('ველები არ არის')}</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Workflows */}
      {tab === 'workflows' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button className="btn-primary flex items-center gap-2" onClick={() => setWfOpen(true)}><Plus size={17} /> {t('ახალი ვორქფლოუ')}</button>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {(workflowsQ.data || []).map((w: any) => (
              <div key={w.id} className="card p-4 dark:bg-dark-200 dark:border-dark-50">
                <div className="flex items-center justify-between">
                  <div><div className="font-semibold">{w.name}</div><div className="text-xs text-gray-400">{w.entity_type}</div></div>
                  <button onClick={() => confirm(t('წავშალოთ?')) && deleteWorkflow.mutate(w.id)}><Trash2 size={16} className="text-red-500" /></button>
                </div>
                <div className="mt-3 space-y-1.5">
                  {(w.steps || []).map((s: any, i: number) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
                      <GitBranch size={14} className="text-primary-600" />
                      {s.status_from || '—'} → {s.status_to || '—'} · {s.name} {s.required_role ? `· ${s.required_role}` : ''}
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {!workflowsQ.data?.length && <p className="col-span-2 text-sm text-gray-400">{t('ვორქფლოუები არ არის')}</p>}
          </div>
        </div>
      )}

      {/* Reports */}
      {tab === 'reports' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button className="btn-primary flex items-center gap-2" onClick={() => setRepOpen(true)}><Plus size={17} /> {t('ახალი ანგარიში')}</button>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {(reportsQ.data || []).map((r: any) => (
              <div key={r.id} className="card p-4 dark:bg-dark-200 dark:border-dark-50">
                <div className="flex items-center gap-3">
                  <FileText size={18} className="text-primary-600" />
                  <div className="flex-1"><div className="font-semibold">{r.name}</div><div className="text-xs text-gray-400">{r.entity_type} · {(r.columns || []).length} {t('სვეტი')}</div></div>
                  <a className="btn-secondary text-xs" href={`${import.meta.env.VITE_API_BASE || ''}/api/v1/platform/reports/${r.id}/export`} target="_blank" rel="noreferrer">{t('CSV ექსპორტი')}</a>
                </div>
              </div>
            ))}
            {!reportsQ.data?.length && <p className="col-span-2 text-sm text-gray-400">{t('ანგარიშები არ არის')}</p>}
          </div>
        </div>
      )}

      {/* PDF templates */}
      {tab === 'pdf' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button className="btn-primary flex items-center gap-2" onClick={() => setPdfOpen(true)}><Plus size={17} /> {t('ახალი PDF შაბლონი')}</button>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {(pdfQ.data || []).map((p: any) => (
              <div key={p.id} className="card p-4 dark:bg-dark-200 dark:border-dark-50">
                <div className="flex items-center justify-between">
                  <div><div className="font-semibold">{p.name}</div><div className="text-xs text-gray-400">{p.doc_type}</div></div>
                  <button onClick={() => confirm(t('წავშალოთ?')) && deletePdf.mutate(p.id)}><Trash2 size={16} className="text-red-500" /></button>
                </div>
                <div className="mt-3 flex gap-2">
                  <button className="btn-secondary text-xs flex items-center gap-1" onClick={() => { setPreviewId(p.id); renderPdf.mutate(p.id) }} disabled={renderPdf.isPending}>
                    <Printer size={14} /> {t('პრევიუ')}
                  </button>
                </div>
              </div>
            ))}
            {!pdfQ.data?.length && <p className="col-span-3 text-sm text-gray-400">{t('PDF შაბლონები არ არის')}</p>}
          </div>
        </div>
      )}

      {/* Custom roles */}
      {tab === 'roles' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button className="btn-primary flex items-center gap-2" onClick={() => setRoleOpen(true)}><Plus size={17} /> {t('ახალი როლი')}</button>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {(rolesQ.data || []).map((r: any) => (
              <div key={r.id} className="card p-4 dark:bg-dark-200 dark:border-dark-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2"><ShieldCheck size={17} className="text-primary-600" /><span className="font-semibold">{r.name}</span></div>
                  <button onClick={() => confirm(t('წავშალოთ?')) && deleteRole.mutate(r.id)}><Trash2 size={16} className="text-red-500" /></button>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {Object.entries(r.permissions || {}).map(([mod, perms]: any) => (
                    <span key={mod} className="badge badge-blue">{mod} · {perms.can_create ? 'full' : perms.can_access ? 'read' : '—'}</span>
                  ))}
                </div>
              </div>
            ))}
            {!rolesQ.data?.length && <p className="col-span-3 text-sm text-gray-400">{t('როლები არ არის')}</p>}
          </div>
        </div>
      )}

      {/* Import mapping */}
      {tab === 'imports' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button className="btn-primary flex items-center gap-2" onClick={() => setImpOpen(true)}><Plus size={17} /> {t('ახალი მეპინგი')}</button>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {(importsQ.data || []).map((m: any) => (
              <div key={m.id} className="card p-4 dark:bg-dark-200 dark:border-dark-50">
                <div className="flex items-center justify-between">
                  <div><div className="font-semibold">{m.name}</div><div className="text-xs text-gray-400">{m.entity_type}</div></div>
                  <button onClick={() => confirm(t('წავშალოთ?')) && deleteImport.mutate(m.id)}><Trash2 size={16} className="text-red-500" /></button>
                </div>
                <div className="mt-3 space-y-1 text-xs font-mono text-gray-600 dark:text-gray-300">
                  {Object.entries(m.mapping || {}).map(([src, dst]) => <div key={src}>{src} → {dst as string}</div>)}
                </div>
              </div>
            ))}
            {!importsQ.data?.length && <p className="col-span-2 text-sm text-gray-400">{t('მეპინგები არ არის')}</p>}
          </div>
        </div>
      )}

      {/* Industry templates */}
      {tab === 'industry' && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {(industryQ.data || []).map((it: any) => (
            <div key={it.id} className="card p-4 dark:bg-dark-200 dark:border-dark-50">
              <LayoutTemplate size={20} className="text-primary-600" />
              <div className="mt-2 font-semibold">{it.name_ka}</div>
              <div className="text-xs text-gray-400">{it.slug}</div>
              {it.description && <p className="mt-2 text-xs text-gray-600 dark:text-gray-300">{it.description}</p>}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {(it.modules || []).map((m: string) => <span key={m} className="badge badge-green">{m}</span>)}
              </div>
            </div>
          ))}
          {!industryQ.data?.length && <p className="col-span-3 text-sm text-gray-400">{t('ინდუსტრიის შაბლონები არ არის')}</p>}
        </div>
      )}

      {/* ── modals ── */}
      <Modal open={fieldOpen} onClose={() => setFieldOpen(false)} title={t('ახალი ველი')}>
        <div className="space-y-4">
          <FormField label={t('Entity')} required><Select value={fieldForm.entity_type} onChange={e => setFieldForm({ ...fieldForm, entity_type: e.target.value })} options={entities} /></FormField>
          <FormField label={t('კოდი (name)')} required><input className="input" value={fieldForm.name} onChange={e => setFieldForm({ ...fieldForm, name: e.target.value })} placeholder="custom_note" /></FormField>
          <FormField label={t('დასახელება (ქართული)')} required><input className="input" value={fieldForm.label_ka} onChange={e => setFieldForm({ ...fieldForm, label_ka: e.target.value })} /></FormField>
          <FormField label={t('ტიპი')}><Select value={fieldForm.field_type} onChange={e => setFieldForm({ ...fieldForm, field_type: e.target.value })} options={[{ value: 'text', label: 'Text' }, { value: 'number', label: 'Number' }, { value: 'date', label: 'Date' }, { value: 'boolean', label: 'Boolean' }, { value: 'select', label: 'Select' }]} /></FormField>
          {fieldForm.field_type === 'select' && <FormField label={t('ოფციები (მძიმით)')}><input className="input" value={fieldForm.options} onChange={e => setFieldForm({ ...fieldForm, options: e.target.value })} placeholder="ვარიანტი 1, ვარიანტი 2" /></FormField>}
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setFieldOpen(false)}>{t('გაუქმება')}</button><button className="btn-primary" disabled={!fieldForm.name || !fieldForm.label_ka || createField.isPending} onClick={() => createField.mutate()}>{t('შენახვა')}</button></div>
        </div>
      </Modal>

      <Modal open={wfOpen} onClose={() => setWfOpen(false)} title={t('ახალი ვორქფლოუ')}>
        <div className="space-y-4">
          <FormField label={t('Entity')} required><Select value={wfForm.entity_type} onChange={e => setWfForm({ ...wfForm, entity_type: e.target.value })} options={entities} /></FormField>
          <FormField label={t('სახელი')} required><input className="input" value={wfForm.name} onChange={e => setWfForm({ ...wfForm, name: e.target.value })} /></FormField>
          <FormField label={t('საფეხურები (თითო ხაზი: სახელი | from | to | როლი)')}><textarea className="input" rows={5} value={wfForm.steps} onChange={e => setWfForm({ ...wfForm, steps: e.target.value })} placeholder={'დამტკიცება | draft | confirmed | manager\nშიპინგი | confirmed | shipping |' } /></FormField>
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setWfOpen(false)}>{t('გაუქმება')}</button><button className="btn-primary" disabled={!wfForm.name || !wfForm.steps || createWorkflow.isPending} onClick={() => createWorkflow.mutate()}>{t('შენახვა')}</button></div>
        </div>
      </Modal>

      <Modal open={repOpen} onClose={() => setRepOpen(false)} title={t('ახალი ანგარიში')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')} required><input className="input" value={repForm.name} onChange={e => setRepForm({ ...repForm, name: e.target.value })} /></FormField>
          <FormField label={t('Entity')}><Select value={repForm.entity_type} onChange={e => setRepForm({ ...repForm, entity_type: e.target.value })} options={entities} /></FormField>
          <FormField label={t('სვეტები (მძიმით: name, identification_code, status)')}><input className="input" value={repForm.columns} onChange={e => setRepForm({ ...repForm, columns: e.target.value })} /></FormField>
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setRepOpen(false)}>{t('გაუქმება')}</button><button className="btn-primary" disabled={!repForm.name || !repForm.columns || createReport.isPending} onClick={() => createReport.mutate()}>{t('შენახვა')}</button></div>
        </div>
      </Modal>

      <Modal open={pdfOpen} onClose={() => setPdfOpen(false)} title={t('ახალი PDF შაბლონი')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')} required><input className="input" value={pdfForm.name} onChange={e => setPdfForm({ ...pdfForm, name: e.target.value })} /></FormField>
          <FormField label={t('ტიპი')}><Select value={pdfForm.doc_type} onChange={e => setPdfForm({ ...pdfForm, doc_type: e.target.value })} options={[{ value: 'invoice', label: 'ინვოისი' }, { value: 'waybill', label: 'ზედნადები' }, { value: 'report', label: 'ანგარიში' }]} /></FormField>
          <FormField label={t('სათაური')}><input className="input" value={pdfForm.title} onChange={e => setPdfForm({ ...pdfForm, title: e.target.value })} /></FormField>
          <FormField label={t('ფერი')}><input type="color" className="h-10 w-20" value={pdfForm.color} onChange={e => setPdfForm({ ...pdfForm, color: e.target.value })} /></FormField>
          <FormField label={t('ფუტერი')}><input className="input" value={pdfForm.footer} onChange={e => setPdfForm({ ...pdfForm, footer: e.target.value })} /></FormField>
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setPdfOpen(false)}>{t('გაუქმება')}</button><button className="btn-primary" disabled={!pdfForm.name || createPdf.isPending} onClick={() => createPdf.mutate()}>{t('შენახვა')}</button></div>
        </div>
      </Modal>

      <Modal open={roleOpen} onClose={() => setRoleOpen(false)} title={t('ახალი როლი')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')} required><input className="input" value={roleForm.name} onChange={e => setRoleForm({ ...roleForm, name: e.target.value })} /></FormField>
          <FormField label={t('უფლებები (თითო ხაზი: მოდული | read/full/no)')}><textarea className="input" rows={5} value={roleForm.perms} onChange={e => setRoleForm({ ...roleForm, perms: e.target.value })} placeholder={'pos | full\ninventory | read\nfinance | no'} /></FormField>
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setRoleOpen(false)}>{t('გაუქმება')}</button><button className="btn-primary" disabled={!roleForm.name || !roleForm.perms || createRole.isPending} onClick={() => createRole.mutate()}>{t('შენახვა')}</button></div>
        </div>
      </Modal>

      <Modal open={impOpen} onClose={() => setImpOpen(false)} title={t('ახალი იმპორტ მეპინგი')}>
        <div className="space-y-4">
          <FormField label={t('Entity')}><Select value={impForm.entity_type} onChange={e => setImpForm({ ...impForm, entity_type: e.target.value })} options={entities} /></FormField>
          <FormField label={t('სახელი')} required><input className="input" value={impForm.name} onChange={e => setImpForm({ ...impForm, name: e.target.value })} /></FormField>
          <FormField label={t('მეპინგი (თითო ხაზი: CSV სვეტი → ველი)')}><textarea className="input" rows={5} value={impForm.mapping} onChange={e => setImpForm({ ...impForm, mapping: e.target.value })} placeholder={'A → name\nB → identification_code'} /></FormField>
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setImpOpen(false)}>{t('გაუქმება')}</button><button className="btn-primary" disabled={!impForm.name || !impForm.mapping || createImport.isPending} onClick={() => createImport.mutate()}>{t('შენახვა')}</button></div>
        </div>
      </Modal>

      {pdfPreview && (
        <Modal open onClose={() => setPdfPreview(null)} title={pdfPreview.filename} size="lg">
          <iframe className="h-[70vh] w-full rounded-lg border" src={`data:application/pdf;base64,${pdfPreview.base64}`} />
          <div className="mt-3 flex justify-end"><button className="btn-secondary" onClick={() => setPdfPreview(null)}>{t('დახურვა')}</button></div>
        </Modal>
      )}
    </div>
  )
}
