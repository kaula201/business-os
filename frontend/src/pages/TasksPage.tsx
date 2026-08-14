import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tasksApi, usersApi, clientsApi } from '../services/api'
import {Plus, CheckSquare, Clock, Calendar, User as UserIcon, Search, Play, CheckCircle2, RotateCcw, Eye, X} from 'lucide-react'
import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import { StatusBadge, priorityMap, taskStatusMap } from '../components/ui/Badges'
import type { Task, TaskCreate, TaskComment, TaskStatus } from '../types'

const statusColumns: { status: TaskStatus; label: string }[] = [
  { status: 'todo', label: i18n.t('საჭიროებს') },
  { status: 'in_progress', label: i18n.t('პროცესში') },
  { status: 'done', label: i18n.t('დასრულებული') },
  { status: 'cancelled', label: i18n.t('გაუქმებული') },
]

export default function TasksPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [view, setView] = useState<'list' | 'kanban' | 'calendar' | 'gantt'>('list')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editTask, setEditTask] = useState<Task | null>(null)
  const [viewTask, setViewTask] = useState<Task | null>(null)
  const [comment, setComment] = useState('')
  const [depTaskId, setDepTaskId] = useState('')
  const [deps, setDeps] = useState<any[]>([])

  // Debounce: search იგზავნება server-ზე მხოლოდ აკრეფის შეწყვეტის შემდეგ
  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput); setPage(1) }, 400)
    return () => clearTimeout(t)
  }, [searchInput])

  const { data, isLoading } = useQuery({
    queryKey: ['tasks', search, statusFilter, priorityFilter, page],
    queryFn: () => tasksApi.list({
      search: search || undefined,
      status: statusFilter || undefined,
      priority: priorityFilter || undefined,
      page,
      page_size: 20
    }).then(r => r.data.data),
  })
  const { data: usersData } = useQuery({ queryKey: ['users-list'], queryFn: () => usersApi.list({ page_size: 100 }).then(r => r.data.data) })
  const { data: clientsData } = useQuery({ queryKey: ['clients-ref'], queryFn: () => clientsApi.list({ page_size: 100 }).then(r => r.data.data) })
  const { data: calendarData } = useQuery({
    queryKey: ['tasks-calendar'],
    queryFn: () => tasksApi.calendar().then(r => r.data.data),
    enabled: view === 'calendar' || view === 'gantt',
  })

  const tasks: Task[] = data?.items || []
  const tasksTotal = data?.total || 0
  const tasksTotalPages = Math.max(1, Math.ceil(tasksTotal / 20))
  const users = usersData?.items || []
  const clients = clientsData?.items || []

  const [form, setForm] = useState<TaskCreate>({
    title: '', description: '', assigned_to: '', due_date: '', priority: 'medium',
  })

  const createMutation = useMutation({
    mutationFn: (data: TaskCreate) => tasksApi.create(data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['tasks'] }); closeModal() },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => tasksApi.update(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const commentMutation = useMutation({
    mutationFn: ({ taskId, content }: { taskId: string; content: string }) => tasksApi.addComment(taskId, { content }),
    onSuccess: () => { setComment(''); queryClient.invalidateQueries({ queryKey: ['tasks'] }) },
  })

  const depMutation = useMutation({
    mutationFn: ({ taskId, depId }: { taskId: string; depId: string }) => tasksApi.addDependency(taskId, { depends_on_task_id: depId }),
    onSuccess: () => { setDepTaskId(''); loadDeps() },
  })

  const removeDepMutation = useMutation({
    mutationFn: ({ taskId, depId }: { taskId: string; depId: string }) => tasksApi.removeDependency(taskId, depId),
    onSuccess: () => loadDeps(),
  })

  async function loadDeps() {
    if (!viewTask) return
    try {
      const res = await tasksApi.dependencies(viewTask.id)
      setDeps(res.data.data || [])
    } catch { setDeps([]) }
  }

  useEffect(() => { if (viewTask) loadDeps() }, [viewTask?.id])

  function openCreate() {
    setEditTask(null)
    setForm({ title: '', description: '', assigned_to: '', due_date: '', priority: 'medium' })
    setModalOpen(true)
  }

  function openEdit(task: Task) {
    setEditTask(task)
    setForm({ title: task.title, description: task.description || '', assigned_to: task.assigned_to || '', due_date: task.due_date?.split('T')[0] || '', priority: task.priority })
    setModalOpen(true)
  }

  function closeModal() {
    setModalOpen(false)
    setEditTask(null)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (editTask) {
      updateMutation.mutate({ id: editTask.id, data: form })
      closeModal()
    } else {
      createMutation.mutate(form)
    }
  }

  function handleStatusChange(task: Task, newStatus: TaskStatus) {
    updateMutation.mutate({ id: task.id, data: { status: newStatus } })
  }

  function handleAddComment() {
    if (!viewTask || !comment.trim()) return
    commentMutation.mutate({ taskId: viewTask.id, content: comment })
  }

  const listColumns = [
    { key: 'title', label: i18n.t('დავალება'), render: (t: Task) => <span className="font-medium text-gray-900 dark:text-gray-100">{t.title}</span> },
    { key: 'priority', label: i18n.t('პრიორიტეტი'), render: (t: Task) => <StatusBadge status={t.priority} map={priorityMap} /> },
    { key: 'status', label: i18n.t('სტატუსი'), render: (t: Task) => <StatusBadge status={t.status} map={taskStatusMap} /> },
    {
      key: 'due_date', label: i18n.t('ვადა'), hideOnMobile: true,
      render: (t: Task) => {
        if (!t.due_date) return <span className="text-gray-400 dark:text-gray-500">—</span>
        const d = new Date(t.due_date)
        const isOverdue = d < new Date() && t.status !== 'done' && t.status !== 'cancelled'
        return <span className={isOverdue ? 'text-red-600 font-medium' : ''}>{d.toLocaleDateString('ka-GE')}</span>
      },
    },
    {
      key: 'assigned_to_name', label: i18n.t('პასუხისმგებელი'), hideOnMobile: true,
      render: (t: Task) => t.assigned_to_name || '—',
    },
    {
      key: 'actions', label: '',
      render: (t: Task) => (
        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => handleStatusChange(t, t.status === 'todo' ? 'in_progress' : t.status === 'in_progress' ? 'done' : 'todo')}
            title={t.status === 'todo' ? i18n.t('სტატუსის შეცვლა: პროცესში') : t.status === 'in_progress' ? i18n.t('სტატუსის შეცვლა: დასრულებული') : i18n.t('სტატუსის შეცვლა: საჭიროებს')}
            aria-label={t.status === 'todo' ? i18n.t('სტატუსის შეცვლა: პროცესში') : t.status === 'in_progress' ? i18n.t('სტატუსის შეცვლა: დასრულებული') : i18n.t('სტატუსის შეცვლა: საჭიროებს')}
            className="p-1.5 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 rounded text-gray-500 dark:text-gray-400 hover:text-green-600"
          >
            {t.status === 'todo' ? <Play size={16} /> : t.status === 'in_progress' ? <CheckCircle2 size={16} /> : <RotateCcw size={16} />}
          </button>
          <button onClick={() => setViewTask(t)} title={i18n.t('ნახვა')} aria-label={i18n.t('ნახვა')} className="p-1.5 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 rounded text-gray-500 dark:text-gray-400"><Eye size={16} /></button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('დავალებები')}</h1>
        <div className="flex items-center gap-3">
          <div className="flex gap-2">
            <button onClick={() => setView('list')} className={`btn-secondary text-sm ${view === 'list' ? 'ring-2 ring-primary-500' : ''}`}>{t('სია')}</button>
            <button onClick={() => setView('kanban')} className={`btn-secondary text-sm ${view === 'kanban' ? 'ring-2 ring-primary-500' : ''}`}>{t('დოსკა')}</button>
            <button onClick={() => setView('calendar')} className={`btn-secondary text-sm ${view === 'calendar' ? 'ring-2 ring-primary-500' : ''}`}>{t('კალენდარი')}</button>
            <button onClick={() => setView('gantt')} className={`btn-secondary text-sm ${view === 'gantt' ? 'ring-2 ring-primary-500' : ''}`}>{t('Gantt')}</button>
          </div>
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('ახალი დავალება')}
          </button>
        </div>
      </div>

      <div className="card flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" size={18} />
          <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder={t('ძებნა სათაურით...')} className="input pl-10" />
        </div>
        <div className="flex gap-1 flex-wrap">
          <button onClick={() => setStatusFilter('')} className={`btn-secondary text-sm ${!statusFilter ? 'ring-2 ring-primary-500' : ''}`}>{t('ყველა')}</button>
          {Object.entries(taskStatusMap).map(([key, { label }]) => (
            <button key={key} onClick={() => setStatusFilter(key)} className={`btn-secondary text-sm ${statusFilter === key ? 'ring-2 ring-primary-500' : ''}`}>{t(label)}</button>
          ))}
        </div>
        <div className="flex gap-1 flex-wrap">
          <button onClick={() => setPriorityFilter('')} className={`btn-secondary text-sm ${!priorityFilter ? 'ring-2 ring-primary-500' : ''}`}>{t('პრიორიტეტი')}</button>
          {Object.entries(priorityMap).map(([key, { label }]) => (
            <button key={key} onClick={() => setPriorityFilter(key)} className={`btn-secondary text-sm ${priorityFilter === key ? 'ring-2 ring-primary-500' : ''}`}>{t(label)}</button>
          ))}
        </div>
      </div>

      {view === 'list' ? (
        <DataTable columns={listColumns} data={tasks} isLoading={isLoading} emptyMessage={t('დავალებები არ მოიძებნა')} onRowClick={(t) => setViewTask(t)} page={page} totalPages={tasksTotalPages} total={tasksTotal} onPageChange={setPage} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {statusColumns.map(({ status, label }) => {
            const columnTasks = tasks.filter(t => t.status === status)
            return (
              <div key={status} className="bg-gray-50 dark:bg-dark-100 rounded-xl p-3 min-h-[300px]">
                <h3 className="font-semibold text-gray-700 dark:text-gray-300 mb-3 px-2 flex items-center justify-between">
                  {label}
                  <span className="text-xs text-gray-400 bg-white dark:bg-dark-200 px-2 py-0.5 rounded-full dark:text-gray-500">{columnTasks.length}</span>
                </h3>
                <div className="space-y-2">
                  {columnTasks.map(task => (
                    <div
                      key={task.id}
                      draggable
                      onDragEnd={() => handleStatusChange(task, status)}
                      className="bg-white dark:bg-dark-200 rounded-lg p-3 shadow-sm border border-gray-200 dark:border-dark-50 cursor-pointer hover:shadow-md transition-shadow"
                      onClick={() => setViewTask(task)}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <span className="font-medium text-sm text-gray-900 dark:text-gray-100 line-clamp-2">{task.title}</span>
                        <StatusBadge status={task.priority} map={priorityMap} />
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500">
                        {task.due_date && (
                          <span className="flex items-center gap-1">
                            <Clock size={12} />
                            {new Date(task.due_date).toLocaleDateString('ka-GE')}
                          </span>
                        )}
                        {task.assigned_to_name && (
                          <span className="flex items-center gap-1 ml-auto">
                            <UserIcon size={12} /> {task.assigned_to_name}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                  {columnTasks.length === 0 && (
                    <div className="text-center text-gray-400 text-xs py-8 dark:text-gray-500">{t('ცარიელია')}</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {view === 'calendar' && (
        <div className="rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('თარიღი')}</th>
                  <th className="px-4 py-3">{t('დავალება')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3">{t('პრიორიტეტი')}</th>
                  <th className="px-4 py-3">{t('პასუხისმგებელი')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {!calendarData || calendarData.length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('კალენდარში დავალებები არ არის')}</td></tr>
                ) : calendarData.map((ev: any) => (
                  <tr key={ev.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono text-gray-600 dark:text-gray-400">{ev.start ? new Date(ev.start).toLocaleDateString('ka-GE') : '—'}</td>
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{ev.title}</td>
                    <td className="px-4 py-3"><StatusBadge status={ev.status} map={taskStatusMap} /></td>
                    <td className="px-4 py-3"><StatusBadge status={ev.priority} map={priorityMap} /></td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{ev.assigned_to_name || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {view === 'gantt' && (
        <div className="rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200 overflow-hidden">
          <div className="overflow-x-auto p-4">
            {!calendarData || calendarData.length === 0 ? (
              <p className="text-center text-sm text-gray-500 dark:text-gray-400 py-8">{t('Gantt-ისთვის დავალებები არ არის')}</p>
            ) : (
              <div className="space-y-2 min-w-[600px]">
                {calendarData.map((ev: any) => {
                  const start = ev.start ? new Date(ev.start) : null
                  const end = ev.end ? new Date(ev.end) : start
                  const today = new Date()
                  const min = start ? Math.min(start.getTime(), today.getTime()) : today.getTime()
                  const max = end ? Math.max(end.getTime(), today.getTime()) : today.getTime()
                  const span = Math.max(1, (max - min) / (1000 * 60 * 60 * 24))
                  const left = start ? ((start.getTime() - min) / (1000 * 60 * 60 * 24)) / span * 100 : 0
                  const width = start && end ? Math.max(4, ((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) / span * 100) : 4
                  return (
                    <div key={ev.id} className="flex items-center gap-3">
                      <div className="w-48 truncate text-sm text-gray-700 dark:text-gray-300">{ev.title}</div>
                      <div className="relative flex-1 h-6 rounded bg-gray-100 dark:bg-dark-100">
                        <div className="absolute top-1 bottom-1 rounded bg-primary-500/80" style={{ left: `${left}%`, width: `${width}%` }} title={ev.title} />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Task Create/Edit Modal */}
      <Modal open={modalOpen} onClose={closeModal} title={editTask ? t('დავალების რედაქტირება') : t('ახალი დავალება')} size="lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <FormField label={t('სათაური')} required>
            <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" required />
          </FormField>
          <FormField label={t('აღწერა')}>
            <textarea value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={3} />
          </FormField>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <FormField label={t('პრიორიტეტი')}>
              <Select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as any })} options={[{ value: 'low', label: i18n.t('დაბალი') }, { value: 'medium', label: i18n.t('საშუალო') }, { value: 'high', label: i18n.t('მაღალი') }]} />
            </FormField>
            <FormField label={t('ვადა')}>
              <input type="date" value={form.due_date || ''} onChange={(e) => setForm({ ...form, due_date: e.target.value })} className="input" />
            </FormField>
            <FormField label={t('პასუხისმგებელი')}>
              <Select value={form.assigned_to || ''} onChange={(e) => setForm({ ...form, assigned_to: e.target.value })} placeholder={t('აირჩიეთ')} options={users.map((u: any) => ({ value: u.id, label: u.full_name }))} />
            </FormField>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FormField label={t('კლიენტი')}>
              <Select value={form.client_id || ''} onChange={(e) => setForm({ ...form, client_id: e.target.value })} placeholder={t('აირჩიეთ')} options={clients.map((c: any) => ({ value: c.id, label: c.name }))} />
            </FormField>
            <FormField label={t('შეკვეთა')}>
              <input type="text" value={form.order_id || ''} onChange={(e) => setForm({ ...form, order_id: e.target.value })} className="input" placeholder={t('შეკვეთის ID')} />
            </FormField>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FormField label={t('გამეორება')}>
              <Select value={form.recurrence || ''} onChange={(e) => setForm({ ...form, recurrence: e.target.value })} placeholder={t('არა')} options={[{ value: 'daily', label: t('ყოველდღიური') }, { value: 'weekly', label: t('ყოველკვირეული') }, { value: 'monthly', label: t('ყოველთვიური') }]} />
            </FormField>
            <FormField label={t('გამეორების ბოლო თარიღი')}>
              <input type="date" value={form.recurrence_end || ''} onChange={(e) => setForm({ ...form, recurrence_end: e.target.value })} className="input" />
            </FormField>
          </div>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-dark-50">
            <button type="button" onClick={closeModal} className="btn-secondary">{t('გაუქმება')}</button>
            <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'შენახვა...' : editTask ? t('განახლება') : t('დამატება')}
            </button>
          </div>
        </form>
      </Modal>

      {/* View Task Modal */}
      <Modal open={!!viewTask} onClose={() => setViewTask(null)} title={t('დავალების დეტალები')} size="lg">
        {viewTask && (
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">{viewTask.title}</h3>
                <div className="flex gap-2 mt-2">
                  <StatusBadge status={viewTask.status} map={taskStatusMap} />
                  <StatusBadge status={viewTask.priority} map={priorityMap} />
                </div>
              </div>
              <Select
                value={viewTask.status}
                onChange={(e) => { handleStatusChange(viewTask, e.target.value as TaskStatus); setViewTask({ ...viewTask, status: e.target.value as TaskStatus }) }}
                options={[
                  { value: 'todo', label: i18n.t('საჭიროებს') },
                  { value: 'in_progress', label: i18n.t('პროცესში') },
                  { value: 'done', label: i18n.t('დასრულებული') },
                  { value: 'cancelled', label: i18n.t('გაუქმებული') },
                ]}
                className="w-40"
              />
            </div>

            {viewTask.description && (
              <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg text-sm whitespace-pre-wrap">{viewTask.description}</div>
            )}

            <div className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
              {viewTask.assigned_to_name && <div className="flex items-center gap-2"><UserIcon size={14} /> {viewTask.assigned_to_name}</div>}
              {viewTask.due_date && <div className="flex items-center gap-2"><Calendar size={14} /> ვადა: {new Date(viewTask.due_date).toLocaleDateString('ka-GE')}</div>}
              {viewTask.client_name && <div>კლიენტი: {viewTask.client_name}</div>}
              {viewTask.order_number && <div>შეკვეთა: {viewTask.order_number}</div>}
              {viewTask.project_name && <div>პროექტი: {viewTask.project_name}</div>}
              {viewTask.recurrence && <div className="flex items-center gap-2"><RotateCcw size={14} /> {t('გამეორება')}: {viewTask.recurrence}{viewTask.recurrence_end ? ` → ${new Date(viewTask.recurrence_end).toLocaleDateString('ka-GE')}` : ''}</div>}
            </div>

            {/* Dependencies */}
            <div className="pt-4 border-t border-gray-200 dark:border-dark-50">
              <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-2">{t('დამოკიდებულებები')}</h4>
              <div className="space-y-2 mb-3">
                {deps.length === 0 ? (
                  <p className="text-sm text-gray-400 dark:text-gray-500">{t('დამოკიდებულებები არ არის')}</p>
                ) : deps.map((d: any) => (
                  <div key={d.id} className="flex items-center justify-between rounded-lg border border-gray-200 dark:border-dark-50 px-3 py-2 text-sm">
                    <span className="text-gray-700 dark:text-gray-300">{d.depends_on_task?.title || d.depends_on_task_id}</span>
                    <button onClick={() => removeDepMutation.mutate({ taskId: viewTask.id, depId: d.id })} className="text-red-500 hover:text-red-700" title={t('წაშლა')}>
                      <X size={15} />
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <select value={depTaskId} onChange={(e) => setDepTaskId(e.target.value)} className="input flex-1">
                  <option value="">{t('აირჩიეთ დავალება')}</option>
                  {tasks.filter((x: Task) => x.id !== viewTask.id).map((x: Task) => <option key={x.id} value={x.id}>{x.title}</option>)}
                </select>
                <button onClick={() => depTaskId && depMutation.mutate({ taskId: viewTask.id, depId: depTaskId })} className="btn-primary" disabled={!depTaskId}>
                  <Plus size={15} />
                </button>
              </div>
            </div>

            <div className="pt-4 border-t border-gray-200 dark:border-dark-50">
              <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-2">{t('კომენტარები')}</h4>
              <div className="space-y-2 mb-3">
                {/* Inline comment display — will work when comments are fetched */}
              </div>
              <div className="flex gap-2">
                <input type="text" value={comment} onChange={(e) => setComment(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleAddComment()} placeholder={t('დაწერეთ კომენტარი...')} className="input flex-1" />
                <button onClick={handleAddComment} className="btn-primary" disabled={!comment.trim()}>{t('გაგზავნა')}</button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}