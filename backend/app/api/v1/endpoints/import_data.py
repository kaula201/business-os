"""Excel import endpoints — upload .xlsx files to bulk-create records."""
import io
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.client import Client
from app.models.product import Product, ProductCategory
from app.schemas.common import ResponseBase, MessageResponse
from app.utils.excel_import import parse_excel_upload, safe_str, safe_float, safe_int

router = APIRouter(prefix="/import", tags=["იმპორტი"])


@router.post("/clients", response_model=ResponseBase[MessageResponse])
async def import_clients(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("clients", "can_create")),
):
    """Import clients from Excel (.xlsx). Expected columns: name, identification_code, phone, email, address, notes."""
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="გთხოვთ ატვირთოთ Excel ფაილი (.xlsx)")

    content = await file.read()
    expected = ["name", "identification_code", "phone", "email", "address", "notes"]
    aliases = {
        "name": ["სახელი", "დასახელება", "კომპანია"],
        "identification_code": ["საიდენტიფიკაციო კოდი", "საგადასახადო კოდი", "კოდი"],
        "phone": ["ტელეფონი", "მობილური"],
        "email": ["ელ.ფოსტა", "იმეილი"],
        "address": ["მისამართი"],
        "notes": ["შენიშვნა", "კომენტარი"],
    }
    try:
        rows = parse_excel_upload(content, expected, aliases)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    created = 0
    errors = []
    for i, row in enumerate(rows, 1):
        name = safe_str(row.get("name"))
        if not name:
            errors.append(f"ხაზი {i}: სახელი ცარიელია")
            continue
        try:
            client = Client(
                company_id=current_user.company_id,
                name=name,
                client_type="legal",
                identification_code=safe_str(row.get("identification_code")),
                phone=safe_str(row.get("phone")),
                email=safe_str(row.get("email")),
                address=safe_str(row.get("address")),
                notes=safe_str(row.get("notes")),
                created_by=current_user.id,
            )
            db.add(client)
            created += 1
        except Exception as e:
            errors.append(f"ხაზი {i}: {str(e)}")

    await db.flush()

    msg = f"წარმატებით იმპორტირებულია {created} კლიენტი"
    if errors:
        msg += f". შეცდომები: {'; '.join(errors[:5])}"
        if len(errors) > 5:
            msg += f" (+ {len(errors) - 5} სხვა)"

    return ResponseBase(data=MessageResponse(message=msg))


@router.post("/products", response_model=ResponseBase[MessageResponse])
async def import_products(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    """Import products from Excel (.xlsx). Expected columns: sku, name, category_name, unit, sale_price, purchase_price, min_stock, current_stock."""
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="გთხოვთ ატვირთოთ Excel ფაილი (.xlsx)")

    content = await file.read()
    expected = ["sku", "name", "category", "unit", "sale_price", "purchase_price", "min_stock", "current_stock"]
    aliases = {
        "sku": ["არტიკული", "კოდი"],
        "name": ["სახელი", "დასახელება"],
        "category": ["კატეგორია"],
        "unit": ["ერთეული"],
        "sale_price": ["გასაყიდი ფასი", "ფასი"],
        "purchase_price": ["შესყიდვის ფასი", "თვითღირებულება"],
        "min_stock": ["მინიმალური მარაგი"],
        "current_stock": ["მიმდინარე მარაგი", "რაოდენობა"],
    }
    try:
        rows = parse_excel_upload(content, expected, aliases)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Cache categories
    cat_result = await db.execute(
        select(ProductCategory).where(ProductCategory.company_id == current_user.company_id)
    )
    categories = {c.name.lower(): c for c in cat_result.scalars().all()}

    created = 0
    errors = []
    for i, row in enumerate(rows, 1):
        name = safe_str(row.get("name"))
        sku = safe_str(row.get("sku"))
        if not name:
            errors.append(f"ხაზი {i}: სახელი ცარიელია")
            continue
        if not sku:
            errors.append(f"ხაზი {i}: SKU ცარიელია")
            continue

        # Resolve category
        category_id = None
        cat_name = safe_str(row.get("category"))
        if cat_name:
            cat_key = cat_name.lower()
            if cat_key in categories:
                category_id = categories[cat_key].id
            else:
                # Auto-create category
                new_cat = ProductCategory(company_id=current_user.company_id, name=cat_name)
                db.add(new_cat)
                await db.flush()
                categories[cat_key] = new_cat
                category_id = new_cat.id

        try:
            product = Product(
                company_id=current_user.company_id,
                sku=sku,
                name=name,
                category_id=category_id,
                unit=safe_str(row.get("unit")) or "ცალი",
                sale_price=safe_float(row.get("sale_price")) or 0,
                purchase_price=safe_float(row.get("purchase_price")),
                min_stock=safe_int(row.get("min_stock")) or 0,
                current_stock=safe_int(row.get("current_stock")) or 0,
            )
            db.add(product)
            created += 1
        except Exception as e:
            errors.append(f"ხაზი {i}: {str(e)}")

    await db.flush()

    msg = f"წარმატებით იმპორტირებულია {created} პროდუქტი"
    if errors:
        msg += f". შეცდომები: {'; '.join(errors[:5])}"
        if len(errors) > 5:
            msg += f" (+ {len(errors) - 5} სხვა)"

    return ResponseBase(data=MessageResponse(message=msg))
