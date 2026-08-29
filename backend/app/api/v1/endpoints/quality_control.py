# backend/app/api/v1/endpoints/quality_control.py
"""Quality Control API."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.quality_control import (
    QualityAlert,
    QualityCheck,
    QualityControlPoint,
    QualityTest,
    QualityTestResult,
)
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.quality_control import QualityCheckCreate, QualityCheckResponse, QualityCheckUpdate

router = APIRouter(prefix="/quality-control", tags=["Quality Control"])


@router.get("/", response_model=ResponseBase[PaginatedResponse[QualityCheckResponse]])
async def list_quality_checks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    product_id: UUID | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality-control", "can_access")),
):
    query = select(QualityCheck).where(QualityCheck.company_id == current_user.company_id)
    if product_id:
        query = query.where(QualityCheck.product_id == product_id)
    if status:
        query = query.where(QualityCheck.status == status)
    query = query.order_by(QualityCheck.created_at.desc())

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    items = result.scalars().all()
    return ResponseBase(
        data=PaginatedResponse(
            items=[QualityCheckResponse.model_validate(q) for q in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{check_id:uuid}", response_model=ResponseBase[QualityCheckResponse])
async def get_quality_check(
    check_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality-control", "can_access")),
):
    result = await db.execute(
        select(QualityCheck).where(
            QualityCheck.id == check_id,
            QualityCheck.company_id == current_user.company_id,
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="ხარისხის შემოწმება არ მოიძებნა")
    return ResponseBase(data=QualityCheckResponse.model_validate(check))


@router.post("/", response_model=ResponseBase[QualityCheckResponse], status_code=201)
async def create_quality_check(
    data: QualityCheckCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality-control", "can_create")),
):
    check = QualityCheck(
        company_id=current_user.company_id,
        product_id=data.product_id,
        checked_by=data.checked_by,
        status=data.status,
        notes=data.notes,
        checked_at=data.checked_at,
    )
    db.add(check)
    await db.commit()
    await db.refresh(check)
    return ResponseBase(data=QualityCheckResponse.model_validate(check))


@router.put("/{check_id:uuid}", response_model=ResponseBase[QualityCheckResponse])
async def update_quality_check(
    check_id: UUID,
    data: QualityCheckUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality-control", "can_edit")),
):
    result = await db.execute(
        select(QualityCheck).where(
            QualityCheck.id == check_id,
            QualityCheck.company_id == current_user.company_id,
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="ხარისხის შემოწმება არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(check, field, value)
    await db.commit()
    await db.refresh(check)
    return ResponseBase(data=QualityCheckResponse.model_validate(check))


@router.delete("/{check_id:uuid}", response_model=ResponseBase[dict])
async def delete_quality_check(
    check_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality-control", "can_delete")),
):
    result = await db.execute(
        select(QualityCheck).where(
            QualityCheck.id == check_id,
            QualityCheck.company_id == current_user.company_id,
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="ხარისხის შემოწმება არ მოიძებნა")
    await db.delete(check)
    await db.commit()
    return ResponseBase(data={"id": str(check_id)}, message="ხარისხის შემოწმება წაიშალა")


# ═══════════════════════ Control points ═══════════════════════════════════════

@router.get("/control-points", response_model=ResponseBase[list[dict]])
async def list_control_points(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality", "can_access")),
):
    rows = (await db.execute(
        select(QualityControlPoint).where(QualityControlPoint.company_id == current_user.company_id)
        .order_by(QualityControlPoint.name)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(p.id), "name": p.name, "point_type": p.point_type,
        "product_id": str(p.product_id) if p.product_id else None,
        "operation_id": str(p.operation_id) if p.operation_id else None,
        "is_active": p.is_active,
    } for p in rows])


@router.post("/control-points", response_model=ResponseBase[dict], status_code=201)
async def create_control_point(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality", "can_create")),
):
    cp = QualityControlPoint(
        company_id=current_user.company_id,
        name=data["name"], point_type=data.get("point_type", "receipt"),
        product_id=data.get("product_id"), operation_id=data.get("operation_id"),
        is_active=bool(data.get("is_active", True)),
    )
    db.add(cp)
    await db.commit()
    await db.refresh(cp)
    return ResponseBase(data={"id": str(cp.id), "name": cp.name}, message="კონტროლის წერტილი შეიქმნა")


@router.delete("/control-points/{cp_id}", response_model=ResponseBase[dict])
async def delete_control_point(
    cp_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality", "can_delete")),
):
    cp = (await db.execute(select(QualityControlPoint).where(
        QualityControlPoint.id == cp_id, QualityControlPoint.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not cp:
        raise HTTPException(status_code=404, detail="კონტროლის წერტილი არ მოიძებნა")
    await db.delete(cp)
    await db.commit()
    return ResponseBase(data={"id": str(cp_id)}, message="კონტროლის წერტილი წაიშალა")


# ═══════════════════════ Tests ═══════════════════════════════════════════════

@router.get("/control-points/{cp_id}/tests", response_model=ResponseBase[list[dict]])
async def list_quality_tests(
    cp_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality", "can_access")),
):
    rows = (await db.execute(
        select(QualityTest).where(
            QualityTest.control_point_id == cp_id,
            QualityTest.company_id == current_user.company_id,
        ).order_by(QualityTest.name)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(t.id), "control_point_id": str(t.control_point_id), "name": t.name,
        "test_type": t.test_type, "unit": t.unit,
        "min_value": float(t.min_value) if t.min_value is not None else None,
        "max_value": float(t.max_value) if t.max_value is not None else None,
        "tolerance_percent": float(t.tolerance_percent) if t.tolerance_percent is not None else None,
        "instructions": t.instructions, "is_active": t.is_active,
    } for t in rows])


@router.post("/control-points/{cp_id}/tests", response_model=ResponseBase[dict], status_code=201)
async def create_quality_test(
    cp_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality", "can_create")),
):
    cp = (await db.execute(select(QualityControlPoint).where(
        QualityControlPoint.id == cp_id, QualityControlPoint.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not cp:
        raise HTTPException(status_code=404, detail="კონტროლის წერტილი არ მოიძებნა")
    from decimal import Decimal
    t = QualityTest(
        company_id=current_user.company_id, control_point_id=cp_id,
        name=data["name"], test_type=data.get("test_type", "pass_fail"),
        unit=data.get("unit"),
        min_value=Decimal(str(data["min_value"])) if data.get("min_value") is not None else None,
        max_value=Decimal(str(data["max_value"])) if data.get("max_value") is not None else None,
        tolerance_percent=Decimal(str(data["tolerance_percent"])) if data.get("tolerance_percent") is not None else None,
        instructions=data.get("instructions"), is_active=bool(data.get("is_active", True)),
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return ResponseBase(data={"id": str(t.id), "name": t.name}, message="ტესტი შეიქმნა")


# ═══════════════════════ Test results on a check ══════════════════════════════

@router.post("/checks/{check_id:uuid}/results", response_model=ResponseBase[dict], status_code=201)
async def record_test_result(
    check_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality", "can_edit")),
):
    check = (await db.execute(select(QualityCheck).where(
        QualityCheck.id == check_id, QualityCheck.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="შემოწმება არ მოიძებნა")
    from decimal import Decimal
    test = (await db.execute(select(QualityTest).where(
        QualityTest.id == data["test_id"], QualityTest.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="ტესტი არ მოიძებნა")

    measured = Decimal(str(data["measured_value"])) if data.get("measured_value") is not None else None
    passed = bool(data.get("passed", False))
    if test.test_type == "measure" and measured is not None:
        passed = True
        if test.min_value is not None and measured < test.min_value:
            passed = False
        if test.max_value is not None and measured > test.max_value:
            passed = False
    elif test.test_type == "tolerance" and measured is not None and test.tolerance_percent is not None:
        # tolerance around a nominal (min+max)/2
        nominal = (test.min_value + test.max_value) / 2 if test.min_value is not None and test.max_value is not None else measured
        allowed = nominal * test.tolerance_percent / 100
        passed = abs(measured - nominal) <= allowed

    result = QualityTestResult(
        company_id=current_user.company_id, check_id=check_id, test_id=test.id,
        measured_value=measured, passed=passed, notes=data.get("notes"),
    )
    db.add(result)
    # auto-fail the check if any test fails
    if not passed:
        check.status = QualityCheck.Status.FAIL
        check.checked_at = func.now()
    await db.commit()
    await db.refresh(result)
    return ResponseBase(data={
        "id": str(result.id), "passed": result.passed,
        "measured_value": float(result.measured_value) if result.measured_value is not None else None,
    }, message="შედეგი დაფიქსირდა")


# ═══════════════════════ Quality alerts ═══════════════════════════════════════

@router.get("/alerts", response_model=ResponseBase[list[dict]])
async def list_quality_alerts(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality", "can_access")),
):
    filters = [QualityAlert.company_id == current_user.company_id]
    if status:
        filters.append(QualityAlert.status == status)
    rows = (await db.execute(
        select(QualityAlert).where(*filters).order_by(QualityAlert.created_at.desc()).limit(100)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(a.id), "title": a.title, "source": a.source,
        "product_id": str(a.product_id) if a.product_id else None,
        "priority": a.priority, "status": a.status,
        "assignee_id": str(a.assignee_id) if a.assignee_id else None,
        "description": a.description, "resolution": a.resolution,
        "created_at": a.created_at.isoformat(),
    } for a in rows])


@router.post("/alerts", response_model=ResponseBase[dict], status_code=201)
async def create_quality_alert(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality", "can_create")),
):
    alert = QualityAlert(
        company_id=current_user.company_id,
        title=data["title"], source=data.get("source", "manual"),
        product_id=data.get("product_id"), check_id=data.get("check_id"),
        priority=data.get("priority", "medium"), status="open",
        assignee_id=data.get("assignee_id"), description=data.get("description"),
        created_by=current_user.id,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return ResponseBase(data={"id": str(alert.id)}, message="ხარისხის გაფრთხილება შეიქმნა")


@router.post("/alerts/{alert_id}/resolve", response_model=ResponseBase[dict])
async def resolve_quality_alert(
    alert_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality", "can_edit")),
):
    alert = (await db.execute(select(QualityAlert).where(
        QualityAlert.id == alert_id, QualityAlert.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="გაფრთხილება არ მოიძებნა")
    alert.status = "done"
    alert.resolution = data.get("resolution")
    alert.resolved_at = func.now()
    await db.commit()
    return ResponseBase(data={"id": str(alert_id), "status": "done"}, message="გაფრთხილება დახურულია")


# ═══════════════════════ Barcode scanning ═════════════════════════════════════

@router.post("/scan", response_model=ResponseBase[dict])
async def scan_barcode(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality", "can_create")),
):
    """Odoo-style barcode scan: find the product by barcode/SKU/GTIN and
    auto-create a pending quality check for it."""
    from app.models.product import Product

    code = (data.get("barcode") or "").strip()
    if not code:
        raise HTTPException(status_code=422, detail="ბარკოდი არ არის მითითებული")

    product = (await db.execute(select(Product).where(
        Product.company_id == current_user.company_id,
        (Product.barcode == code) | (Product.sku == code) | (Product.gtin == code),
    ))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=f"პროდუქტი ბარკოდით '{code}' არ მოიძებნა")

    # auto-create a pending check for the scanned product
    check = QualityCheck(
        company_id=current_user.company_id,
        product_id=product.id,
        barcode=code,
        checked_by=current_user.id,
        status=QualityCheck.Status.PENDING,
    )
    db.add(check)
    await db.commit()
    await db.refresh(check)
    return ResponseBase(data={
        "check_id": str(check.id),
        "product_id": str(product.id),
        "product_name": product.name,
        "sku": product.sku,
        "barcode": code,
        "status": check.status,
    }, message="პროდუქტი დასკანერდა — შემოწმება შეიქმნა")
