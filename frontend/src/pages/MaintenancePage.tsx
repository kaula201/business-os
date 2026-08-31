import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Wrench, CalendarClock, Hammer, Plus, CheckCircle2, ClipboardList, CalendarDays, Boxes, MapPin, Gauge, Users, Handshake, Package, Coins, BarChart3, Settings2, Shield } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { maintenanceApi } from '../services/api'
import { fmtDate } from '../lib/format'

const statusBadge = (s: string) => {
  const map: Record<string, string> = {
    draft: 'badge', scheduled: 'badge-warning', in_progress: 'badge-info',
    completed: 'badge-success', cancelled: 'badge-danger', pending: 'badge-warning',
    done: 'badge-success', open: 'badge-danger',
  }
  return map[s] || 'badge'
}

const TABS: { key: string; label: string; icon: any }[] = [
  { key: 'requests', label: 'მოთხოვნები', icon: ClipboardList },
  { key: 'orders', label: 'სამუშაო დავალებები', icon: Wrench },
  { key: 'plans', label: 'მოვლის გეგმები', icon: CalendarClock },
  { key: 'calendar', label: 'კალენდარი', icon: CalendarDays },
  { key: 'assets', label: 'აქტივები', icon: Boxes },
  { key: 'locations', label: 'მდებარეობები', icon: MapPin },
  { key: 'meters', label: 'მრიცხველები', icon: Gauge },
  { key: 'technicians', label: 'ტექნიკოსები და გუნდები', icon: Users },
  { key: 'contractors', label: 'კონტრაქტორები და SLA', icon: Handshake },
  { key: 'parts', label: 'ნაწილები და მასალები', icon: Package },
  { key: 'safety', label: 'უსაფრთხოება', icon: Shield },
  { key: 'costs', label: 'ხარჯები', icon: Coins },
  { key: 'analytics', label: 'ანალიტიკა', icon: BarChart3 },
  { key: 'config', label: 'კონფიგურაცია', icon: Settings2 },
]

export default function MaintenancePage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab')
  const [tab, setTab] = useState<string>(requestedTab && TABS.some((x) => x.key === requestedTab) ? requestedTab : 'requests')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<Record<string, any>>({})

  const changeTab = (key: string) => {
    setTab(key)
    setSearchParams({ tab: key })
  }

  const { data: plans } = useQuery({ queryKey: ['maint-plans'], queryFn: () => maintenanceApi.plans().then(r => r.data.data) })
  const { data: orders } = useQuery({ queryKey: ['maint-orders'], queryFn: () => maintenanceApi.orders().then(r => r.data.data) })
  const { data: repairs } = useQuery({ queryKey: ['maint-repairs'], queryFn: () => maintenanceApi.repairs().then(r => r.data.data) })
  const { data: assets } = useQuery({ queryKey: ['maint-assets'], queryFn: () => maintenanceApi.assets().then(r => r.data.data) })
  const { data: requests } = useQuery({ queryKey: ['maint-requests'], queryFn: () => maintenanceApi.requests().then(r => r.data.data) })
  const { data: meters } = useQuery({ queryKey: ['maint-meters'], queryFn: () => maintenanceApi.meters().then(r => r.data.data) })
  const { data: locations } = useQuery({ queryKey: ['maint-locations'], queryFn: () => maintenanceApi.locations().then(r => r.data.data) })
  const { data: categories } = useQuery({ queryKey: ['maint-categories'], queryFn: () => maintenanceApi.assetCategories().then(r => r.data.data) })
  const { data: technicians } = useQuery({ queryKey: ['maint-technicians'], queryFn: () => maintenanceApi.technicians().then(r => r.data.data) })
  const { data: teams } = useQuery({ queryKey: ['maint-teams'], queryFn: () => maintenanceApi.teams().then(r => r.data.data) })
  const { data: contractors } = useQuery({ queryKey: ['maint-contractors'], queryFn: () => maintenanceApi.contractors().then(r => r.data.data) })
  const { data: slas } = useQuery({ queryKey: ['maint-slas'], queryFn: () => maintenanceApi.slas().then(r => r.data.data) })
  const { data: certificates } = useQuery({ queryKey: ['maint-certificates'], queryFn: () => maintenanceApi.certificates().then(r => r.data.data) })
  const { data: parts } = useQuery({ queryKey: ['maint-parts'], queryFn: () => maintenanceApi.parts().then(r => r.data.data) })
  const { data: partRequests } = useQuery({ queryKey: ['maint-part-requests'], queryFn: () => maintenanceApi.partRequests().then(r => r.data.data) })
  const { data: tools } = useQuery({ queryKey: ['maint-tools'], queryFn: () => maintenanceApi.tools().then(r => r.data.data) })
  const { data: toolIssues } = useQuery({ queryKey: ['maint-tool-issues'], queryFn: () => maintenanceApi.toolIssues().then(r => r.data.data) })
  const { data: safetyInstructions } = useQuery({ queryKey: ['maint-safety'], queryFn: () => maintenanceApi.safetyInstructions().then(r => r.data.data) })
  const { data: workPermits } = useQuery({ queryKey: ['maint-permits'], queryFn: () => maintenanceApi.workPermits().then(r => r.data.data) })
  const { data: checklists } = useQuery({ queryKey: ['maint-checklists'], queryFn: () => maintenanceApi.checklists().then(r => r.data.data) })
  const { data: incidents } = useQuery({ queryKey: ['maint-incidents'], queryFn: () => maintenanceApi.incidents().then(r => r.data.data) })

  const createPlan = useMutation({
    mutationFn: () => maintenanceApi.createPlan(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-plans'] }) },
  })
  const createOrder = useMutation({
    mutationFn: () => maintenanceApi.createOrder(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-orders'] }) },
  })
  const createRepair = useMutation({
    mutationFn: () => maintenanceApi.createRepair(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-repairs'] }) },
  })
  const createAsset = useMutation({
    mutationFn: () => maintenanceApi.createAsset(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-assets'] }) },
  })
  const createRequest = useMutation({
    mutationFn: () => maintenanceApi.createRequest(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-requests'] }) },
  })
  const createMeter = useMutation({
    mutationFn: () => maintenanceApi.createMeter(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-meters'] }) },
  })
  const createLocation = useMutation({
    mutationFn: () => maintenanceApi.createLocation(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-locations'] }) },
  })
  const updateOrder = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) => maintenanceApi.updateOrder(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['maint-orders'] }),
  })
  const updateRepair = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) => maintenanceApi.updateRepair(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['maint-repairs'] }),
  })
  const updateRequest = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) => maintenanceApi.updateRequest(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['maint-requests'] }),
  })
  const updateMeter = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) => maintenanceApi.updateMeter(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['maint-meters'] }),
  })
  const deleteAsset = useMutation({
    mutationFn: (id: string) => maintenanceApi.deleteAsset(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['maint-assets'] }),
  })
  const createTechnician = useMutation({
    mutationFn: () => maintenanceApi.createTechnician(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-technicians'] }) },
  })
  const createTeam = useMutation({
    mutationFn: () => maintenanceApi.createTeam(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-teams'] }) },
  })
  const createContractor = useMutation({
    mutationFn: () => maintenanceApi.createContractor(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-contractors'] }) },
  })
  const createSla = useMutation({
    mutationFn: () => maintenanceApi.createSla(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-slas'] }) },
  })
  const createCertificate = useMutation({
    mutationFn: () => maintenanceApi.createCertificate(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-certificates'] }) },
  })
  const createPart = useMutation({
    mutationFn: () => maintenanceApi.createPart(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-parts'] }) },
  })
  const createPartRequest = useMutation({
    mutationFn: () => maintenanceApi.createPartRequest(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-part-requests'] }) },
  })
  const createTool = useMutation({
    mutationFn: () => maintenanceApi.createTool(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-tools'] }) },
  })
  const issueTool = useMutation({
    mutationFn: () => maintenanceApi.issueTool(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-tool-issues'] }); qc.invalidateQueries({ queryKey: ['maint-tools'] }) },
  })
  const returnTool = useMutation({
    mutationFn: (id: string) => maintenanceApi.returnTool(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['maint-tool-issues'] }); qc.invalidateQueries({ queryKey: ['maint-tools'] }) },
  })
  const createSafetyInstruction = useMutation({
    mutationFn: () => maintenanceApi.createSafetyInstruction(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-safety'] }) },
  })
  const createWorkPermit = useMutation({
    mutationFn: () => maintenanceApi.createWorkPermit(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-permits'] }) },
  })
  const approveWorkPermit = useMutation({
    mutationFn: (id: string) => maintenanceApi.updateWorkPermit(id, { status: 'approved' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['maint-permits'] }),
  })
  const createChecklist = useMutation({
    mutationFn: (data: Record<string, unknown>) => maintenanceApi.createChecklist(data),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-checklists'] }) },
  })
  const createIncident = useMutation({
    mutationFn: () => maintenanceApi.createIncident(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-incidents'] }) },
  })
  const resolveIncident = useMutation({
    mutationFn: (id: string) => maintenanceApi.updateIncident(id, { status: 'resolved' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['maint-incidents'] }),
  })

  const openCreate = (kind: string) => {
    setForm({ kind })
    setOpen(true)
  }

  const renderForm = () => {
    const kind = form.kind
    if (kind === 'plan') return (
      <>
        <FormField label={t('სახელი')}><input className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('ინტერვალი (დღე)')}><input type="number" className="input" value={form.interval_days || 30} onChange={e => setForm({ ...form, interval_days: e.target.value })} /></FormField>
        <FormField label={t('შემდეგი ვადა')}><input type="date" className="input" value={form.next_due_at || ''} onChange={e => setForm({ ...form, next_due_at: e.target.value })} /></FormField>
      </>
    )
    if (kind === 'order') return (
      <>
        <FormField label={t('აქტივი')}><input className="input" value={form.asset_name || ''} onChange={e => setForm({ ...form, asset_name: e.target.value })} /></FormField>
        <FormField label={t('ტიპი')}>
          <select className="input" value={form.maintenance_type || 'preventive'} onChange={e => setForm({ ...form, maintenance_type: e.target.value })}>
            <option value="preventive">Preventive</option><option value="corrective">Corrective</option><option value="predictive">Predictive</option><option value="emergency">Emergency</option>
          </select>
        </FormField>
        <FormField label={t('პრიორიტეტი')}>
          <select className="input" value={form.priority || 'medium'} onChange={e => setForm({ ...form, priority: e.target.value })}>
            <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
          </select>
        </FormField>
        <FormField label={t('თარიღი')}><input type="date" className="input" value={form.scheduled_date || ''} onChange={e => setForm({ ...form, scheduled_date: e.target.value })} /></FormField>
        <FormField label={t('აღწერა')}><textarea className="input min-h-[80px]" value={form.description || ''} onChange={e => setForm({ ...form, description: e.target.value })} /></FormField>
      </>
    )
    if (kind === 'asset') return (
      <>
        <FormField label={t('აქტივის კოდი')} required><input required className="input" value={form.asset_code || ''} onChange={e => setForm({ ...form, asset_code: e.target.value })} /></FormField>
        <FormField label={t('სახელი')} required><input required className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('კატეგორია')}>
          <select className="input" value={form.category_id || ''} onChange={e => setForm({ ...form, category_id: e.target.value || null })}>
            <option value="">—</option>
            {(categories || []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </FormField>
        <FormField label={t('მდებარეობა')}>
          <select className="input" value={form.location_id || ''} onChange={e => setForm({ ...form, location_id: e.target.value || null })}>
            <option value="">—</option>
            {(locations || []).map((l: any) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </FormField>
        <FormField label={t('მწარმოებელი')}><input className="input" value={form.manufacturer || ''} onChange={e => setForm({ ...form, manufacturer: e.target.value })} /></FormField>
        <FormField label={t('სერიული ნომერი')}><input className="input" value={form.serial_number || ''} onChange={e => setForm({ ...form, serial_number: e.target.value })} /></FormField>
        <FormField label={t('შეძენის ღირებულება')}><input type="number" className="input" value={form.purchase_cost || 0} onChange={e => setForm({ ...form, purchase_cost: Number(e.target.value) })} /></FormField>
        <FormField label={t('გარანტია ვადა')}><input type="date" className="input" value={form.warranty_until || ''} onChange={e => setForm({ ...form, warranty_until: e.target.value })} /></FormField>
      </>
    )
    if (kind === 'request') return (
      <>
        <FormField label={t('აქტივი')}>
          <select className="input" value={form.asset_id || ''} onChange={e => setForm({ ...form, asset_id: e.target.value || null })}>
            <option value="">—</option>
            {(assets || []).map((a: any) => <option key={a.id} value={a.id}>{a.asset_code} — {a.name}</option>)}
          </select>
        </FormField>
        <FormField label={t('სათაური')} required><input required className="input" value={form.title || ''} onChange={e => setForm({ ...form, title: e.target.value })} /></FormField>
        <FormField label={t('პრიორიტეტი')}>
          <select className="input" value={form.priority || 'medium'} onChange={e => setForm({ ...form, priority: e.target.value })}>
            <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
          </select>
        </FormField>
        <FormField label={t('აღწერა')}><textarea className="input min-h-[80px]" value={form.description || ''} onChange={e => setForm({ ...form, description: e.target.value })} /></FormField>
      </>
    )
    if (kind === 'meter') return (
      <>
        <FormField label={t('აქტივი')} required>
          <select required className="input" value={form.asset_id || ''} onChange={e => setForm({ ...form, asset_id: e.target.value })}>
            <option value="">—</option>
            {(assets || []).map((a: any) => <option key={a.id} value={a.id}>{a.asset_code} — {a.name}</option>)}
          </select>
        </FormField>
        <FormField label={t('სახელი')} required><input required className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('ერთეული')}>
          <select className="input" value={form.unit || 'hours'} onChange={e => setForm({ ...form, unit: e.target.value })}>
            <option value="hours">Hours</option><option value="km">Km</option><option value="cycles">Cycles</option>
          </select>
        </FormField>
        <FormField label={t('მიმდინარე მნიშვნელობა')}><input type="number" className="input" value={form.current_value || 0} onChange={e => setForm({ ...form, current_value: Number(e.target.value) })} /></FormField>
      </>
    )
    if (kind === 'location') return (
      <>
        <FormField label={t('სახელი')} required><input required className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('აღწერა')}><textarea className="input min-h-[80px]" value={form.description || ''} onChange={e => setForm({ ...form, description: e.target.value })} /></FormField>
      </>
    )
    if (kind === 'technician') return (
      <>
        <FormField label={t('სახელი')} required><input required className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('სპეციალიზაცია')}><input className="input" value={form.specialization || ''} onChange={e => setForm({ ...form, specialization: e.target.value })} /></FormField>
        <FormField label={t('ტელეფონი')}><input className="input" value={form.phone || ''} onChange={e => setForm({ ...form, phone: e.target.value })} /></FormField>
        <FormField label={t('საათობრივი ტარიფი')}><input type="number" className="input" value={form.hourly_rate || 0} onChange={e => setForm({ ...form, hourly_rate: Number(e.target.value) })} /></FormField>
      </>
    )
    if (kind === 'team') return (
      <>
        <FormField label={t('სახელი')} required><input required className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('ლიდერი')}>
          <select className="input" value={form.leader_id || ''} onChange={e => setForm({ ...form, leader_id: e.target.value || null })}>
            <option value="">—</option>
            {(technicians || []).map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </FormField>
        <FormField label={t('აღწერა')}><textarea className="input min-h-[80px]" value={form.description || ''} onChange={e => setForm({ ...form, description: e.target.value })} /></FormField>
      </>
    )
    if (kind === 'contractor') return (
      <>
        <FormField label={t('სახელი')} required><input required className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('საკონტაქტო პირი')}><input className="input" value={form.contact_person || ''} onChange={e => setForm({ ...form, contact_person: e.target.value })} /></FormField>
        <FormField label={t('სპეციალიზაცია')}><input className="input" value={form.specialization || ''} onChange={e => setForm({ ...form, specialization: e.target.value })} /></FormField>
        <FormField label={t('საათობრივი ტარიფი')}><input type="number" className="input" value={form.hourly_rate || 0} onChange={e => setForm({ ...form, hourly_rate: Number(e.target.value) })} /></FormField>
      </>
    )
    if (kind === 'sla') return (
      <>
        <FormField label={t('სახელი')} required><input required className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('პრიორიტეტი')}>
          <select className="input" value={form.priority || 'medium'} onChange={e => setForm({ ...form, priority: e.target.value })}>
            <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
          </select>
        </FormField>
        <FormField label={t('რეაგირების დრო (სთ)')}><input type="number" className="input" value={form.response_hours || 4} onChange={e => setForm({ ...form, response_hours: Number(e.target.value) })} /></FormField>
        <FormField label={t('მოგვარების დრო (სთ)')}><input type="number" className="input" value={form.resolution_hours || 24} onChange={e => setForm({ ...form, resolution_hours: Number(e.target.value) })} /></FormField>
        <FormField label={t('კონტრაქტორი')}>
          <select className="input" value={form.contractor_id || ''} onChange={e => setForm({ ...form, contractor_id: e.target.value || null })}>
            <option value="">—</option>
            {(contractors || []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </FormField>
      </>
    )
    if (kind === 'certificate') return (
      <>
        <FormField label={t('ტექნიკოსი')} required>
          <select required className="input" value={form.technician_id || ''} onChange={e => setForm({ ...form, technician_id: e.target.value })}>
            <option value="">—</option>
            {(technicians || []).map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </FormField>
        <FormField label={t('სერტიფიკატის სახელი')} required><input required className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('ვადის გასვლა')}><input type="date" className="input" value={form.expiry_date || ''} onChange={e => setForm({ ...form, expiry_date: e.target.value })} /></FormField>
      </>
    )
    if (kind === 'part') return (
      <>
        <FormField label={t('ნაწილის კოდი')} required><input required className="input" value={form.part_code || ''} onChange={e => setForm({ ...form, part_code: e.target.value })} /></FormField>
        <FormField label={t('სახელი')} required><input required className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('კატეგორია')}><input className="input" value={form.category || ''} onChange={e => setForm({ ...form, category: e.target.value })} /></FormField>
        <FormField label={t('რაოდენობა')}><input type="number" className="input" value={form.quantity_on_hand || 0} onChange={e => setForm({ ...form, quantity_on_hand: e.target.value })} /></FormField>
        <FormField label={t('მინიმალური მარაგი')}><input type="number" className="input" value={form.reorder_level || 0} onChange={e => setForm({ ...form, reorder_level: e.target.value })} /></FormField>
        <FormField label={t('ერთეულის ფასი')}><input type="number" className="input" value={form.unit_cost || 0} onChange={e => setForm({ ...form, unit_cost: e.target.value })} /></FormField>
        <FormField label={t('მდებარეობა')}><input className="input" value={form.location || ''} onChange={e => setForm({ ...form, location: e.target.value })} /></FormField>
        <FormField label={t('მომწოდებელი')}><input className="input" value={form.supplier || ''} onChange={e => setForm({ ...form, supplier: e.target.value })} /></FormField>
      </>
    )
    if (kind === 'part-request') return (
      <>
        <FormField label={t('ნაწილი')} required>
          <select required className="input" value={form.part_id || ''} onChange={e => setForm({ ...form, part_id: e.target.value })}>
            <option value="">—</option>
            {(parts || []).map((p: any) => <option key={p.id} value={p.id}>{p.part_code} — {p.name}</option>)}
          </select>
        </FormField>
        <FormField label={t('რაოდენობა')}><input type="number" className="input" value={form.quantity || 1} onChange={e => setForm({ ...form, quantity: e.target.value })} /></FormField>
      </>
    )
    if (kind === 'tool') return (
      <>
        <FormField label={t('ხელსაწყოს კოდი')} required><input required className="input" value={form.tool_code || ''} onChange={e => setForm({ ...form, tool_code: e.target.value })} /></FormField>
        <FormField label={t('სახელი')} required><input required className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('კატეგორია')}><input className="input" value={form.category || ''} onChange={e => setForm({ ...form, category: e.target.value })} /></FormField>
        <FormField label={t('რაოდენობა')}><input type="number" className="input" value={form.quantity || 1} onChange={e => setForm({ ...form, quantity: e.target.value })} /></FormField>
      </>
    )
    if (kind === 'tool-issue') return (
      <>
        <FormField label={t('ხელსაწყო')} required>
          <select required className="input" value={form.tool_id || ''} onChange={e => setForm({ ...form, tool_id: e.target.value })}>
            <option value="">—</option>
            {(tools || []).filter((tl: any) => tl.available > 0).map((tl: any) => <option key={tl.id} value={tl.id}>{tl.tool_code} — {tl.name} ({tl.available})</option>)}
          </select>
        </FormField>
        <FormField label={t('ტექნიკოსი')} required>
          <select required className="input" value={form.technician_id || ''} onChange={e => setForm({ ...form, technician_id: e.target.value })}>
            <option value="">—</option>
            {(technicians || []).map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </FormField>
      </>
    )
    if (kind === 'safety') return (
      <>
        <FormField label={t('სათაური')} required><input required className="input" value={form.title || ''} onChange={e => setForm({ ...form, title: e.target.value })} /></FormField>
        <FormField label={t('კატეგორია')}><input className="input" value={form.category || ''} onChange={e => setForm({ ...form, category: e.target.value })} /></FormField>
        <FormField label={t('შინაარსი')}><textarea className="input" rows={3} value={form.content || ''} onChange={e => setForm({ ...form, content: e.target.value })} /></FormField>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={!!form.is_mandatory} onChange={e => setForm({ ...form, is_mandatory: e.target.checked })} />
          {t('სავალდებულო')}
        </label>
      </>
    )
    if (kind === 'permit') return (
      <>
        <FormField label={t('ნებართვის ნომერი')} required><input required className="input" value={form.permit_number || ''} onChange={e => setForm({ ...form, permit_number: e.target.value })} /></FormField>
        <FormField label={t('სამუშაოს ტიპი')} required><input required className="input" value={form.work_type || ''} onChange={e => setForm({ ...form, work_type: e.target.value })} /></FormField>
        <FormField label={t('მდებარეობა')}><input className="input" value={form.location || ''} onChange={e => setForm({ ...form, location: e.target.value })} /></FormField>
        <FormField label={t('რისკის დონე')}>
          <select className="input" value={form.risk_level || 'low'} onChange={e => setForm({ ...form, risk_level: e.target.value })}>
            <option value="low">{t('დაბალი')}</option>
            <option value="medium">{t('საშუალო')}</option>
            <option value="high">{t('მაღალი')}</option>
            <option value="critical">{t('კრიტიკული')}</option>
          </select>
        </FormField>
      </>
    )
    if (kind === 'checklist') return (
      <>
        <FormField label={t('სახელი')} required><input required className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('კატეგორია')}><input className="input" value={form.category || ''} onChange={e => setForm({ ...form, category: e.target.value })} /></FormField>
        <FormField label={t('პუნქტები (მძიმით გამოყოფილი)')}><textarea className="input" rows={3} value={form.items_text || ''} onChange={e => setForm({ ...form, items_text: e.target.value })} /></FormField>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={!!form.is_mandatory} onChange={e => setForm({ ...form, is_mandatory: e.target.checked })} />
          {t('სავალდებულო')}
        </label>
      </>
    )
    if (kind === 'incident') return (
      <>
        <FormField label={t('ინციდენტის ნომერი')} required><input required className="input" value={form.incident_number || ''} onChange={e => setForm({ ...form, incident_number: e.target.value })} /></FormField>
        <FormField label={t('სათაური')} required><input required className="input" value={form.title || ''} onChange={e => setForm({ ...form, title: e.target.value })} /></FormField>
        <FormField label={t('სიმძიმე')}>
          <select className="input" value={form.severity || 'low'} onChange={e => setForm({ ...form, severity: e.target.value })}>
            <option value="low">{t('დაბალი')}</option>
            <option value="medium">{t('საშუალო')}</option>
            <option value="high">{t('მაღალი')}</option>
            <option value="critical">{t('კრიტიკული')}</option>
          </select>
        </FormField>
        <FormField label={t('აღწერა')}><textarea className="input" rows={3} value={form.description || ''} onChange={e => setForm({ ...form, description: e.target.value })} /></FormField>
      </>
    )
    return (
      <>
        <FormField label={t('აღჭურვილობა')}><input className="input" value={form.equipment_name || ''} onChange={e => setForm({ ...form, equipment_name: e.target.value })} /></FormField>
        <FormField label={t('პრიორიტეტი')}>
          <select className="input" value={form.priority || 'medium'} onChange={e => setForm({ ...form, priority: e.target.value })}>
            <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
          </select>
        </FormField>
        <FormField label={t('აღწერა')}><textarea className="input min-h-[80px]" value={form.description || ''} onChange={e => setForm({ ...form, description: e.target.value })} /></FormField>
      </>
    )
  }

  const submit = () => {
    if (form.kind === 'plan') createPlan.mutate()
    else if (form.kind === 'order') createOrder.mutate()
    else if (form.kind === 'asset') createAsset.mutate()
    else if (form.kind === 'request') createRequest.mutate()
    else if (form.kind === 'meter') createMeter.mutate()
    else if (form.kind === 'location') createLocation.mutate()
    else if (form.kind === 'technician') createTechnician.mutate()
    else if (form.kind === 'team') createTeam.mutate()
    else if (form.kind === 'contractor') createContractor.mutate()
    else if (form.kind === 'sla') createSla.mutate()
    else if (form.kind === 'certificate') createCertificate.mutate()
    else if (form.kind === 'part') createPart.mutate()
    else if (form.kind === 'part-request') createPartRequest.mutate()
    else if (form.kind === 'tool') createTool.mutate()
    else if (form.kind === 'tool-issue') issueTool.mutate()
    else if (form.kind === 'safety') createSafetyInstruction.mutate()
    else if (form.kind === 'permit') createWorkPermit.mutate()
    else if (form.kind === 'checklist') {
      const items = (form.items_text || '').split(',').map((s: string) => s.trim()).filter(Boolean)
      createChecklist.mutate({ ...form, items })
    }
    else if (form.kind === 'incident') createIncident.mutate()
    else createRepair.mutate()
  }

  const EmptyState = ({ text }: { text: string }) => (
    <div className="rounded-xl border border-dashed border-gray-300 p-10 text-center text-sm text-gray-500 dark:border-dark-50 dark:text-gray-400">{text}</div>
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('მოვლა და შეკეთება')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('მოთხოვნები, სამუშაო დავალებები, გეგმები, აქტივები და ანალიტიკა')}</p>
        </div>
        {['requests', 'orders', 'plans', 'assets', 'meters', 'locations'].includes(tab) && (
          <button onClick={() => openCreate(tab === 'plans' ? 'plan' : tab === 'orders' ? 'order' : tab === 'assets' ? 'asset' : tab === 'meters' ? 'meter' : tab === 'locations' ? 'location' : 'request')} className="btn btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('ახალი')}
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-1 border-b pb-2 dark:border-dark-50">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => changeTab(key)} className={`flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium ${tab === key ? 'border-primary-600 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'}`}>
            <Icon size={15} /> {t(label)}
          </button>
        ))}
      </div>

      {tab === 'plans' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('სახელი')}</th>
                <th className="px-4 py-3">{t('ინტერვალი')}</th>
                <th className="px-4 py-3">{t('შემდეგი ვადა')}</th>
                <th className="px-4 py-3">{t('აქტიური')}</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(plans || []).length === 0 ? (
                <tr><td colSpan={4} className="p-8 text-center text-gray-500">{t('გეგმები არ არის')}</td></tr>
              ) : (plans || []).map((p: any) => (
                <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{p.name}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{p.interval_days} {t('დღე')}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{p.next_due_at ? fmtDate(new Date(p.next_due_at)) : '—'}</td>
                  <td className="px-4 py-3">{p.is_active ? <span className="badge badge-success">{t('აქტიური')}</span> : <span className="badge">{t('გაჩერებული')}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'orders' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('ნომერი')}</th>
                <th className="px-4 py-3">{t('აქტივი')}</th>
                <th className="px-4 py-3">{t('ტიპი')}</th>
                <th className="px-4 py-3">{t('სტატუსი')}</th>
                <th className="px-4 py-3">{t('თარიღი')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(orders || []).length === 0 ? (
                <tr><td colSpan={6} className="p-8 text-center text-gray-500">{t('დავალებები არ არის')}</td></tr>
              ) : (orders || []).map((o: any) => (
                <tr key={o.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{o.order_number}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{o.asset_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{o.maintenance_type}</td>
                  <td className="px-4 py-3"><span className={`badge ${statusBadge(o.status)}`}>{o.status}</span></td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{o.scheduled_date ? fmtDate(new Date(o.scheduled_date)) : '—'}</td>
                  <td className="px-4 py-3">
                    {o.status !== 'completed' && (
                      <button onClick={() => updateOrder.mutate({ id: o.id, data: { status: 'completed' } })} className="btn btn-sm btn-success flex items-center gap-1">
                        <CheckCircle2 size={14} /> {t('დასრულება')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'requests' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('ნომერი')}</th>
                <th className="px-4 py-3">{t('აღჭურვილობა')}</th>
                <th className="px-4 py-3">{t('სტატუსი')}</th>
                <th className="px-4 py-3">{t('პრიორიტეტი')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(repairs || []).length === 0 ? (
                <tr><td colSpan={5} className="p-8 text-center text-gray-500">{t('მოთხოვნები არ არის')}</td></tr>
              ) : (repairs || []).map((r: any) => (
                <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{r.repair_number}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.equipment_name || '—'}</td>
                  <td className="px-4 py-3"><span className={`badge ${statusBadge(r.status)}`}>{r.status}</span></td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.priority}</td>
                  <td className="px-4 py-3">
                    {r.status !== 'done' && (
                      <button onClick={() => updateRepair.mutate({ id: r.id, data: { status: 'done' } })} className="btn btn-sm btn-success flex items-center gap-1">
                        <CheckCircle2 size={14} /> {t('დასრულება')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'assets' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => openCreate('asset')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი აქტივი')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('კოდი')}</th>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('კატეგორია')}</th>
                  <th className="px-4 py-3">{t('მდებარეობა')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3">{t('გარანტია')}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(assets || []).length === 0 ? (
                  <tr><td colSpan={7} className="p-8 text-center text-gray-500">{t('აქტივები არ არის')}</td></tr>
                ) : (assets || []).map((a: any) => (
                  <tr key={a.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{a.asset_code}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{a.name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{a.category_name || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{a.location_name || '—'}</td>
                    <td className="px-4 py-3"><span className={`badge ${statusBadge(a.status)}`}>{a.status}</span></td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{a.warranty_until ? fmtDate(new Date(a.warranty_until)) : '—'}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => { if (window.confirm(t('წავშალოთ?'))) deleteAsset.mutate(a.id) }} className="text-xs font-semibold text-red-600 hover:underline">{t('წაშლა')}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'requests' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => openCreate('request')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი მოთხოვნა')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('ნომერი')}</th>
                  <th className="px-4 py-3">{t('სათაური')}</th>
                  <th className="px-4 py-3">{t('აქტივი')}</th>
                  <th className="px-4 py-3">{t('პრიორიტეტი')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(requests || []).length === 0 ? (
                  <tr><td colSpan={6} className="p-8 text-center text-gray-500">{t('მოთხოვნები არ არის')}</td></tr>
                ) : (requests || []).map((r: any) => (
                  <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{r.request_number}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.title}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.asset_name || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.priority}</td>
                    <td className="px-4 py-3"><span className={`badge ${statusBadge(r.status)}`}>{r.status}</span></td>
                    <td className="px-4 py-3">
                      {r.status !== 'completed' && (
                        <button onClick={() => updateRequest.mutate({ id: r.id, data: { status: 'completed' } })} className="btn btn-sm btn-success flex items-center gap-1">
                          <CheckCircle2 size={14} /> {t('დასრულება')}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'meters' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => openCreate('meter')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი მრიცხველი')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('აქტივი')}</th>
                  <th className="px-4 py-3">{t('ერთეული')}</th>
                  <th className="px-4 py-3">{t('მიმდინარე მნიშვნელობა')}</th>
                  <th className="px-4 py-3">{t('ბოლო წაკითხვა')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(meters || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500">{t('მრიცხველები არ არის')}</td></tr>
                ) : (meters || []).map((m: any) => (
                  <tr key={m.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{m.name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{m.asset_name || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{m.unit}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{m.current_value}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{m.last_reading_at ? fmtDate(new Date(m.last_reading_at)) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'locations' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => openCreate('location')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი მდებარეობა')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('აღწერა')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(locations || []).length === 0 ? (
                  <tr><td colSpan={2} className="p-8 text-center text-gray-500">{t('მდებარეობები არ არის')}</td></tr>
                ) : (locations || []).map((l: any) => (
                  <tr key={l.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{l.name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{l.description || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'technicians' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => openCreate('technician')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი ტექნიკოსი')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('სპეციალიზაცია')}</th>
                  <th className="px-4 py-3">{t('ტელეფონი')}</th>
                  <th className="px-4 py-3">{t('საათობრივი ტარიფი')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(technicians || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500">{t('ტექნიკოსები არ არის')}</td></tr>
                ) : (technicians || []).map((t: any) => (
                  <tr key={t.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{t.name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{t.specialization || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{t.phone || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{t.hourly_rate} ₾</td>
                    <td className="px-4 py-3">{t.is_active ? <span className="badge badge-success">{t('აქტიური')}</span> : <span className="badge">{t('გაჩერებული')}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'contractors' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => openCreate('contractor')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი კონტრაქტორი')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('საკონტაქტო პირი')}</th>
                  <th className="px-4 py-3">{t('სპეციალიზაცია')}</th>
                  <th className="px-4 py-3">{t('საათობრივი ტარიფი')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(contractors || []).length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500">{t('კონტრაქტორები არ არის')}</td></tr>
                ) : (contractors || []).map((c: any) => (
                  <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{c.name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{c.contact_person || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{c.specialization || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{c.hourly_rate} ₾</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'parts' && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <button onClick={() => openCreate('part')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი ნაწილი')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('კოდი')}</th>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('კატეგორია')}</th>
                  <th className="px-4 py-3">{t('რაოდენობა')}</th>
                  <th className="px-4 py-3">{t('მინ. მარაგი')}</th>
                  <th className="px-4 py-3">{t('ფასი')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(parts || []).length === 0 ? (
                  <tr><td colSpan={7} className="p-8 text-center text-gray-500">{t('ნაწილები არ არის')}</td></tr>
                ) : (parts || []).map((p: any) => (
                  <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{p.part_code}</td>
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{p.name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{p.category || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{p.quantity_on_hand} {p.unit}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{p.reorder_level}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{p.unit_cost} ₾</td>
                    <td className="px-4 py-3">{p.is_low ? <span className="badge badge-danger">{t('დეფიციტი')}</span> : <span className="badge badge-success">{t('ნორმაში')}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end">
            <button onClick={() => openCreate('part-request')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი მოთხოვნა')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('ნაწილი')}</th>
                  <th className="px-4 py-3">{t('რაოდენობა')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3">{t('მოთხოვნილია')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(partRequests || []).length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500">{t('მოთხოვნები არ არის')}</td></tr>
                ) : (partRequests || []).map((pr: any) => (
                  <tr key={pr.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{pr.part_name || pr.part_code}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{pr.quantity}</td>
                    <td className="px-4 py-3">
                      {pr.status === 'issued' ? <span className="badge badge-success">{t('გაცემული')}</span> : pr.status === 'reserved' ? <span className="badge">{t('რეზერვირებული')}</span> : <span className="badge badge-warning">{t('მოთხოვნილი')}</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{pr.requested_at ? fmtDate(new Date(pr.requested_at)) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end">
            <button onClick={() => openCreate('tool')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი ხელსაწყო')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('კოდი')}</th>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('კატეგორია')}</th>
                  <th className="px-4 py-3">{t('ხელმისაწვდომი')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(tools || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500">{t('ხელსაწყოები არ არის')}</td></tr>
                ) : (tools || []).map((tl: any) => (
                  <tr key={tl.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{tl.tool_code}</td>
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{tl.name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{tl.category || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{tl.available} / {tl.quantity}</td>
                    <td className="px-4 py-3">{tl.status === 'available' ? <span className="badge badge-success">{t('ხელმისაწვდომი')}</span> : <span className="badge badge-warning">{t('გაცემული')}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end">
            <button onClick={() => openCreate('tool-issue')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ხელსაწყოს გაცემა')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('ხელსაწყო')}</th>
                  <th className="px-4 py-3">{t('ტექნიკოსი')}</th>
                  <th className="px-4 py-3">{t('გაცემულია')}</th>
                  <th className="px-4 py-3">{t('დაბრუნებულია')}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(toolIssues || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500">{t('გაცემები არ არის')}</td></tr>
                ) : (toolIssues || []).map((ti: any) => (
                  <tr key={ti.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{ti.tool_name || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{ti.technician_name || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{ti.issued_at ? fmtDate(new Date(ti.issued_at)) : '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{ti.returned_at ? fmtDate(new Date(ti.returned_at)) : <span className="badge badge-warning">{t('გაცემულია')}</span>}</td>
                    <td className="px-4 py-3 text-right">
                      {!ti.returned_at && (
                        <button onClick={() => returnTool.mutate(ti.id)} className="btn btn-sm btn-outline">{t('დაბრუნება')}</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'safety' && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <button onClick={() => openCreate('safety')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი ინსტრუქცია')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სათაური')}</th>
                  <th className="px-4 py-3">{t('კატეგორია')}</th>
                  <th className="px-4 py-3">{t('სავალდებულო')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(safetyInstructions || []).length === 0 ? (
                  <tr><td colSpan={3} className="p-8 text-center text-gray-500">{t('ინსტრუქციები არ არის')}</td></tr>
                ) : (safetyInstructions || []).map((s: any) => (
                  <tr key={s.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{s.title}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{s.category || '—'}</td>
                    <td className="px-4 py-3">{s.is_mandatory ? <span className="badge badge-danger">{t('სავალდებულო')}</span> : <span className="badge">{t('რეკომენდებული')}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end">
            <button onClick={() => openCreate('permit')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი ნებართვა')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('ნომერი')}</th>
                  <th className="px-4 py-3">{t('სამუშაოს ტიპი')}</th>
                  <th className="px-4 py-3">{t('რისკი')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(workPermits || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500">{t('ნებართვები არ არის')}</td></tr>
                ) : (workPermits || []).map((w: any) => (
                  <tr key={w.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{w.permit_number}</td>
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{w.work_type}</td>
                    <td className="px-4 py-3">
                      {w.risk_level === 'high' || w.risk_level === 'critical' ? <span className="badge badge-danger">{w.risk_level}</span> : w.risk_level === 'medium' ? <span className="badge badge-warning">{w.risk_level}</span> : <span className="badge">{w.risk_level}</span>}
                    </td>
                    <td className="px-4 py-3">
                      {w.status === 'approved' ? <span className="badge badge-success">{t('დამტკიცებული')}</span> : w.status === 'rejected' ? <span className="badge badge-danger">{t('უარყოფილი')}</span> : <span className="badge badge-warning">{t('ნახაზი')}</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {w.status === 'draft' && (
                        <button onClick={() => approveWorkPermit.mutate(w.id)} className="btn btn-sm btn-outline">{t('დამტკიცება')}</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end">
            <button onClick={() => openCreate('checklist')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი ჩეკლისტი')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('კატეგორია')}</th>
                  <th className="px-4 py-3">{t('პუნქტები')}</th>
                  <th className="px-4 py-3">{t('სავალდებულო')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(checklists || []).length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500">{t('ჩეკლისტები არ არის')}</td></tr>
                ) : (checklists || []).map((c: any) => (
                  <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{c.name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{c.category || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{c.item_count}</td>
                    <td className="px-4 py-3">{c.is_mandatory ? <span className="badge badge-danger">{t('სავალდებულო')}</span> : <span className="badge">{t('რეკომენდებული')}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end">
            <button onClick={() => openCreate('incident')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი ინციდენტი')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('ნომერი')}</th>
                  <th className="px-4 py-3">{t('სათაური')}</th>
                  <th className="px-4 py-3">{t('სიმძიმე')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(incidents || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500">{t('ინციდენტები არ არის')}</td></tr>
                ) : (incidents || []).map((i: any) => (
                  <tr key={i.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{i.incident_number}</td>
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{i.title}</td>
                    <td className="px-4 py-3">
                      {i.severity === 'high' || i.severity === 'critical' ? <span className="badge badge-danger">{i.severity}</span> : i.severity === 'medium' ? <span className="badge badge-warning">{i.severity}</span> : <span className="badge">{i.severity}</span>}
                    </td>
                    <td className="px-4 py-3">
                      {i.status === 'resolved' || i.status === 'closed' ? <span className="badge badge-success">{t('მოგვარებული')}</span> : <span className="badge badge-warning">{t('ღია')}</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {i.status === 'open' && (
                        <button onClick={() => resolveIncident.mutate(i.id)} className="btn btn-sm btn-outline">{t('მოგვარება')}</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'costs' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => openCreate('sla')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი SLA')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('პრიორიტეტი')}</th>
                  <th className="px-4 py-3">{t('რეაგირება (სთ)')}</th>
                  <th className="px-4 py-3">{t('მოგვარება (სთ)')}</th>
                  <th className="px-4 py-3">{t('კონტრაქტორი')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(slas || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500">{t('SLA არ არის')}</td></tr>
                ) : (slas || []).map((s: any) => (
                  <tr key={s.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{s.name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{s.priority}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{s.response_hours}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{s.resolution_hours}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{s.contractor_name || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'analytics' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => openCreate('certificate')} className="btn btn-primary flex items-center gap-2"><Plus size={16} /> {t('ახალი სერტიფიკატი')}</button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სერტიფიკატი')}</th>
                  <th className="px-4 py-3">{t('ტექნიკოსი')}</th>
                  <th className="px-4 py-3">{t('ვადის გასვლა')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(certificates || []).length === 0 ? (
                  <tr><td colSpan={3} className="p-8 text-center text-gray-500">{t('სერტიფიკატები არ არის')}</td></tr>
                ) : (certificates || []).map((c: any) => (
                  <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{c.name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{c.technician_name || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{c.expiry_date ? fmtDate(new Date(c.expiry_date)) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {['calendar', 'config'].includes(tab) && (
        <EmptyState text={t('ეს განყოფილება მალე დაემატება — მონაცემები ინახება აქტივებისა და სამუშაო დავალებების მიხედვით.')} />
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი ჩანაწერი')}>
        <div className="space-y-4">
          {renderForm()}
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setOpen(false)}>{t('გაუქმება')}</button>
            <button className="btn btn-primary" onClick={submit}>{t('შექმნა')}</button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
