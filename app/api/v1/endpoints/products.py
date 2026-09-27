from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_, func
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Product, Commerce, User
from app.schemas.schemas import ProductCreate, ProductUpdate, ProductResponse

router = APIRouter(prefix="/products", tags=["Marketplace Products"])


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new marketplace product attached to a commerce."""
    # Verify commerce exists
    comm_result = await db.execute(
        select(Commerce).where(Commerce.id == data.commerce_id)
    )
    commerce = comm_result.scalar_one_or_none()
    if not commerce:
        raise HTTPException(status_code=404, detail="Commerce introuvable")

    # Inherit location from commerce if requested or missing
    lat = data.latitude if (data.latitude is not None and not data.is_same_location_as_commerce) else commerce.latitude
    lng = data.longitude if (data.longitude is not None and not data.is_same_location_as_commerce) else commerce.longitude

    product = Product(
        commerce_id=data.commerce_id,
        name=data.name,
        description=data.description,
        price_fcfa=data.price_fcfa,
        category=data.category or "Autre",
        condition=data.condition or "Neuf",
        unit=data.unit or "Pièce",
        stock=data.stock if data.stock is not None else 1,
        cover_photo=data.cover_photo or (data.photos[0] if data.photos else None),
        photos=data.photos or [],
        latitude=lat,
        longitude=lng,
        is_same_location_as_commerce=data.is_same_location_as_commerce,
        status=data.status or "en_ligne",
        is_active=True,
        created_by=current_user.id,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)

    res = ProductResponse.model_validate(product)
    res.commerce_name = commerce.name
    return res


@router.get("/", response_model=List[ProductResponse])
async def list_products(
    commerce_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List products with optional search and filters."""
    query = select(Product, Commerce.name.label("commerce_name")).join(
        Commerce, Product.commerce_id == Commerce.id, isouter=True
    ).where(Product.is_active == True)

    if commerce_id:
        query = query.where(Product.commerce_id == commerce_id)
    if category and category != "Tous":
        query = query.where(func.lower(Product.category) == category.lower())
    if status:
        query = query.where(Product.status == status)
    if q and q.strip():
        search_term = f"%{q.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Product.name).like(search_term),
                func.lower(Product.description).like(search_term),
                func.lower(Commerce.name).like(search_term),
            )
        )

    query = query.order_by(desc(Product.created_at)).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    items = []
    for product, comm_name in rows:
        resp = ProductResponse.model_validate(product)
        resp.commerce_name = comm_name
        items.append(resp)

    return items


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get single product details."""
    query = select(Product, Commerce.name.label("commerce_name")).join(
        Commerce, Product.commerce_id == Commerce.id, isouter=True
    ).where(Product.id == product_id)

    result = await db.execute(query)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    product, comm_name = row
    resp = ProductResponse.model_validate(product)
    resp.commerce_name = comm_name
    return resp


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    data: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a product."""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(product, key, value)

    await db.commit()
    await db.refresh(product)

    # Fetch commerce name
    comm_result = await db.execute(select(Commerce.name).where(Commerce.id == product.commerce_id))
    comm_name = comm_result.scalar_one_or_none()

    resp = ProductResponse.model_validate(product)
    resp.commerce_name = comm_name
    return resp


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def delete_product(
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate or remove a product."""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    product.is_active = False
    product.status = "desactive"
    await db.commit()
    return {"message": "Produit désactivé avec succès"}
