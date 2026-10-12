"""Unit tests for bundle‑dependency constraints in the module catalog (no DB)."""

from seed_modules import MODULES
from app.core.modules import BASE_MODULE_CODES

# v3.0 bundle -> codes, mirrors frontend Sidebar.tsx SCOPE_CODES until tech spec v3.0 is committed
BUNDLES = {
    "DASH": {"dashboard"},
    "CRM": {"crm"},
    "SAL": {"quotations", "orders", "invoices", "price-lists"},
    "WMS": {"wms", "inventory", "inventory-valuation"},
    "MFG": {"production"},
    "TMS": {"fleet"},
    "MNT": {"maintenance"},
    "FIN": {
        "cash",
        "banking",
        "banking-rules",
        "currency",
        "customer-finance",
        "supplier-finance",
        "expenses",
        "assets",
    },
    "ACC": {
        "gl",
        "journal-entries",
        "trial-balance",
        "profit-loss",
        "balance-sheet",
        "srs",
        "budgeting",
        "analytic",
        "deferred",
        "accounting-periods",
        "gl-recurring",
        "exchange-differences",
        "consolidated",
        "accounting-controls",
    },
    "TASK": {"tasks", "projects"},
    "HELPDESK": {"helpdesk"},
    "DOC": {"documents"},
    "RPT": {"reports"},
    "AI": {"ai"},
}

# Known exception: helpdesk depends on tasks (issue #9)
KNOWN_EXCEPTIONS = {("helpdesk", "tasks")}


def _module_map():
    return {code: (name, desc, icon, route, category, sort_order, depends_on)
            for code, name, desc, icon, route, category, sort_order, depends_on in MODULES}


def test_depends_on_target_exists():
    """Every non‑None depends_on must reference an existing module code."""
    mod_map = _module_map()
    missing = []
    for code, _, _, _, _, _, _, dep in MODULES:
        if dep is not None and dep not in mod_map:
            missing.append((code, dep))
    assert missing == [], f"depends_on targets not found: {missing}"


def test_bundle_definitions_are_consistent():
    """Bundle codes must exist, not overlap, and exclude base modules."""
    mod_map = _module_map()
    all_codes = set(mod_map)
    seen = set()
    duplicates = set()
    missing = []
    for bundle, codes in BUNDLES.items():
        for code in codes:
            if code not in all_codes:
                missing.append((bundle, code))
            if code in seen:
                duplicates.add(code)
            seen.add(code)
    base_in_bundle = [code for code in seen if code in BASE_MODULE_CODES]
    assert missing == [], f"Bundle contains unknown module codes: {missing}"
    assert duplicates == set(), f"Duplicate module codes across bundles: {duplicates}"
    assert base_in_bundle == [], f"Base module codes must not be in any bundle: {base_in_bundle}"


def test_depends_on_respects_bundle_boundaries():
    """For in‑scope modules, depends_on must be within the same bundle or base."""
    mod_map = _module_map()
    code_to_bundle = {}
    for bundle, codes in BUNDLES.items():
        for code in codes:
            code_to_bundle[code] = bundle

    violations = []
    for code in code_to_bundle:
        dep = mod_map[code][6]  # depends_on is the last element of the tuple
        if dep is None:
            continue
        if (code, dep) in KNOWN_EXCEPTIONS:
            continue
        if dep in BASE_MODULE_CODES:
            continue
        if dep in code_to_bundle and code_to_bundle[dep] == code_to_bundle[code]:
            continue
        violations.append((code, dep))

    assert violations == [], (
        "depends_on crosses bundle boundaries:\n"
        + "\n".join(f"  {code} -> {dep}" for code, dep in violations)
    )


def test_known_exceptions_still_exist_in_modules():
    """Ensure KNOWN_EXCEPTIONS edges are still present (remove when issue #9 is fixed)."""
    mod_map = _module_map()
    missing = []
    for code, dep in KNOWN_EXCEPTIONS:
        if code not in mod_map or mod_map[code][6] != dep:
            missing.append((code, dep))
    assert missing == [], (
        "KNOWN_EXCEPTIONS no longer match actual depends_on; "
        "remove the exception if the dependency was changed/fixed: "
        f"{missing}"
    )
