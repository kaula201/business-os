import pytest
from decimal import Decimal

from app.api.v1.endpoints.ecommerce import _host_without_port
from app.models.company import Company
from app.models.ecommerce import EcomCategory, EcomProduct
from app.models.product import Product



def test_host_without_port():
    assert _host_without_port("[::1]:8000") == "::1"
    assert _host_without_port("[::1]") == "::1"
    assert _host_without_port("example.com:443") == "example.com"
    assert _host_without_port("example.com") == "example.com"
    assert _host_without_port("::1") == "::1"


@pytest.mark.asyncio
async def test_storefront_tenant_isolation(client, test_company, other_company, db_session):
    session = db_session
    company_a = await session.get(Company, test_company.id)
    company_b = await session.get(Company, other_company.id)
    company_a.storefront_slug = "shop-a"
    company_b.storefront_slug = "shop-b"
    company_a.storefront_domain = "shop-a.example"
    await session.flush()

    for comp, prefix in [(company_a, "A"), (company_b, "B")]:
        product = Product(
            company_id=comp.id,
            name=f"Product {prefix}",
            sku=f"SKU-{prefix}",
        )
        session.add(product)
        await session.flush()

        category = EcomCategory(
            company_id=comp.id,
            name=f"Category {prefix}",
            slug=f"category-{prefix.lower()}",
            is_active=True,
        )
        session.add(category)
        await session.flush()

        ecom = EcomProduct(
            company_id=comp.id,
            product_id=product.id,
            category_id=category.id,
            name=f"Ecom Product {prefix}",
            slug=f"ecom-product-{prefix.lower()}",
            price=Decimal("10.00"),
            is_published=True,
            stock_quantity=1,
        )
        session.add(ecom)
        await session.flush()

    await session.commit()

    # Slug resolution for products
    response = await client.get("/api/v1/ecommerce/storefront/shop-a/products")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Ecom Product A"

    response = await client.get("/api/v1/ecommerce/storefront/shop-b/products")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Ecom Product B"

    # Categories for shop-a list only A's category with product_count 1.
    response = await client.get("/api/v1/ecommerce/storefront/shop-a/categories")
    assert response.status_code == 200
    categories = response.json()["data"]
    assert len(categories) == 1
    assert categories[0]["name"] == "Category A"
    assert categories[0]["product_count"] == 1

    # Unknown slug -> 404
    response = await client.get("/api/v1/ecommerce/storefront/unknown-shop/products")
    assert response.status_code == 404

    # Unknown Host -> 404
    response = await client.get("/api/v1/ecommerce/storefront/products", headers={"host": "nope.example"})
    assert response.status_code == 404

    # Domain resolution for A
    response = await client.get(
        "/api/v1/ecommerce/storefront/products",
        headers={"host": "shop-a.example"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Ecom Product A"
