"""Document Management API: categories, documents, version history, approval workflow, audit trail."""
import os
import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.documents import DocumentCategory, Document, DocumentVersion, DocumentApproval
from app.models.audit import AuditLog
from app.schemas.common import ResponseBase, PaginatedResponse
from app.schemas.documents import (
    DocumentCategoryCreate, DocumentCategoryResponse, DocumentCategoryUpdate,
    DocumentCategoryTreeResponse,
    DocumentCreate, DocumentResponse, DocumentUpdate,
    DocumentVersionCreate, DocumentVersionResponse,
    DocumentSubmitForApproval, DocumentApprovalAction, DocumentPublishAction,
    DocumentApprovalResponse,
    FileUploadPolicy,
    DocumentAuditLogResponse,
)

router = APIRouter(prefix="/documents", tags=["დოკუმენტები"])

# ── Helpers ─────────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS_DEFAULT = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "jpg", "jpeg", "png", "gif", "svg", "webp",
    "txt", "csv", "json", "xml",
    "zip", "rar", "7z",
}
BLOCKED_EXTENSIONS = {
    "exe", "bat", "cmd", "com", "msi", "scr", "vbs",
    "js", "vba", "ps1", "sh", "bin", "dll", "sys",
}
MAX_FILE_SIZE_DEFAULT = 50 * 1024 * 1024  # 50 MB


def _get_file_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lower().lstrip(".")


def _validate_file_upload(filename: str, file_size: int, category: DocumentCategory | None = None):
    """Validate file upload against security rules."""
    ext = _get_file_extension(filename)

    # Block dangerous extensions unconditionally
    if ext in BLOCKED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"ფაილის ტიპი '{ext}' აკრძალულია უსაფრთხოების მიზეზების გამო",
        )

    # Check category-level allowed extensions
    if category and category.allowed_extensions:
        allowed = {e.strip().lower() for e in category.allowed_extensions.split(",")}
        if ext not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"ფაილის ტიპი '{ext}' არ არის დაშვებული ამ კატეგორიაში. დაშვებულია: {', '.join(sorted(allowed))}",
            )
    else:
        # Default allowed extensions
        if ext and ext not in ALLOWED_EXTENSIONS_DEFAULT:
            raise HTTPException(
                status_code=400,
                detail=f"ფაილის ტიპი '{ext}' არ არის დაშვებული",
            )

    # Check file size
    max_size = MAX_FILE_SIZE_DEFAULT
    if category and category.max_file_size:
        max_size = category.max_file_size

    if file_size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"ფაილის ზომა აღემატება დაშვებულ ლიმიტს ({max_size_mb:.0f} MB)",
        )


def _check_category_access(category: DocumentCategory, current_user: User):
    """Check if user's role is allowed to access this category."""
    if not category.access_roles:
        return  # no restriction
    allowed_roles = {r.strip() for r in category.access_roles.split(",")}
    if current_user.role not in allowed_roles and current_user.role != User.Role.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="ამ კატეგორიაზე წვდომა არ გაქვთ",
        )


async def _log_audit(
    db: AsyncSession,
    company_id: UUID,
    user_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    details: str | None = None,
):
    db.add(AuditLog(
        company_id=company_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    ))


async def _compute_category_path(db: AsyncSession, category: DocumentCategory) -> str:
    """Compute materialized path for a category."""
    parts = [category.name]
    current = category
    while current.parent_id:
        result = await db.execute(
            select(DocumentCategory).where(DocumentCategory.id == current.parent_id)
        )
        parent = result.scalar_one_or_none()
        if not parent:
            break
        parts.insert(0, parent.name)
        current = parent
    return "/" + "/".join(parts)


async def _build_category_tree(
    db: AsyncSession,
    company_id: UUID,
    parent_id: UUID | None = None,
) -> list[dict]:
    """Build nested category tree."""
    query = (
        select(DocumentCategory)
        .where(
            DocumentCategory.company_id == company_id,
            DocumentCategory.is_active == True,
            DocumentCategory.parent_id == parent_id,
        )
        .order_by(DocumentCategory.sort_order, DocumentCategory.name)
    )
    result = await db.execute(query)
    categories = result.scalars().all()

    tree = []
    for cat in categories:
        # Count children
        child_count_q = select(func.count()).select_from(
            select(DocumentCategory)
            .where(
                DocumentCategory.company_id == company_id,
                DocumentCategory.is_active == True,
                DocumentCategory.parent_id == cat.id,
            )
            .subquery()
        )
        child_count = (await db.execute(child_count_q)).scalar() or 0

        # Count documents
        doc_count_q = select(func.count()).select_from(
            select(Document)
            .where(
                Document.company_id == company_id,
                Document.category_id == cat.id,
                Document.is_archived == False,
            )
            .subquery()
        )
        doc_count = (await db.execute(doc_count_q)).scalar() or 0

        children = await _build_category_tree(db, company_id, cat.id)

        tree.append(DocumentCategoryTreeResponse(
            **cat.__dict__,
            children_count=child_count,
            document_count=doc_count,
            children=children,
        ))

    return tree


# ── File Upload Policy ─────────────────────────────────────────────────────────

@router.get("/upload-policy", response_model=ResponseBase[FileUploadPolicy])
async def get_upload_policy(
    current_user: User = Depends(require_module("documents", "can_access")),
):
    """Get the file upload security policy."""
    return ResponseBase(data=FileUploadPolicy())


# ── Categories ──────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=ResponseBase[list[DocumentCategoryResponse]])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_access")),
):
    result = await db.execute(
        select(DocumentCategory)
        .where(DocumentCategory.company_id == current_user.company_id, DocumentCategory.is_active == True)
        .order_by(DocumentCategory.sort_order, DocumentCategory.code)
    )
    categories = result.scalars().all()

    items = []
    for cat in categories:
        child_count_q = select(func.count()).select_from(
            select(DocumentCategory).where(
                DocumentCategory.parent_id == cat.id,
                DocumentCategory.is_active == True,
            ).subquery()
        )
        child_count = (await db.execute(child_count_q)).scalar() or 0

        doc_count_q = select(func.count()).select_from(
            select(Document).where(
                Document.category_id == cat.id,
                Document.is_archived == False,
            ).subquery()
        )
        doc_count = (await db.execute(doc_count_q)).scalar() or 0

        resp = DocumentCategoryResponse.model_validate(cat)
        resp.children_count = child_count
        resp.document_count = doc_count
        items.append(resp)

    return ResponseBase(data=items)


@router.get("/categories/tree", response_model=ResponseBase[list[DocumentCategoryTreeResponse]])
async def list_categories_tree(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_access")),
):
    """Get categories as a nested tree for folder hierarchy UI."""
    tree = await _build_category_tree(db, current_user.company_id, parent_id=None)
    return ResponseBase(data=tree)


@router.get("/categories/{cat_id}", response_model=ResponseBase[DocumentCategoryResponse])
async def get_category(
    cat_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_access")),
):
    result = await db.execute(
        select(DocumentCategory).where(
            DocumentCategory.id == cat_id,
            DocumentCategory.company_id == current_user.company_id,
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="კატეგორია არ მოიძებნა")

    child_count_q = select(func.count()).select_from(
        select(DocumentCategory).where(
            DocumentCategory.parent_id == cat.id,
            DocumentCategory.is_active == True,
        ).subquery()
    )
    child_count = (await db.execute(child_count_q)).scalar() or 0

    doc_count_q = select(func.count()).select_from(
        select(Document).where(
            Document.category_id == cat.id,
            Document.is_archived == False,
        ).subquery()
    )
    doc_count = (await db.execute(doc_count_q)).scalar() or 0

    resp = DocumentCategoryResponse.model_validate(cat)
    resp.children_count = child_count
    resp.document_count = doc_count
    return ResponseBase(data=resp)


@router.post("/categories", response_model=ResponseBase[DocumentCategoryResponse], status_code=201)
async def create_category(
    data: DocumentCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_create")),
):
    existing = await db.execute(
        select(DocumentCategory).where(
            DocumentCategory.company_id == current_user.company_id,
            DocumentCategory.code == data.code,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="კატეგორიის კოდი უკვე არსებობს")

    # Validate parent exists if set
    if data.parent_id:
        parent_result = await db.execute(
            select(DocumentCategory).where(
                DocumentCategory.id == data.parent_id,
                DocumentCategory.company_id == current_user.company_id,
            )
        )
        if not parent_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="მშობელი კატეგორია არ მოიძებნა")

    cat = DocumentCategory(company_id=current_user.company_id, **data.model_dump())
    db.add(cat)
    await db.flush()

    # Compute path and level
    cat.path = await _compute_category_path(db, cat)
    if data.parent_id:
        parent_result = await db.execute(
            select(DocumentCategory).where(DocumentCategory.id == data.parent_id)
        )
        parent = parent_result.scalar_one_or_none()
        cat.level = (parent.level + 1) if parent else 0

    await db.flush()
    await db.refresh(cat)

    await _log_audit(
        db, current_user.company_id, current_user.id,
        "document_category.created", "document_category", cat.id,
        f"შეიქმნა კატეგორია: {cat.name} ({cat.code})",
    )

    resp = DocumentCategoryResponse.model_validate(cat)
    return ResponseBase(data=resp)


@router.patch("/categories/{cat_id}", response_model=ResponseBase[DocumentCategoryResponse])
async def update_category(
    cat_id: UUID,
    data: DocumentCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_edit")),
):
    result = await db.execute(
        select(DocumentCategory).where(
            DocumentCategory.id == cat_id,
            DocumentCategory.company_id == current_user.company_id,
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="კატეგორია არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    old_name = cat.name

    # Validate parent change
    if "parent_id" in update_data and update_data["parent_id"] is not None:
        if update_data["parent_id"] == cat.id:
            raise HTTPException(status_code=400, detail="კატეგორია არ შეიძლება იყოს საკუთარი მშობელი")
        parent_result = await db.execute(
            select(DocumentCategory).where(
                DocumentCategory.id == update_data["parent_id"],
                DocumentCategory.company_id == current_user.company_id,
            )
        )
        if not parent_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="მშობელი კატეგორია არ მოიძებნა")

    for field, value in update_data.items():
        setattr(cat, field, value)

    # Recompute path if name or parent changed
    if "name" in update_data or "parent_id" in update_data:
        cat.path = await _compute_category_path(db, cat)
        if cat.parent_id:
            parent_result = await db.execute(
                select(DocumentCategory).where(DocumentCategory.id == cat.parent_id)
            )
            parent = parent_result.scalar_one_or_none()
            cat.level = (parent.level + 1) if parent else 0
        else:
            cat.level = 0

    await db.flush()
    await db.refresh(cat)

    await _log_audit(
        db, current_user.company_id, current_user.id,
        "document_category.updated", "document_category", cat.id,
        f"განახლდა კატეგორია: {old_name} → {cat.name}",
    )

    resp = DocumentCategoryResponse.model_validate(cat)
    return ResponseBase(data=resp)


@router.delete("/categories/{cat_id}", response_model=ResponseBase[dict])
async def delete_category(
    cat_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_delete")),
):
    result = await db.execute(
        select(DocumentCategory).where(
            DocumentCategory.id == cat_id,
            DocumentCategory.company_id == current_user.company_id,
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="კატეგორია არ მოიძებნა")

    # Check for children
    child_q = select(DocumentCategory).where(DocumentCategory.parent_id == cat.id)
    child_result = await db.execute(child_q)
    if child_result.scalars().first():
        raise HTTPException(status_code=400, detail="კატეგორიას გააჩნია ქვეკატეგორიები. ჯერ წაშალეთ ისინი")

    # Move documents to uncategorized
    doc_q = select(Document).where(Document.category_id == cat.id)
    doc_result = await db.execute(doc_q)
    for doc in doc_result.scalars().all():
        doc.category_id = None

    cat_name = cat.name
    await db.delete(cat)
    await db.flush()

    await _log_audit(
        db, current_user.company_id, current_user.id,
        "document_category.deleted", "document_category", cat_id,
        f"წაიშალა კატეგორია: {cat_name}",
    )

    return ResponseBase(data=dict(message="კატეგორია წაიშალა"))


# ── Documents ────────────────────────────────────────────────────────────────────

@router.get("/", response_model=ResponseBase[PaginatedResponse[DocumentResponse]])
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: UUID | None = None,
    document_type: str | None = None,
    approval_status: str | None = None,
    search: str | None = None,
    is_archived: bool | None = False,
    sort_by: str | None = Query(None, pattern="^(created_at|updated_at|title|file_size|version)$"),
    sort_order: str | None = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_access")),
):
    query = select(Document).where(Document.company_id == current_user.company_id)

    if is_archived is not None:
        query = query.where(Document.is_archived == is_archived)
    if category_id:
        query = query.where(Document.category_id == category_id)
    if document_type:
        query = query.where(Document.document_type == document_type)
    if approval_status:
        query = query.where(Document.approval_status == approval_status)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            Document.title.ilike(term)
            | Document.tags.ilike(term)
            | Document.filename.ilike(term)
            | Document.description.ilike(term)
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    # Sorting
    sort_col = getattr(Document, sort_by, Document.created_at) if sort_by else Document.created_at
    order_fn = sort_col.desc() if sort_order == "desc" else sort_col.asc()
    query = query.options(joinedload(Document.category)).order_by(order_fn)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    docs = result.unique().scalars().all()

    items = []
    for doc in docs:
        resp = DocumentResponse.model_validate(doc)
        resp.category_name = doc.category.name if doc.category else None
        if doc.uploaded_by:
            user_result = await db.execute(select(User).where(User.id == doc.uploaded_by))
            user = user_result.scalar_one_or_none()
            resp.uploaded_by_name = user.full_name if user else None
        items.append(resp)

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.post("/", response_model=ResponseBase[DocumentResponse], status_code=201)
async def create_document(
    data: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_create")),
):
    # Validate category access and file upload rules
    cat = None
    if data.category_id:
        cat_result = await db.execute(
            select(DocumentCategory).where(
                DocumentCategory.id == data.category_id,
                DocumentCategory.company_id == current_user.company_id,
            )
        )
        cat = cat_result.scalar_one_or_none()
        if not cat:
            raise HTTPException(status_code=404, detail="კატეგორია არ მოიძებნა")
        _check_category_access(cat, current_user)

    # File upload security validation
    _validate_file_upload(data.filename, data.file_size, cat)

    # Compute checksum if not provided
    checksum = data.checksum
    if not checksum and data.file_path and os.path.isfile(data.file_path):
        try:
            with open(data.file_path, "rb") as f:
                checksum = hashlib.sha256(f.read()).hexdigest()
        except (OSError, IOError):
            pass

    # Determine retention
    retention_days = data.retention_days
    if retention_days is None and cat and cat.retention_days:
        retention_days = cat.retention_days

    doc = Document(
        company_id=current_user.company_id,
        uploaded_by=current_user.id,
        **data.model_dump(exclude={"checksum", "retention_days"}),
    )
    if retention_days:
        doc.retention_days = retention_days
        from datetime import datetime, timedelta, timezone
        doc.expires_at = datetime.now(timezone.utc) + timedelta(days=retention_days)

    db.add(doc)
    await db.flush()

    # Create initial version
    version = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        filename=doc.filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        file_path=doc.file_path,
        checksum=checksum,
        is_current=True,
        change_summary="თავდაპირველი ვერსია",
        uploaded_by=current_user.id,
    )
    db.add(version)
    await db.flush()
    await db.refresh(doc)

    if doc.category_id and cat:
        cat_result = await db.execute(select(DocumentCategory).where(DocumentCategory.id == doc.category_id))
        cat = cat_result.scalar_one_or_none()

    await _log_audit(
        db, current_user.company_id, current_user.id,
        "document.created", "document", doc.id,
        f"აიტვირთა დოკუმენტი: {doc.title} ({doc.filename})",
    )

    resp = DocumentResponse.model_validate(doc)
    resp.category_name = cat.name if doc.category_id and cat else None
    if doc.uploaded_by:
        user_result = await db.execute(select(User).where(User.id == doc.uploaded_by))
        user = user_result.scalar_one_or_none()
        resp.uploaded_by_name = user.full_name if user else None
    return ResponseBase(data=resp)


@router.get("/{doc_id}", response_model=ResponseBase[DocumentResponse])
async def get_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_access")),
):
    result = await db.execute(
        select(Document)
        .where(Document.id == doc_id, Document.company_id == current_user.company_id)
        .options(joinedload(Document.category))
    )
    doc = result.unique().scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    resp = DocumentResponse.model_validate(doc)
    resp.category_name = doc.category.name if doc.category else None
    if doc.uploaded_by:
        user_result = await db.execute(select(User).where(User.id == doc.uploaded_by))
        user = user_result.scalar_one_or_none()
        resp.uploaded_by_name = user.full_name if user else None
    return ResponseBase(data=resp)


@router.patch("/{doc_id}", response_model=ResponseBase[DocumentResponse])
async def update_document(
    doc_id: UUID,
    data: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_edit")),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == current_user.company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    # Cannot edit approved/published documents
    if doc.approval_status in (Document.ApprovalStatus.APPROVED, Document.ApprovalStatus.PUBLISHED):
        raise HTTPException(status_code=400, detail="დამტკიცებული/გამოქვეყნებული დოკუმენტის რედაქტირება შეუძლებელია")

    update_data = data.model_dump(exclude_unset=True)

    # If changing category, validate access
    if "category_id" in update_data and update_data["category_id"] is not None:
        cat_result = await db.execute(
            select(DocumentCategory).where(
                DocumentCategory.id == update_data["category_id"],
                DocumentCategory.company_id == current_user.company_id,
            )
        )
        cat = cat_result.scalar_one_or_none()
        if not cat:
            raise HTTPException(status_code=404, detail="კატეგორია არ მოიძებნა")
        _check_category_access(cat, current_user)

    for field, value in update_data.items():
        setattr(doc, field, value)
    await db.flush()
    await db.refresh(doc)

    if doc.category_id:
        cat_result = await db.execute(select(DocumentCategory).where(DocumentCategory.id == doc.category_id))
        cat = cat_result.scalar_one_or_none()

    await _log_audit(
        db, current_user.company_id, current_user.id,
        "document.updated", "document", doc.id,
        f"განახლდა დოკუმენტი: {doc.title}",
    )

    resp = DocumentResponse.model_validate(doc)
    resp.category_name = cat.name if doc.category_id and cat else None
    if doc.uploaded_by:
        user_result = await db.execute(select(User).where(User.id == doc.uploaded_by))
        user = user_result.scalar_one_or_none()
        resp.uploaded_by_name = user.full_name if user else None
    return ResponseBase(data=resp)


@router.delete("/{doc_id}", response_model=ResponseBase[dict])
async def archive_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_delete")),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == current_user.company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    doc.is_archived = True
    await db.flush()

    await _log_audit(
        db, current_user.company_id, current_user.id,
        "document.archived", "document", doc.id,
        f"დარქივდა დოკუმენტი: {doc.title}",
    )

    return ResponseBase(data=dict(message="დოკუმენტი დარქივებულია"))


@router.delete("/{doc_id}/permanent", response_model=ResponseBase[dict])
async def permanent_delete_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_delete")),
):
    """Permanently delete a document and all its versions. Audit-logged destructive action."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == current_user.company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    doc_title = doc.title
    doc_filename = doc.filename

    # Delete versions
    await db.execute(
        select(DocumentVersion).where(DocumentVersion.document_id == doc_id)
    )
    await db.execute(
        select(DocumentApproval).where(DocumentApproval.document_id == doc_id)
    )

    await db.delete(doc)
    await db.flush()

    await _log_audit(
        db, current_user.company_id, current_user.id,
        "document.permanently_deleted", "document", doc_id,
        f"სამუდამოდ წაიშალა დოკუმენტი: {doc_title} ({doc_filename})",
    )

    return ResponseBase(data=dict(message="დოკუმენტი სამუდამოდ წაიშალა"))


# ── Versions ────────────────────────────────────────────────────────────────────

@router.get("/{doc_id}/versions", response_model=ResponseBase[list[DocumentVersionResponse]])
async def list_versions(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_access")),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == current_user.company_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    ver_result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version_number.desc())
    )
    versions = ver_result.scalars().all()

    items = []
    for v in versions:
        resp = DocumentVersionResponse.model_validate(v)
        if v.uploaded_by:
            user_result = await db.execute(select(User).where(User.id == v.uploaded_by))
            user = user_result.scalar_one_or_none()
            resp.uploaded_by_name = user.full_name if user else None
        items.append(resp)

    return ResponseBase(data=items)


@router.post("/{doc_id}/versions", response_model=ResponseBase[DocumentVersionResponse], status_code=201)
async def create_version(
    doc_id: UUID,
    data: DocumentVersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_create")),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == current_user.company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    # File upload security
    cat = None
    if doc.category_id:
        cat_result = await db.execute(select(DocumentCategory).where(DocumentCategory.id == doc.category_id))
        cat = cat_result.scalar_one_or_none()
    _validate_file_upload(data.filename, data.file_size, cat)

    # Compute checksum
    checksum = data.checksum
    if not checksum and data.file_path and os.path.isfile(data.file_path):
        try:
            with open(data.file_path, "rb") as f:
                checksum = hashlib.sha256(f.read()).hexdigest()
        except (OSError, IOError):
            pass

    # Mark current version as not current
    await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == doc_id,
            DocumentVersion.is_current == True,
        )
    )
    current_ver_result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == doc_id,
            DocumentVersion.is_current == True,
        )
    )
    for old_ver in current_ver_result.scalars().all():
        old_ver.is_current = False

    # Create new version
    new_version_number = doc.version + 1
    version = DocumentVersion(
        document_id=doc_id,
        version_number=new_version_number,
        filename=data.filename,
        file_size=data.file_size,
        mime_type=data.mime_type,
        file_path=data.file_path,
        checksum=checksum,
        change_summary=data.change_summary,
        is_current=True,
        notes=data.notes,
        uploaded_by=current_user.id,
    )
    db.add(version)

    # Update document
    doc.filename = data.filename
    doc.file_size = data.file_size
    doc.mime_type = data.mime_type
    doc.file_path = data.file_path
    doc.version = new_version_number

    await db.flush()
    await db.refresh(version)

    await _log_audit(
        db, current_user.company_id, current_user.id,
        "document.version_created", "document_version", version.id,
        f"შეიქმნა ვერსია #{new_version_number} დოკუმენტისთვის: {doc.title}",
    )

    resp = DocumentVersionResponse.model_validate(version)
    if version.uploaded_by:
        user_result = await db.execute(select(User).where(User.id == version.uploaded_by))
        user = user_result.scalar_one_or_none()
        resp.uploaded_by_name = user.full_name if user else None
    return ResponseBase(data=resp)


@router.get("/{doc_id}/versions/{version_id}", response_model=ResponseBase[DocumentVersionResponse])
async def get_version(
    doc_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_access")),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == current_user.company_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    ver_result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == doc_id,
        )
    )
    version = ver_result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="ვერსია არ მოიძებნა")

    resp = DocumentVersionResponse.model_validate(version)
    if version.uploaded_by:
        user_result = await db.execute(select(User).where(User.id == version.uploaded_by))
        user = user_result.scalar_one_or_none()
        resp.uploaded_by_name = user.full_name if user else None
    return ResponseBase(data=resp)


@router.post("/{doc_id}/versions/{version_id}/restore", response_model=ResponseBase[DocumentVersionResponse])
async def restore_version(
    doc_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_edit")),
):
    """Restore a previous version as the current version."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == current_user.company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    ver_result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == doc_id,
        )
    )
    old_version = ver_result.scalar_one_or_none()
    if not old_version:
        raise HTTPException(status_code=404, detail="ვერსია არ მოიძებნა")

    # Mark current version as not current
    current_ver_result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == doc_id,
            DocumentVersion.is_current == True,
        )
    )
    for cur_ver in current_ver_result.scalars().all():
        cur_ver.is_current = False

    # Create new version from old version's data
    new_version_number = doc.version + 1
    version = DocumentVersion(
        document_id=doc_id,
        version_number=new_version_number,
        filename=old_version.filename,
        file_size=old_version.file_size,
        mime_type=old_version.mime_type,
        file_path=old_version.file_path,
        checksum=old_version.checksum,
        change_summary=f"აღდგენილია ვერსიიდან #{old_version.version_number}",
        is_current=True,
        uploaded_by=current_user.id,
    )
    db.add(version)

    # Update document
    doc.filename = old_version.filename
    doc.file_size = old_version.file_size
    doc.mime_type = old_version.mime_type
    doc.file_path = old_version.file_path
    doc.version = new_version_number

    await db.flush()
    await db.refresh(version)

    await _log_audit(
        db, current_user.company_id, current_user.id,
        "document.version_restored", "document_version", version.id,
        f"აღდგენილია ვერსია #{old_version.version_number} → #{new_version_number} დოკუმენტისთვის: {doc.title}",
    )

    resp = DocumentVersionResponse.model_validate(version)
    if version.uploaded_by:
        user_result = await db.execute(select(User).where(User.id == version.uploaded_by))
        user = user_result.scalar_one_or_none()
        resp.uploaded_by_name = user.full_name if user else None
    return ResponseBase(data=resp)


# ── Approval Workflow ───────────────────────────────────────────────────────────

@router.post("/{doc_id}/submit-for-approval", response_model=ResponseBase[DocumentResponse])
async def submit_document_for_approval(
    doc_id: UUID,
    data: DocumentSubmitForApproval,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_create")),
):
    """Submit a draft document for approval."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == current_user.company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    if doc.approval_status != Document.ApprovalStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail=f"დოკუმენტის სტატუსია '{doc.approval_status}'. მხოლოდ DRAFT დოკუმენტის წარდგენა შეიძლება დამტკიცებაზე",
        )

    doc.approval_status = Document.ApprovalStatus.PENDING
    from datetime import datetime, timezone
    doc.submitted_for_approval_at = datetime.now(timezone.utc)
    await db.flush()

    # Create approval trail entry
    approval = DocumentApproval(
        document_id=doc_id,
        company_id=current_user.company_id,
        submitted_by=current_user.id,
        action="submitted",
        notes=data.notes,
    )
    db.add(approval)
    await db.flush()

    await _log_audit(
        db, current_user.company_id, current_user.id,
        "document.submitted_for_approval", "document", doc.id,
        f"წარდგენილია დამტკიცებაზე: {doc.title}",
    )

    await db.refresh(doc)
    resp = DocumentResponse.model_validate(doc)
    resp.category_name = doc.category.name if doc.category else None
    return ResponseBase(data=resp)


@router.post("/{doc_id}/approve", response_model=ResponseBase[DocumentResponse])
async def approve_document(
    doc_id: UUID,
    data: DocumentApprovalAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_approve")),
):
    """Approve or reject a document pending approval."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == current_user.company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    if doc.approval_status != Document.ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"დოკუმენტის სტატუსია '{doc.approval_status}'. მხოლოდ PENDING დოკუმენტის დამტკიცება/უარყოფა შეიძლება",
        )

    if data.action == "approved":
        doc.approval_status = Document.ApprovalStatus.APPROVED
    else:
        doc.approval_status = Document.ApprovalStatus.REJECTED

    doc.approved_by = current_user.id
    from datetime import datetime, timezone
    doc.approved_at = datetime.now(timezone.utc)
    doc.approval_notes = data.notes
    await db.flush()

    # Create approval trail entry
    approval = DocumentApproval(
        document_id=doc_id,
        company_id=current_user.company_id,
        submitted_by=doc.uploaded_by or current_user.id,
        reviewed_by=current_user.id,
        action=data.action,
        notes=data.notes,
    )
    db.add(approval)
    await db.flush()

    action_label = "დამტკიცდა" if data.action == "approved" else "უარყოფილ იქნა"
    await _log_audit(
        db, current_user.company_id, current_user.id,
        f"document.{data.action}", "document", doc.id,
        f"{action_label} დოკუმენტი: {doc.title}",
    )

    await db.refresh(doc)
    resp = DocumentResponse.model_validate(doc)
    resp.category_name = doc.category.name if doc.category else None
    return ResponseBase(data=resp)


@router.post("/{doc_id}/publish", response_model=ResponseBase[DocumentResponse])
async def publish_document(
    doc_id: UUID,
    data: DocumentPublishAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_approve")),
):
    """Publish an approved document."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == current_user.company_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    if doc.approval_status != Document.ApprovalStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"დოკუმენტის სტატუსია '{doc.approval_status}'. მხოლოდ APPROVED დოკუმენტის გამოქვეყნება შეიძლება",
        )

    doc.approval_status = Document.ApprovalStatus.PUBLISHED
    await db.flush()

    # Create approval trail entry
    approval = DocumentApproval(
        document_id=doc_id,
        company_id=current_user.company_id,
        submitted_by=doc.uploaded_by or current_user.id,
        reviewed_by=current_user.id,
        action="published",
        notes=data.notes,
    )
    db.add(approval)
    await db.flush()

    await _log_audit(
        db, current_user.company_id, current_user.id,
        "document.published", "document", doc.id,
        f"გამოქვეყნდა დოკუმენტი: {doc.title}",
    )

    await db.refresh(doc)
    resp = DocumentResponse.model_validate(doc)
    resp.category_name = doc.category.name if doc.category else None
    return ResponseBase(data=resp)


@router.get("/{doc_id}/approval-history", response_model=ResponseBase[list[DocumentApprovalResponse]])
async def get_approval_history(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_access")),
):
    """Get the approval workflow history for a document."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == current_user.company_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    approval_result = await db.execute(
        select(DocumentApproval)
        .where(DocumentApproval.document_id == doc_id)
        .order_by(DocumentApproval.created_at.desc())
    )
    approvals = approval_result.scalars().all()

    items = []
    for a in approvals:
        resp = DocumentApprovalResponse.model_validate(a)
        if a.submitted_by:
            user_result = await db.execute(select(User).where(User.id == a.submitted_by))
            user = user_result.scalar_one_or_none()
            resp.submitted_by_name = user.full_name if user else None
        if a.reviewed_by:
            user_result = await db.execute(select(User).where(User.id == a.reviewed_by))
            user = user_result.scalar_one_or_none()
            resp.reviewed_by_name = user.full_name if user else None
        items.append(resp)

    return ResponseBase(data=items)


# ── Audit Trail ─────────────────────────────────────────────────────────────────

@router.get("/{doc_id}/audit-log", response_model=ResponseBase[list[DocumentAuditLogResponse]])
async def get_document_audit_log(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_access")),
):
    """Get audit trail for a specific document."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.company_id == current_user.company_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="დოკუმენტი არ მოიძებნა")

    audit_result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.company_id == current_user.company_id,
            AuditLog.entity_type.in_(["document", "document_version"]),
            AuditLog.entity_id == doc_id,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )
    logs = audit_result.scalars().all()

    items = []
    for log in logs:
        resp = DocumentAuditLogResponse.model_validate(log)
        if log.user_id:
            user_result = await db.execute(select(User).where(User.id == log.user_id))
            user = user_result.scalar_one_or_none()
            resp.user_name = user.full_name if user else None
        items.append(resp)

    return ResponseBase(data=items)


@router.get("/audit-log", response_model=ResponseBase[PaginatedResponse[DocumentAuditLogResponse]])
async def list_document_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_access")),
):
    """Get the full document audit trail across all documents."""
    query = select(AuditLog).where(
        AuditLog.company_id == current_user.company_id,
        AuditLog.entity_type.in_(["document", "document_version", "document_category"]),
    )
    if action:
        query = query.where(AuditLog.action == action)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.scalars().all()

    items = []
    for log in logs:
        resp = DocumentAuditLogResponse.model_validate(log)
        if log.user_id:
            user_result = await db.execute(select(User).where(User.id == log.user_id))
            user = user_result.scalar_one_or_none()
            resp.user_name = user.full_name if user else None
        items.append(resp)

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


# ── Retention / Expiry ─────────────────────────────────────────────────────────

@router.get("/expired", response_model=ResponseBase[list[DocumentResponse]])
async def list_expired_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("documents", "can_access")),
):
    """List documents that have passed their retention expiry date."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Document)
        .where(
            Document.company_id == current_user.company_id,
            Document.expires_at.isnot(None),
            Document.expires_at <= now,
            Document.is_archived == False,
        )
        .order_by(Document.expires_at)
    )
    docs = result.scalars().all()

    items = []
    for doc in docs:
        resp = DocumentResponse.model_validate(doc)
        resp.category_name = doc.category.name if doc.category else None
        items.append(resp)

    return ResponseBase(data=items)
