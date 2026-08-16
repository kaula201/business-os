// frontend/src/services/api.ts
import axios from 'axios'
import type { CRMLeadConvert, CRMLeadCreate, CustomerCreditNoteCreate, CustomerInvoiceDraftUpdate, CustomerInvoiceGenerate, CustomerPaymentCreate, GLAccountCreate, GLAccountUpdate } from '../types'

const API_BASE = import.meta.env.VITE_API_URL || ''
const API_PREFIX = '/api/v1'

export const api = axios.create({
  baseURL: API_BASE + API_PREFIX,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor — token-ის დამატება
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor — 401 შემთხვევაში logout
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Don't intercept blob responses (file downloads)
    if (error.config?.responseType === 'blob') {
      return Promise.reject(error)
    }
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  register: (data: { company_name: string; full_name: string; email: string; password: string }) =>
    api.post('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  refresh: (refreshToken: string) =>
    api.post('/auth/refresh', { refresh_token: refreshToken }),
  forgotPassword: (email: string) => api.post('/auth/forgot-password', { email, password: '' }),
  resetPassword: (token: string, new_password: string) =>
    api.post(`/auth/reset-password?token=${encodeURIComponent(token)}&new_password=${encodeURIComponent(new_password)}`),
  verifyEmail: (token: string) => api.get(`/auth/verify-email?token=${encodeURIComponent(token)}`),
  resendVerification: (email: string) => api.post('/auth/resend-verification', { email, password: '' }),
  ssoToken: () => api.get('/auth/sso-token'),
}

// Users API
export const usersApi = {
  list: (params?: { page?: number; page_size?: number; role?: string; search?: string }) =>
    api.get('/users/', { params }),
  getMe: () => api.get('/users/me'),
  update: (id: string, data: any) => api.patch(`/users/${id}`, data),
  delete: (id: string) => api.delete(`/users/${id}`),
  invite: (data: { email: string; full_name: string; role: string }) =>
    api.post('/users/invite', data),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post('/users/change-password', data),
}

// Clients API
export const clientsApi = {
  list: (params?: any) => api.get('/clients/', { params }),
  get: (id: string) => api.get(`/clients/${id}`),
  create: (data: any) => api.post('/clients/', data),
  update: (id: string, data: any) => api.patch(`/clients/${id}`, data),
  delete: (id: string) => api.delete(`/clients/${id}`),
  addInteraction: (id: string, data: any) => api.post(`/clients/${id}/interactions`, data),
}

// CRM API — potential clients, pipeline and follow-up activities
export const crmApi = {
  listLeads: (params?: { page?: number; page_size?: number; status?: string; search?: string }) =>
    api.get('/crm/leads', { params }),
  createLead: (data: CRMLeadCreate) => api.post('/crm/leads', data),
  updateLead: (id: string, data: Record<string, unknown>) => api.patch(`/crm/leads/${id}`, data),
  convertLead: (id: string, data: CRMLeadConvert) => api.post(`/crm/leads/${id}/convert`, data),
  listOpportunities: (params?: { page?: number; page_size?: number; stage?: string }) =>
    api.get('/crm/opportunities', { params }),
  createOpportunity: (data: Record<string, unknown>) => api.post('/crm/opportunities', data),
  updateOpportunity: (id: string, data: Record<string, unknown>) => api.patch(`/crm/opportunities/${id}`, data),
  listActivities: (params?: { page?: number; page_size?: number; status?: string }) =>
    api.get('/crm/activities', { params }),
  createActivity: (data: Record<string, unknown>) => api.post('/crm/activities', data),
  updateActivity: (id: string, data: Record<string, unknown>) => api.patch(`/crm/activities/${id}`, data),
  // ── CRM ინდიკატორები (enhanced) ──
  forecast: () => api.get('/crm/forecast'),
  pipelineValue: () => api.get('/crm/pipeline-value'),
  conversionRate: (params?: { days?: number }) => api.get('/crm/conversion-rate', { params }),
  leadSources: () => api.get('/crm/lead-sources'),
  staleLeads: (params?: { threshold_days?: number }) => api.get('/crm/stale-leads', { params }),
}

// Orders API
export const ordersApi = {
  list: (params?: any) => api.get('/orders/', { params }),
  get: (id: string) => api.get(`/orders/${id}`),
  create: (data: any) => api.post('/orders/', data),
  changeStatus: (id: string, data: { status: string; notes?: string }) =>
    api.patch(`/orders/${id}/status`, data),
  history: (id: string) => api.get(`/orders/${id}/history`),
  reservations: (id: string) => api.get(`/orders/${id}/reservations`),
}

// Products API
export const productsApi = {
  list: (params?: any) => api.get('/products/', { params }),
  get: (id: string) => api.get(`/products/${id}`),
  create: (data: any) => api.post('/products/', data),
  update: (id: string, data: any) => api.patch(`/products/${id}`, data),
  adjustStock: (data: any) => api.post('/products/adjust-stock', data),
  listCategories: () => api.get('/products/categories'),
  createCategory: (data: any) => api.post('/products/categories', data),
}

// Warehouses API
export const warehousesApi = {
  list: (params?: { include_inactive?: boolean }) => api.get('/warehouses/', { params }),
  create: (data: any) => api.post('/warehouses/', data),
  update: (id: string, data: any) => api.patch(`/warehouses/${id}`, data),
  setDefault: (id: string) => api.post(`/warehouses/${id}/set-default`),
  archive: (id: string) => api.post(`/warehouses/${id}/archive`),
  delete: (id: string) => api.delete(`/warehouses/${id}`),
  balances: (params?: { product_id?: string; warehouse_id?: string }) =>
    api.get('/warehouses/balances', { params }),
  adjustStock: (data: any) => api.post('/warehouses/adjust-stock', data),
  transfer: (data: any) => api.post('/warehouses/transfers', data),
  // Movement history
  movements: (params?: {
    product_id?: string; warehouse_id?: string; movement_type?: string;
    reason_category?: string; date_from?: string; date_to?: string;
    limit?: number; offset?: number;
  }) => api.get('/warehouses/movements', { params }),
  // Zones
  listZones: (params?: { warehouse_id?: string; zone_type?: string; include_inactive?: boolean }) =>
    api.get('/warehouses/zones', { params }),
  createZone: (data: any) => api.post('/warehouses/zones', data),
  updateZone: (id: string, data: any) => api.patch(`/warehouses/zones/${id}`, data),
  deleteZone: (id: string) => api.delete(`/warehouses/zones/${id}`),
  zoneBalances: (params?: { zone_id?: string; product_id?: string }) =>
    api.get('/warehouses/zone-balances', { params }),
  // Inventory counts
  listCounts: (params?: { warehouse_id?: string; status?: string; limit?: number; offset?: number }) =>
    api.get('/warehouses/counts', { params }),
  getCount: (id: string) => api.get(`/warehouses/counts/${id}`),
  createCount: (data: any) => api.post('/warehouses/counts', data),
  updateCount: (id: string, data: any) => api.patch(`/warehouses/counts/${id}`, data),
  listCountLines: (countId: string) => api.get(`/warehouses/counts/${countId}/lines`),
  addCountLine: (countId: string, data: any) => api.post(`/warehouses/counts/${countId}/lines`, data),
  updateCountLine: (countId: string, lineId: string, data: any) =>
    api.patch(`/warehouses/counts/${countId}/lines/${lineId}`, data),
  deleteCountLine: (countId: string, lineId: string) =>
    api.delete(`/warehouses/counts/${countId}/lines/${lineId}`),
  postCount: (countId: string) => api.post(`/warehouses/counts/${countId}/post`),
}

// Tasks API
export const tasksApi = {
  list: (params?: any) => api.get('/tasks/', { params }),
  get: (id: string) => api.get(`/tasks/${id}`),
  create: (data: any) => api.post('/tasks/', data),
  update: (id: string, data: any) => api.patch(`/tasks/${id}`, data),
  addComment: (id: string, data: { content: string }) =>
    api.post(`/tasks/${id}/comments`, data),
  dependencies: (id: string) => api.get(`/tasks/${id}/dependencies`),
  addDependency: (id: string, data: { depends_on_task_id: string; dependency_type?: string }) =>
    api.post(`/tasks/${id}/dependencies`, data),
  removeDependency: (id: string, depId: string) => api.delete(`/tasks/${id}/dependencies/${depId}`),
  calendar: (params?: any) => api.get('/tasks/calendar', { params }),
}

// Helpdesk API
export const helpdeskApi = {
  listTickets: (params?: Record<string, unknown>) => api.get('/helpdesk/', { params }),
  createTicket: (data: Record<string, unknown>) => api.post('/helpdesk/', data),
  updateTicket: (id: string, data: Record<string, unknown>) => api.patch(`/helpdesk/${id}`, data),
  removeTicket: (id: string) => api.delete(`/helpdesk/${id}`),
  queues: () => api.get('/helpdesk/queues'),
  createQueue: (data: Record<string, unknown>) => api.post('/helpdesk/queues', data),
  slas: () => api.get('/helpdesk/slas'),
  createSla: (data: Record<string, unknown>) => api.post('/helpdesk/slas', data),
  escalations: () => api.get('/helpdesk/escalations'),
  createEscalation: (data: Record<string, unknown>) => api.post('/helpdesk/escalations', data),
  cannedReplies: () => api.get('/helpdesk/canned-replies'),
  createCannedReply: (data: Record<string, unknown>) => api.post('/helpdesk/canned-replies', data),
  knowledge: () => api.get('/helpdesk/knowledge'),
  createKnowledge: (data: Record<string, unknown>) => api.post('/helpdesk/knowledge', data),
  fieldService: () => api.get('/helpdesk/field-service'),
  createFieldService: (data: Record<string, unknown>) => api.post('/helpdesk/field-service', data),
  emailIntake: () => api.get('/helpdesk/email-intake'),
  createEmailIntake: (data: Record<string, unknown>) => api.post('/helpdesk/email-intake', data),
}

// Reports API
export const reportsApi = {
  summary: (params?: Record<string, unknown>) => api.get('/reports/summary', { params }),
  revenue: (params?: Record<string, unknown>) => api.get('/reports/revenue', { params }),
  definitions: () => api.get('/reports/definitions'),
  saved: () => api.get('/reports/saved'),
  createSaved: (data: Record<string, unknown>) => api.post('/reports/saved', data),
  removeSaved: (id: string) => api.delete(`/reports/saved/${id}`),
  schedules: () => api.get('/reports/schedules'),
  createSchedule: (data: Record<string, unknown>) => api.post('/reports/schedules', data),
  dimensions: () => api.get('/reports/dimensions'),
  createDimension: (data: Record<string, unknown>) => api.post('/reports/dimensions', data),
  pivot: (params?: Record<string, unknown>) => api.get('/reports/pivot', { params }),
}

// Integrations API
export const integrationsApi = {
  apiKeys: () => api.get('/integrations/api-keys'),
  createApiKey: (data: Record<string, unknown>) => api.post('/integrations/api-keys', data),
  removeApiKey: (id: string) => api.delete(`/integrations/api-keys/${id}`),
  webhooks: () => api.get('/integrations/webhooks'),
  createWebhook: (data: Record<string, unknown>) => api.post('/integrations/webhooks', data),
  removeWebhook: (id: string) => api.delete(`/integrations/webhooks/${id}`),
  webhookEvents: () => api.get('/integrations/webhook-events'),
  rsStatus: () => api.get('/integrations/rs/status'),
}

// Payments API
export const paymentsApi = {
  list: () => api.get('/payments/'),
  create: (data: Record<string, unknown>) => api.post('/payments/', data),
  confirm: (id: string) => api.post(`/payments/${id}/confirm`),
  refund: (id: string) => api.post(`/payments/${id}/refund`),
}

// Email + Calendar API
export const emailCalendarApi = {
  emails: () => api.get('/email-calendar/emails'),
  sendEmail: (data: Record<string, unknown>) => api.post('/email-calendar/emails', data),
  events: () => api.get('/email-calendar/events'),
  createEvent: (data: Record<string, unknown>) => api.post('/email-calendar/events', data),
  removeEvent: (id: string) => api.delete(`/email-calendar/events/${id}`),
}

// Dashboard API
export const dashboardApi = {
  getSummary: (period: string = '30d', ownerId?: string) => api.get('/dashboard/summary', { params: { period, ...(ownerId ? { owner_id: ownerId } : {}) } }),
  getAging: () => api.get('/dashboard/aging'),
  getCashFlow: () => api.get('/dashboard/cash-flow'),
  getDrillDown: (entity: 'ar' | 'ap', bucket: string = 'all') =>
    api.get(`/dashboard/drill-down/${entity}`, { params: { bucket } }),
}

// AI API
export const aiApi = {
  chat: (message: string) => api.post('/ai/chat', { message }),
  quickActions: () => api.get('/ai/quick-actions'),
}

// Invoices API
export const invoicesApi = {
  generate: (data: CustomerInvoiceGenerate) => api.post('/invoices/generate', data),
  list: (params?: { page?: number; page_size?: number; status?: string; client_id?: string; search?: string }) =>
    api.get('/invoices/', { params }),
  get: (id: string) => api.get(`/invoices/${id}`),
  updateDraft: (id: string, data: CustomerInvoiceDraftUpdate) => api.patch(`/invoices/${id}/draft`, data),
  issue: (id: string) => api.post(`/invoices/${id}/issue`),
  preview: (id: string) => api.get(`/invoices/${id}/preview`, { responseType: 'blob' }),
  download: (id: string) => api.get(`/invoices/${id}/download`, { responseType: 'blob' }),
  downloadWord: (id: string) => api.get(`/invoices/${id}/download-word`, { responseType: 'blob' }),
  downloadExcel: (id: string) => api.get(`/invoices/${id}/download-excel`, { responseType: 'blob' }),
}

// Suppliers API
export const suppliersApi = {
  list: (params?: { page?: number; page_size?: number; search?: string; include_inactive?: boolean }) =>
    api.get('/suppliers/', { params }),
  get: (id: string) => api.get(`/suppliers/${id}`),
  create: (data: any) => api.post('/suppliers/', data),
  update: (id: string, data: any) => api.patch(`/suppliers/${id}`, data),
  archive: (id: string) => api.post(`/suppliers/${id}/archive`),
}

// Purchase Orders & Goods Receipts API
export const purchaseOrdersApi = {
  list: (params?: { page?: number; page_size?: number; status?: string; supplier_id?: string; search?: string }) =>
    api.get('/purchase-orders/', { params }),
  get: (id: string) => api.get(`/purchase-orders/${id}`),
  create: (data: any) => api.post('/purchase-orders/', data),
  changeStatus: (id: string, status: string, notes?: string) =>
    api.patch(`/purchase-orders/${id}/status`, { status, notes }),
  history: (id: string) => api.get(`/purchase-orders/${id}/history`),
  receipts: (id: string) => api.get(`/purchase-orders/${id}/receipts`),
  receive: (id: string, data: any) => api.post(`/purchase-orders/${id}/receipts`, data),
}

export const purchaseCostsApi = {
  list: (params?: { page?: number; page_size?: number; product_id?: string; supplier_id?: string; date_from?: string; date_to?: string }) =>
    api.get('/purchase-cost-history/', { params }),
}

export const purchaseApprovalApi = {
  get: () => api.get('/purchase-approval-policy/'),
  update: (manager_approval_limit: number) =>
    api.patch('/purchase-approval-policy/', { manager_approval_limit }),
}

// Supplier invoices, 3-way matching & payables API
export const supplierFinanceApi = {
  listInvoices: (params?: { page?: number; page_size?: number; status?: string; supplier_id?: string; search?: string }) =>
    api.get('/supplier-invoices/', { params }),
  getInvoice: (id: string) => api.get(`/supplier-invoices/${id}`),
  createInvoice: (data: any) => api.post('/supplier-invoices/', data),
  changeInvoiceStatus: (id: string, status: 'approved' | 'cancelled', notes?: string) =>
    api.patch(`/supplier-invoices/${id}/status`, { status, notes }),
  listPayables: (params?: { page?: number; page_size?: number; status?: string; supplier_id?: string; search?: string }) =>
    api.get('/supplier-payables/', { params }),
  getPayable: (id: string) => api.get(`/supplier-payables/${id}`),
  postPayment: (id: string, data: any) => api.post(`/supplier-payables/${id}/payments`, data),
  postCreditNote: (id: string, data: any) => api.post(`/supplier-payables/${id}/credit-notes`, data),
  reversePayment: (id: string, data: any) => api.post(`/supplier-payments/${id}/reversal`, data),
}

export const bankingApi = {
  listAccounts: () => api.get('/bank-accounts/'),
  createAccount: (data: { bank_name: string; account_name: string; iban: string; currency: string }) =>
    api.post('/bank-accounts/', data),
  importStatement: (accountId: string, data: { idempotency_key: string; filename: string; csv_content: string }) =>
    api.post(`/bank-accounts/${accountId}/statement-imports`, data),
  listTransactions: (params?: { page?: number; page_size?: number; bank_account_id?: string; direction?: string; status?: string }) =>
    api.get('/bank-transactions/', { params }),
  reconcile: (transactionId: string, data: { idempotency_key: string; supplier_payable_id: string; amount: number; notes?: string }) =>
    api.post(`/bank-transactions/${transactionId}/reconciliations`, data),
  listReconciliations: (params?: { page?: number; page_size?: number; bank_transaction_id?: string; status?: string }) =>
    api.get('/bank-reconciliations/', { params }),
  reverseReconciliation: (id: string, data: { idempotency_key: string; reason: string }) =>
    api.post(`/bank-reconciliations/${id}/reversal`, data),
  // Reconciliation rules
  listRules: (params?: { page?: number; page_size?: number; is_active?: boolean }) =>
    api.get('/banking/reconciliation-rules/', { params }),
  createRule: (data: Record<string, unknown>) => api.post('/banking/reconciliation-rules/', data),
  updateRule: (id: string, data: Record<string, unknown>) => api.patch(`/banking/reconciliation-rules/${id}`, data),
  deleteRule: (id: string) => api.delete(`/banking/reconciliation-rules/${id}`),
  applyRules: (on_date?: string) => api.post('/banking/reconciliation-rules/apply', null, { params: on_date ? { on_date } : {} }),
}

// Inventory valuation API
export const inventoryValuationApi = {
  get: (productId: string) => api.get(`/inventory/valuation/${productId}`),
  adjust: (data: { product_id: string; quantity: number; unit_cost: number; note?: string }) =>
    api.post('/inventory/valuation/adjust', data),
}

export const customerFinanceApi = {
  listReceivables: (params?: { page?: number; page_size?: number; status?: string; client_id?: string; invoice_id?: string; search?: string }) =>
    api.get('/customer-receivables/', { params }),
  postPayment: (id: string, data: CustomerPaymentCreate) =>
    api.post(`/customer-receivables/${id}/payments`, data),
  reversePayment: (id: string, data: { idempotency_key: string; reason: string }) =>
    api.post(`/customer-payments/${id}/reversal`, data),
  postCreditNote: (id: string, data: CustomerCreditNoteCreate) =>
    api.post(`/customer-receivables/${id}/credit-notes`, data),
  reconcileBankTransaction: (transactionId: string, data: { idempotency_key: string; customer_receivable_id: string; amount: number; notes?: string }) =>
    api.post(`/bank-transactions/${transactionId}/customer-reconciliations`, data),
  listBankReconciliations: (params?: { page?: number; page_size?: number; customer_receivable_id?: string; bank_transaction_id?: string; status?: string }) =>
    api.get('/bank-customer-reconciliations/', { params }),
  reverseBankReconciliation: (id: string, data: { idempotency_key: string; reason: string }) =>
    api.post(`/bank-customer-reconciliations/${id}/reversal`, data),
}

// Exports API
export const exportsApi = {
  orders: (params?: any) => api.get('/export/orders', { params, responseType: 'blob' }),
  clients: () => api.get('/export/clients', { responseType: 'blob' }),
  products: () => api.get('/export/products', { responseType: 'blob' }),
  tasks: () => api.get('/export/tasks', { responseType: 'blob' }),
}

// General Ledger API
export const glApi = {
  listAccounts: (params?: { page?: number; page_size?: number; account_type?: string; is_active?: boolean; search?: string }) =>
    api.get('/gl/accounts/', { params }),
  getAccount: (id: string) => api.get(`/gl/accounts/${id}`),
  createAccount: (data: GLAccountCreate) => api.post('/gl/accounts/', data),
  updateAccount: (id: string, data: GLAccountUpdate) => api.patch(`/gl/accounts/${id}`, data),
  listJournalEntries: (params?: { page?: number; page_size?: number; reference_type?: string; date_from?: string; date_to?: string }) =>
    api.get('/gl/journal-entries/', { params }),
  getJournalEntry: (id: string) => api.get(`/gl/journal-entries/${id}`),
  trialBalance: (params?: { as_of_date?: string }) => api.get('/gl/trial-balance/', { params }),
  profitLoss: (params?: { date_from?: string; date_to?: string }) => api.get('/gl/profit-loss/', { params }),
  balanceSheet: (params?: { as_of_date?: string }) => api.get('/gl/balance-sheet/', { params }),
  // Manual journal entry
  createJournalEntry: (data: { entry_date: string; description: string; lines: { gl_account_id: string; debit_amount?: number; credit_amount?: number; description?: string }[] }) =>
    api.post('/gl/journal-entries/', data),
  // Recurring entries
  listRecurring: (params?: { page?: number; page_size?: number; is_active?: boolean }) =>
    api.get('/gl/recurring/', { params }),
  createRecurring: (data: Record<string, unknown>) => api.post('/gl/recurring/', data),
  updateRecurring: (id: string, data: Record<string, unknown>) => api.patch(`/gl/recurring/${id}`, data),
  deleteRecurring: (id: string) => api.delete(`/gl/recurring/${id}`),
  runRecurring: (through_date?: string) => api.post('/gl/recurring/run', null, { params: through_date ? { through_date } : {} }),
  // Exchange differences
  runExchangeDifferences: (on_date?: string) => api.post('/gl/exchange-differences/run', null, { params: on_date ? { on_date } : {} }),
  listExchangeDifferences: (params?: { page?: number; page_size?: number; currency?: string; date_from?: string; date_to?: string }) =>
    api.get('/gl/exchange-differences/', { params }),
  // Consolidated reports
  consolidatedCompanies: () => api.get('/gl/consolidated/companies'),
  consolidatedProfitLoss: (params?: { date_from?: string; date_to?: string }) =>
    api.get('/gl/consolidated/profit-loss', { params }),
  consolidatedBalanceSheet: (params?: { as_of_date?: string }) =>
    api.get('/gl/consolidated/balance-sheet', { params }),
}

// Company API
export const companyApi = {
  getMyCompany: () => api.get('/companies/me'),
  updateMyCompany: (data: { name?: string; address?: string; phone?: string; email?: string; website?: string; logo_url?: string; is_vat_payer?: boolean; currency?: string }) =>
    api.patch('/companies/me', data),
}

// Import API
export const importApi = {
  importClients: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/import/clients', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  importProducts: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/import/products', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
}

// Fleet Management API
export const fleetApi = {
  listVehicles: () => api.get('/fleet/vehicles'),
  getVehicle: (id: string) => api.get(`/fleet/vehicles/${id}`),
  createVehicle: (data: import('../types').VehicleCreate) => api.post('/fleet/vehicles', data),
  updateVehicle: (id: string, data: import('../types').VehicleUpdate) => api.put(`/fleet/vehicles/${id}`, data),
  deleteVehicle: (id: string) => api.delete(`/fleet/vehicles/${id}`),
  listFuelLogs: (vehicleId: string) => api.get(`/fleet/vehicles/${vehicleId}/fuel-logs`),
  createFuelLog: (vehicleId: string, data: import('../types').FuelLogCreate) => api.post(`/fleet/vehicles/${vehicleId}/fuel-logs`, data),
  deleteFuelLog: (id: string) => api.delete(`/fleet/fuel-logs/${id}`),
  listServices: (vehicleId: string) => api.get(`/fleet/vehicles/${vehicleId}/services`),
  createService: (vehicleId: string, data: import('../types').ServiceRecordCreate) => api.post(`/fleet/vehicles/${vehicleId}/services`, data),
  deleteService: (id: string) => api.delete(`/fleet/services/${id}`),
  listDrivers: (vehicleId: string) => api.get(`/fleet/vehicles/${vehicleId}/drivers`),
  createDriver: (vehicleId: string, data: import('../types').DriverAssignmentCreate) => api.post(`/fleet/vehicles/${vehicleId}/drivers`, data),
  updateDriver: (id: string, data: import('../types').DriverAssignmentUpdate) => api.put(`/fleet/drivers/${id}`, data),
  deleteDriver: (id: string) => api.delete(`/fleet/drivers/${id}`),
}

// App Module API
export const modulesApi = {
  list: (params?: { page?: number; page_size?: number; category?: string; is_active?: boolean }) =>
    api.get('/modules/', { params }),
  get: (id: string) => api.get(`/modules/${id}`),
  create: (data: { code: string; name: string; description?: string; icon?: string; route?: string; category?: string; sort_order?: number }) =>
    api.post('/modules/', data),
  update: (id: string, data: Record<string, unknown>) => api.patch(`/modules/${id}`, data),
  deactivate: (id: string) => api.delete(`/modules/${id}`),
  getCompanyModules: () => api.get('/modules/company'),
  toggleModule: (moduleId: string, enabled: boolean) =>
    api.post(`/modules/company/${moduleId}/toggle`, { enabled }),
  listPermissions: (moduleId: string) => api.get(`/modules/permissions/${moduleId}`),
  upsertPermission: (moduleId: string, data: { role: string; can_access?: boolean; can_create?: boolean; can_edit?: boolean; can_delete?: boolean; can_approve?: boolean }) =>
    api.post(`/modules/permissions/${moduleId}`, data),
}

// Sales tools API — quotations, price lists, payment terms
export const salesToolsApi = {
  listQuotations: (params?: Record<string, unknown>) => api.get('/quotations/', { params }),
  getQuotation: (id: string) => api.get(`/quotations/${id}`),
  createQuotation: (data: Record<string, unknown>) => api.post('/quotations/', data),
  updateQuotationStatus: (id: string, status: string) => api.patch(`/quotations/${id}/status`, { status }),
  convertQuotation: (id: string) => api.post(`/quotations/${id}/convert`),
  deleteQuotation: (id: string) => api.delete(`/quotations/${id}`),
  listPriceLists: (params?: Record<string, unknown>) => api.get('/price-lists/', { params }),
  createPriceList: (data: Record<string, unknown>) => api.post('/price-lists/', data),
  updatePriceList: (id: string, data: Record<string, unknown>) => api.patch(`/price-lists/${id}`, data),
  deletePriceList: (id: string) => api.delete(`/price-lists/${id}`),
  listPaymentTerms: (params?: Record<string, unknown>) => api.get('/payment-terms/', { params }),
  createPaymentTerm: (data: Record<string, unknown>) => api.post('/payment-terms/', data),
  updatePaymentTerm: (id: string, data: Record<string, unknown>) => api.patch(`/payment-terms/${id}`, data),
  deletePaymentTerm: (id: string) => api.delete(`/payment-terms/${id}`),
}

// Sales org API — teams, targets, commissions
export const salesOrgApi = {
  listTeams: (params?: Record<string, unknown>) => api.get('/sales/teams/', { params }),
  createTeam: (data: Record<string, unknown>) => api.post('/sales/teams/', data),
  updateTeam: (id: string, data: Record<string, unknown>) => api.patch(`/sales/teams/${id}`, data),
  deleteTeam: (id: string) => api.delete(`/sales/teams/${id}`),
  addMember: (teamId: string, userId: string) => api.post(`/sales/teams/${teamId}/members`, { user_id: userId }),
  removeMember: (teamId: string, userId: string) => api.delete(`/sales/teams/${teamId}/members/${userId}`),
  listTargets: (params?: Record<string, unknown>) => api.get('/sales/targets/', { params }),
  createTarget: (data: Record<string, unknown>) => api.post('/sales/targets/', data),
  updateTarget: (id: string, data: Record<string, unknown>) => api.patch(`/sales/targets/${id}`, data),
  deleteTarget: (id: string) => api.delete(`/sales/targets/${id}`),
  listRules: (params?: Record<string, unknown>) => api.get('/sales/commission-rules/', { params }),
  createRule: (data: Record<string, unknown>) => api.post('/sales/commission-rules/', data),
  updateRule: (id: string, data: Record<string, unknown>) => api.patch(`/sales/commission-rules/${id}`, data),
  deleteRule: (id: string) => api.delete(`/sales/commission-rules/${id}`),
  listCommissions: (params?: Record<string, unknown>) => api.get('/sales/commissions/', { params }),
  markCommissionPaid: (id: string) => api.post(`/sales/commissions/${id}/mark-paid`),
}

// Communication API — email tracking, e-signature, subscriptions, portal
export const commApi = {
  recordEmailEvent: (data: { campaign_id: string; recipient_email: string; event_type: string }) =>
    api.post('/email-events/', data),
  listEmailEvents: (params?: Record<string, unknown>) => api.get('/email-events/', { params }),
  campaignStats: (campaignId: string) => api.get(`/email-campaigns/${campaignId}/stats`),
  listSignatureRequests: (params?: Record<string, unknown>) => api.get('/signature-requests/', { params }),
  createSignatureRequest: (data: Record<string, unknown>) => api.post('/signature-requests/', data),
  signRequest: (data: { token: string; signer_email: string; decision: string }) =>
    api.post('/signature-requests/sign', data),
  listSubscriptions: (params?: Record<string, unknown>) => api.get('/subscriptions/', { params }),
  createSubscription: (data: Record<string, unknown>) => api.post('/subscriptions/', data),
  updateSubscription: (id: string, data: Record<string, unknown>) => api.patch(`/subscriptions/${id}`, data),
  renewSubscription: (id: string) => api.post(`/subscriptions/${id}/renew`),
  deleteSubscription: (id: string) => api.delete(`/subscriptions/${id}`),
  listPortalUsers: (params?: Record<string, unknown>) => api.get('/customer-portal/', { params }),
  createPortalUser: (data: Record<string, unknown>) => api.post('/customer-portal/', data),
  updatePortalUser: (id: string, data: Record<string, unknown>) => api.patch(`/customer-portal/${id}`, data),
  deletePortalUser: (id: string) => api.delete(`/customer-portal/${id}`),
  portalSummary: (clientId: string) => api.get(`/customer-portal/clients/${clientId}/summary`),
}

// WMS API — batches (lots) and serial numbers
export const wmsApi = {
  listBatches: (params?: { product_id?: string; expiring_soon?: boolean; limit?: number }) =>
    api.get('/wms/batches', { params }),
  createBatch: (data: Record<string, unknown>) => api.post('/wms/batches', data),
  receiveBatch: (id: string, quantity: number) => api.post(`/wms/batches/${id}/receive`, null, { params: { quantity } }),
  adjustBatch: (id: string, data: { quantity_delta: number; reason: string }) =>
    api.post(`/wms/batches/${id}/adjust`, data),
  transferBatch: (id: string, data: { destination_warehouse_id: string; reason?: string }) =>
    api.post(`/wms/batches/${id}/transfer`, data),
  listSerials: (params?: { product_id?: string; status?: string; limit?: number }) =>
    api.get('/wms/serials', { params }),
  registerSerial: (data: Record<string, unknown>) => api.post('/wms/serials', data),
  updateSerialStatus: (id: string, status: string) =>
    api.patch(`/wms/serials/${id}/status`, null, { params: { status } }),
}

// WMS operations API — picking, packing, replenishment, landed cost, traceability
export const wmsOpsApi = {
  listPickLists: (params?: { status?: string; limit?: number }) => api.get('/wms-ops/pick-lists', { params }),
  createPickList: (data: Record<string, unknown>) => api.post('/wms-ops/pick-lists', data),
  pickItem: (pickListId: string, data: { item_id: string; quantity: number }) =>
    api.post(`/wms-ops/pick-lists/${pickListId}/pick`, data),
  completePickList: (id: string) => api.post(`/wms-ops/pick-lists/${id}/complete`),
  listPackingSlips: (params?: { status?: string; limit?: number }) => api.get('/wms-ops/packing-slips', { params }),
  createPackingSlip: (data: Record<string, unknown>) => api.post('/wms-ops/packing-slips', data),
  listReplenishmentRules: () => api.get('/wms-ops/replenishment-rules'),
  createReplenishmentRule: (data: Record<string, unknown>) => api.post('/wms-ops/replenishment-rules', data),
  replenishmentSuggestions: () => api.get('/wms-ops/replenishment/suggestions'),
  listLandedCosts: () => api.get('/wms-ops/landed-costs'),
  createLandedCost: (data: Record<string, unknown>) => api.post('/wms-ops/landed-costs', data),
  allocateLandedCost: (id: string, data: { allocations: { batch_id: string; amount: number }[] }) =>
    api.post(`/wms-ops/landed-costs/${id}/allocate`, data),
  batchTrace: (batchId: string) => api.get(`/wms-ops/trace/${batchId}`),
  serialTrace: (serialId: string) => api.get(`/wms-ops/trace/serial/${serialId}`),
  allocationSuggestion: (productId: string, strategy: 'fifo' | 'fefo', quantity: number) =>
    api.get(`/wms-ops/allocation/${productId}`, { params: { strategy, quantity } }),
}

// Procurement API — RFQ, comparison, vendor pricelists, blanket orders, scorecards
export const procurementApi = {
  listRfqs: (params?: { status?: string; limit?: number }) => api.get('/procurement/rfqs', { params }),
  createRfq: (data: Record<string, unknown>) => api.post('/procurement/rfqs', data),
  submitRfqResponse: (rfqId: string, data: Record<string, unknown>) =>
    api.post(`/procurement/rfqs/${rfqId}/responses`, data),
  rfqComparison: (rfqId: string) => api.get(`/procurement/rfqs/${rfqId}/comparison`),
  awardRfq: (rfqId: string, supplierId: string) =>
    api.post(`/procurement/rfqs/${rfqId}/award`, null, { params: { supplier_id: supplierId } }),
  listPriceLists: (params?: { supplier_id?: string; product_id?: string }) =>
    api.get('/procurement/price-lists', { params }),
  upsertPriceList: (data: Record<string, unknown>) => api.post('/procurement/price-lists', data),
  listBlanketOrders: (params?: { status?: string }) => api.get('/procurement/blanket-orders', { params }),
  createBlanketOrder: (data: Record<string, unknown>) => api.post('/procurement/blanket-orders', data),
  activateBlanketOrder: (id: string) => api.post(`/procurement/blanket-orders/${id}/activate`),
  listScorecards: (params?: { supplier_id?: string }) => api.get('/procurement/scorecards', { params }),
  upsertScorecard: (data: Record<string, unknown>) => api.post('/procurement/scorecards', data),
  autoReplenish: (warehouseId?: string) =>
    api.post('/procurement/auto-replenish', null, { params: warehouseId ? { warehouse_id: warehouseId } : {} }),
}

// Contracts API
export const contractsApi = {
  list: (params?: { page?: number; page_size?: number; status?: string; search?: string }) =>
    api.get('/contracts/', { params }),
  get: (id: string) => api.get(`/contracts/${id}`),
  create: (data: Record<string, unknown>) => api.post('/contracts/', data),
  update: (id: string, data: Record<string, unknown>) => api.patch(`/contracts/${id}`, data),
  remove: (id: string) => api.delete(`/contracts/${id}`),
}

// POS API — sessions, orders, refunds, loyalty, offline, fiscal devices
export const posApi = {
  listSessions: (params?: { status?: string }) => api.get('/pos/sessions', { params }),
  openSession: (data: { name: string }) => api.post('/pos/sessions', data),
  closeSession: (id: string) => api.post(`/pos/sessions/${id}/close`),
  listOrders: (params?: { session_id?: string }) => api.get('/pos/orders', { params }),
  createOrder: (data: Record<string, unknown>) => api.post('/pos/orders', data),
  refundOrder: (id: string, amount: number, reason?: string) =>
    api.post(`/pos/orders/${id}/refund`, null, { params: { amount, reason } }),
  listRefunds: () => api.get('/pos/refunds'),
  loyaltyBalance: (clientId: string) => api.get(`/pos/loyalty/${clientId}`),
  earnLoyalty: (clientId: string, orderId: string, points: number) =>
    api.post('/pos/loyalty/earn', null, { params: { client_id: clientId, order_id: orderId, points } }),
  redeemLoyalty: (clientId: string, points: number) =>
    api.post('/pos/loyalty/redeem', null, { params: { client_id: clientId, points } }),
  listOfflineQueue: (params?: { status?: string }) => api.get('/pos/offline/queue', { params }),
  queueOfflineOrder: (deviceId: string, payload: Record<string, unknown>) =>
    api.post('/pos/offline/queue', payload, { params: { device_id: deviceId } }),
  syncOfflineOrder: (id: string) => api.post(`/pos/offline/queue/${id}/sync`),
  listFiscalDevices: () => api.get('/pos/fiscal-devices'),
  registerFiscalDevice: (data: { name: string; device_type: string; serial_number: string }) =>
    api.post('/pos/fiscal-devices', null, { params: data }),
}

// HR API — payroll, payslips, leave, attendance, appraisal, recruitment
export const hrApi = {
  listEmployees: (params?: Record<string, unknown>) => api.get('/hr/employees', { params }),
  createEmployee: (data: Record<string, unknown>) => api.post('/hr/employees', data),
  updateEmployee: (id: string, data: Record<string, unknown>) => api.patch(`/hr/employees/${id}`, data),
  listDepartments: () => api.get('/hr/departments'),
  calculatePayroll: (year: number, month: number) => api.post('/hr/payroll/calculate', { year, month }),
  listPayroll: (params?: Record<string, unknown>) => api.get('/hr/payroll', { params }),
  generatePayslips: (year: number, month: number) => api.post('/hr/payslips/generate', null, { params: { year, month } }),
  listPayslips: (params?: { year?: number; month?: number }) => api.get('/hr/payslips', { params }),
  listTimesheets: (params?: Record<string, unknown>) => api.get('/hr/timesheets', { params }),
  createTimesheet: (data: Record<string, unknown>) => api.post('/hr/timesheets', data),
  listLeaveRequests: (params?: Record<string, unknown>) => api.get('/hr/leave-requests', { params }),
  createLeaveRequest: (data: Record<string, unknown>) => api.post('/hr/leave-requests', data),
  listAttendance: (params?: Record<string, unknown>) => api.get('/hr/attendance', { params }),
  createAttendance: (data: Record<string, unknown>) => api.post('/hr/attendance', data),
  listReviews: (params?: Record<string, unknown>) => api.get('/hr/reviews', { params }),
  createReview: (data: Record<string, unknown>) => api.post('/hr/reviews', data),
  listJobPostings: (params?: Record<string, unknown>) => api.get('/recruitment/job-postings', { params }),
  createJobPosting: (data: Record<string, unknown>) => api.post('/recruitment/job-postings', data),
}

// Projects API
export const projectsApi = {
  list: (params?: Record<string, unknown>) => api.get('/projects/', { params }),
  get: (id: string) => api.get(`/projects/${id}`),
  create: (data: Record<string, unknown>) => api.post('/projects/', data),
  update: (id: string, data: Record<string, unknown>) => api.patch(`/projects/${id}`, data),
  remove: (id: string) => api.delete(`/projects/${id}`),
  milestones: (projectId: string) => api.get(`/projects/${projectId}/milestones`),
  createMilestone: (projectId: string, data: Record<string, unknown>) => api.post(`/projects/${projectId}/milestones`, data),
  updateMilestone: (projectId: string, milestoneId: string, data: Record<string, unknown>) => api.patch(`/projects/${projectId}/milestones/${milestoneId}`, data),
  removeMilestone: (projectId: string, milestoneId: string) => api.delete(`/projects/${projectId}/milestones/${milestoneId}`),
  progress: (projectId: string) => api.get(`/projects/${projectId}/progress`),
  profitability: (projectId: string) => api.get(`/projects/${projectId}/profitability`),
}
