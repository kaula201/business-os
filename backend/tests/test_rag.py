"""RAG indexing regression tests."""
import uuid

from sqlalchemy import func, select
import pytest

from app.models.embedding import Embedding
from app.services.rag import _get_embedding, _local_embedding, index_company_data, search_similar


@pytest.mark.asyncio
async def test_reindex_creates_rows_with_generated_ids(db_session, test_company):
    count = await index_company_data(db_session, test_company.id)
    await db_session.flush()

    stored = await db_session.scalar(
        select(func.count()).select_from(Embedding).where(
            Embedding.company_id == test_company.id
        )
    )
    assert stored == count

    rows = (
        await db_session.execute(
            select(Embedding).where(Embedding.company_id == test_company.id)
        )
    ).scalars().all()
    assert all(row.id is not None for row in rows)
    assert all(row.embedding is not None for row in rows)


@pytest.mark.asyncio
async def test_reindex_replaces_existing_company_index(db_session, test_company):
    first = await index_company_data(db_session, test_company.id)
    second = await index_company_data(db_session, test_company.id)
    await db_session.flush()

    stored = await db_session.scalar(
        select(func.count()).select_from(Embedding).where(
            Embedding.company_id == test_company.id
        )
    )
    assert second == first
    assert stored == second


@pytest.mark.asyncio
async def test_pgvector_search_returns_most_similar_company_document(
    db_session, test_company, monkeypatch
):
    vector_a = [1.0] + [0.0] * 1535
    vector_b = [0.0, 1.0] + [0.0] * 1534
    db_session.add_all([
        Embedding(
            company_id=test_company.id,
            content_type="product",
            content_id=test_company.id,
            content_text="ლეპტოპი საწყობშია",
            embedding=vector_a,
        ),
        Embedding(
            company_id=test_company.id,
            content_type="client",
            content_id=test_company.id,
            content_text="კლიენტის საკონტაქტო ინფორმაცია",
            embedding=vector_b,
        ),
    ])
    await db_session.flush()

    async def fake_query_embedding(_query: str):
        return vector_a

    monkeypatch.setattr("app.services.rag._get_embedding", fake_query_embedding)
    results = await search_similar(db_session, test_company.id, "ლეპტოპი", limit=1)

    assert len(results) == 1
    assert results[0]["type"] == "product"
    assert results[0]["text"] == "ლეპტოპი საწყობშია"
    assert results[0]["similarity"] == 1.0


@pytest.mark.asyncio
async def test_local_embedding_is_deterministic_and_nonzero():
    first = await _get_embedding("ლეპტოპი საწყობშია")
    second = await _get_embedding("ლეპტოპი საწყობშია")

    assert first == second
    assert first is not None
    assert len(first) == 1536
    assert any(value != 0 for value in first)


@pytest.mark.asyncio
async def test_chat_uses_local_rag_without_openai(
    client, auth_headers, test_company, db_session, monkeypatch
):
    monkeypatch.setattr(
        "app.api.v1.endpoints.ai.settings.OPENAI_API_KEY", None
    )
    query = "რომელია უნიკალური RAG პროდუქტი?"
    marker = "უნიკალური RAG პროდუქტი: საწყობის სპეციალური სკანერი"
    db_session.add(Embedding(
        company_id=test_company.id,
        content_type="product",
        content_id=uuid.uuid4(),
        content_text=marker,
        embedding=_local_embedding(query),
    ))
    await db_session.commit()

    response = await client.post(
        "/api/v1/ai/chat",
        json={"message": query},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert marker in response.json()["data"]["message"]
