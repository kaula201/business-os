from app.models.company import Company
from app.models.user import User
from app.models.client import Client, ClientAddress, ClientGroupDef, ClientRelation
from app.models.contract import Contract
from app.models.leave import Leave
from app.models.subscription import Subscription
from app.models.customer_portal import PortalUser
from app.models.vendor_portal import VendorPortalUser
from app.models.order import (
    DocumentSequence,
    InventoryReservation,
    Order,
    OrderFulfillment,
    OrderItem,
    OrderStatusHistory,
)
from app.models.product import Product, ProductCategory, ProductVariant, ProductImage, StockMovement
from app.models.task import Task, TaskComment, TaskAttachment, TaskHistory, TaskReminder, TaskDependency
from app.models.invoice import Invoice, InvoiceItem
from app.models.receivable import (
    CustomerReceivable,
    CustomerPayment,
    CustomerPaymentReversal,
    CustomerCreditNote,
    CustomerBankReconciliation,
    CustomerBankReconciliationReversal,
)
from app.models.warehouse import Warehouse, InventoryBalance, InventoryMovement, WarehouseZone, ZoneBalance, InventoryCount, InventoryCountLine
from app.models.wms_ops import (
    PickList, PickListItem, PackingSlip, ReplenishmentRule,
    LandedCost, LandedCostAllocation, BatchTraceEvent,
)
from app.models.helpdesk_ext import (
    HelpdeskQueue, HelpdeskSla, HelpdeskEscalation, CannedReply, KnowledgeArticle, FieldServiceJob, EmailIntakeRule,
)
from app.models.reporting import SavedReport, ReportSchedule, ReportDimension
from app.models.integration import ApiKey, Webhook, WebhookEvent
from app.models.bank_connection import BankConnection
from app.models.payment import PaymentTransaction
from app.models.email_calendar import EmailMessage, CalendarEvent
from app.models.security import LoginHistory, User2FA, ApprovalStep
from app.models.field_access import FieldAccessRule
from app.models.notification import Notification
from app.models.automation import AutomationRule
from app.models.accounting_controls import FiscalPosition, ConsolidationAccountMapping, FxTranslationRate
from app.models.consolidation_elimination import ConsolidationElimination
from app.models.tender import Tender, TenderLine, TenderBid, TenderBidLine
from app.models.procurement import (
    RFQ, RFQLine, RFQResponse, RFQResponseLine,
    SupplierPriceList, SupplierPriceHistory, BlanketOrder, BlanketOrderLine, SupplierScorecard,
)
from app.models.audit import AuditLog
from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.models.fleet import Vehicle, FuelLog, ServiceRecord, DriverAssignment, OdometerReading
from app.models.cash import CashAccount, CashTransaction
from app.models.assets import FixedAsset, AssetDepreciation
from app.models.expenses import Expense, ExpenseCategory
from app.models.budgeting import BudgetPlan, BudgetLine
from app.models.currency import CurrencyRate, IntegrationSyncLog
from app.models.analytic import AnalyticAccount, AnalyticEntry
from app.models.approval import ApprovalRequest
from app.models.deferred import DeferredSchedule, DeferredRecognition
from app.models.accounting_period import AccountingPeriod, AccountingPeriodEvent
from app.models.crm import CRMActivity, CRMLead, CRMOpportunity, CRMPipelineStage  # noqa: F401
from app.models.banking import (
    BankAccount,
    BankStatementImport,
    BankTransaction,
    BankReconciliation,
)
from app.models.module import AppModule, CompanyModule, ModulePermission
from app.models.hr import (
    Department, Employee, PayrollEntry, Timesheet,
    EmployeeDocument, LeaveType, LeaveBalance, LeaveRequest,
    Attendance, PerformanceReview, PerformanceGoal,
    Payslip,
)
from app.models.documents import DocumentCategory, Document, DocumentVersion, DocumentApproval
from app.models.production import (
    BillOfMaterial, BOMItem, WorkOrder, WorkCenter,
    ProductionReservation, FinishedGoodsReceipt,
)
from app.models.projects import Project, ProjectMember, ProjectMilestone, ProjectTimesheet
from app.models.studio import StudioApp, StudioField, StudioForm, StudioRecord
from app.models.marketplace import CompanyAppInstallation, MarketplaceApp, MarketplacePurchase
from app.models.report import ReportPreference
from app.models.helpdesk import HelpdeskTicket
from app.models.pos import POSSession, POSOrder, POSOrderItem
from app.models.pos import POSRefund, POSLoyaltyAccount, POSLoyaltyTransaction, POSOfflineQueue, POSFiscalDevice
from app.models.pos_extended import GiftCard, GiftCardTransaction, POSCashMovement, POSZReport, POSPayment
from app.models.pos_restaurant import RestaurantTable, POSOrderType, SelfOrderSession
from app.models.ecommerce import EcomCategory, EcomProduct
from app.models.purchase import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatusHistory,
    Supplier,
    SupplierBankDetail,
    SupplierRatingHistory,
    SupplierInvoice,
    SupplierInvoiceItem,
    SupplierPayable,
    SupplierPayment,
    SupplierCreditNote,
    SupplierPaymentReversal,
    SupplierOverpayment,
    SupplierInvoiceTolerance,
    SupplierCreditNoteCurrencyDiff,
    PurchaseCostHistory,
    PurchaseApprovalPolicy,
)
from app.models.recruitment import JobPosting
from app.models.email_marketing import EmailCampaign
from app.models.quality_control import (
    QualityAlert,
    QualityCheck,
    QualityControlPoint,
    QualityTest,
    QualityTestResult,
)
from app.models.live_chat import ChatMessage
from app.models.embedding import Embedding

__all__ = [
    "Company", "User", "Client", "ClientAddress", "ClientGroupDef", "ClientRelation", "Contract", "Leave", "Order", "OrderItem", "OrderStatusHistory", "OrderFulfillment",
 "InventoryReservation", "DocumentSequence",
    "Product", "ProductCategory", "ProductVariant", "ProductImage", "StockMovement", "Task", "TaskComment", "TaskAttachment", "TaskHistory", "TaskReminder", "TaskDependency", "Invoice", "InvoiceItem",
    "CustomerReceivable", "CustomerPayment", "CustomerPaymentReversal", "CustomerCreditNote", "CustomerBankReconciliation", "CustomerBankReconciliationReversal",
    "Warehouse", "InventoryBalance", "InventoryMovement", "WarehouseZone", "ZoneBalance", "InventoryCount", "InventoryCountLine", "AuditLog",
    "PickList", "PickListItem", "PackingSlip", "ReplenishmentRule", "LandedCost", "LandedCostAllocation", "BatchTraceEvent",
    "HelpdeskQueue", "HelpdeskSla", "HelpdeskEscalation", "CannedReply", "KnowledgeArticle", "FieldServiceJob", "EmailIntakeRule",
    "SavedReport", "ReportSchedule", "ReportDimension",
    "ApiKey", "Webhook", "WebhookEvent",
    "BankConnection",
    "PaymentTransaction",
    "EmailMessage", "CalendarEvent",
    "LoginHistory", "User2FA", "ApprovalStep",
    "FieldAccessRule",
    "Notification",
    "AutomationRule",
    "FiscalPosition", "ConsolidationAccountMapping", "FxTranslationRate",
    "ConsolidationElimination",
    "Tender", "TenderLine", "TenderBid", "TenderBidLine",
    "RFQ", "RFQLine", "RFQResponse", "RFQResponseLine", "SupplierPriceList", "SupplierPriceHistory", "BlanketOrder", "BlanketOrderLine", "SupplierScorecard",
    "Supplier", "SupplierBankDetail", "SupplierRatingHistory", "PurchaseOrder", "PurchaseOrderItem", "PurchaseOrderStatusHistory",
    "GoodsReceipt", "GoodsReceiptItem",
    "SupplierInvoice", "SupplierInvoiceItem", "SupplierPayable", "SupplierPayment",
    "SupplierCreditNote", "SupplierPaymentReversal",
    "PurchaseCostHistory", "PurchaseApprovalPolicy",
    "BankAccount", "BankStatementImport", "BankTransaction", "BankReconciliation",
    "AppModule", "CompanyModule", "ModulePermission",
    "Department", "Employee", "PayrollEntry", "Timesheet",
    "EmployeeDocument", "LeaveType", "LeaveBalance", "LeaveRequest",
    "Attendance", "PerformanceReview", "PerformanceGoal", "Payslip",
    "DocumentCategory", "Document", "DocumentVersion", "DocumentApproval",
    "BillOfMaterial", "BOMItem", "WorkOrder", "WorkCenter",
    "ProductionReservation", "FinishedGoodsReceipt",
    "Project", "ProjectMilestone", "ReportPreference",
    "HelpdeskTicket",
    "POSSession", "POSOrder", "POSOrderItem",
    "POSRefund", "POSLoyaltyAccount", "POSLoyaltyTransaction", "POSOfflineQueue", "POSFiscalDevice",
    "EcomCategory", "EcomProduct",
    "GLAccount", "JournalEntry", "JournalEntryLine",
    "Vehicle", "FuelLog", "ServiceRecord", "DriverAssignment", "OdometerReading",
    "CRMLead", "CRMOpportunity", "CRMActivity",
    "ApprovalRequest",
    "JobPosting",
    "EmailCampaign",
    "PortalUser",
    "VendorPortalUser",
    "QualityCheck", "QualityControlPoint", "QualityTest", "QualityTestResult", "QualityAlert",
    "MarketplacePurchase",
    "ChatMessage", "Embedding",
]

from app.models.recurring import RecurringJournalEntry  # noqa: F401
from app.models.exchange_difference import ExchangeDifference  # noqa: F401
from app.models.bank_rule import BankReconciliationRule  # noqa: F401
from app.models.cost_layer import (  # noqa: F401
    FifoCostLot,
    ProductCostLayer,
    ProductValuationConfig,
)
from app.models.counterparty import CounterpartyCheck  # noqa: F401
from app.models.payroll_engine import (  # noqa: F401
    PayrollAdjustment,
    PayrollLine,
    RuleParameter,
    SalaryRule,
    SalaryStructure,
    WorkEntry,
)
from app.models.platform import (  # noqa: F401
    CustomField,
    CustomFieldValue,
    WorkflowTemplate,
    ReportTemplate,
    ImportMapping,
    IndustryTemplate,
    PdfTemplate,
    CustomRole,
)
from app.models.pricing import PriceList, PriceListItem  # noqa: F401
from app.models.quotation import Quotation, QuotationItem  # noqa: F401
from app.models.payment_term import PaymentTerm  # noqa: F401
from app.models.sales_team import SalesTeam, SalesTeamMember, SalesTarget, CommissionRule, CommissionAccrual  # noqa: F401
from app.models.email_tracking import EmailEvent  # noqa: F401
from app.models.signature import SignatureRequest  # noqa: F401
from app.models.maintenance import (  # noqa: F401
    MaintenanceAsset,
    MaintenanceAssetCategory,
    MaintenanceBudget,
    MaintenanceCertificate,
    MaintenanceChecklist,
    MaintenanceChecklistItem,
    MaintenanceContractor,
    MaintenanceCostRecord,
    MaintenanceIncident,
    MaintenanceLocation,
    MaintenanceMeter,
    MaintenanceNumberingConfig,
    MaintenanceOrder,
    MaintenancePart,
    MaintenancePartRequest,
    MaintenancePlan,
    MaintenancePriority,
    MaintenanceReliabilityMetric,
    MaintenanceRequest,
    MaintenanceSafetyInstruction,
    MaintenanceSLA,
    MaintenanceStatusConfig,
    MaintenanceTeam,
    MaintenanceTeamMember,
    MaintenanceTechnician,
    MaintenanceTool,
    MaintenanceToolIssue,
    MaintenanceWorkPermit,
    MaintenanceWorkType,
    RepairOrder,
)
