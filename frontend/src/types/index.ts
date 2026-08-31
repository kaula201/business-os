// Business OS — Shared TypeScript Interfaces

// === Common ===
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ApiResponse<T> {
  data: T
  message?: string
}

// === Auth ===
export interface User {
  id: string
  company_id: string
  email: string
  full_name: string
  role: 'admin' | 'manager' | 'employee' | 'accountant'
  is_active: boolean
  last_login?: string
  created_at: string
}

export interface AuthData {
  user: User
  access_token: string
  refresh_token: string
}

export interface LoginInput {
  email: string
  password: string
}

export interface RegisterInput {
  company_name: string
  full_name: string
  email: string
  password: string
}

// === Company ===
export interface Company {
  id: string
  name: string
  identification_code: string
  address: string
  phone: string
  email: string
  website: string
  is_vat_payer: boolean
  currency: string
  logo_url?: string
}

// === Client ===
export interface Client {
  id: string
  company_id: string
  name: string
  client_type: 'legal' | 'individual'
  identification_code: string
  is_vat_payer: boolean
  status: 'potential' | 'active' | 'inactive'
  address?: string
  phone?: string
  email?: string
  notes?: string
  created_by?: string
  created_at: string
  updated_at: string
}

export interface ClientCreate {
  name: string
  client_type: 'legal' | 'individual'
  identification_code: string
  is_vat_payer?: boolean
  address?: string
  phone?: string
  email?: string
  notes?: string
}

// === CRM — Leads, pipeline and activities ===
export type CRMLeadStatus = 'new' | 'contacted' | 'qualified' | 'unqualified' | 'converted'
export type CRMLeadSource = 'website' | 'referral' | 'campaign' | 'phone' | 'email' | 'other'
export type CRMOpportunityStage = string
export type CRMActivityType = 'call' | 'meeting' | 'email' | 'task' | 'note'
export type CRMActivityStatus = 'planned' | 'completed' | 'cancelled'

export interface CRMPipelineStage {
  id: string
  company_id: string
  key: string
  name: string
  probability: number
  color: string
  sort_order: number
  is_won: boolean
  is_lost: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CRMLead {
  id: string
  company_id: string
  owner_id?: string
  team_id?: string
  converted_client_id?: string
  company_name: string
  contact_name?: string
  email?: string
  phone?: string
  source: CRMLeadSource
  status: CRMLeadStatus
  estimated_value: number
  score: number
  notes?: string
  converted_at?: string
  created_at: string
  updated_at: string
}

export interface CRMLeadCreate {
  company_name: string
  contact_name?: string
  email?: string
  phone?: string
  source: CRMLeadSource
  estimated_value: number
  notes?: string
  owner_id?: string
  team_id?: string
}

export interface CRMOpportunity {
  id: string
  company_id: string
  lead_id?: string
  client_id?: string
  owner_id?: string
  team_id?: string
  name: string
  stage: CRMOpportunityStage
  amount: number
  probability: number
  expected_close_date?: string
  lost_reason?: string
  notes?: string
  lead_company_name?: string
  created_at: string
  updated_at: string
}

export interface CRMActivity {
  id: string
  company_id: string
  lead_id?: string
  opportunity_id?: string
  client_id?: string
  assigned_to?: string
  created_by: string
  activity_type: CRMActivityType
  subject: string
  description?: string
  status: CRMActivityStatus
  due_at?: string
  completed_at?: string
  related_name?: string
  created_at: string
  updated_at: string
}

export interface CRMLeadConvert {
  client_type: 'legal' | 'individual'
  identification_code: string
  is_vat_payer: boolean
  name?: string
  address?: string
  notes?: string
}

// === Order ===
export type OrderStatus = 'new' | 'confirmed' | 'preparing' | 'shipping' | 'completed' | 'cancelled' | 'returned'

export interface OrderSummary {
  id: string
  order_number: string
  client_name?: string
  status: OrderStatus
  total: number
  assigned_to_name?: string
  created_at: string
}

export interface Order {
  id: string
  company_id: string
  client_id: string
  client_name?: string
  order_number: string
  status: OrderStatus
  subtotal: number
  vat_amount: number
  total: number
  delivery_date?: string
  delivery_address?: string
  notes?: string
  assigned_to?: string
  assigned_to_name?: string
  created_by?: string
  warehouse_id?: string
  warehouse_name?: string
  reservation_status?: 'active' | 'released' | 'consumed' | 'returned'
  items: OrderItem[]
  created_at: string
  updated_at: string
}

export interface OrderItem {
  id: string
  product_id?: string
  product_name: string
  quantity: number
  unit_price: number
  discount_percent: number
  total: number
}

export interface OrderCreate {
  client_id: string
  warehouse_id?: string
  items: { product_id?: string; product_name: string; quantity: number; unit_price: number; discount_percent?: number }[]
  delivery_date?: string
  delivery_address?: string
  notes?: string
  assigned_to?: string
  is_vat_payer?: boolean
}

export interface OrderStatusHistory {
  id: string
  status: OrderStatus
  notes?: string
  changed_by?: string
  changed_by_name?: string
  created_at: string
}

export interface InventoryReservation {
  id: string
  product_id: string
  product_name: string
  warehouse_id: string
  warehouse_name: string
  quantity: number
  status: 'active' | 'released' | 'consumed' | 'returned'
  available_after_reservation: number
}

export interface CustomerInvoiceItem {
  id: string
  order_item_id?: string
  product_id?: string
  line_number: number
  product_name: string
  quantity: number
  unit_price: number
  discount_percent: number
  line_subtotal: number
  vat_rate: number
  vat_amount: number
  line_total: number
}

export interface CustomerInvoiceSummary {
  id: string
  order_id: string
  invoice_number: string
  status: 'draft' | 'issued' | 'cancelled'
  invoice_date: string
  due_date: string
  currency: string
  total: number
  order_number: string
  client_name: string
  client_identification_code: string
  download_url: string
  created_at: string
}

export interface CustomerInvoice extends CustomerInvoiceSummary {
  company_id: string
  client_id: string
  subtotal: number
  vat_amount: number
  seller_name: string
  seller_identification_code: string
  seller_address: string
  seller_phone: string
  seller_email: string
  client_address: string
  notes?: string
  items: CustomerInvoiceItem[]
  updated_at: string
}

export interface CustomerInvoiceGenerate {
  order_id: string
  idempotency_key: string
  invoice_date: string
  due_date: string
  notes?: string
}

export interface CustomerInvoiceDraftUpdate {
  invoice_date: string
  due_date: string
  currency: string
  seller_name: string
  seller_identification_code: string
  seller_address: string
  seller_phone: string
  seller_email: string
  client_name: string
  client_identification_code: string
  client_address: string
  notes?: string
  items: {
    product_name: string
    quantity: number
    unit_price: number
    discount_percent: number
    vat_rate: number
  }[]
}

// === Suppliers & purchasing ===
export interface Supplier {
  id: string
  code: string
  name: string
  identification_code?: string
  is_vat_payer: boolean
  contact_name?: string
  phone?: string
  email?: string
  address?: string
  bank_account?: string
  payment_terms_days: number
  notes?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SupplierCreate {
  code: string
  name: string
  identification_code?: string
  is_vat_payer?: boolean
  contact_name?: string
  phone?: string
  email?: string
  address?: string
  bank_account?: string
  payment_terms_days?: number
  notes?: string
}

export type PurchaseOrderStatus = 'draft' | 'approved' | 'partially_received' | 'received' | 'cancelled'

export interface PurchaseOrderItem {
  id: string
  product_id: string
  product_name: string
  quantity: number
  received_quantity: number
  remaining_quantity: number
  unit_price: number
  discount_percent: number
  vat_rate: number
  line_subtotal: number
  vat_amount: number
  line_total: number
}

export interface PurchaseOrder {
  id: string
  supplier_id: string
  supplier_name: string
  warehouse_id: string
  warehouse_name: string
  purchase_order_number: string
  status: PurchaseOrderStatus
  expected_delivery_date?: string
  subtotal: number
  vat_amount: number
  total: number
  notes?: string
  approved_at?: string
  approved_by?: string
  required_approval_role: 'manager' | 'admin'
  items: PurchaseOrderItem[]
  created_at: string
  updated_at: string
}

export interface PurchaseOrderCreate {
  supplier_id: string
  warehouse_id: string
  expected_delivery_date?: string
  notes?: string
  items: {
    product_id: string
    quantity: number
    unit_price: number
    discount_percent: number
    vat_rate: number
  }[]
}

export interface PurchaseOrderHistory {
  id: string
  status: PurchaseOrderStatus
  notes?: string
  changed_by?: string
  created_at: string
}

export interface GoodsReceipt {
  id: string
  purchase_order_id: string
  receipt_number: string
  warehouse_id: string
  warehouse_name: string
  idempotency_key: string
  status: 'posted'
  purchase_order_status: PurchaseOrderStatus
  notes?: string
  received_at: string
  quality_status?: string | null
  quality_notes?: string | null
  items: {
    id: string
    purchase_order_item_id: string
    product_id: string
    product_name: string
    quantity: number
  }[]
}

export type SupplierInvoiceStatus = 'draft' | 'approved' | 'cancelled'
export type SupplierInvoiceMatchingStatus = 'matched' | 'quantity_mismatch' | 'amount_mismatch' | 'unmatched'
export type SupplierPayableStatus = 'unpaid' | 'partially_paid' | 'paid' | 'overdue'

export interface SupplierPayment {
  id: string
  amount: number
  payment_date: string
  payment_method: 'bank_transfer' | 'cash' | 'card' | 'other'
  reference?: string
  notes?: string
  is_reversed: boolean
  reversal?: {
    id: string
    amount: number
    reason: string
    created_at: string
  }
  created_at: string
}

export interface SupplierCreditNote {
  id: string
  supplier_credit_note_number: string
  amount: number
  credit_date: string
  reason: string
  created_at: string
}

export interface SupplierPayable {
  id: string
  supplier_id: string
  supplier_name: string
  supplier_invoice_id: string
  internal_invoice_number: string
  supplier_invoice_number: string
  due_date: string
  original_amount: number
  paid_amount: number
  credited_amount: number
  outstanding_amount: number
  status: SupplierPayableStatus
  days_overdue: number
  payments: SupplierPayment[]
  credit_notes: SupplierCreditNote[]
  created_at: string
  updated_at: string
}

export interface SupplierInvoiceItem {
  id: string
  purchase_order_item_id: string
  product_id: string
  product_name: string
  quantity: number
  unit_price: number
  discount_percent: number
  vat_rate: number
  line_subtotal: number
  vat_amount: number
  line_total: number
  matching_status: SupplierInvoiceMatchingStatus
  match_issue?: string
}

export interface SupplierInvoice {
  id: string
  supplier_id: string
  supplier_name: string
  purchase_order_id: string
  purchase_order_number: string
  internal_invoice_number: string
  supplier_invoice_number: string
  invoice_date: string
  due_date: string
  status: SupplierInvoiceStatus
  matching_status: SupplierInvoiceMatchingStatus
  match_issues: string[]
  subtotal: number
  vat_amount: number
  total: number
  notes?: string
  approved_at?: string
  items: SupplierInvoiceItem[]
  payable?: SupplierPayable
  created_at: string
  updated_at: string
}

export interface SupplierInvoiceCreate {
  supplier_id: string
  purchase_order_id: string
  supplier_invoice_number: string
  invoice_date: string
  due_date: string
  notes?: string
  items: {
    purchase_order_item_id: string
    quantity: number
    unit_price: number
    discount_percent: number
    vat_rate: number
  }[]
}

export interface SupplierPaymentCreate {
  idempotency_key: string
  amount: number
  payment_date: string
  payment_method: 'bank_transfer' | 'cash' | 'card' | 'other'
  reference?: string
  notes?: string
}

export interface SupplierCreditNoteCreate {
  idempotency_key: string
  supplier_credit_note_number: string
  amount: number
  credit_date: string
  reason: string
}

export interface SupplierPaymentReversalCreate {
  idempotency_key: string
  reason: string
}

export interface BankAccount {
  id: string
  bank_name: string
  account_name: string
  iban: string
  currency: string
  status: 'active' | 'inactive'
  created_at: string
}

export interface BankStatementImport {
  id: string
  bank_account_id: string
  filename: string
  transaction_count: number
  debit_total: number
  credit_total: number
  created_at: string
}

export interface BankTransaction {
  id: string
  bank_account_id: string
  bank_account_name: string
  transaction_date: string
  reference: string
  description: string
  counterparty: string
  amount: number
  matched_amount: number
  unmatched_amount: number
  direction: 'debit' | 'credit'
  currency: string
  status: 'unmatched' | 'partially_matched' | 'matched'
  created_at: string
}

export interface BankReconciliation {
  id: string
  bank_transaction_id: string
  supplier_payable_id: string
  supplier_payment_id: string
  amount: number
  status: 'active' | 'reversed'
  notes?: string
  reversal_reason?: string
  reversed_at?: string
  created_at: string
  transaction_reference?: string
  supplier_name?: string
  supplier_invoice_number?: string
}

export interface BankReconciliationResult {
  transaction: BankTransaction
  payable: SupplierPayable
  reconciliation: BankReconciliation
}

export type CustomerReceivableStatus = 'unpaid' | 'partially_paid' | 'paid' | 'overdue' | 'credited'

export interface CustomerPayment {
  id: string
  receivable_id: string
  amount: number
  payment_date: string
  payment_method: 'bank_transfer' | 'cash' | 'card' | 'other'
  reference: string
  notes?: string
  status: 'active' | 'reversed'
  reversal_reason?: string
  created_at: string
}

export interface CustomerCreditNote {
  id: string
  receivable_id: string
  credit_note_number: string
  amount: number
  credit_date: string
  reason: string
  created_at: string
}

export interface CustomerReceivable {
  id: string
  invoice_id: string
  invoice_number: string
  client_id: string
  client_name: string
  currency: string
  original_amount: number
  paid_amount: number
  credited_amount: number
  outstanding_amount: number
  due_date: string
  overdue_days: number
  status: CustomerReceivableStatus
  payments: CustomerPayment[]
  credit_notes: CustomerCreditNote[]
  created_at: string
}

export interface CustomerPaymentCreate {
  idempotency_key: string
  amount: number
  payment_date: string
  payment_method: 'bank_transfer' | 'cash' | 'card' | 'other'
  reference?: string
  notes?: string
}

export interface CustomerCreditNoteCreate {
  idempotency_key: string
  credit_note_number: string
  amount: number
  credit_date: string
  reason: string
}

export interface CustomerBankReconciliation {
  id: string
  bank_transaction_id: string
  customer_receivable_id: string
  customer_payment_id: string
  amount: number
  status: 'active' | 'reversed'
  notes?: string
  reversal_reason?: string
  reversed_at?: string
  created_at: string
}

export interface CustomerBankReconciliationResult {
  transaction: BankTransaction
  receivable: CustomerReceivable
  reconciliation: CustomerBankReconciliation
}

// === Product ===
export type StockStatus = 'good' | 'low' | 'critical'

export interface Product {
  id: string
  sku: string
  name: string
  description?: string
  category_id?: string
  category_name?: string
  barcode?: string
  gtin?: string
  sale_price: number
  purchase_price?: number
  average_cost?: number
  unit: string
  min_stock: number
  current_stock: number
  stock_status: StockStatus
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ProductCreate {
  sku: string
  name: string
  description?: string
  category_id?: string
  barcode?: string
  gtin?: string
  sale_price: number
  purchase_price?: number
  unit?: string
  min_stock?: number
  current_stock?: number
}

export interface PurchaseCostHistory {
  id: string
  product_id: string
  product_name: string
  supplier_id: string
  supplier_name: string
  purchase_order_id: string
  purchase_order_number: string
  goods_receipt_id: string
  receipt_number: string
  quantity: number
  unit_cost: number
  previous_stock: number
  new_stock: number
  previous_average_cost: number
  new_average_cost: number
  created_at: string
}

export interface StockAdjustment {
  product_id: string
  movement_type: 'in' | 'out' | 'adjustment'
  quantity: number
  reason: string
  notes?: string
}

export interface Category {
  id: string
  name: string
  parent_id?: string
}

// === Warehouses & multi-location inventory ===
export interface Warehouse {
  id: string
  code: string
  name: string
  address?: string
  is_default: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface WarehouseCreate {
  code: string
  name: string
  address?: string
  is_default?: boolean
}

export interface WarehouseUpdate {
  code?: string
  name?: string
  address?: string
}

export interface InventoryBalance {
  id: string
  product_id: string
  product_name: string
  warehouse_id: string
  warehouse_name: string
  warehouse_code: string
  quantity: number
  reserved_quantity: number
  available_quantity: number
  updated_at: string
}

export interface WarehouseStockAdjustment {
  product_id: string
  warehouse_id: string
  zone_id?: string
  movement_type: 'in' | 'out' | 'adjustment'
  quantity: number
  reason: string
  reason_category?: string
  notes?: string
}

export interface StockTransfer {
  product_id: string
  source_warehouse_id: string
  destination_warehouse_id: string
  quantity: number
  reason: string
  reason_category?: string
  notes?: string
}

export interface WarehouseZone {
  id: string
  warehouse_id: string
  parent_id?: string
  code: string
  name: string
  zone_type: 'aisle' | 'rack' | 'shelf' | 'bin' | 'dock' | 'staging'
  is_pickable: boolean
  is_active: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface WarehouseZoneCreate {
  warehouse_id: string
  parent_id?: string
  code: string
  name: string
  zone_type: 'aisle' | 'rack' | 'shelf' | 'bin' | 'dock' | 'staging'
  is_pickable?: boolean
  sort_order?: number
}

export interface InventoryMovement {
  id: string
  product_id: string
  product_name?: string
  warehouse_id: string
  warehouse_name?: string
  zone_id?: string
  zone_name?: string
  movement_type: string
  quantity: number
  balance_before?: number
  balance_after: number
  reserved_before?: number
  reserved_after?: number
  reason: string
  reason_category?: string
  notes?: string
  reference?: string
  reference_type?: string
  created_by?: string
  created_at: string
}

export interface InventoryCount {
  id: string
  warehouse_id: string
  warehouse_name?: string
  zone_id?: string
  zone_name?: string
  count_number: string
  status: 'draft' | 'in_progress' | 'completed' | 'cancelled' | 'posted'
  count_type: 'full' | 'spot' | 'cycle' | 'annual'
  notes?: string
  counted_by?: string
  approved_by?: string
  counted_at?: string
  approved_at?: string
  line_count?: number
  total_difference?: number
  created_at: string
  updated_at: string
}

export interface InventoryCountCreate {
  warehouse_id: string
  zone_id?: string
  count_type?: 'full' | 'spot' | 'cycle' | 'annual'
  notes?: string
}

export interface InventoryCountLine {
  id: string
  count_id: string
  product_id: string
  product_name?: string
  zone_id?: string
  zone_name?: string
  expected_quantity: number
  counted_quantity?: number
  difference?: number
  notes?: string
  created_at: string
}

export interface InventoryCountLineCreate {
  product_id: string
  zone_id?: string
  counted_quantity: number
  notes?: string
}

export interface ZoneBalance {
  id: string
  zone_id: string
  zone_code: string
  zone_name: string
  product_id: string
  product_name: string
  quantity: number
  updated_at: string
}

// === Task ===
export type TaskStatus = 'todo' | 'in_progress' | 'done' | 'cancelled'
export type TaskPriority = 'low' | 'medium' | 'high'

export interface Task {
  id: string
  title: string
  description?: string
  status: TaskStatus
  priority: TaskPriority
  due_date?: string
  assigned_to?: string
  assigned_to_name?: string
  client_name?: string
  client_id?: string
  order_number?: string
  order_id?: string
  project_id?: string
  project_name?: string
  parent_id?: string
  recurrence?: string
  recurrence_end?: string
  created_at: string
  updated_at: string
}

export interface TaskCreate {
  title: string
  description?: string
  assigned_to?: string
  due_date?: string
  priority?: TaskPriority
  client_id?: string
  order_id?: string
  project_id?: string
  parent_id?: string
  recurrence?: string
  recurrence_end?: string
}

export interface TaskComment {
  id: string
  user_name?: string
  content: string
  created_at: string
}

// === Dashboard ===
export interface DashboardKPI {
  active_clients: number
  active_orders: number
  overdue_tasks: number
  low_stock_products: number
  total_revenue: number
  monthly_revenue?: number
  revenue_change?: number
}

export interface RevenuePoint {
  date: string
  amount: number
}

export interface DashboardData {
  kpi: DashboardKPI
  revenue_chart: { data: RevenuePoint[] }
  order_status_distribution: { status: string; count: number; color: string }[]
  recent_orders: Order[]
  critical_alerts: { severity: 'high' | 'medium'; title: string; description: string }[]
  total_revenue: number
  invoiced_orders_count: number
  total_orders_count: number
}

// === General Ledger ===
export interface GLAccount {
  id: string
  company_id: string
  code: string
  name: string
  account_type: 'asset' | 'liability' | 'equity' | 'income' | 'expense'
  parent_id?: string
  is_active: boolean
  description?: string
  created_at: string
  updated_at: string
}

export interface GLAccountCreate {
  code: string
  name: string
  account_type: string
  parent_id?: string
  description?: string
}

export interface GLAccountUpdate {
  name?: string
  is_active?: boolean
  description?: string
}

export interface JournalEntryLine {
  id: string
  journal_entry_id: string
  gl_account_id: string
  line_number: number
  debit_amount: number
  credit_amount: number
  description?: string
  created_at: string
}

export interface JournalEntry {
  id: string
  company_id: string
  entry_number: string
  entry_date: string
  description: string
  reference_type: string
  reference_id: string
  is_reversal: boolean
  reversed_entry_id?: string
  created_by?: string
  created_at: string
  lines: JournalEntryLine[]
}

export interface JournalEntrySummary {
  id: string
  entry_number: string
  entry_date: string
  description: string
  reference_type: string
  is_reversal: boolean
  created_at: string
}

export interface TrialBalanceAccount {
  code: string
  name: string
  account_type: string
  total_debit: number
  total_credit: number
  balance: number
}

export interface TrialBalance {
  as_of_date: string
  accounts: TrialBalanceAccount[]
}

// === Fleet Management ===
export interface Vehicle {
  id: string
  company_id: string
  plate_number: string
  brand: string
  model: string
  year: number | null
  vin: string | null
  color: string | null
  fuel_type: string
  engine_capacity: number | null
  initial_mileage: number
  current_mileage: number
  insurance_company: string | null
  insurance_policy: string | null
  insurance_valid_until: string | null
  tech_inspection_until: string | null
  location_name: string | null
  latitude: number | null
  longitude: number | null
  is_active: boolean
  notes: string | null
  created_at: string
  updated_at: string
}

export interface VehicleCreate {
  plate_number: string
  brand: string
  model: string
  year?: number | null
  vin?: string | null
  color?: string | null
  fuel_type?: string
  engine_capacity?: number | null
  initial_mileage?: number
  current_mileage?: number
  insurance_company?: string | null
  insurance_policy?: string | null
  insurance_valid_until?: string | null
  tech_inspection_until?: string | null
  location_name?: string | null
  latitude?: number | null
  longitude?: number | null
  notes?: string | null
}

export interface VehicleUpdate {
  plate_number?: string
  brand?: string
  model?: string
  year?: number | null
  vin?: string | null
  color?: string | null
  fuel_type?: string
  engine_capacity?: number | null
  current_mileage?: number | null
  insurance_company?: string | null
  insurance_policy?: string | null
  insurance_valid_until?: string | null
  tech_inspection_until?: string | null
  location_name?: string | null
  latitude?: number | null
  longitude?: number | null
  is_active?: boolean
  notes?: string | null
}

export interface FuelLog {
  id: string
  company_id: string
  vehicle_id: string
  refuel_date: string
  liters: number
  price_per_liter: number
  total_amount: number
  mileage_at_refuel: number
  fuel_card: string | null
  station: string | null
  receipt_number: string | null
  notes: string | null
  created_at: string
}

export interface FuelLogCreate {
  vehicle_id: string
  refuel_date: string
  liters: number
  price_per_liter: number
  total_amount: number
  mileage_at_refuel: number
  fuel_card?: string | null
  station?: string | null
  receipt_number?: string | null
  notes?: string | null
}

export interface ServiceRecord {
  id: string
  company_id: string
  vehicle_id: string
  service_date: string
  service_type: string
  description: string
  mileage_at_service: number
  cost: number
  service_provider: string | null
  invoice_number: string | null
  next_service_mileage: number | null
  next_service_date: string | null
  notes: string | null
  created_at: string
}

export interface ServiceRecordCreate {
  vehicle_id: string
  service_date: string
  service_type: string
  description: string
  mileage_at_service: number
  cost?: number
  service_provider?: string | null
  invoice_number?: string | null
  next_service_mileage?: number | null
  next_service_date?: string | null
  notes?: string | null
}

export interface DriverAssignment {
  id: string
  company_id: string
  vehicle_id: string
  driver_name: string
  driver_phone: string | null
  driver_license: string | null
  assigned_from: string
  assigned_until: string | null
  is_active: boolean
  notes: string | null
  created_at: string
}

export interface DriverAssignmentCreate {
  vehicle_id: string
  driver_name: string
  driver_phone?: string | null
  driver_license?: string | null
  assigned_from: string
  assigned_until?: string | null
  notes?: string | null
}

export interface DriverAssignmentUpdate {
  driver_name?: string
  driver_phone?: string | null
  driver_license?: string | null
  assigned_from?: string
  assigned_until?: string | null
  is_active?: boolean
  notes?: string | null
}

// === Cash Register ===
export interface CashAccount {
  id: string
  company_id: string
  name: string
  currency: string
  balance: number
  is_active: boolean
  notes: string | null
  created_at: string
  updated_at: string
}

export interface CashTransaction {
  id: string
  company_id: string
  cash_account_id: string
  cash_account_name: string
  transaction_date: string
  direction: 'inflow' | 'outflow'
  amount: number
  category: string
  description: string
  counterparty: string | null
  receipt_number: string | null
  reference_type: string | null
  reference_id: string | null
  created_by: string | null
  created_at: string
}

export interface CashDailyReport {
  date: string
  opening_balance: number
  total_inflow: number
  total_outflow: number
  closing_balance: number
  transaction_count: number
}

// === Fixed Assets ===
export interface FixedAsset {
  id: string
  company_id: string
  name: string
  asset_type: string
  purchase_date: string
  purchase_cost: number
  useful_life_years: number
  depreciation_method: string
  salvage_value: number
  accumulated_depreciation: number
  book_value: number
  last_depreciation_date: string | null
  status: string
  serial_number: string | null
  location: string | null
  notes: string | null
  gl_account_id: string | null
  created_at: string
  updated_at: string
}

export interface FixedAssetCreate {
  name: string
  asset_type: string
  purchase_date: string
  purchase_cost: number
  useful_life_years: number
  depreciation_method?: string
  salvage_value?: number
  serial_number?: string | null
  location?: string | null
  notes?: string | null
  gl_account_id?: string | null
}

export interface FixedAssetUpdate {
  name?: string
  status?: string
  location?: string | null
  notes?: string | null
  serial_number?: string | null
}

export interface DepreciationRunResult {
  asset_id: string
  asset_name: string
  depreciation_amount: number
  new_book_value: number
  new_accumulated_depreciation: number
  is_fully_depreciated: boolean
}

export interface AssetDepreciationEntry {
  id: string
  asset_id: string
  depreciation_date: string
  amount: number
  period_label: string
  created_at: string
}

// === SRS Tax Reporting ===
export interface VatDeclarationRow {
  line_code: string
  line_name: string
  amount: number
}

export interface VatDeclaration {
  period: string
  rows: VatDeclarationRow[]
  total_vat_payable: number
  total_vat_credit: number
  net_vat: number
}

export interface IncomeTaxRow {
  line_code: string
  line_name: string
  amount: number
}

export interface IncomeTaxReport {
  period: string
  rows: IncomeTaxRow[]
  total_revenue: number
  total_expenses: number
  taxable_profit: number
  estimated_tax: number
}

export interface BalanceFormRow {
  code: string
  name: string
  amount: number
}

export interface BalanceForm {
  as_of_date: string
  assets: BalanceFormRow[]
  liabilities: BalanceFormRow[]
  equity: BalanceFormRow[]
  total_assets: number
  total_liabilities: number
  total_equity: number
}

// === Expenses ===
export interface ExpenseCategory {
  id: string
  company_id: string
  name: string
  is_active: boolean
  created_at: string
}

export interface Expense {
  id: string
  company_id: string
  employee_id: string
  employee_name: string
  category_id: string | null
  category_name: string | null
  expense_date: string
  description: string
  amount: number
  currency: string
  status: 'pending' | 'approved' | 'rejected' | 'paid'
  receipt_url: string | null
  notes: string | null
  approved_by: string | null
  approved_at: string | null
  created_at: string
  updated_at: string
}

export interface ExpenseCreate {
  category_id: string | null
  expense_date: string
  description: string
  amount: number
  currency?: string
  notes?: string | null
}

// === Budgeting ===
export interface BudgetPlan {
  id: string
  company_id: string
  name: string
  fiscal_year: number
  period_type: string
  status: string
  notes: string | null
  total_planned: number
  total_actual: number
  created_at: string
  updated_at: string
}

export interface BudgetPlanCreate {
  name: string
  fiscal_year: number
  period_type?: string
  notes?: string | null
}

export interface BudgetLine {
  id: string
  plan_id: string
  gl_account_id: string
  gl_account_code: string
  gl_account_name: string
  period: string
  planned_amount: number
  actual_amount: number
  variance: number
  variance_percent: number | null
  notes: string | null
  created_at: string
}

export interface BudgetLineCreate {
  gl_account_id: string
  period: string
  planned_amount: number
  notes?: string | null
}

// === Multi-currency ===
export interface CurrencyRate {
  id: string
  company_id: string
  from_currency: string
  to_currency: string
  rate_date: string
  rate: number
  source: string
  created_at: string
}

export interface CurrencyRateCreate {
  from_currency: string
  to_currency: string
  rate_date: string
  rate: number
  source?: string
}

export interface CurrencyConversion {
  from_currency: string
  to_currency: string
  amount: number
  converted_amount: number
  rate: number
  rate_date: string
}

// === Analytic accounting ===
export interface AnalyticAccount {
  id: string
  company_id: string
  code: string
  name: string
  account_type: string
  is_active: boolean
  notes: string | null
  income_total: number
  expense_total: number
  balance: number
  created_at: string
}

export interface AnalyticEntry {
  id: string
  analytic_account_id: string
  analytic_account_name: string
  gl_account_id: string | null
  entry_date: string
  description: string
  amount: number
  direction: 'income' | 'expense'
  reference: string | null
  created_at: string
}

// === Deferred revenue / expense ===
export interface DeferredRecognition {
  id: string
  period_no: number
  recognition_date: string
  amount: number
  status: 'pending' | 'recognized'
  journal_entry_id: string | null
  recognized_at: string | null
}

export interface DeferredSchedule {
  id: string
  company_id: string
  name: string
  deferral_type: 'revenue' | 'expense'
  total_amount: number
  recognized_amount: number
  remaining_amount: number
  start_date: string
  periods: number
  source_gl_account_id: string
  source_gl_account_code: string
  source_gl_account_name: string
  recognition_gl_account_id: string
  recognition_gl_account_code: string
  recognition_gl_account_name: string
  status: string
  notes: string | null
  created_at: string
  recognitions: DeferredRecognition[]
}

// === App Module Architecture ===
export interface AppModule {
  id: string
  code: string
  name: string
  description: string | null
  icon: string | null
  route: string | null
  category: string
  is_active: boolean
  depends_on: string | null
  sort_order: number
  created_at: string
  updated_at: string
}

export interface ModulePermission {
  id: string
  module_id: string
  role: string
  can_access: boolean
  can_create: boolean
  can_edit: boolean
  can_delete: boolean
  can_approve: boolean
  created_at: string
  updated_at: string
  module?: AppModule
}

export interface CompanyModuleStatus {
  module: AppModule
  enabled: boolean
  permissions: ModulePermission[]
}