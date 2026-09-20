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
  // Client 2.0
  listAddresses: (id: string) => api.get(`/clients/${id}/addresses`),
  createAddress: (id: string, data: any) => api.post(`/clients/${id}/addresses`, data),
  deleteAddress: (addressId: string) => api.delete(`/clients/addresses/${addressId}`),
  listGroups: () => api.get('/clients/client-groups'),
  createGroup: (data: any) => api.post('/clients/client-groups', data),
  deleteGroup: (groupId: string) => api.delete(`/clients/client-groups/${groupId}`),
  setClientGroups: (id: string, groupIds: string[]) => api.post(`/clients/${id}/groups`, groupIds),
  listRelations: (id: string) => api.get(`/clients/${id}/relations`),
  createRelation: (id: string, data: any) => api.post(`/clients/${id}/relations`, data),
  deleteRelation: (relationId: string) => api.delete(`/clients/relations/${relationId}`),
  getStatement: (id: string) => api.get(`/clients/${id}/statement`),
  merge: (data: any) => api.post('/clients/merge', data),
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
  // ── Configurable pipeline stages (kanban) ──
  listPipelineStages: () => api.get('/crm/pipeline-stages'),
  createPipelineStage: (data: Record<string, unknown>) => api.post('/crm/pipeline-stages', data),
  updatePipelineStage: (id: string, data: Record<string, unknown>) => api.patch(`/crm/pipeline-stages/${id}`, data),
  deletePipelineStage: (id: string) => api.delete(`/crm/pipeline-stages/${id}`),
  reorderPipelineStages: (stages: { id: string; sort_order: number }[]) =>
    api.post('/crm/pipeline-stages/reorder', { stages }),
  // ── Lead scoring ──
  leadScore: (id: string) => api.get(`/crm/leads/${id}/score`),
  // ── CRM → Quotation + email ──
  createQuotationFromOpportunity: (id: string) => api.post(`/crm/opportunities/${id}/quotation`),
  sendQuotationEmail: (id: string) => api.post(`/crm/quotations/${id}/send-email`),
  // ── CRM 2.0 — enterprise ──
  listContacts: (params?: Record<string, unknown>) => api.get('/crm/contacts', { params }),
  createContact: (data: Record<string, unknown>) => api.post('/crm/contacts', data),
  createEmailThread: (data: Record<string, unknown>) => api.post('/crm/email-threads', data),
  listEmailMessages: (threadId: string) => api.get(`/crm/email-threads/${threadId}/messages`),
  logCall: (data: Record<string, unknown>) => api.post('/crm/telephony/calls', data),
  listCalls: (params?: Record<string, unknown>) => api.get('/crm/telephony/calls', { params }),
  createAttribution: (data: Record<string, unknown>) => api.post('/crm/attribution', data),
  attributionAnalytics: () => api.get('/crm/attribution/analytics'),
  runRouting: (leadId: string) => api.post('/crm/routing/run', { lead_id: leadId }),
  listTerritories: () => api.get('/crm/territories'),
  createTerritory: (data: Record<string, unknown>) => api.post('/crm/territories', data),
  listSlas: () => api.get('/crm/slas'),
  createSla: (data: Record<string, unknown>) => api.post('/crm/slas', data),
  setGdprConsent: (data: Record<string, unknown>) => api.post('/crm/gdpr/consents', data),
  listGdprConsents: (params?: Record<string, unknown>) => api.get('/crm/gdpr/consents', { params }),
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
  // Order 2.0
  updateBackorder: (id: string, data: any) => api.patch(`/orders/${id}/backorder`, data),
  updateFulfillment: (id: string, data: any) => api.patch(`/orders/${id}/fulfillment`, data),
  updateDropShip: (id: string, data: any) => api.patch(`/orders/${id}/drop-ship`, data),
  createReturn: (id: string, data: any) => api.post(`/orders/${id}/returns`, data),
  listReturns: () => api.get('/orders/order-returns'),
  updateReturnStatus: (id: string, data: any) => api.patch(`/orders/returns/${id}`, data),
  updateItemSerialLot: (itemId: string, data: any) => api.patch(`/orders/items/${itemId}/serial-lot`, data),
  approveCreditLimit: (id: string, data: any) => api.post(`/orders/${id}/credit-limit-approval`, data),
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
  teams: () => api.get('/helpdesk/teams'),
  createTeam: (data: Record<string, unknown>) => api.post('/helpdesk/teams', data),
  addTeamMember: (teamId: string, userId: string) => api.post(`/helpdesk/teams/${teamId}/members`, null, { params: { user_id: userId } }),
  removeTeam: (teamId: string) => api.delete(`/helpdesk/teams/${teamId}`),
  pipelines: () => api.get('/helpdesk/pipelines'),
  createPipeline: (data: Record<string, unknown>) => api.post('/helpdesk/pipelines', data),
  removePipeline: (pipelineId: string) => api.delete(`/helpdesk/pipelines/${pipelineId}`),
  // P1.6 rich ticket features
  get: (id: string) => api.get(`/helpdesk/${id}`),
  messages: (id: string) => api.get(`/helpdesk/${id}/messages`),
  addMessage: (id: string, data: Record<string, unknown>) => api.post(`/helpdesk/${id}/messages`, data),
  followers: (id: string) => api.get(`/helpdesk/${id}/followers`),
  addFollower: (id: string, userId: string) => api.post(`/helpdesk/${id}/followers`, { user_id: userId }),
  attachments: (id: string) => api.get(`/helpdesk/${id}/attachments`),
  uploadAttachment: (id: string, formData: FormData) => api.post(`/helpdesk/${id}/attachments`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  addTimeSpent: (id: string, minutes: number) => api.post(`/helpdesk/${id}/time-spent`, { minutes }),
  rateSatisfaction: (id: string, data: Record<string, unknown>) => api.post(`/helpdesk/${id}/satisfaction`, data),
  kbSuggestions: (id: string) => api.get(`/helpdesk/${id}/kb-suggestions`),
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
  submitInvoice: (data: Record<string, unknown>) => api.post('/integrations/rs/invoices/submit', data),
  submitWaybill: (data: Record<string, unknown>) => api.post('/integrations/rs/waybills/submit', data),
  exportDeclaration: (data: Record<string, unknown>) => api.post('/integrations/rs/declarations/export', data),
  verifyCounterparty: (data: Record<string, unknown>) => api.post('/integrations/counterparties/verify', data),
  counterpartyChecks: (params?: { identification_code?: string }) => api.get('/integrations/counterparties/checks', { params }),
}

// Configurable platform (Studio-style)
export const platformApi = {
  customFields: () => api.get('/platform/custom-fields'),
  createCustomField: (data: Record<string, unknown>) => api.post('/platform/custom-fields', data),
  deleteCustomField: (id: string) => api.delete(`/platform/custom-fields/${id}`),
  customValues: (params: { entity_type: string; entity_id: string }) => api.get('/platform/custom-values', { params }),
  setCustomValues: (entityType: string, entityId: string, data: Record<string, unknown>) => api.put(`/platform/custom-values/${entityType}/${entityId}`, data),
  workflows: () => api.get('/platform/workflows'),
  createWorkflow: (data: Record<string, unknown>) => api.post('/platform/workflows', data),
  deleteWorkflow: (id: string) => api.delete(`/platform/workflows/${id}`),
  reports: () => api.get('/platform/reports'),
  createReport: (data: Record<string, unknown>) => api.post('/platform/reports', data),
  pdfTemplates: () => api.get('/platform/pdf-templates'),
  createPdfTemplate: (data: Record<string, unknown>) => api.post('/platform/pdf-templates', data),
  renderPdfTemplate: (id: string, data: Record<string, unknown>) => api.post(`/platform/pdf-templates/${id}/render`, data),
  deletePdfTemplate: (id: string) => api.delete(`/platform/pdf-templates/${id}`),
  customRoles: () => api.get('/platform/custom-roles'),
  createCustomRole: (data: Record<string, unknown>) => api.post('/platform/custom-roles', data),
  deleteCustomRole: (id: string) => api.delete(`/platform/custom-roles/${id}`),
  importMappings: () => api.get('/platform/import-mappings'),
  createImportMapping: (data: Record<string, unknown>) => api.post('/platform/import-mappings', data),
  deleteImportMapping: (id: string) => api.delete(`/platform/import-mappings/${id}`),
  industryTemplates: () => api.get('/platform/industry-templates'),
}

// API Keys API (Odoo JSON-2 API style)
export const apiKeysApi = {
  list: () => api.get('/api-keys/'),
  create: (data: Record<string, unknown>) => api.post('/api-keys/', data),
  rotate: (id: string) => api.post(`/api-keys/${id}/rotate`),
  revoke: (id: string) => api.post(`/api-keys/${id}/revoke`),
  createBotUser: (data: Record<string, unknown>) => api.post('/api-keys/bot-users', data),
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

// Security API (2FA, login history, approval steps)
export const securityApi = {
  twoFaStatus: () => api.get('/auth/2fa/status'),
  twoFaSetup: () => api.post('/auth/2fa/setup'),
  twoFaDisable: () => api.post('/auth/2fa/disable'),
  loginHistory: () => api.get('/auth/login-history'),
  sessions: () => api.get('/auth/sessions'),
  revokeSession: (id: string) => api.post(`/auth/sessions/${id}/revoke`),
  logout: () => api.post('/auth/logout'),
  auditLogs: (entityType?: string) => api.get('/auth/audit-logs', { params: entityType ? { entity_type: entityType } : {} }),
  approvalSteps: (id: string) => api.get(`/approvals/${id}/steps`),
  addApprovalStep: (id: string, data: Record<string, unknown>) => api.post(`/approvals/${id}/steps`, data),
  decideApprovalStep: (stepId: string, data: Record<string, unknown>) => api.patch(`/approvals/steps/${stepId}/decide`, data),
}

// Field-level access API
export const fieldAccessApi = {
  list: (module?: string) => api.get('/field-access/', { params: module ? { module } : {} }),
  create: (data: Record<string, unknown>) => api.post('/field-access/', data),
  remove: (id: string) => api.delete(`/field-access/${id}`),
}

// Notifications API
export const notificationsApi = {
  list: (limit = 20) => api.get('/notifications/', { params: { limit } }),
  unreadCount: () => api.get('/notifications/unread-count'),
  markRead: (id: string) => api.post(`/notifications/${id}/read`),
  markAllRead: () => api.post('/notifications/read-all'),
}

// Automations API
export const automationsApi = {
  list: () => api.get('/automations/'),
  create: (data: Record<string, unknown>) => api.post('/automations/', data),
  update: (id: string, data: Record<string, unknown>) => api.patch(`/automations/${id}`, data),
  remove: (id: string) => api.delete(`/automations/${id}`),
  trigger: (trigger: string, data: Record<string, unknown> = {}) => api.post(`/automations/trigger/${trigger}`, data),
  meta: () => api.get('/automations/meta').then((r: any) => r.data.data),
}

// Email marketing API
export const emailMarketingApi = {
  list: (params?: Record<string, unknown>) => api.get('/email-campaigns/', { params }),
  create: (data: Record<string, unknown>) => api.post('/email-campaigns/', data),
  update: (id: string, data: Record<string, unknown>) => api.patch(`/email-campaigns/${id}`, data),
  remove: (id: string) => api.delete(`/email-campaigns/${id}`),
  send: (id: string) => api.post(`/email-campaigns/${id}/send`),
  stats: (id: string) => api.get(`/email-campaigns/${id}/stats`),
}

// eCommerce storefront API
export const ecommerceApi = {
  categories: () => api.get('/ecommerce/storefront/categories'),
  products: (params?: Record<string, unknown>) => api.get('/ecommerce/storefront/products', { params }),
  adminProducts: (params?: Record<string, unknown>) => api.get('/ecommerce/products', { params }),
  createProduct: (data: Record<string, unknown>) => api.post('/ecommerce/products', data),
  createCategory: (data: Record<string, unknown>) => api.post('/ecommerce/categories', data),
  createCart: () => api.post('/ecommerce/cart', {}),
  addItem: (cartId: string, data: Record<string, unknown>) => api.post(`/ecommerce/cart/${cartId}/items`, data),
  getCart: (cartId: string) => api.get(`/ecommerce/cart/${cartId}`),
  checkout: (cartId: string, data: Record<string, unknown>) => api.post(`/ecommerce/cart/${cartId}/checkout`, data),
  orders: () => api.get('/ecommerce/orders'),
  // eCommerce 2.0
  listPromotions: () => api.get('/ecommerce/promotions'),
  createPromotion: (data: Record<string, unknown>) => api.post('/ecommerce/promotions', data),
  validatePromo: (data: Record<string, unknown>) => api.post('/ecommerce/promotions/validate', data),
  listShippingRules: () => api.get('/ecommerce/shipping-rules'),
  createShippingRule: (data: Record<string, unknown>) => api.post('/ecommerce/shipping-rules', data),
  calculateShipping: (data: Record<string, unknown>) => api.post('/ecommerce/shipping/calculate', data),
  addTracking: (orderId: string, data: Record<string, unknown>) => api.post(`/ecommerce/orders/${orderId}/tracking`, data),
  getTracking: (orderId: string) => api.get(`/ecommerce/orders/${orderId}/tracking`),
  requestReturn: (orderId: string, data: Record<string, unknown>) => api.post(`/ecommerce/orders/${orderId}/return`, data),
  listReturns: () => api.get('/ecommerce/returns'),
  approveReturn: (returnId: string, data: Record<string, unknown>) => api.post(`/ecommerce/returns/${returnId}/approve`, data),
  listContentPages: () => api.get('/ecommerce/content-pages'),
  createContentPage: (data: Record<string, unknown>) => api.post('/ecommerce/content-pages', data),
}

// E-signature API
export const signatureApi = {
  list: (params?: Record<string, unknown>) => api.get('/signature-requests/', { params }),
  create: (data: Record<string, unknown>) => api.post('/signature-requests/', data),
  resend: (id: string) => api.post(`/signature-requests/${id}/resend`),
}

// No-code Studio API
export const studioApi = {
  apps: () => api.get('/studio/apps'),
  createApp: (data: Record<string, unknown>) => api.post('/studio/apps', data),
  updateApp: (id: string, data: Record<string, unknown>) => api.patch(`/studio/apps/${id}`, data),
  removeApp: (id: string) => api.delete(`/studio/apps/${id}`),
  forms: (appId: string) => api.get(`/studio/apps/${appId}/forms`),
  createForm: (appId: string, data: Record<string, unknown>) => api.post(`/studio/apps/${appId}/forms`, data),
  removeForm: (id: string) => api.delete(`/studio/forms/${id}`),
  records: (formId: string, params?: Record<string, unknown>) => api.get(`/studio/forms/${formId}/records`, { params }),
  createRecord: (formId: string, data: Record<string, unknown>) => api.post(`/studio/forms/${formId}/records`, data),
  removeRecord: (id: string) => api.delete(`/studio/records/${id}`),
}

// Marketplace API
export const marketplaceApi = {
  apps: (params?: Record<string, unknown>) => api.get('/marketplace/apps', { params }),
  get: (id: string) => api.get(`/marketplace/apps/${id}`),
  create: (data: Record<string, unknown>) => api.post('/marketplace/apps', data),
  install: (id: string, data?: Record<string, unknown>) => api.post(`/marketplace/apps/${id}/install`, data || {}),
  uninstall: (id: string) => api.post(`/marketplace/apps/${id}/uninstall`),
  updateConfig: (id: string, data: Record<string, unknown>) => api.patch(`/marketplace/apps/${id}/config`, data),
  myApps: () => api.get('/marketplace/my-apps'),
  purchase: (id: string, data?: Record<string, unknown>) => api.post(`/marketplace/apps/${id}/purchase`, data || {}),
  trial: (id: string) => api.post(`/marketplace/apps/${id}/trial`),
  purchases: () => api.get('/marketplace/purchases'),
}

// Project resources API
export const projectResourcesApi = {
  members: (projectId: string) => api.get(`/projects/${projectId}/members`),
  addMember: (projectId: string, data: Record<string, unknown>) => api.post(`/projects/${projectId}/members`, data),
  updateMember: (id: string, data: Record<string, unknown>) => api.patch(`/projects/members/${id}`, data),
  removeMember: (id: string) => api.delete(`/projects/members/${id}`),
  timesheets: (projectId: string) => api.get(`/projects/${projectId}/timesheets`),
  addTimesheet: (projectId: string, data: Record<string, unknown>) => api.post(`/projects/${projectId}/timesheets`, data),
  removeTimesheet: (id: string) => api.delete(`/projects/timesheets/${id}`),
  billingSummary: (projectId: string) => api.get(`/projects/${projectId}/billing-summary`).then((r: any) => r.data.data),
  markBilled: (projectId: string, entryId: string) => api.post(`/projects/${projectId}/timesheets/${entryId}/mark-billed`),
  utilization: () => api.get('/projects/resources/utilization'),
}

// Field service API
export const fieldServiceApi = {
  list: (params?: Record<string, unknown>) => api.get('/helpdesk/field-service', { params }),
  create: (data: Record<string, unknown>) => api.post('/helpdesk/field-service', data),
  myJobs: () => api.get('/helpdesk/field-service/my-jobs'),
  start: (id: string) => api.post(`/helpdesk/field-service/${id}/start`),
  complete: (id: string, data: Record<string, unknown>) => api.post(`/helpdesk/field-service/${id}/complete`, data),
}

// Consolidated intercompany API
export const consolidatedApi = {
  intercompany: (params?: Record<string, unknown>) => api.get('/gl/consolidated/intercompany-balances', { params }),
}

// Maintenance & Repairs API
export const maintenanceApi = {
  plans: (params?: Record<string, unknown>) => api.get('/maintenance/plans', { params }),
  createPlan: (data: Record<string, unknown>) => api.post('/maintenance/plans', data),
  updatePlan: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/plans/${id}`, data),
  orders: (params?: Record<string, unknown>) => api.get('/maintenance/orders', { params }),
  createOrder: (data: Record<string, unknown>) => api.post('/maintenance/orders', data),
  updateOrder: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/orders/${id}`, data),
  repairs: (status?: string) => api.get('/maintenance/repairs', { params: status ? { status } : {} }),
  createRepair: (data: Record<string, unknown>) => api.post('/maintenance/repairs', data),
  updateRepair: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/repairs/${id}`, data),
  deleteRepair: (id: string) => api.delete(`/maintenance/repairs/${id}`),
  // ── CMMS Phase 1 ──
  assets: (params?: Record<string, unknown>) => api.get('/maintenance/assets', { params }),
  createAsset: (data: Record<string, unknown>) => api.post('/maintenance/assets', data),
  updateAsset: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/assets/${id}`, data),
  deleteAsset: (id: string) => api.delete(`/maintenance/assets/${id}`),
  assetCategories: () => api.get('/maintenance/asset-categories'),
  createAssetCategory: (data: Record<string, unknown>) => api.post('/maintenance/asset-categories', data),
  locations: () => api.get('/maintenance/locations'),
  createLocation: (data: Record<string, unknown>) => api.post('/maintenance/locations', data),
  meters: (params?: Record<string, unknown>) => api.get('/maintenance/meters', { params }),
  createMeter: (data: Record<string, unknown>) => api.post('/maintenance/meters', data),
  updateMeter: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/meters/${id}`, data),
  requests: (params?: Record<string, unknown>) => api.get('/maintenance/requests', { params }),
  createRequest: (data: Record<string, unknown>) => api.post('/maintenance/requests', data),
  updateRequest: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/requests/${id}`, data),
  // ── CMMS Phase 2: resources ──
  technicians: () => api.get('/maintenance/technicians'),
  createTechnician: (data: Record<string, unknown>) => api.post('/maintenance/technicians', data),
  updateTechnician: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/technicians/${id}`, data),
  teams: () => api.get('/maintenance/teams'),
  createTeam: (data: Record<string, unknown>) => api.post('/maintenance/teams', data),
  addTeamMember: (teamId: string, technicianId: string) => api.post(`/maintenance/teams/${teamId}/members?technician_id=${technicianId}`),
  removeTeamMember: (teamId: string, technicianId: string) => api.delete(`/maintenance/teams/${teamId}/members/${technicianId}`),
  contractors: () => api.get('/maintenance/contractors'),
  createContractor: (data: Record<string, unknown>) => api.post('/maintenance/contractors', data),
  updateContractor: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/contractors/${id}`, data),
  slas: () => api.get('/maintenance/slas'),
  createSla: (data: Record<string, unknown>) => api.post('/maintenance/slas', data),
  updateSla: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/slas/${id}`, data),
  certificates: () => api.get('/maintenance/certificates'),
  createCertificate: (data: Record<string, unknown>) => api.post('/maintenance/certificates', data),
  // Phase 3: parts & tools
  parts: (params?: Record<string, unknown>) => api.get('/maintenance/parts', { params }),
  createPart: (data: Record<string, unknown>) => api.post('/maintenance/parts', data),
  updatePart: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/parts/${id}`, data),
  partRequests: (params?: Record<string, unknown>) => api.get('/maintenance/part-requests', { params }),
  createPartRequest: (data: Record<string, unknown>) => api.post('/maintenance/part-requests', data),
  updatePartRequest: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/part-requests/${id}`, data),
  tools: () => api.get('/maintenance/tools'),
  createTool: (data: Record<string, unknown>) => api.post('/maintenance/tools', data),
  updateTool: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/tools/${id}`, data),
  toolIssues: (params?: Record<string, unknown>) => api.get('/maintenance/tool-issues', { params }),
  issueTool: (data: Record<string, unknown>) => api.post('/maintenance/tool-issues', data),
  returnTool: (id: string) => api.post(`/maintenance/tool-issues/${id}/return`),
  // Phase 4: planning & safety
  safetyInstructions: () => api.get('/maintenance/safety-instructions'),
  createSafetyInstruction: (data: Record<string, unknown>) => api.post('/maintenance/safety-instructions', data),
  workPermits: (params?: Record<string, unknown>) => api.get('/maintenance/work-permits', { params }),
  createWorkPermit: (data: Record<string, unknown>) => api.post('/maintenance/work-permits', data),
  updateWorkPermit: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/work-permits/${id}`, data),
  checklists: () => api.get('/maintenance/checklists'),
  createChecklist: (data: Record<string, unknown>) => api.post('/maintenance/checklists', data),
  incidents: (params?: Record<string, unknown>) => api.get('/maintenance/incidents', { params }),
  createIncident: (data: Record<string, unknown>) => api.post('/maintenance/incidents', data),
  updateIncident: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/incidents/${id}`, data),
  // Phase 5: costs & analytics
  costRecords: (params?: Record<string, unknown>) => api.get('/maintenance/cost-records', { params }),
  createCostRecord: (data: Record<string, unknown>) => api.post('/maintenance/cost-records', data),
  budgets: () => api.get('/maintenance/budgets'),
  createBudget: (data: Record<string, unknown>) => api.post('/maintenance/budgets', data),
  reliabilityMetrics: (params?: Record<string, unknown>) => api.get('/maintenance/reliability-metrics', { params }),
  createReliabilityMetric: (data: Record<string, unknown>) => api.post('/maintenance/reliability-metrics', data),
  analyticsSummary: () => api.get('/maintenance/analytics/summary'),
  // Phase 6: configuration
  workTypes: () => api.get('/maintenance/config/work-types'),
  createWorkType: (data: Record<string, unknown>) => api.post('/maintenance/config/work-types', data),
  priorities: () => api.get('/maintenance/config/priorities'),
  createPriority: (data: Record<string, unknown>) => api.post('/maintenance/config/priorities', data),
  statusConfigs: () => api.get('/maintenance/config/statuses'),
  createStatusConfig: (data: Record<string, unknown>) => api.post('/maintenance/config/statuses', data),
  numberingConfigs: () => api.get('/maintenance/config/numbering'),
  createNumberingConfig: (data: Record<string, unknown>) => api.post('/maintenance/config/numbering', data),
  // P1 audit: edit & delete support
  deletePlan: (id: string) => api.delete(`/maintenance/plans/${id}`),
  deleteOrder: (id: string) => api.delete(`/maintenance/orders/${id}`),
  deleteRequest: (id: string) => api.delete(`/maintenance/requests/${id}`),
  deleteMeter: (id: string) => api.delete(`/maintenance/meters/${id}`),
  deleteTechnician: (id: string) => api.delete(`/maintenance/technicians/${id}`),
  deleteContractor: (id: string) => api.delete(`/maintenance/contractors/${id}`),
  deleteSla: (id: string) => api.delete(`/maintenance/slas/${id}`),
  deletePart: (id: string) => api.delete(`/maintenance/parts/${id}`),
  deletePartRequest: (id: string) => api.delete(`/maintenance/part-requests/${id}`),
  deleteTool: (id: string) => api.delete(`/maintenance/tools/${id}`),
  deleteToolIssue: (id: string) => api.delete(`/maintenance/tool-issues/${id}`),
  updateAssetCategory: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/asset-categories/${id}`, data),
  deleteAssetCategory: (id: string) => api.delete(`/maintenance/asset-categories/${id}`),
  updateLocation: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/locations/${id}`, data),
  deleteLocation: (id: string) => api.delete(`/maintenance/locations/${id}`),
  updateBudget: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/budgets/${id}`, data),
  deleteBudget: (id: string) => api.delete(`/maintenance/budgets/${id}`),
  updateCertificate: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/certificates/${id}`, data),
  deleteCertificate: (id: string) => api.delete(`/maintenance/certificates/${id}`),
  updateChecklist: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/checklists/${id}`, data),
  deleteChecklist: (id: string) => api.delete(`/maintenance/checklists/${id}`),
  updateCostRecord: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/cost-records/${id}`, data),
  deleteCostRecord: (id: string) => api.delete(`/maintenance/cost-records/${id}`),
  updateSafetyInstruction: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/safety-instructions/${id}`, data),
  deleteSafetyInstruction: (id: string) => api.delete(`/maintenance/safety-instructions/${id}`),
  updateReliabilityMetric: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/reliability-metrics/${id}`, data),
  deleteReliabilityMetric: (id: string) => api.delete(`/maintenance/reliability-metrics/${id}`),
  updateWorkType: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/config/work-types/${id}`, data),
  deleteWorkType: (id: string) => api.delete(`/maintenance/config/work-types/${id}`),
  updatePriority: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/config/priorities/${id}`, data),
  deletePriority: (id: string) => api.delete(`/maintenance/config/priorities/${id}`),
  updateStatusConfig: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/config/statuses/${id}`, data),
  deleteStatusConfig: (id: string) => api.delete(`/maintenance/config/statuses/${id}`),
  updateNumberingConfig: (id: string, data: Record<string, unknown>) => api.patch(`/maintenance/config/numbering/${id}`, data),
  deleteNumberingConfig: (id: string) => api.delete(`/maintenance/config/numbering/${id}`),
  // ── CMMS 2.1: plan triggers, photos, signatures, reminders ──
  evaluatePlan: (id: string) => api.post(`/maintenance/plans/${id}/evaluate`),
  generateOrderFromPlan: (id: string) => api.post(`/maintenance/plans/${id}/generate-order`),
  planParts: (id: string) => api.get(`/maintenance/plans/${id}/parts`),
  addPlanPart: (id: string, data: Record<string, unknown>) => api.post(`/maintenance/plans/${id}/parts`, data),
  orderPhotos: (id: string) => api.get(`/maintenance/orders/${id}/photos`),
  addOrderPhoto: (id: string, data: Record<string, unknown>) => api.post(`/maintenance/orders/${id}/photos`, data),
  orderSignature: (id: string) => api.get(`/maintenance/orders/${id}/signature`),
  saveOrderSignature: (id: string, data: Record<string, unknown>) => api.post(`/maintenance/orders/${id}/signature`, data),
  reminders: (pendingOnly: boolean = true) => api.get('/maintenance/reminders', { params: { pending_only: pendingOnly } }),
}

// PLM API
export const plmApi = {
  versions: (productId: string) => api.get(`/plm/products/${productId}/versions`),
  createVersion: (productId: string, data: Record<string, unknown>) => api.post(`/plm/products/${productId}/versions`, data),
  lifecycle: (productId: string) => api.get(`/plm/products/${productId}/lifecycle`),
  setLifecycle: (productId: string, data: Record<string, unknown>) => api.put(`/plm/products/${productId}/lifecycle`, data),
  engineeringChanges: (status?: string) => api.get('/plm/engineering-changes', { params: status ? { status } : {} }),
  createEco: (data: Record<string, unknown>) => api.post('/plm/engineering-changes', data),
  updateEco: (id: string, data: Record<string, unknown>) => api.patch(`/plm/engineering-changes/${id}`, data),
}

// Quality Control API
export const qualityApi = {
  checks: (params?: Record<string, unknown>) => api.get('/quality-control/', { params }),
  createCheck: (data: Record<string, unknown>) => api.post('/quality-control/', data),
  controlPoints: () => api.get('/quality-control/control-points'),
  createControlPoint: (data: Record<string, unknown>) => api.post('/quality-control/control-points', data),
  tests: (cpId: string) => api.get(`/quality-control/control-points/${cpId}/tests`),
  createTest: (cpId: string, data: Record<string, unknown>) => api.post(`/quality-control/control-points/${cpId}/tests`, data),
  recordResult: (checkId: string, data: Record<string, unknown>) => api.post(`/quality-control/checks/${checkId}/results`, data),
  alerts: (status?: string) => api.get('/quality-control/alerts', { params: status ? { status } : {} }),
  createAlert: (data: Record<string, unknown>) => api.post('/quality-control/alerts', data),
  resolveAlert: (id: string, data: Record<string, unknown>) => api.post(`/quality-control/alerts/${id}/resolve`, data),
  scan: (barcode: string) => api.post('/quality-control/scan', { barcode }),
}

// Accounting controls API
export const accountingControlsApi = {
  fiscalPositions: () => api.get('/accounting-controls/fiscal-positions'),
  createFiscalPosition: (data: Record<string, unknown>) => api.post('/accounting-controls/fiscal-positions', data),
  mappings: () => api.get('/accounting-controls/consolidation-mappings'),
  createMapping: (data: Record<string, unknown>) => api.post('/accounting-controls/consolidation-mappings', data),
  fxRates: (target_currency?: string) => api.get('/accounting-controls/fx-rates', { params: target_currency ? { target_currency } : {} }),
  createFxRate: (data: Record<string, unknown>) => api.post('/accounting-controls/fx-rates', data),
}

// Dashboard API
export const dashboardApi = {
  getSummary: (period: string = '30d', ownerId?: string, warehouseId?: string) =>
    api.get('/dashboard/summary', { params: { period, ...(ownerId ? { owner_id: ownerId } : {}), ...(warehouseId ? { warehouse_id: warehouseId } : {}) } }),
  getAging: () => api.get('/dashboard/aging'),
  getCashFlow: () => api.get('/dashboard/cash-flow'),
  getDrillDown: (entity: 'ar' | 'ap', bucket: string = 'all') =>
    api.get(`/dashboard/drill-down/${entity}`, { params: { bucket } }),
  getRoleViews: () => api.get('/dashboard/role-views'),
  getKpiDefinitions: () => api.get('/dashboard/kpi-definitions'),
  getKpiDrillDown: (kpiKey: string, limit?: number) =>
    api.get(`/dashboard/kpi-detail/${kpiKey}`, { params: { limit } }),
  getLayout: () => api.get('/dashboard/layout'),
  putLayout: (layouts: Record<string, string[]>) => api.put('/dashboard/layout', { layouts }),
  getMetrics: (params: { from_date?: string; to_date?: string; warehouse_id?: string; branch_id?: string; team_id?: string } = {}) =>
    api.get('/dashboard/metrics', { params }),
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
  // Invoice 2.0
  createNote: (id: string, data: any) => api.post(`/invoices/${id}/notes`, data),
  listNotes: (id: string) => api.get(`/invoices/${id}/notes`),
  reverse: (id: string, data: any) => api.post(`/invoices/${id}/reversal`, data),
  setRecurring: (id: string, data: any) => api.post(`/invoices/${id}/recurring`, data),
  createInstallments: (id: string, data: any) => api.post(`/invoices/${id}/installments`, data),
  listInstallments: (id: string) => api.get(`/invoices/${id}/installments`),
  allocate: (id: string, data: any) => api.post(`/invoices/${id}/allocate`, data),
  syncFiscalStatus: (id: string, data: any) => api.patch(`/invoices/${id}/fiscal-status`, data),
}

// Suppliers API
export const suppliersApi = {
  list: (params?: { page?: number; page_size?: number; search?: string; include_inactive?: boolean; category?: string }) =>
    api.get('/suppliers/', { params }),
  get: (id: string) => api.get(`/suppliers/${id}`),
  create: (data: any) => api.post('/suppliers/', data),
  update: (id: string, data: any) => api.patch(`/suppliers/${id}`, data),
  archive: (id: string) => api.post(`/suppliers/${id}/archive`),
  // Supplier 2.0
  startOnboarding: (id: string) => api.post(`/suppliers/${id}/onboarding/start`),
  getOnboarding: (id: string) => api.get(`/suppliers/${id}/onboarding`),
  completeOnboardingStep: (id: string, stepId: string) => api.post(`/suppliers/${id}/onboarding/${stepId}/complete`),
  setRisk: (id: string, data: any) => api.post(`/suppliers/${id}/risk`, data),
  listRiskEvents: (id: string) => api.get(`/suppliers/${id}/risk-events`),
  upsertCurrencyTerm: (id: string, data: any) => api.post(`/suppliers/${id}/currency-terms`, data),
  listCurrencyTerms: (id: string) => api.get(`/suppliers/${id}/currency-terms`),
  approveBankDetail: (bankDetailId: string) => api.post(`/suppliers/bank-details/${bankDetailId}/approve`),
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
  qualityCheck: (poId: string, receiptId: string, data: any) =>
    api.post(`/purchase-orders/${poId}/receipts/${receiptId}/quality-check`, data),
  threeWayMatch: (id: string) => api.get(`/purchase-orders/${id}/three-way-match`),
  // PO 2.0
  createSupplierInvoice: (poId: string) => api.post(`/purchase-orders/${poId}/create-supplier-invoice`),
  listScheduledDeliveries: (poId: string) => api.get(`/purchase-orders/${poId}/scheduled-deliveries`),
  createScheduledDelivery: (poId: string, data: any) => api.post(`/purchase-orders/${poId}/scheduled-deliveries`, data),
  getBackorder: (poId: string) => api.get(`/purchase-orders/${poId}/backorder`),
  listReturns: (poId: string) => api.get(`/purchase-orders/${poId}/returns`),
  createReturn: (poId: string, data: any) => api.post(`/purchase-orders/${poId}/returns`, data),
  listAmendments: (poId: string) => api.get(`/purchase-orders/${poId}/amendments`),
  createAmendment: (poId: string, data: any) => api.post(`/purchase-orders/${poId}/amendments`, data),
  approveAmendment: (amendmentId: string) => api.post(`/purchase-orders/amendments/${amendmentId}/approve`),
  listLandedCosts: (poId: string) => api.get(`/purchase-orders/${poId}/landed-costs`),
  validatePrices: (poId: string) => api.post(`/purchase-orders/${poId}/validate-prices`),
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
  // Bank connections (TBC/BOG/Liberty) + file import
  connections: () => api.get('/connections'),
  createConnection: (data: { bank: string; name: string; account_number: string; client_id?: string; client_secret?: string }) =>
    api.post('/connections', data),
  importFile: (connectionId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/connections/${connectionId}/import-file`, form)
  },
  // Reconciliation suggestions (Odoo-style matching with confidence)
  suggestions: (params?: { bank_account_id?: string; limit?: number }) =>
    api.get('/reconciliation-suggestions', { params }),
  batchApprove: (items: Array<{ transaction_id: string; kind: string; candidate_id: string; amount: number }>) =>
    api.post('/bank-reconciliations/batch-approve', { items }),
}

// Inventory valuation API
export const inventoryValuationApi = {
  get: (productId: string) => api.get(`/inventory/valuation/${productId}`),
  adjust: (data: { product_id: string; quantity: number; unit_cost: number; note?: string }) =>
    api.post('/inventory/valuation/adjust', data),
  summary: () => api.get('/inventory/valuation/summary'),
  methods: () => api.get('/inventory/valuation/methods'),
  setMethod: (data: { product_id: string; method: 'standard' | 'avco' | 'fifo'; standard_cost?: number }) =>
    api.post('/inventory/valuation/methods', data),
  // Inventory Valuation 2.0
  setNegativeStock: (data: any) => api.post('/inventory/valuation/methods/negative-stock', data),
  applyLandedCost: (landedCostId: string) => api.post('/inventory/valuation/apply-landed-cost', { landed_cost_id: landedCostId }),
  applyProductionCost: (data: any) => api.post('/inventory/valuation/apply-production-cost', data),
  adjustToGl: (data: any) => api.post('/inventory/valuation/adjust-to-gl', data),
  listReconciliations: () => api.get('/inventory/valuation/reconciliations'),
  createReconciliation: (data: any) => api.post('/inventory/valuation/reconciliations', data),
  postReconciliation: (id: string) => api.post(`/inventory/valuation/reconciliations/${id}/post`),
  listLocationValuations: () => api.get('/inventory/valuation/locations'),
  upsertLocationValuation: (data: any) => api.post('/inventory/valuation/locations', data),
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
  consolidatedChecks: (params?: { as_of_date?: string }) => api.get('/gl/consolidated/checks', { params }),
  consolidatedProfitLoss: (params?: { date_from?: string; date_to?: string }) =>
    api.get('/gl/consolidated/profit-loss', { params }),
  consolidatedBalanceSheet: (params?: { as_of_date?: string }) =>
    api.get('/gl/consolidated/balance-sheet', { params }),
  consolidationEliminations: () => api.get('/gl/consolidation-eliminations/'),
  createConsolidationElimination: (data: Record<string, unknown>) => api.post('/gl/consolidation-eliminations/', data),
  approveConsolidationElimination: (id: string) => api.post(`/gl/consolidation-eliminations/${id}/approve`),
  reverseConsolidationElimination: (id: string) => api.post(`/gl/consolidation-eliminations/${id}/reverse`),
  autoDetectConsolidationEliminations: (params?: { date_from?: string; date_to?: string }) =>
    api.post('/gl/consolidation-eliminations/auto-detect', null, { params }),
  autoDetectConsolidationPurchases: (params?: { date_from?: string; date_to?: string }) =>
    api.post('/gl/consolidation-eliminations/auto-detect-purchases', null, { params }),
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
  // Quotation 2.0
  updateQuotation: (id: string, data: Record<string, unknown>) => api.put(`/quotations/${id}`, data),
  listQuotationVersions: (id: string) => api.get(`/quotations/${id}/versions`),
  requestApproval: (id: string) => api.post(`/quotations/${id}/approval`),
  signQuotation: (id: string, data: Record<string, unknown>) => api.post(`/quotations/${id}/sign`, data),
  generatePortalToken: (id: string) => api.post(`/quotations/${id}/portal-token`),
  listPriceLists: (params?: Record<string, unknown>) => api.get('/price-lists/', { params }),
  createPriceList: (data: Record<string, unknown>) => api.post('/price-lists/', data),
  updatePriceList: (id: string, data: Record<string, unknown>) => api.patch(`/price-lists/${id}`, data),
  deletePriceList: (id: string) => api.delete(`/price-lists/${id}`),
  resolvePrice: (params: Record<string, unknown>) => api.get('/price-lists/resolve', { params }),
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
  approveCommission: (id: string, data: Record<string, unknown>) => api.post(`/sales/commissions/${id}/approve`, data),
  adjustCommission: (id: string, data: Record<string, unknown>) => api.post(`/sales/commissions/${id}/adjust`, data),
  linkCommissionToPayslip: (id: string, data: Record<string, unknown>) => api.post(`/sales/commissions/${id}/link-payslip`, data),
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
  // Subscriptions 2.0
  listPlans: (params?: Record<string, unknown>) => api.get('/subscriptions/plans/', { params }),
  createPlan: (data: Record<string, unknown>) => api.post('/subscriptions/plans/', data),
  runBilling: () => api.post('/subscriptions/billing/run'),
  retryBilling: (id: string) => api.post(`/subscriptions/${id}/retry`),
  pauseSubscription: (id: string, data: Record<string, unknown>) => api.post(`/subscriptions/${id}/pause`, data),
  resumeSubscription: (id: string, data: Record<string, unknown>) => api.post(`/subscriptions/${id}/resume`, data),
  cancelSubscription: (id: string, data: Record<string, unknown>) => api.post(`/subscriptions/${id}/cancel`, data),
  changePlan: (id: string, data: Record<string, unknown>) => api.post(`/subscriptions/${id}/change-plan`, data),
  subscriptionAnalytics: () => api.get('/subscriptions/analytics/overview'),
  listPortalUsers: (params?: Record<string, unknown>) => api.get('/customer-portal/', { params }),
  createPortalUser: (data: Record<string, unknown>) => api.post('/customer-portal/', data),
  updatePortalUser: (id: string, data: Record<string, unknown>) => api.patch(`/customer-portal/${id}`, data),
  deletePortalUser: (id: string) => api.delete(`/customer-portal/${id}`),
  portalSummary: (clientId: string) => api.get(`/customer-portal/clients/${clientId}/summary`),
}

// Vendor Portal API — supplier self-service users + summary
export const vendorPortalApi = {
  list: (params?: Record<string, unknown>) => api.get('/vendor-portal/', { params }),
  create: (data: Record<string, unknown>) => api.post('/vendor-portal/', data),
  update: (id: string, data: Record<string, unknown>) => api.patch(`/vendor-portal/${id}`, data),
  remove: (id: string) => api.delete(`/vendor-portal/${id}`),
  supplierSummary: (supplierId: string) => api.get(`/vendor-portal/suppliers/${supplierId}/summary`),
}

// Vendor Auth API — supplier self-service login + dashboard
export const vendorAuthApi = {
  login: (data: { email: string; password: string }) => api.post('/vendor-auth/login', data),
  me: (token: string) => api.get('/vendor-auth/me', { params: { token } }),
  dashboard: (token: string) => api.get('/vendor-auth/dashboard', { params: { token } }),
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
  // Warehouse/WMS 2.0
  listUoms: () => api.get('/wms-ops/uoms'),
  createUom: (data: any) => api.post('/wms-ops/uoms', data),
  listUomConversions: () => api.get('/wms-ops/uom-conversions'),
  createUomConversion: (data: any) => api.post('/wms-ops/uom-conversions', data),
  convertUom: (data: any) => api.post('/wms-ops/uom/convert', data),
  listReorderRules: () => api.get('/wms-ops/reorder-rules'),
  upsertReorderRule: (data: any) => api.post('/wms-ops/reorder-rules', data),
  reorderSuggestions: () => api.get('/wms-ops/reorder/suggestions'),
  listPutawayStrategies: () => api.get('/wms-ops/putaway-strategies'),
  createPutawayStrategy: (data: any) => api.post('/wms-ops/putaway-strategies', data),
  suggestPutaway: (data: any) => api.post('/wms-ops/putaway/suggest', data),
  listCycleCountSchedules: () => api.get('/wms-ops/cycle-count-schedules'),
  createCycleCountSchedule: (data: any) => api.post('/wms-ops/cycle-count-schedules', data),
  listConsignmentStock: () => api.get('/wms-ops/consignment-stock'),
  upsertConsignmentStock: (data: any) => api.post('/wms-ops/consignment-stock', data),
  stockAging: () => api.get('/wms-ops/stock-aging'),
  expiryAlerts: (days?: number) => api.get('/wms-ops/expiry-alerts', { params: days ? { days } : {} }),
  listAbcXyz: () => api.get('/wms-ops/abc-xyz'),
  setAbcXyz: (data: any) => api.post('/wms-ops/abc-xyz', data),
  listWaves: () => api.get('/wms-ops/waves'),
  createWave: (data: any) => api.post('/wms-ops/waves', data),
  completeWave: (id: string) => api.post(`/wms-ops/waves/${id}/complete`),
  listCrossDockOrders: () => api.get('/wms-ops/cross-dock-orders'),
  createCrossDockOrder: (data: any) => api.post('/wms-ops/cross-dock-orders', data),
  listShipments: () => api.get('/wms-ops/shipments'),
  createShipment: (data: any) => api.post('/wms-ops/shipments', data),
  shipShipment: (id: string) => api.post(`/wms-ops/shipments/${id}/ship`),
  listLotZoneBalances: () => api.get('/wms-ops/lot-zone-balances'),
  upsertLotZoneBalance: (data: any) => api.post('/wms-ops/lot-zone-balances', data),
  parseGs1: (barcode: string) => api.post('/wms-ops/gs1/parse', { barcode }),
}

// Procurement API — RFQ, comparison, vendor pricelists, blanket orders, scorecards
export const procurementApi = {
  listRfqs: (params?: { status?: string; limit?: number }) => api.get('/procurement/rfqs', { params }),
  createRfq: (data: Record<string, unknown>) => api.post('/procurement/rfqs', data),
  submitRfqResponse: (rfqId: string, data: Record<string, unknown>) =>
    api.post(`/procurement/rfqs/${rfqId}/responses`, data),
  rfqComparison: (rfqId: string) => api.get(`/procurement/rfqs/${rfqId}/comparison`),
  sendRfqEmail: (rfqId: string) => api.post(`/procurement/rfqs/${rfqId}/send-email`),
  awardRfq: (rfqId: string, supplierId: string) =>
    api.post(`/procurement/rfqs/${rfqId}/award`, null, { params: { supplier_id: supplierId } }),
  listPriceLists: (params?: { supplier_id?: string; product_id?: string }) =>
    api.get('/procurement/price-lists', { params }),
  upsertPriceList: (data: Record<string, unknown>) => api.post('/procurement/price-lists', data),
  priceTrend: (params?: { supplier_id?: string; product_id?: string; limit?: number }) =>
    api.get('/procurement/price-trend', { params }),
  listBlanketOrders: (params?: { status?: string }) => api.get('/procurement/blanket-orders', { params }),
  createBlanketOrder: (data: Record<string, unknown>) => api.post('/procurement/blanket-orders', data),
  activateBlanketOrder: (id: string) => api.post(`/procurement/blanket-orders/${id}/activate`),
  listScorecards: (params?: { supplier_id?: string }) => api.get('/procurement/scorecards', { params }),
  upsertScorecard: (data: Record<string, unknown>) => api.post('/procurement/scorecards', data),
  autoReplenish: (warehouseId?: string) =>
    api.post('/procurement/auto-replenish', null, { params: warehouseId ? { warehouse_id: warehouseId } : {} }),
  autoCalculateScorecards: (period: string) =>
    api.post('/procurement/scorecards/auto-calculate', null, { params: { period } }),
  // Procurement 2.0
  listRequisitions: (params?: Record<string, unknown>) => api.get('/procurement/requisitions', { params }),
  createRequisition: (data: Record<string, unknown>) => api.post('/procurement/requisitions', data),
  submitRequisition: (id: string) => api.post(`/procurement/requisitions/${id}/submit`),
  approveRequisition: (id: string, level: number) => api.post(`/procurement/requisitions/${id}/approve`, { level }),
  requisitionBudgetCheck: (id: string) => api.post(`/procurement/requisitions/${id}/budget-check`),
  createPoFromRfq: (rfqId: string, data: Record<string, unknown>) => api.post(`/procurement/rfqs/${rfqId}/create-po`, data),
  listSupplierProducts: (params?: Record<string, unknown>) => api.get('/procurement/supplier-products', { params }),
  createSupplierProduct: (data: Record<string, unknown>) => api.post('/procurement/supplier-products', data),
  autoSelectPrice: (data: Record<string, unknown>) => api.post('/procurement/price/auto-select', data),
  // Tenders
  listTenders: (params?: { status?: string; limit?: number }) => api.get('/procurement/tenders', { params }),
  createTender: (data: Record<string, unknown>) => api.post('/procurement/tenders', data),
  publishTender: (id: string) => api.post(`/procurement/tenders/${id}/publish`),
  submitTenderBid: (id: string, data: Record<string, unknown>) => api.post(`/procurement/tenders/${id}/bids`, data),
  tenderComparison: (id: string) => api.get(`/procurement/tenders/${id}/comparison`),
  awardTender: (id: string, supplierId: string) =>
    api.post(`/procurement/tenders/${id}/award`, null, { params: { supplier_id: supplierId } }),
  // Vendor analytics
  vendorAnalytics: (params?: { date_from?: string; date_to?: string }) =>
    api.get('/procurement/vendor-analytics', { params }),
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
  openSession: (data: { name: string; opening_cash?: number; register_id?: string; cashier_id?: string }) => api.post('/pos/sessions', data),
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
  updateFiscalDevice: (id: string, is_active: boolean, name?: string) =>
    api.patch(`/pos/fiscal-devices/${id}`, null, { params: { is_active, name } }),
  // Gift cards
  listGiftCards: () => api.get('/pos/gift-cards'),
  issueGiftCard: (amount: number, expires_at?: string) =>
    api.post('/pos/gift-cards', null, { params: { amount, expires_at } }),
  topUpGiftCard: (id: string, amount: number) =>
    api.post(`/pos/gift-cards/${id}/top-up`, null, { params: { amount } }),
  redeemGiftCard: (id: string, amount: number, order_id?: string) =>
    api.post(`/pos/gift-cards/${id}/redeem`, null, { params: { amount, order_id } }),
  updateGiftCard: (id: string, data: Record<string, unknown>) =>
    api.patch(`/pos/gift-cards/${id}`, null, { params: data }),
  voidGiftCard: (id: string) => api.post(`/pos/gift-cards/${id}/void`),
  // Cash register
  cashIn: (sessionId: string, amount: number, reason?: string) =>
    api.post(`/pos/sessions/${sessionId}/cash-in`, null, { params: { amount, reason } }),
  cashOut: (sessionId: string, amount: number, reason?: string) =>
    api.post(`/pos/sessions/${sessionId}/cash-out`, null, { params: { amount, reason } }),
  xReport: (sessionId: string) => api.get(`/pos/sessions/${sessionId}/x-report`),
  zReport: (sessionId: string, declared_cash?: number) =>
    api.post(`/pos/sessions/${sessionId}/z-report`, null, { params: { declared_cash } }),
  listZReports: () => api.get('/pos/z-reports'),
  // Hardware & configuration (P1.5)
  listRegisters: () => api.get('/pos/registers'),
  createRegister: (data: Record<string, unknown>) => api.post('/pos/registers', data),
  listCashiers: () => api.get('/pos/cashiers'),
  createCashier: (data: Record<string, unknown>) => api.post('/pos/cashiers', data),
  verifyCashierPin: (userId: string, pin: string) => api.post('/pos/cashiers/verify', { user_id: userId, pin }),
  listTerminals: () => api.get('/pos/terminals'),
  createTerminal: (data: Record<string, unknown>) => api.post('/pos/terminals', data),
  terminalCharge: (terminalId: string, amount: number, reference?: string) =>
    api.post(`/pos/terminals/${terminalId}/charge`, { amount, reference }),
  terminalRefund: (terminalId: string, providerRef: string, amount: number) =>
    api.post(`/pos/terminals/${terminalId}/refund`, { provider_ref: providerRef, amount }),
  terminalStatus: (terminalId: string, providerRef: string) =>
    api.get(`/pos/terminals/${terminalId}/status/${providerRef}`),
  qrPay: (amount: number) => api.post('/pos/qr/pay', { amount }),
  customerBalance: (clientId: string) => api.get(`/pos/customer-balance/${clientId}`),
  customerDeposit: (clientId: string, amount: number) =>
    api.post(`/pos/customers/${clientId}/deposit`, { amount }),
  // Restaurant
  listTables: () => api.get('/pos/tables'),
  createTable: (name: string, capacity: number) =>
    api.post('/pos/tables', null, { params: { name, capacity } }),
  occupyTable: (id: string) => api.post(`/pos/tables/${id}/occupy`),
  freeTable: (id: string) => api.post(`/pos/tables/${id}/free`),
  listOrderTypes: () => api.get('/pos/order-types'),
  createOrderType: (code: string, name: string) =>
    api.post('/pos/order-types', null, { params: { code, name } }),
  startSelfOrder: (table_id?: string) =>
    api.post('/pos/self-order/start', null, { params: { table_id } }),
  submitSelfOrder: (token: string, items: Record<string, unknown>[]) =>
    api.post(`/pos/self-order/${token}/submit`, { items }),
  emailReceipt: (orderId: string, to_email: string) =>
    api.post(`/pos/orders/${orderId}/email-receipt`, null, { params: { to_email } }),
  kitchenQueue: () => api.get('/pos/kitchen/queue'),
  setKitchenStatus: (orderId: string, status: string) =>
    api.patch(`/pos/orders/${orderId}/kitchen-status`, null, { params: { status } }),
  listCoupons: () => api.get('/pos/coupons'),
  createCoupon: (data: Record<string, unknown>) => api.post('/pos/coupons', null, { params: data }),
  validateCoupon: (code: string) => api.post('/pos/coupons/validate', null, { params: { code } }),
  escposReceipt: (orderId: string) => api.get(`/pos/orders/${orderId}/escpos`),
  printReceipt: (orderId: string, deviceId: string) =>
    api.post(`/pos/orders/${orderId}/print`, null, { params: { device_id: deviceId } }),
  fiscalJournal: () => api.get('/pos/fiscal-journal'),
  registerFiscalDevice: (data: { name: string; device_type: string; serial_number: string; ip_address?: string; port?: number }) =>
    api.post('/pos/fiscal-devices', null, { params: data }),
  setTablePosition: (id: string, pos_x: number, pos_y: number) =>
    api.patch(`/pos/tables/${id}/position`, null, { params: { pos_x, pos_y } }),
  splitBill: (orderId: string, parts: Record<string, unknown>[]) =>
    api.post(`/pos/orders/${orderId}/split`, { parts }),
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
  listTemplates: () => api.get('/projects/templates'),
  createTemplate: (data: Record<string, unknown>) => api.post('/projects/templates', data),
  instantiateTemplate: (templateId: string, data: Record<string, unknown>) =>
    api.post(`/projects/templates/${templateId}/instantiate`, data),
  removeTemplate: (templateId: string) => api.delete(`/projects/templates/${templateId}`),
}

export const payrollEngineApi = {
  structures: () => api.get('/payroll-engine/structures').then(r => r.data.data),
  createStructure: (data: Record<string, unknown>) => api.post('/payroll-engine/structures', data).then(r => r.data.data),
  deleteStructure: (id: string) => api.delete(`/payroll-engine/structures/${id}`).then(r => r.data.data),
  rules: (structureId: string) => api.get(`/payroll-engine/structures/${structureId}/rules`).then(r => r.data.data),
  createRule: (structureId: string, data: Record<string, unknown>) => api.post(`/payroll-engine/structures/${structureId}/rules`, data).then(r => r.data.data),
  deleteRule: (id: string) => api.delete(`/payroll-engine/rules/${id}`).then(r => r.data.data),
  parameters: () => api.get('/payroll-engine/parameters').then(r => r.data.data),
  setParameter: (data: Record<string, unknown>) => api.post('/payroll-engine/parameters', data).then(r => r.data.data),
  workEntries: (params?: Record<string, unknown>) => api.get('/payroll-engine/work-entries', { params }).then(r => r.data.data),
  createWorkEntry: (data: Record<string, unknown>) => api.post('/payroll-engine/work-entries', data).then(r => r.data.data),
  calculate: (data: Record<string, unknown>) => api.post('/payroll-engine/calculate', data).then(r => r.data.data),
  entryLines: (entryId: string) => api.get(`/payroll-engine/entries/${entryId}/lines`).then(r => r.data.data),
  adjustments: (params?: Record<string, unknown>) => api.get('/payroll-engine/adjustments', { params }).then(r => r.data.data),
  createAdjustment: (data: Record<string, unknown>) => api.post('/payroll-engine/adjustments', data).then(r => r.data.data),
  deleteAdjustment: (id: string) => api.delete(`/payroll-engine/adjustments/${id}`).then(r => r.data.data),
}
