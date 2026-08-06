# backend/tests/conftest.py
import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.company import Company
from app.models.user import User

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://business_os_app:business_os_app@postgres:5432/business_os_test",
)

test_database_name = make_url(TEST_DATABASE_URL).database or ""
if not test_database_name.endswith("_test"):
    raise RuntimeError(
        "Refusing to run destructive tests against a non-test database. "
        "TEST_DATABASE_URL must point to a database whose name ends with '_test'."
    )

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db
# Production rate limiting must not make the deterministic test suite order-dependent.
app.state.limiter.enabled = False


@pytest_asyncio.fixture
async def setup_db():
    async with test_engine.begin() as conn:
        # Use CASCADE to handle circular FK dependencies (departments ↔ employees)
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        # pgvector is installed once in a durable `extensions` schema because
        # this fixture recreates `public` for every test. Keep both schemas on
        # the connection search path so Base.metadata can create VECTOR columns.
        await conn.execute(text("SET LOCAL search_path TO public, extensions"))
        await conn.run_sync(Base.metadata.create_all)
        # Mirror migration 062: enable Row-Level Security on every table that
        # carries company_id, so tests exercise the same tenant isolation the
        # production database has.
        await conn.execute(text(
            """
            DO $$
            DECLARE
                t TEXT;
            BEGIN
                FOR t IN
                    SELECT table_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND column_name = 'company_id'
                    ORDER BY table_name
                LOOP
                    EXECUTE format(
                        'CREATE POLICY tenant_isolation ON %I '
                        'USING ('
                        '  current_setting(''app.current_company_id'', true) IS NULL '
                        '  OR current_setting(''app.current_company_id'', true) = '''' '
                        '  OR company_id::text = current_setting(''app.current_company_id'', true)'
                        ')',
                        t
                    );
                    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
                    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
                END LOOP;
            END
            $$;
            """
        ))
    yield
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))


@pytest_asyncio.fixture
async def client(setup_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session(setup_db):
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_company(setup_db):
    async with TestSessionLocal() as session:
        company = Company(
            name="Test Company",
            identification_code="TEST-001",
            vat_status=True,
            currency="GEL",
        )
        session.add(company)
        await session.commit()
        await session.refresh(company)
        # Seed default GL accounts so GL posting hooks work
        from app.services.gl_posting import seed_default_accounts
        await seed_default_accounts(session, company.id)
        await session.commit()
        return company


@pytest_asyncio.fixture
async def test_admin(test_company):
    async with TestSessionLocal() as session:
        admin = User(
            company_id=test_company.id,
            email="admin@test.ge",
            hashed_password=hash_password("admin123"),
            full_name="Test Admin",
            role=User.Role.ADMIN,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin


@pytest_asyncio.fixture
async def auth_headers(client, test_admin):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_admin.email, "password": "admin123"},
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_employee(test_company):
    async with TestSessionLocal() as session:
        employee = User(
            company_id=test_company.id,
            email="employee@test.ge",
            hashed_password=hash_password("employee123"),
            full_name="Test Employee",
            role=User.Role.EMPLOYEE,
            is_active=True,
        )
        session.add(employee)
        await session.commit()
        await session.refresh(employee)
        return employee


@pytest_asyncio.fixture
async def employee_auth_headers(client, test_employee):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_employee.email, "password": "employee123"},
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def other_company(setup_db):
    async with TestSessionLocal() as session:
        company = Company(
            name="Other Company",
            identification_code="OTHER-001",
            vat_status=True,
            currency="GEL",
        )
        session.add(company)
        await session.commit()
        await session.refresh(company)
        return company


@pytest_asyncio.fixture
async def other_admin(other_company):
    async with TestSessionLocal() as session:
        admin = User(
            company_id=other_company.id,
            email="admin@other.ge",
            hashed_password=hash_password("admin123"),
            full_name="Other Admin",
            role=User.Role.ADMIN,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin


@pytest_asyncio.fixture
async def other_auth_headers(client, other_admin):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": other_admin.email, "password": "admin123"},
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
