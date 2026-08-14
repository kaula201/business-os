// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense, type ReactNode } from 'react'
import { useAuthStore } from './store/authStore'
import Layout from './components/layout/Layout'
const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const VerifyEmailPage = lazy(() => import('./pages/VerifyEmailPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ClientsPage = lazy(() => import('./pages/ClientsPage'))
const OrdersPage = lazy(() => import('./pages/OrdersPage'))
const InventoryPage = lazy(() => import('./pages/InventoryPage'))
const TasksPage = lazy(() => import('./pages/TasksPage'))
const ReportsPage = lazy(() => import('./pages/ReportsPage'))
const AIPage = lazy(() => import('./pages/AIPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const PurchasesPage = lazy(() => import('./pages/PurchasesPage'))
const SuppliersPage = lazy(() => import('./pages/SuppliersPage'))
const SupplierFinancePage = lazy(() => import('./pages/SupplierFinancePage'))
const BankingPage = lazy(() => import('./pages/BankingPage'))
const InvoicesPage = lazy(() => import('./pages/InvoicesPage'))
const CustomerFinancePage = lazy(() => import('./pages/CustomerFinancePage'))
const ChartOfAccountsPage = lazy(() => import('./pages/ChartOfAccountsPage'))
const JournalEntriesPage = lazy(() => import('./pages/JournalEntriesPage'))
const TrialBalancePage = lazy(() => import('./pages/TrialBalancePage'))
const ProfitLossPage = lazy(() => import('./pages/ProfitLossPage'))
const BalanceSheetPage = lazy(() => import('./pages/BalanceSheetPage'))
const FleetPage = lazy(() => import('./pages/FleetPage'))
const CashPage = lazy(() => import('./pages/CashPage'))
const AssetsPage = lazy(() => import('./pages/AssetsPage'))
const SrsPage = lazy(() => import('./pages/SrsPage'))
const ExpensesPage = lazy(() => import('./pages/ExpensesPage'))
const BudgetingPage = lazy(() => import('./pages/BudgetingPage'))
const CurrencyPage = lazy(() => import('./pages/CurrencyPage'))
const AnalyticAccountingPage = lazy(() => import('./pages/AnalyticAccountingPage'))
const DeferredPage = lazy(() => import('./pages/DeferredPage'))
const AccountingPeriodsPage = lazy(() => import('./pages/AccountingPeriodsPage'))
const RecurringEntriesPage = lazy(() => import('./pages/RecurringEntriesPage'))
const ExchangeDifferencesPage = lazy(() => import('./pages/ExchangeDifferencesPage'))
const ConsolidatedReportsPage = lazy(() => import('./pages/ConsolidatedReportsPage'))
const BankRulesPage = lazy(() => import('./pages/BankRulesPage'))
const InventoryValuationPage = lazy(() => import('./pages/InventoryValuationPage'))
const QuotationsPage = lazy(() => import('./pages/QuotationsPage'))
const PriceListsPage = lazy(() => import('./pages/PriceListsPage'))
const SalesTeamsPage = lazy(() => import('./pages/SalesTeamsPage'))
const EmailTrackingPage = lazy(() => import('./pages/EmailTrackingPage'))
const SubscriptionsPage = lazy(() => import('./pages/SubscriptionsPage'))
const PortalPage = lazy(() => import('./pages/PortalPage'))
const WmsPage = lazy(() => import('./pages/WmsPage'))
const ProcurementPage = lazy(() => import('./pages/ProcurementPage'))
const CRMPage = lazy(() => import('./pages/CRMPage'))
const HRPage = lazy(() => import('./pages/HRPage'))
const DocumentsPage = lazy(() => import('./pages/DocumentsPage'))
const ProductionPage = lazy(() => import('./pages/ProductionPage'))
const ProjectsPage = lazy(() => import('./pages/ProjectsPage'))

function ProtectedRoute({ children }: { children: ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />
}

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-gray-50 text-sm text-gray-500 dark:bg-dark-300 dark:text-gray-400">იტვირთება...</div>}>
        <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/clients" element={<ClientsPage />} />
                  <Route path="/clients/:id" element={<ClientsPage />} />
                  <Route path="/crm" element={<CRMPage />} />
                  <Route path="/hr" element={<HRPage />} />
                  <Route path="/documents" element={<DocumentsPage />} />
                  <Route path="/production" element={<ProductionPage />} />
                  <Route path="/projects" element={<ProjectsPage />} />
                  <Route path="/orders" element={<OrdersPage />} />
                  <Route path="/orders/:id" element={<OrdersPage />} />
                  <Route path="/invoices" element={<InvoicesPage />} />
                  <Route path="/customer-finance" element={<CustomerFinancePage />} />
                  <Route path="/purchases" element={<PurchasesPage />} />
                  <Route path="/purchases/:id" element={<PurchasesPage />} />
                  <Route path="/suppliers" element={<SuppliersPage />} />
                  <Route path="/supplier-finance" element={<SupplierFinancePage />} />
                  <Route path="/banking" element={<BankingPage />} />
                  <Route path="/inventory" element={<InventoryPage />} />
                  <Route path="/tasks" element={<TasksPage />} />
                  <Route path="/reports" element={<ReportsPage />} />
                  <Route path="/ai" element={<AIPage />} />
                  <Route path="/chart-of-accounts" element={<ChartOfAccountsPage />} />
                  <Route path="/journal-entries" element={<JournalEntriesPage />} />
                  <Route path="/trial-balance" element={<TrialBalancePage />} />
                  <Route path="/profit-loss" element={<ProfitLossPage />} />
                  <Route path="/balance-sheet" element={<BalanceSheetPage />} />
                  <Route path="/fleet" element={<FleetPage />} />
                  <Route path="/cash" element={<CashPage />} />
                  <Route path="/assets" element={<AssetsPage />} />
                  <Route path="/srs" element={<SrsPage />} />
                  <Route path="/expenses" element={<ExpensesPage />} />
                  <Route path="/budgeting" element={<BudgetingPage />} />
                  <Route path="/currency" element={<CurrencyPage />} />
                  <Route path="/analytic-accounting" element={<AnalyticAccountingPage />} />
                  <Route path="/deferred" element={<DeferredPage />} />
                  <Route path="/accounting-periods" element={<AccountingPeriodsPage />} />
                  <Route path="/gl-recurring" element={<RecurringEntriesPage />} />
                  <Route path="/gl-exchange-differences" element={<ExchangeDifferencesPage />} />
                  <Route path="/gl-consolidated" element={<ConsolidatedReportsPage />} />
                  <Route path="/banking-rules" element={<BankRulesPage />} />
                  <Route path="/inventory-valuation" element={<InventoryValuationPage />} />
                  <Route path="/quotations" element={<QuotationsPage />} />
                  <Route path="/price-lists" element={<PriceListsPage />} />
                  <Route path="/sales-teams" element={<SalesTeamsPage />} />
                  <Route path="/email-tracking" element={<EmailTrackingPage />} />
                  <Route path="/subscriptions" element={<SubscriptionsPage />} />
                  <Route path="/customer-portal" element={<PortalPage />} />
                  <Route path="/wms" element={<WmsPage />} />
                  <Route path="/procurement" element={<ProcurementPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          }
        />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
