"""Seed the AppModule catalog with all existing Business OS modules.

Run:  docker exec -i business_os_backend python /app/seed_modules.py
"""
import asyncio
from sqlalchemy import select, text
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
    ("wms",           "საწყობის მართვა (WMS)",    "Warehouse management (WMS)",  "Boxes",           "/wms",          "operations", 56,  "inventory"),
    ("helpdesk",      "Helpdesk",                   "Tickets, SLA, knowledge base","LifeBuoy",        "/helpdesk",     "operations", 57,  "tasks"),
    ("integrations",  "ინტეგრაციები",               "API keys, webhooks, RS.ge",   "Plug",            "/integrations", "operations", 58,  "settings"),
    ("payments",      "გადახდები",                   "Payment gateway",             "CreditCard",      "/payments",     "operations", 59,  "invoices"),
    ("email-calendar","ელ.ფოსტა და კალენდარი",       "Email send, calendar events",  "Mail",            "/email-calendar","operations", 60,  "tasks"),
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
FINANCIAL_MODULES = {"cash", "banking", "currency", "gl", "journal-entries", "trial-balance", "profit-loss", "balance-sheet", "expenses", "assets", "customer-finance", "supplier-finance", "srs", "budgeting", "analytic", "deferred", "accounting-periods", "gl-recurring", "exchange-differences", "consolidated", "banking-rules"}

# Operational modules where manager gets create/edit
OPERATIONAL_MODULES = {"clients", "orders", "invoices", "inventory", "tasks", "purchases", "suppliers", "fleet", "crm", "quotations", "price-lists", "sales-teams", "email-tracking", "subscriptions", "customer-portal", "wms", "helpdesk", "integrations", "payments", "email-calendar", "procurement", "pos", "hr"}


async def seed_modules():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM module_permissions"))
        await conn.execute(text("DELETE FROM company_modules"))
        await conn.execute(text("DELETE FROM app_modules"))

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        for code, name, desc, icon, route, category, sort_order, depends_on in MODULES:
            mod = AppModule(
                code=code,
                name=name,
                description=desc,
                icon=icon,
                route=route,
                category=category,
                sort_order=sort_order,
                depends_on=depends_on,
            )
            session.add(mod)
            await session.flush()

            # Create default permissions for each role
            for role, perms in DEFAULT_PERMISSIONS.items():
                p = ModulePermission(
                    module_id=mod.id,
                    role=role,
                    **perms,
                )
                session.add(p)

            # Override: accountant gets create/edit on financial modules
            if code in FINANCIAL_MODULES:
                existing = await session.execute(
                    select(ModulePermission).where(
                        ModulePermission.module_id == mod.id,
                        ModulePermission.role == User.Role.ACCOUNTANT,
                    )
                )
                perm = existing.scalar_one_or_none()
                if perm:
                    perm.can_create = True
                    perm.can_edit = True

                # Financial writes are admin/accountant only: strip write
                # permissions from manager on financial modules.
                mgr_existing = await session.execute(
                    select(ModulePermission).where(
                        ModulePermission.module_id == mod.id,
                        ModulePermission.role == User.Role.MANAGER,
                    )
                )
                mgr_perm = mgr_existing.scalar_one_or_none()
                if mgr_perm:
                    mgr_perm.can_create = False
                    mgr_perm.can_edit = False
                    mgr_perm.can_delete = False
                    mgr_perm.can_approve = False

            # Override: manager gets approve on operational modules
            if code in OPERATIONAL_MODULES:
                existing = await session.execute(
                    select(ModulePermission).where(
                        ModulePermission.module_id == mod.id,
                        ModulePermission.role == User.Role.MANAGER,
                    )
                )
                perm = existing.scalar_one_or_none()
                if perm:
                    perm.can_approve = True

        await session.commit()

    await engine.dispose()
    print(f"✅ Seeded {len(MODULES)} modules with default permissions.")


if __name__ == "__main__":
    asyncio.run(seed_modules())
