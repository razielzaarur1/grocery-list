from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Category, Item

router = APIRouter(prefix="/api/categories", tags=["categories"])

class CategoryCreate(BaseModel):
    name: str

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    order_index: Optional[int] = None

class ReorderItem(BaseModel):
    id: int
    order_index: int

class ReorderRequest(BaseModel):
    categories: List[ReorderItem]

@router.get("")
def get_categories(db: Session = Depends(get_db)):
    """Returns all categories ordered by order_index."""
    return db.query(Category).order_by(Category.order_index.asc()).all()

@router.post("")
def add_category(cat: CategoryCreate, db: Session = Depends(get_db)):
    """Adds a new category."""
    name = cat.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="שם הקטגוריה אינו יכול להיות ריק")

    existing = db.query(Category).filter(Category.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="קטגוריה בשם זה כבר קיימת")

    # Get highest order index
    max_idx = db.query(Category).count()
    new_cat = Category(name=name, order_index=max_idx)
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat

@router.patch("/reorder")
def reorder_categories(req: ReorderRequest, db: Session = Depends(get_db)):
    """Updates order indices for categories."""
    for item in req.categories:
        cat = db.query(Category).filter(Category.id == item.id).first()
        if cat:
            cat.order_index = item.order_index
    db.commit()
    return {"success": True}

@router.patch("/{category_id}")
def update_category(category_id: int, req: CategoryUpdate, db: Session = Depends(get_db)):
    """Renames or updates category."""
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="קטגוריה לא נמצאה")

    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="שם לא חוקי")
        cat.name = name

    if req.order_index is not None:
        cat.order_index = req.order_index

    db.commit()
    return cat

@router.delete("/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """Deletes category and moves its items to 'שונות' if available."""
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="קטגוריה לא נמצאה")

    # Prevent deleting if it's the only category
    total_cats = db.query(Category).count()
    if total_cats <= 1:
        raise HTTPException(status_code=400, detail="לא ניתן למחוק את הקטגוריה היחידה שנותרה")

    # Find another category to reassign items (preferably 'שונות')
    fallback_cat = db.query(Category).filter(Category.name == "שונות", Category.id != category_id).first()
    if not fallback_cat:
        fallback_cat = db.query(Category).filter(Category.id != category_id).first()

    # Reassign existing items
    if fallback_cat:
        db.query(Item).filter(Item.category_id == category_id).update({"category_id": fallback_cat.id})

    db.delete(cat)
    db.commit()
    return {"success": True}
