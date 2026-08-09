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
