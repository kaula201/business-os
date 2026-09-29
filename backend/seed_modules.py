"""Seed the AppModule catalog with all existing Business OS modules.

Idempotent: inserts modules and role permissions that are missing.
Does not delete ``app_modules``, ``company_modules``, or existing
permission rows, so company toggles survive a second run.

Run:  docker exec -i business_os_backend python /app/seed_modules.py
"""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings
from app.models.module import AppModule, ModulePermission
from app.models.user import User

MODULES = [
    # (code, name, description, icon, route, category, sort_order, depends_on)
    ("dashboard",     "Dashboard",          "მთავარი სამუშაო მაგიდა",          "LayoutDashboard",  "/dashboard",     "main",       0,  None),
    ("crm",           "CRM",                "ლიდები, გაყიდვების pipeline",     "Target",           "/crm",           "sales",      10,  None),
    ("clients",       "კლიენტების რეესტრი","მომხმარებელთა მონაცემთა ბაზა",    "Users",            "/clients",       "sales",      20,  None),
    ("orders",        "გაყიდვის შეკვეთები", "Sales orders",                    "ShoppingCart",     "/orders",        "sales",      30,  "clients"),
    ("invoices",      "გაყიდვის ინვოისები", "Invoicing",                       "ReceiptText",      "/invoices",      "sales",      40,  "orders"),
    ("inventory",     "საწყობი",            "Warehouse & stock",                "Package",          "/inventory",     "operations", 50,  None),
    ("tasks",         "დავალებები",         "Task management",                  "CheckSquare",      "/tasks",         "operations", 60,  None),
    ("documents",     "დოკუმენტები",        "Document management",               "FileText",         "/documents",     "operations", 61,  None),
    ("production",    "წარმოება",            "BOM & work orders",                "Factory",          "/production",    "operations", 62,  "inventory"),
    ("maintenance",   "Maintenance",         "Equipment maintenance & work orders", "Wrench",        "/maintenance",  "operations", 63,  "production"),
    ("projects",      "პროექტები",           "Project management",               "FolderKanban",     "/projects",      "operations", 63,  "tasks"),
    ("kitchen",       "სამზარეულო (KDS)",    "Kitchen display system",           "ChefHat",          "/kitchen",       "tools",      64,  "pos"),
    ("purchases",     "შესყიდვები",         "Purchase orders",                  "ShoppingCart",     "/purchases",     "purchases",  70,  None),
    ("suppliers",     "მომწოდებლები",       "Supplier registry",                "Building2",        "/suppliers",     "purchases",  80,  None),
    ("supplier-finance","მომწოდებლის ფინანსები","Supplier payables & payments","Building2",        "/supplier-finance","purchases", 90,  "suppliers"),
    ("cash",          "სალარო",             "Cash accounts & transactions",      "DollarSign",       "/cash",          "finance",   100,  None),
    ("banking",       "საბანკო",            "Bank accounts & reconciliation",   "Landmark",         "/banking",       "finance",   110,  None),
    ("currency",      "ვალუტის კურსები",   "Currency rates",                   "Coins",            "/currency",      "finance",   120,  None),
    ("customer-finance","კლიენტის ფინანსები","Receivables & payments",         "WalletCards",      "/customer-finance","finance", 130,  "invoices"),
    ("expenses",      "ხარჯები",            "Expense tracking",                 "DollarSign",       "/expenses",      "finance",   140,  None),
    ("assets",        "ძირითადი საშუალებები","Fixed assets & depreciation",     "Wrench",           "/assets",        "finance",   150,  None),
    ("gl",            "ანგარიშთა გეგმა",    "Chart of accounts",               "BookOpen",         "/chart-of-accounts","accounting",160, None),
    ("journal-entries","საჟურნალო ჩანაწერები","Journal entries",                "FileText",         "/journal-entries","accounting",170, "gl"),
    ("trial-balance", "საცდელი ბალანსი",    "Trial balance report",            "BarChart3",        "/trial-balance", "accounting",180, "gl"),
    ("profit-loss",   "მოგება-ზარალი",      "P&L statement",                   "TrendingUp",       "/profit-loss",   "accounting",190, "gl"),
    ("balance-sheet", "ბალანსი",            "Balance sheet",                    "Scale",            "/balance-sheet", "accounting",200, "gl"),
    ("srs",           "SRS ანგარიშგება",    "SRS reporting",                   "FileText",         "/srs",           "accounting",210, "gl"),
    ("budgeting",     "ბიუჯეტირება",        "Budget planning",                  "Target",           "/budgeting",     "accounting",220, None),
    ("analytic",      "ანალიტიკური აღრიცხვა","Analytic accounting",           "Network",          "/analytic-accounting","accounting",230, "gl"),
    ("deferred",      "გადავადებული ოპერაციები","Deferred operations",        "CalendarClock",    "/deferred",      "accounting",240, "gl"),
    ("accounting-periods","სააღრიცხვო პერიოდები","Accounting periods",       "CalendarRange",    "/accounting-periods","accounting",250, None),
    ("gl-recurring",   "განმეორებადი ჩანაწერები", "Recurring journal entries",  "CalendarClock",    "/gl-recurring",  "accounting",255, "gl"),
    ("exchange-differences","საკურსო სხვაობები", "FX revaluation",            "TrendingDown",     "/gl-exchange-differences","accounting",256, "gl"),
    ("consolidated",   "კონსოლიდირებული ანგარიშები","Multi-company reports", "Scale",            "/gl-consolidated","accounting",257, "gl"),
    ("banking-rules",  "შეჯერების წესები",        "Reconciliation rules",      "Landmark",         "/banking-rules", "finance",   115,  "banking"),
    ("inventory-valuation","მარაგების შეფასება", "WAC valuation",             "Package",          "/inventory-valuation","operations",55, "inventory"),
    ("quotations",     "კომერციული შემოთავაზებები","Quotations (convert to order)", "FileText",      "/quotations",    "sales",     45,  "clients"),
    ("price-lists",    "ფასების სიები",            "Price lists & payment terms","Tags",           "/price-lists",   "sales",     46,  "products"),
    ("sales-teams",    "გაყიდვების გუნდები",       "Teams, targets, commissions","Users",          "/sales-teams",   "sales",     47,  None),
    ("email-tracking", "ელ.ფოსტა და ხელმოწერები",  "Email tracking & e-signature","Mail",          "/email-tracking","sales",     48,  None),
    ("subscriptions",  "გამოწერები",               "Recurring subscriptions",     "RefreshCw",       "/subscriptions", "sales",     49,  "invoices"),
    ("customer-portal","კლიენტის პორტალი",          "Customer portal users",       "Globe",           "/customer-portal","sales",    50,  "clients"),
    ("vendor-portal",  "მომწოდებლის პორტალი",        "Vendor portal users",         "Globe",           "/vendor-portal", "purchases", 51,  "suppliers"),
    ("wms",           "საწყობის მართვა (WMS)",    "Warehouse management (WMS)",  "Boxes",           "/wms",          "operations", 56,  "inventory"),
    ("helpdesk",      "Helpdesk / მხარდაჭერა",       "Tickets, SLA, knowledge base","LifeBuoy",        "/helpdesk",     "operations", 57,  "tasks"),
    ("integrations",  "ინტეგრაციები",               "API keys, webhooks, RS.ge",   "Plug",            "/integrations", "operations", 58,  "settings"),
    ("payments",      "გადახდები",                   "Payment gateway",             "CreditCard",      "/payments",     "operations", 59,  "invoices"),
    ("email-calendar","ელ.ფოსტა და კალენდარი",       "Email send, calendar events",  "Mail",            "/email-calendar","operations", 60,  "tasks"),
    ("security",      "უსაფრთხოება",                 "2FA, login history, RBAC",    "Shield",          "/security",     "operations", 61,  "settings"),
    ("automations",   "ავტომატიზაცია",               "Trigger → action rules",      "Zap",             "/automations",  "operations", 62,  "settings"),
    ("email-marketing", "ელ. მარკეტინგი",            "Campaigns, send, stats",      "Mail",            "/ecommerce",    "sales",     63,  "email-tracking"),
    ("studio",        "No-code Studio",              "Custom apps & forms",         "LayoutGrid",      "/studio",       "tools",      64,  "settings"),
    ("platform-studio", "პლატფორმა — სტუდია",          "Fields, workflows, reports",  "Settings2",     "/platform-studio", "tools",      641, "settings"),
    ("marketplace",   "Marketplace",                 "App catalog & installs",      "Store",           "/marketplace",  "tools",      65,  "integrations"),
    ("field-service", "საველე სამუშაოები",           "Field service jobs",          "Wrench",          "/field-service","tools",      66,  "helpdesk"),
    ("quality",       "ხარისხის კონტროლი",            "Control points, tests, alerts","BadgeCheck",     "/quality",      "tools",      67,  "production"),
    ("accounting-controls", "ბუღალტრული კონტროლები",  "Fiscal, mapping, FX",         "BookOpenCheck",   "/accounting-controls", "accounting", 120, "consolidated"),
    ("procurement",   "შესყიდვები — Procurement", "RFQ, pricelists, blanket",   "ShoppingCart",    "/procurement",  "purchases", 60,  "suppliers"),
    ("pos",           "სალარო (POS)",              "Cashier, shifts, checks",   "ShoppingCart",    "/pos",          "sales",     51,  "inventory"),
    ("hr",            "HR / ადამიანური რესურსები",   "Employees, payroll, leave", "Users",           "/hr",           "other",     250,  None),
    ("fleet",         "ავტოპარკი",          "Vehicle fleet management",        "Car",              "/fleet",         "fleet",     260,  None),
    ("reports",       "რეპორტები",           "Reports & analytics",             "BarChart3",        "/reports",       "other",     270,  None),
    ("ai",            "AI ასისტენტი",       "AI chat & RAG",                   "Bot",              "/ai",            "other",     280,  None),
    ("settings",      "პარამეტრები",         "Company settings",                "Settings",         "/settings",      "other",     290,  None),
]

# Default permissions per role
DEFAULT_PERMISSIONS = {
    User.Role.ADMIN:     {"can_access": True, "can_create": True, "can_edit": True, "can_delete": True, "can_approve": True},
    User.Role.MANAGER:   {"can_access": True, "can_create": True, "can_edit": True, "can_delete": True, "can_approve": False},
    User.Role.ACCOUNTANT:{"can_access": True, "can_create": False, "can_edit": False, "can_delete": False, "can_approve": False},
    User.Role.EMPLOYEE:  {"can_access": True, "can_create": False, "can_edit": False, "can_delete": False, "can_approve": False},
}

# Financial modules where accountant gets create/edit
FINANCIAL_MODULES = {"cash", "banking", "currency", "gl", "journal-entries", "trial-balance", "profit-loss", "balance-sheet", "expenses", "assets", "customer-finance", "supplier-finance", "srs", "budgeting", "analytic", "deferred", "accounting-periods", "gl-recurring", "exchange-differences", "consolidated", "banking-rules", "accounting-controls"}

# Operational modules where manager gets create/edit
OPERATIONAL_MODULES = {"clients", "orders", "invoices", "inventory", "tasks", "purchases", "suppliers", "fleet", "crm", "quotations", "price-lists", "sales-teams", "email-tracking", "subscriptions", "customer-portal", "vendor-portal", "wms", "helpdesk", "integrations", "payments", "email-calendar", "security", "automations", "email-marketing", "studio", "platform-studio", "marketplace", "field-service", "quality", "procurement", "pos", "hr"}


def permission_flags(code: str, role: str) -> dict:
    """Default permission row for a new (module, role) pair."""
    flags = dict(DEFAULT_PERMISSIONS[role])
    if code in FINANCIAL_MODULES and role == User.Role.ACCOUNTANT:
        flags["can_create"] = True
        flags["can_edit"] = True
    if code in FINANCIAL_MODULES and role == User.Role.MANAGER:
        flags["can_create"] = False
        flags["can_edit"] = False
        flags["can_delete"] = False
        flags["can_approve"] = False
    if code in OPERATIONAL_MODULES and role == User.Role.MANAGER:
        flags["can_approve"] = True
    return flags


async def seed_modules(engine=None) -> int:
    """Insert missing catalog rows. Returns the number of modules in the catalog.

    ``engine`` is the caller's async engine (the migrate superuser, or omit
    it to use ``DATABASE_URL``, which in production is ``business_os_app``).
    """
    own_engine = engine is None
    if own_engine:
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            existing = {
                code: module_id
                for code, module_id in (await session.execute(select(AppModule.code, AppModule.id))).all()
            }
            present = {
                (module_id, role)
                for module_id, role in (
                    await session.execute(select(ModulePermission.module_id, ModulePermission.role))
                ).all()
            }
            for code, name, desc, icon, route, category, sort_order, depends_on in MODULES:
                module_id = existing.get(code)
                if module_id is None:
                    module = AppModule(
                        code=code,
                        name=name,
                        description=desc,
                        icon=icon,
                        route=route,
                        category=category,
                        sort_order=sort_order,
                        depends_on=depends_on,
                    )
                    session.add(module)
                    await session.flush()
                    module_id = module.id
                    existing[code] = module_id
                for role in DEFAULT_PERMISSIONS:
                    if (module_id, role) in present:
                        continue
                    session.add(
                        ModulePermission(
                            module_id=module_id,
                            role=role,
                            **permission_flags(code, role),
                        )
                    )
                    present.add((module_id, role))
            await session.commit()
            return len(existing)
    finally:
        if own_engine:
            await engine.dispose()


if __name__ == "__main__":
    count = asyncio.run(seed_modules())
    print(f"Module catalog has {count} rows.")
