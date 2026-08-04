import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tasksApi, usersApi, clientsApi } from '../services/api'
import { Plus, CheckSquare, Clock, Calendar, User as UserIcon, Search } from 'lucide-react'
import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import { StatusBadge, priorityMap, taskStatusMap } from '../components/ui/Badges'
import type { Task, TaskCreate, TaskComment, TaskStatus } from '../types'

const statusColumns: { status: TaskStatus; label: string }[] = [
  { status: 'todo', label: 'საჭიროებს' },
  { status: 'in_progress', label: 'პროცესში' },
  { status: 'done', label: 'დასრულებული' },
  { status: 'cancelled', label: 'გაუქმებული' },
]

export default function TasksPage() {
  const queryClient = useQueryClient()
  const [view, setView] = useState<'list' | 'kanban'>('list')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editTask, setEditTask] = useState<Task | null>(null)
  const [viewTask, setViewTask] = useState<Task | null>(null)
  const [comment, setComment] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['tasks', search, statusFilter, priorityFilter],
    queryFn: () => tasksApi.list({
      search: search || undefined,
      status: statusFilter || undefined,
      priority: priorityFilter || undefined,
      page_size: 50
    }).then(r => r.data.data),
  })
  const { data: usersData } = useQuery({ queryKey: ['users-list'], queryFn: () => usersApi.list({ page_size: 100 }).then(r => r.data.data) })
  const { data: clientsData } = useQuery({ queryKey: ['clients-ref'], queryFn: () => clientsApi.list({ page_size: 100 }).then(r => r.data.data) })

  const tasks: Task[] = data?.items || []
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
    { key: 'title', label: 'დავალება', render: (t: Task) => <span className="font-medium text-gray-900 dark:text-gray-100">{t.title}</span> },
    { key: 'priority', label: 'პრიორიტეტი', render: (t: Task) => <StatusBadge status={t.priority} map={priorityMap} /> },
    { key: 'status', label: 'სტატუსი', render: (t: Task) => <StatusBadge status={t.status} map={taskStatusMap} /> },
    {
      key: 'due_date', label: 'ვადა', hideOnMobile: true,
      render: (t: Task) => {
        if (!t.due_date) return <span className="text-gray-400">—</span>
        const d = new Date(t.due_date)
        const isOverdue = d < new Date() && t.status !== 'done' && t.status !== 'cancelled'
        return <span className={isOverdue ? 'text-red-600 font-medium' : ''}>{d.toLocaleDateString('ka-GE')}</span>
      },
    },
    {
      key: 'assigned_to_name', label: 'პასუხისმგებელი', hideOnMobile: true,
      render: (t: Task) => t.assigned_to_name || '—',
    },
    {
      key: 'actions', label: '',
      render: (t: Task) => (
        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
          <button onClick={() => handleStatusChange(t, t.status === 'todo' ? 'in_progress' : t.status === 'in_progress' ? 'done' : 'todo')} className="p-1.5 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 rounded text-gray-500 dark:text-gray-400 hover:text-green-600">
            {t.status === 'todo' ? '▶️' : t.status === 'in_progress' ? '✅' : '↩️'}
          </button>
          <button onClick={() => setViewTask(t)} className="p-1.5 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 rounded text-gray-500 dark:text-gray-400">👁️</button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">დავალებები</h1>
        <div className="flex items-center gap-3">
          <div className="flex gap-2">
            <button onClick={() => setView('list')} className={`btn-secondary text-sm ${view === 'list' ? 'ring-2 ring-primary-500' : ''}`}>სია</button>
            <button onClick={() => setView('kanban')} className={`btn-secondary text-sm ${view === 'kanban' ? 'ring-2 ring-primary-500' : ''}`}>დოსკა</button>
          </div>
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus size={18} /> ახალი დავალება
          </button>
        </div>
      </div>

      <div className="card flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="ძებნა სათაურით..." className="input pl-10" />
        </div>
        <div className="flex gap-1 flex-wrap">
          <button onClick={() => setStatusFilter('')} className={`btn-secondary text-sm ${!statusFilter ? 'ring-2 ring-primary-500' : ''}`}>ყველა</button>
          {Object.entries(taskStatusMap).map(([key, { label }]) => (
            <button key={key} onClick={() => setStatusFilter(key)} className={`btn-secondary text-sm ${statusFilter === key ? 'ring-2 ring-primary-500' : ''}`}>{label}</button>
          ))}
        </div>
        <div className="flex gap-1 flex-wrap">
          <button onClick={() => setPriorityFilter('')} className={`btn-secondary text-sm ${!priorityFilter ? 'ring-2 ring-primary-500' : ''}`}>პრიორიტეტი</button>
          {Object.entries(priorityMap).map(([key, { label }]) => (
            <button key={key} onClick={() => setPriorityFilter(key)} className={`btn-secondary text-sm ${priorityFilter === key ? 'ring-2 ring-primary-500' : ''}`}>{label}</button>
          ))}
        </div>
      </div>

      {view === 'list' ? (
        <DataTable columns={listColumns} data={tasks} isLoading={isLoading} emptyMessage="დავალებები არ მოიძებნა" onRowClick={(t) => setViewTask(t)} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {statusColumns.map(({ status, label }) => {
            const columnTasks = tasks.filter(t => t.status === status)
            return (
              <div key={status} className="bg-gray-50 dark:bg-dark-100 rounded-xl p-3 min-h-[300px]">
                <h3 className="font-semibold text-gray-700 dark:text-gray-300 mb-3 px-2 flex items-center justify-between">
                  {label}
                  <span className="text-xs text-gray-400 bg-white dark:bg-dark-200 px-2 py-0.5 rounded-full">{columnTasks.length}</span>
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
                      <div className="flex items-center gap-2 text-xs text-gray-400">
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
                    <div className="text-center text-gray-400 text-xs py-8">ცარიელია</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Task Create/Edit Modal */}
      <Modal open={modalOpen} onClose={closeModal} title={editTask ? 'დავალების რედაქტირება' : 'ახალი დავალება'} size="lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <FormField label="სათაური" required>
            <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" required />
          </FormField>
          <FormField label="აღწერა">
            <textarea value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={3} />
          </FormField>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <FormField label="პრიორიტეტი">
              <Select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as any })} options={[{ value: 'low', label: 'დაბალი' }, { value: 'medium', label: 'საშუალო' }, { value: 'high', label: 'მაღალი' }]} />
            </FormField>
            <FormField label="ვადა">
              <input type="date" value={form.due_date || ''} onChange={(e) => setForm({ ...form, due_date: e.target.value })} className="input" />
            </FormField>
            <FormField label="პასუხისმგებელი">
              <Select value={form.assigned_to || ''} onChange={(e) => setForm({ ...form, assigned_to: e.target.value })} placeholder="აირჩიეთ" options={users.map((u: any) => ({ value: u.id, label: u.full_name }))} />
            </FormField>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FormField label="კლიენტი">
              <Select value={form.client_id || ''} onChange={(e) => setForm({ ...form, client_id: e.target.value })} placeholder="აირჩიეთ" options={clients.map((c: any) => ({ value: c.id, label: c.name }))} />
            </FormField>
            <FormField label="შეკვეთა">
              <input type="text" value={form.order_id || ''} onChange={(e) => setForm({ ...form, order_id: e.target.value })} className="input" placeholder="შეკვეთის ID" />
            </FormField>
          </div>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-dark-50">
            <button type="button" onClick={closeModal} className="btn-secondary">გაუქმება</button>
            <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'შენახვა...' : editTask ? 'განახლება' : 'დამატება'}
            </button>
          </div>
        </form>
      </Modal>

      {/* View Task Modal */}
      <Modal open={!!viewTask} onClose={() => setViewTask(null)} title="დავალების დეტალები" size="lg">
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
                  { value: 'todo', label: 'საჭიროებს' },
                  { value: 'in_progress', label: 'პროცესში' },
                  { value: 'done', label: 'დასრულებული' },
                  { value: 'cancelled', label: 'გაუქმებული' },
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
            </div>

            <div className="pt-4 border-t border-gray-200 dark:border-dark-50">
              <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-2">კომენტარები</h4>
              <div className="space-y-2 mb-3">
                {/* Inline comment display — will work when comments are fetched */}
              </div>
              <div className="flex gap-2">
                <input type="text" value={comment} onChange={(e) => setComment(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleAddComment()} placeholder="დაწერეთ კომენტარი..." className="input flex-1" />
                <button onClick={handleAddComment} className="btn-primary" disabled={!comment.trim()}>გაგზავნა</button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}