import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, CheckCircle2, Clock3, Plus, Search, TrendingDown, TrendingUp } from 'lucide-react'
import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import { api } from '../services/api'
import type { DeferredRecognition, DeferredSchedule, GLAccount } from '../types'

const today = new Date().toISOString().slice(0, 10)
const money = (v: number) => new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)
const errorText = (e: any) => e?.response?.data?.detail || 'ოპერაცია ვერ შესრულდა'

export default function DeferredPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [modal, setModal] = useState(false)
  const [error, setError] = useState('')
  const [asOfDate, setAsOfDate] = useState(today)
  const [form, setForm] = useState({ name:'', deferral_type:'expense', total_amount:0, start_date:today, periods:12, source_gl_account_id:'', recognition_gl_account_id:'', notes:'' })

  const schedulesQuery = useQuery({ queryKey:['deferred-schedules'], queryFn:()=>api.get('/deferred/schedules').then(r=>r.data.data) })
  const accountsQuery = useQuery({ queryKey:['gl-accounts-deferred'], queryFn:()=>api.get('/gl/accounts/?page_size=200&is_active=true').then(r=>r.data.data.items) })
  const schedules: DeferredSchedule[] = schedulesQuery.data || []
  const accounts: GLAccount[] = accountsQuery.data || []
  const selected = schedules.find(s=>s.id===selectedId) || null
  const refresh = () => qc.invalidateQueries({ queryKey:['deferred-schedules'] })

  const create = useMutation({ mutationFn:()=>api.post('/deferred/schedules',form), onSuccess:(r)=>{setModal(false);setSelectedId(r.data.data.id);setError('');refresh()}, onError:e=>setError(errorText(e)) })
  const recognize = useMutation({ mutationFn:(id:string)=>api.post(`/deferred/recognitions/${id}/recognize`), onSuccess:refresh, onError:e=>setError(errorText(e)) })
  const recognizeDue = useMutation({ mutationFn:()=>api.post('/deferred/recognize-due',{as_of_date:asOfDate}), onSuccess:()=>{setError('');refresh()}, onError:e=>setError(errorText(e)) })

  const sourceAccounts = useMemo(()=>accounts.filter(a=>a.account_type===(form.deferral_type==='expense'?'asset':'liability')), [accounts,form.deferral_type])
  const targetAccounts = useMemo(()=>accounts.filter(a=>a.account_type===(form.deferral_type==='expense'?'expense':'income')), [accounts,form.deferral_type])
  const accountOptions = (rows:GLAccount[]) => [{value:'',label:'აირჩიეთ ანგარიში'},...rows.map(a=>({value:a.id,label:`${a.code} — ${a.name}`}))]
  const visible = schedules.filter(s=>!search.trim()||s.name.toLowerCase().includes(search.toLowerCase()))
  const total=schedules.reduce((a,s)=>a+s.total_amount,0), recognized=schedules.reduce((a,s)=>a+s.recognized_amount,0)

  const openCreate = () => { setForm({name:'',deferral_type:'expense',total_amount:0,start_date:today,periods:12,source_gl_account_id:'',recognition_gl_account_id:'',notes:''}); setError(''); setModal(true) }
  const changeType = (type:string) => setForm({...form,deferral_type:type,source_gl_account_id:'',recognition_gl_account_id:''})

  return <div className="space-y-6">
    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div><h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100 dark:text-gray-200">გადავადებული ოპერაციები</h1><p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400 dark:text-gray-500">შემოსავლისა და ხარჯის პერიოდული აღიარება</p></div>
      <div className="flex flex-wrap gap-2"><input type="date" className="input w-auto" value={asOfDate} onChange={e=>setAsOfDate(e.target.value)}/><button className="btn-secondary flex items-center gap-2" onClick={()=>recognizeDue.mutate()} disabled={recognizeDue.isPending}><CalendarClock size={17}/>{recognizeDue.isPending?'მუშავდება...':'ვადამოსული პერიოდების აღიარება'}</button><button className="btn-primary flex items-center gap-2" onClick={openCreate}><Plus size={17}/>ახალი გრაფიკი</button></div>
    </div>

    <div className="grid gap-4 md:grid-cols-3">
      <div className="card p-5 dark:bg-dark-200 dark:border-dark-50"><div className="flex items-center gap-3"><CalendarClock className="text-primary-600"/><div><div className="text-sm text-brandgray-500 dark:text-gray-400 dark:text-gray-500">სრული თანხა</div><div className="text-2xl font-semibold">{money(total)}</div></div></div></div>
      <div className="card p-5 dark:bg-dark-200 dark:border-dark-50"><div className="flex items-center gap-3"><CheckCircle2 className="text-green-600"/><div><div className="text-sm text-brandgray-500 dark:text-gray-400 dark:text-gray-500">აღიარებული</div><div className="text-2xl font-semibold">{money(recognized)}</div></div></div></div>
      <div className="card p-5 dark:bg-dark-200 dark:border-dark-50"><div className="flex items-center gap-3"><Clock3 className="text-amber-600"/><div><div className="text-sm text-brandgray-500 dark:text-gray-400 dark:text-gray-500">დარჩენილი</div><div className="text-2xl font-semibold">{money(total-recognized)}</div></div></div></div>
    </div>

    <div className="relative max-w-xs"><Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500"/><input className="input pl-10" value={search} onChange={e=>setSearch(e.target.value)} placeholder="გრაფიკის ძებნა..."/></div>
    <DataTable columns={[
      {key:'name',label:'დასახელება',render:(s:DeferredSchedule)=><button className="font-semibold text-primary-700 dark:text-primary-300" onClick={()=>setSelectedId(s.id)}>{s.name}</button>},
      {key:'deferral_type',label:'ტიპი',render:(s:DeferredSchedule)=><span className={`badge ${s.deferral_type==='revenue'?'badge-green':'badge-blue'}`}>{s.deferral_type==='revenue'?'შემოსავალი':'ხარჯი'}</span>},
      {key:'total_amount',label:'სრული თანხა',render:(s:DeferredSchedule)=>money(s.total_amount)},
      {key:'recognized_amount',label:'აღიარებული',render:(s:DeferredSchedule)=>money(s.recognized_amount)},
      {key:'remaining_amount',label:'დარჩენილი',render:(s:DeferredSchedule)=>money(s.remaining_amount)},
      {key:'status',label:'სტატუსი',render:(s:DeferredSchedule)=><span className={`badge ${s.status==='completed'?'badge-green':'badge-yellow'}`}>{s.status==='completed'?'დასრულებული':'აქტიური'}</span>},
    ]} data={visible} isLoading={schedulesQuery.isLoading} emptyMessage="გადავადებული გრაფიკები არ არის"/>

    {selected&&<section className="card p-0 overflow-hidden dark:bg-dark-200 dark:border-dark-50">
      <div className="flex flex-col gap-2 border-b px-5 py-4 dark:border-dark-50 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="font-semibold">{selected.name} — აღიარების გრაფიკი</h2><p className="text-xs text-brandgray-500 dark:text-gray-400">{selected.source_gl_account_code} {selected.source_gl_account_name} → {selected.recognition_gl_account_code} {selected.recognition_gl_account_name}</p></div><button className="btn-secondary text-sm" onClick={()=>setSelectedId(null)}>დახურვა</button></div>
      <DataTable columns={[
        {key:'period_no',label:'#'}, {key:'recognition_date',label:'აღიარების თარიღი'},
        {key:'amount',label:'თანხა',render:(r:DeferredRecognition)=>money(r.amount)},
        {key:'status',label:'სტატუსი',render:(r:DeferredRecognition)=><span className={`badge ${r.status==='recognized'?'badge-green':'badge-yellow'}`}>{r.status==='recognized'?'აღიარებული':'მოლოდინში'}</span>},
        {key:'action',label:'',render:(r:DeferredRecognition)=>r.status==='pending'?<button className="btn-secondary py-1 text-xs" disabled={recognize.isPending} onClick={()=>recognize.mutate(r.id)}>აღიარება</button>:<span className="text-xs text-brandgray-500 dark:text-gray-400">GL შექმნილია</span>},
      ]} data={selected.recognitions} emptyMessage="პერიოდები არ არის"/>
    </section>}
    {error&&<p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

    <Modal open={modal} onClose={()=>setModal(false)} title="ახალი აღიარების გრაფიკი" size="lg"><div className="space-y-4">
      <FormField label="დასახელება" required><input className="input" value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="წლიური დაზღვევა"/></FormField>
      <div className="grid gap-4 sm:grid-cols-2"><FormField label="ტიპი" required><Select value={form.deferral_type} onChange={e=>changeType(e.target.value)} options={[{value:'expense',label:'გადავადებული ხარჯი'},{value:'revenue',label:'გადავადებული შემოსავალი'}]}/></FormField><FormField label="სრული თანხა" required><input className="input" type="number" min="0.01" step="0.01" value={form.total_amount||''} onChange={e=>setForm({...form,total_amount:Number(e.target.value)})}/></FormField></div>
      <div className="grid gap-4 sm:grid-cols-2"><FormField label="დაწყების თარიღი" required><input className="input" type="date" value={form.start_date} onChange={e=>setForm({...form,start_date:e.target.value})}/></FormField><FormField label="პერიოდების რაოდენობა" required><input className="input" type="number" min="1" max="120" value={form.periods} onChange={e=>setForm({...form,periods:Number(e.target.value)})}/></FormField></div>
      <FormField label={form.deferral_type==='expense'?'წინასწარ გადახდილი ხარჯის ანგარიში (Asset)':'გადავადებული შემოსავლის ანგარიში (Liability)'} required><Select value={form.source_gl_account_id} onChange={e=>setForm({...form,source_gl_account_id:e.target.value})} options={accountOptions(sourceAccounts)}/></FormField>
      <FormField label={form.deferral_type==='expense'?'ხარჯის აღიარების ანგარიში (Expense)':'შემოსავლის აღიარების ანგარიში (Income)'} required><Select value={form.recognition_gl_account_id} onChange={e=>setForm({...form,recognition_gl_account_id:e.target.value})} options={accountOptions(targetAccounts)}/></FormField>
      <FormField label="შენიშვნა"><textarea className="input" rows={2} value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></FormField>
      {error&&<p className="text-sm text-red-600">{error}</p>}
      <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={()=>setModal(false)}>გაუქმება</button><button className="btn-primary" disabled={!form.name||form.total_amount<=0||form.periods<1||!form.source_gl_account_id||!form.recognition_gl_account_id||create.isPending} onClick={()=>create.mutate()}>{create.isPending?'იქმნება...':'გრაფიკის შექმნა'}</button></div>
    </div></Modal>
  </div>
}
