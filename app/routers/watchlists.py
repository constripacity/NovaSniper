"""
NovaSniper v2.0 Watchlists Router
Named collections of tracked products
"""
import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Watchlist, WatchlistItem, TrackedProduct, User
from app.schemas import (
    WatchlistCreate, WatchlistUpdate, WatchlistResponse, WatchlistWithItems,
    WatchlistItemAdd, WatchlistItemResponse
)
from app.utils.auth import get_current_user_required

router = APIRouter(prefix="/watchlists", tags=["Watchlists"])


def generate_share_code() -> str:
    """Generate a unique share code"""
    return secrets.token_urlsafe(12)


@router.get("", response_model=List[WatchlistResponse])
async def list_watchlists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    List user's watchlists
    """
    watchlists = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id
    ).all()
    
    # Add item counts
    result = []
    for wl in watchlists:
        wl_dict = {
            "id": wl.id,
            "user_id": wl.user_id,
            "name": wl.name,
            "description": wl.description,
            "is_public": wl.is_public,
            "share_code": wl.share_code,
            "created_at": wl.created_at,
            "updated_at": wl.updated_at,
            "items_count": len(wl.items),
        }
        result.append(WatchlistResponse(**wl_dict))
    
    return result


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    watchlist_in: WatchlistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Create a new watchlist
    """
    # Check for duplicate name
    existing = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.name == watchlist_in.name,
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Watchlist with this name already exists"
        )
    
    watchlist = Watchlist(
        user_id=current_user.id,
        name=watchlist_in.name,
        description=watchlist_in.description,
        is_public=watchlist_in.is_public,
        share_code=generate_share_code() if watchlist_in.is_public else None,
    )
    
    db.add(watchlist)
    db.commit()
    db.refresh(watchlist)
    
    return WatchlistResponse(
        id=watchlist.id,
        user_id=watchlist.user_id,
        name=watchlist.name,
        description=watchlist.description,
        is_public=watchlist.is_public,
        share_code=watchlist.share_code,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        items_count=0,
    )


@router.get("/shared/{share_code}", response_model=WatchlistWithItems)
async def get_shared_watchlist(
    share_code: str,
    db: Session = Depends(get_db),
):
    """
    Get a public watchlist by share code (no auth required)
    """
    watchlist = db.query(Watchlist).options(
        joinedload(Watchlist.items).joinedload(WatchlistItem.product)
    ).filter(
        Watchlist.share_code == share_code,
        Watchlist.is_public == True,
    ).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    return _build_watchlist_response(watchlist)


@router.get("/{watchlist_id}", response_model=WatchlistWithItems)
async def get_watchlist(
    watchlist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Get watchlist with items
    """
    watchlist = db.query(Watchlist).options(
        joinedload(Watchlist.items).joinedload(WatchlistItem.product)
    ).filter(
        Watchlist.id == watchlist_id,
        Watchlist.user_id == current_user.id,
    ).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    return _build_watchlist_response(watchlist)


@router.patch("/{watchlist_id}", response_model=WatchlistResponse)
async def update_watchlist(
    watchlist_id: int,
    watchlist_in: WatchlistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Update a watchlist
    """
    watchlist = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.user_id == current_user.id,
    ).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    update_data = watchlist_in.dict(exclude_unset=True)
    
    # Handle public toggle
    if "is_public" in update_data:
        if update_data["is_public"] and not watchlist.share_code:
            watchlist.share_code = generate_share_code()
        elif not update_data["is_public"]:
            watchlist.share_code = None
    
    for field, value in update_data.items():
        setattr(watchlist, field, value)
    
    watchlist.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(watchlist)
    
    return WatchlistResponse(
        id=watchlist.id,
        user_id=watchlist.user_id,
        name=watchlist.name,
        description=watchlist.description,
        is_public=watchlist.is_public,
        share_code=watchlist.share_code,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        items_count=len(watchlist.items),
    )


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    watchlist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Delete a watchlist
    """
    watchlist = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.user_id == current_user.id,
    ).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    db.delete(watchlist)
    db.commit()


# ============ Watchlist Items ============

@router.post("/{watchlist_id}/items", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
async def add_item_to_watchlist(
    watchlist_id: int,
    item_in: WatchlistItemAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Add a product to watchlist
    """
    watchlist = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.user_id == current_user.id,
    ).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    # Verify product exists and belongs to user
    product = db.query(TrackedProduct).filter(
        TrackedProduct.id == item_in.product_id,
        TrackedProduct.user_id == current_user.id,
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check if already in watchlist
    existing = db.query(WatchlistItem).filter(
        WatchlistItem.watchlist_id == watchlist_id,
        WatchlistItem.product_id == item_in.product_id,
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product already in watchlist"
        )
    
    item = WatchlistItem(
        watchlist_id=watchlist_id,
        product_id=item_in.product_id,
        notes=item_in.notes,
        priority=item_in.priority,
    )
    
    db.add(item)
    watchlist.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    
    return _build_item_response(item)


@router.patch("/{watchlist_id}/items/{item_id}", response_model=WatchlistItemResponse)
async def update_watchlist_item(
    watchlist_id: int,
    item_id: int,
    notes: Optional[str] = None,
    priority: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Update watchlist item notes/priority
    """
    watchlist = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.user_id == current_user.id,
    ).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    item = db.query(WatchlistItem).filter(
        WatchlistItem.id == item_id,
        WatchlistItem.watchlist_id == watchlist_id,
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    if notes is not None:
        item.notes = notes
    if priority is not None:
        item.priority = priority
    
    watchlist.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    
    return _build_item_response(item)


@router.delete("/{watchlist_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item_from_watchlist(
    watchlist_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Remove item from watchlist
    """
    watchlist = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.user_id == current_user.id,
    ).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    item = db.query(WatchlistItem).filter(
        WatchlistItem.id == item_id,
        WatchlistItem.watchlist_id == watchlist_id,
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    db.delete(item)
    watchlist.updated_at = datetime.utcnow()
    db.commit()


# ============ Helpers ============

def _build_watchlist_response(watchlist: Watchlist) -> WatchlistWithItems:
    """Build WatchlistWithItems response"""
    items = [_build_item_response(item) for item in watchlist.items]
    
    return WatchlistWithItems(
        id=watchlist.id,
        user_id=watchlist.user_id,
        name=watchlist.name,
        description=watchlist.description,
        is_public=watchlist.is_public,
        share_code=watchlist.share_code,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        items_count=len(items),
        items=items,
    )


def _build_item_response(item: WatchlistItem) -> WatchlistItemResponse:
    """Build WatchlistItemResponse"""
    from app.schemas import TrackedProductBrief
    
    product_brief = TrackedProductBrief(
        id=item.product.id,
        platform=item.product.platform,
        title=item.product.title,
        image_url=item.product.image_url,
        current_price=item.product.current_price,
        target_price=item.product.target_price,
        currency=item.product.currency,
        alert_status=item.product.alert_status,
    )
    
    return WatchlistItemResponse(
        id=item.id,
        product_id=item.product_id,
        notes=item.notes,
        priority=item.priority,
        added_at=item.added_at,
        product=product_brief,
    )
