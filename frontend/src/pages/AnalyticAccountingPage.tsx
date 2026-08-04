import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BarChart3, Plus, Search, Trash2, TrendingDown, TrendingUp } from 'lucide-react'
import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import { api } from '../services/api'
import type { AnalyticAccount, AnalyticEntry } from '../types'

const today = new Date().toISOString().slice(0, 10)
const money = (v: number) => new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)
const errText = (e: any) => e?.response?.data?.detail || 'ოპერაცია ვერ შესრულდა'

export default function AnalyticAccountingPage() {
  const qc = useQueryClient()
  const [accountModal, setAccountModal] = useState(false)
  const [entryModal, setEntryModal] = useState(false)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [accountForm, setAccountForm] = useState({ code: '', name: '', account_type: 'cost_center', notes: '' })
  const [entryForm, setEntryForm] = useState({ analytic_account_id: '', entry_date: today, description: '', amount: 0, direction: 'expense', reference: '' })

  const accountsQuery = useQuery({ queryKey: ['analytic-accounts'], queryFn: () => api.get('/analytic/accounts').then(r => r.data.data) })
  const entriesQuery = useQuery({ queryKey: ['analytic-entries'], queryFn: () => api.get('/analytic/entries').then(r => r.data.data) })
  const accounts: AnalyticAccount[] = accountsQuery.data || []
  const entries: AnalyticEntry[] = entriesQuery.data || []
  const refresh = () => { qc.invalidateQueries({ queryKey: ['analytic-accounts'] }); qc.invalidateQueries({ queryKey: ['analytic-entries'] }) }

  const createAccount = useMutation({ mutationFn: () => api.post('/analytic/accounts', accountForm), onSuccess: () => { setAccountModal(false); setAccountForm({ code:'',name:'',account_type:'cost_center',notes:'' }); refresh() }, onError: e => setError(errText(e)) })
  const createEntry = useMutation({ mutationFn: () => api.post('/analytic/entries', { ...entryForm, notes: undefined }), onSuccess: () => { setEntryModal(false); setEntryForm({ analytic_account_id:'',entry_date:today,description:'',amount:0,direction:'expense',reference:'' }); refresh() }, onError: e => setError(errText(e)) })
  const deleteEntry = useMutation({ mutationFn: (id:string) => api.delete(`/analytic/entries/${id}`), onSuccess: refresh, onError: e => setError(errText(e)) })

  const visible = accounts.filter(a => !search.trim() || `${a.code} ${a.name}`.toLowerCase().includes(search.toLowerCase()))
  const income = accounts.reduce((s,a)=>s+a.income_total,0), expense = accounts.reduce((s,a)=>s+a.expense_total,0)

  return <div className="space-y-6">
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div><h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">ანალიტიკური აღრიცხვა</h1><p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">ხარჯთაღრიცხვის ცენტრები და მიმართულებების შედეგები</p></div>
      <div className="flex gap-2"><button className="btn-secondary flex items-center gap-2" onClick={()=>{setError('');setAccountModal(true)}}><Plus size={17}/> ცენტრი</button><button className="btn-primary flex items-center gap-2" onClick={()=>{setError('');setEntryModal(true)}} disabled={!accounts.length}><Plus size={17}/> ჩანაწერი</button></div>
    </div>
    <div className="grid gap-4 md:grid-cols-3">
      {[['შემოსავალი',income,TrendingUp,'text-green-600'],['ხარჯი',expense,TrendingDown,'text-red-600'],['შედეგი',income-expense,BarChart3,'text-primary-600']].map(([label,value,Icon,cls]:any)=><div key={label} className="card p-5 dark:bg-dark-200 dark:border-dark-50"><div className="flex items-center gap-3"><Icon className={cls}/><div><div className="text-sm text-brandgray-500 dark:text-gray-400">{label}</div><div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{money(value)}</div></div></div></div>)}
    </div>
    <div className="relative max-w-xs"><Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500"/><input className="input pl-10" placeholder="ცენტრის ძებნა..." value={search} onChange={e=>setSearch(e.target.value)}/></div>
    <DataTable columns={[
      {key:'code',label:'კოდი'},{key:'name',label:'დასახელება'},
      {key:'income_total',label:'შემოსავალი',render:(a:AnalyticAccount)=>money(a.income_total)},
      {key:'expense_total',label:'ხარჯი',render:(a:AnalyticAccount)=>money(a.expense_total)},
      {key:'balance',label:'შედეგი',render:(a:AnalyticAccount)=><span className={a.balance>=0?'text-green-600':'text-red-600'}>{money(a.balance)}</span>},
    ]} data={visible} clientPageSize={20} isLoading={accountsQuery.isLoading} emptyMessage="ანალიტიკური ცენტრები არ არის"/>
    <section className="card p-0 overflow-hidden dark:bg-dark-200 dark:border-dark-50"><div className="px-5 py-4 border-b dark:border-dark-50"><h2 className="font-semibold">ბოლო ჩანაწერები</h2></div><DataTable columns={[
      {key:'entry_date',label:'თარიღი'},{key:'analytic_account_name',label:'ცენტრი'},{key:'description',label:'აღწერა'},
      {key:'direction',label:'ტიპი',render:(e:AnalyticEntry)=><span className={`badge ${e.direction==='income'?'badge-green':'badge-red'}`}>{e.direction==='income'?'შემოსავალი':'ხარჯი'}</span>},
      {key:'amount',label:'თანხა',render:(e:AnalyticEntry)=>money(e.amount)},
      {key:'actions',label:'',render:(e:AnalyticEntry)=><button onClick={()=>confirm('წავშალოთ ჩანაწერი?')&&deleteEntry.mutate(e.id)}><Trash2 size={16} className="text-red-500"/></button>},
    ]} data={entries} clientPageSize={20} isLoading={entriesQuery.isLoading} emptyMessage="ჩანაწერები არ არის"/></section>
    {error&&<p className="text-sm text-red-600">{error}</p>}
    <Modal open={accountModal} onClose={()=>setAccountModal(false)} title="ახალი ანალიტიკური ცენტრი" size="md"><div className="space-y-4"><FormField label="კოდი" required><input className="input" value={accountForm.code} onChange={e=>setAccountForm({...accountForm,code:e.target.value})}/></FormField><FormField label="დასახელება" required><input className="input" value={accountForm.name} onChange={e=>setAccountForm({...accountForm,name:e.target.value})}/></FormField><FormField label="ტიპი"><Select value={accountForm.account_type} onChange={e=>setAccountForm({...accountForm,account_type:e.target.value})} options={[{value:'cost_center',label:'ხარჯთაღრიცხვის ცენტრი'},{value:'project',label:'პროექტი'},{value:'department',label:'დეპარტამენტი'}]}/></FormField><div className="flex justify-end gap-2"><button className="btn-secondary" onClick={()=>setAccountModal(false)}>გაუქმება</button><button className="btn-primary" disabled={!accountForm.code||!accountForm.name||createAccount.isPending} onClick={()=>createAccount.mutate()}>შენახვა</button></div></div></Modal>
    <Modal open={entryModal} onClose={()=>setEntryModal(false)} title="ახალი ანალიტიკური ჩანაწერი" size="md"><div className="space-y-4"><FormField label="ცენტრი" required><Select value={entryForm.analytic_account_id} onChange={e=>setEntryForm({...entryForm,analytic_account_id:e.target.value})} options={[{value:'',label:'აირჩიეთ'},...accounts.filter(a=>a.is_active).map(a=>({value:a.id,label:`${a.code} — ${a.name}`}))]}/></FormField><div className="grid grid-cols-2 gap-4"><FormField label="თარიღი"><input type="date" className="input" value={entryForm.entry_date} onChange={e=>setEntryForm({...entryForm,entry_date:e.target.value})}/></FormField><FormField label="ტიპი"><Select value={entryForm.direction} onChange={e=>setEntryForm({...entryForm,direction:e.target.value})} options={[{value:'expense',label:'ხარჯი'},{value:'income',label:'შემოსავალი'}]}/></FormField></div><FormField label="აღწერა" required><input className="input" value={entryForm.description} onChange={e=>setEntryForm({...entryForm,description:e.target.value})}/></FormField><FormField label="თანხა" required><input type="number" min="0.01" step="0.01" className="input" value={entryForm.amount||''} onChange={e=>setEntryForm({...entryForm,amount:Number(e.target.value)})}/></FormField><div className="flex justify-end gap-2"><button className="btn-secondary" onClick={()=>setEntryModal(false)}>გაუქმება</button><button className="btn-primary" disabled={!entryForm.analytic_account_id||!entryForm.description||entryForm.amount<=0||createEntry.isPending} onClick={()=>createEntry.mutate()}>შენახვა</button></div></div></Modal>
  </div>
}
