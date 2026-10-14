import json
import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from database import get_db
from models import Item, Category
from command_processor import process_user_input, get_next_global_add_order
from classifier import record_user_correction
from sync_notifier import sync_notifier

router = APIRouter(prefix="/api/items", tags=["items"])

class UserInputRequest(BaseModel):
    text: str

class ManualItemCreate(BaseModel):
    name: str
    quantity: Optional[str] = ""
    unit: Optional[str] = ""
    note: Optional[str] = ""
    category_id: int

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[str] = None
    unit: Optional[str] = None
    note: Optional[str] = None
    category_id: Optional[int] = None
    is_checked: Optional[bool] = None

@router.get("")
def get_items(db: Session = Depends(get_db)):
    """
    Returns categories with their items sorted according to the exact business rules:
    - Unchecked items: sorted by global_add_order ASC (order of addition)
    - Checked items: placed at the bottom, sorted by checked_at DESC
      (the most recently checked item is at the top of the checked items group)
    """
    categories = db.query(Category).order_by(Category.order_index.asc()).all()
    all_items = db.query(Item).all()

    # Group items by category_id
    cat_items_map = {c.id: [] for c in categories}
    for it in all_items:
        if it.category_id in cat_items_map:
            cat_items_map[it.category_id].append(it)

    result_categories = []
    total_items_count = len(all_items)
    remaining_items_count = sum(1 for it in all_items if not it.is_checked)

    for cat in categories:
        items = cat_items_map[cat.id]
        unchecked = [i for i in items if not i.is_checked]
        checked = [i for i in items if i.is_checked]

        # Sort unchecked by global_add_order ASC
        unchecked.sort(key=lambda x: x.global_add_order)

        # Sort checked by checked_at DESC (newest checked first in the checked section)
        checked.sort(key=lambda x: x.checked_at or datetime.min, reverse=True)

        ordered_items = unchecked + checked

        result_categories.append({
            "id": cat.id,
            "name": cat.name,
            "order_index": cat.order_index,
            "total_count": len(items),
            "remaining_count": len(unchecked),
            "items": [
                {
                    "id": it.id,
                    "name": it.name,
                    "quantity": it.quantity,
                    "unit": it.unit,
                    "note": it.note,
                    "category_id": it.category_id,
                    "is_checked": it.is_checked,
                    "checked_at": it.checked_at.isoformat() if it.checked_at else None,
                    "global_add_order": it.global_add_order,
                    "created_at": it.created_at.isoformat() if it.created_at else None
                }
                for it in ordered_items
            ]
        })

    # Sort categories: active categories first, completed categories (all items checked) to the bottom
    result_categories.sort(
        key=lambda c: (1 if (c["total_count"] > 0 and c["remaining_count"] == 0) else 0, c["order_index"])
    )

    return {
        "version": sync_notifier.version,
        "categories": result_categories,
        "total_count": total_items_count,
        "remaining_count": remaining_items_count
    }

@router.get("/version")
def get_version():
    """Ultra-lightweight version check endpoint for Garmin watches and periodic background sync."""
    return {"version": sync_notifier.version}

@router.get("/events")
async def events_stream(request: Request):
    """Server-Sent Events (SSE) stream for instant real-time live sync (<50ms)."""
    q = await sync_notifier.subscribe()

    async def event_generator():
        try:
            # Send initial version immediately
            yield f"data: {json.dumps({'version': sync_notifier.version})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    version = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps({'version': version})}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            sync_notifier.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/input")
async def handle_input(req: UserInputRequest, db: Session = Depends(get_db)):
    """Process natural language input or items list."""
    res = await process_user_input(req.text, db)
    sync_notifier.notify()
    return res

@router.post("/manual")
def add_item_manual(req: ManualItemCreate, db: Session = Depends(get_db)):
    """Manually add an item."""
    cat = db.query(Category).filter(Category.id == req.category_id).first()
    if not cat:
        raise HTTPException(status_code=400, detail="קטגוריה לא נמצאה")

    next_order = get_next_global_add_order(db)
    new_item = Item(
        name=req.name.strip(),
        quantity=req.quantity.strip() if req.quantity else "",
        unit=req.unit.strip() if req.unit else "",
        note=req.note.strip() if req.note else "",
        category_id=req.category_id,
        is_checked=False,
        global_add_order=next_order,
        created_at=datetime.utcnow()
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    # Learn user category selection
    record_user_correction(new_item.name, req.category_id, db)
    sync_notifier.notify()
    return {"success": True, "item_id": new_item.id}

@router.post("/{item_id}/toggle")
def toggle_item_checked(item_id: int, db: Session = Depends(get_db)):
    """Simple toggle endpoint ideal for Garmin watches and quick tap actions."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="פריט לא נמצא")

    item.is_checked = not item.is_checked
    item.checked_at = datetime.utcnow() if item.is_checked else None
    db.commit()
    sync_notifier.notify()
    return {"success": True, "item_id": item.id, "is_checked": item.is_checked}

@router.patch("/{item_id}")
def update_item(item_id: int, update_data: ItemUpdate, db: Session = Depends(get_db)):
    """Update an item (checkbox toggle, long-press edit, etc.)."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="פריט לא נמצא")

    if update_data.name is not None:
        item.name = update_data.name.strip()

    if update_data.quantity is not None:
        item.quantity = update_data.quantity.strip()

    if update_data.unit is not None:
        item.unit = update_data.unit.strip()

    if update_data.note is not None:
        item.note = update_data.note.strip()

    if update_data.category_id is not None and update_data.category_id != item.category_id:
        item.category_id = update_data.category_id
        # Record user correction for future learning
        record_user_correction(item.name, update_data.category_id, db)

    if update_data.is_checked is not None:
        if update_data.is_checked and not item.is_checked:
            item.is_checked = True
            item.checked_at = datetime.utcnow()
        elif not update_data.is_checked and item.is_checked:
            item.is_checked = False
            item.checked_at = None

    db.commit()
    sync_notifier.notify()
    return {"success": True}

@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    """Delete a single item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="פריט לא נמצא")

    db.delete(item)
    db.commit()
    sync_notifier.notify()
    return {"success": True}
