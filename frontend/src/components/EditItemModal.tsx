import React, { useState, useEffect } from 'react';
import { Item, Category } from '../types';

interface EditItemModalProps {
  item: Item | null;
  categories: Category[];
  isOpen: boolean;
  onClose: () => void;
  onSave: (itemId: number, updateData: Partial<Item>) => Promise<boolean>;
  onDelete: (itemId: number) => void;
}

export const EditItemModal: React.FC<EditItemModalProps> = ({
  item,
  categories,
  isOpen,
  onClose,
  onSave,
  onDelete,
}) => {
  const [name, setName] = useState('');
  const [quantity, setQuantity] = useState('');
  const [unit, setUnit] = useState('');
  const [note, setNote] = useState('');
  const [categoryId, setCategoryId] = useState<number>(1);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (item) {
      setName(item.name);
      setQuantity(item.quantity || '');
      setUnit(item.unit || '');
      setNote(item.note || '');
      setCategoryId(item.category_id);
    }
  }, [item]);

  if (!isOpen || !item) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setLoading(true);
    const success = await onSave(item.id, {
      name: name.trim(),
      quantity: quantity.trim(),
      unit: unit.trim(),
      note: note.trim(),
      category_id: categoryId,
    });
    setLoading(false);

    if (success) {
      onClose();
    }
  };

  const handleDelete = () => {
    onDelete(item.id);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl w-full max-w-sm p-5 shadow-xl border border-slate-100 animate-in fade-in zoom-in-95">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-800">
            עריכת פריט
          </h2>
          <button
            type="button"
            onClick={handleDelete}
            className="text-xs text-red-500 hover:text-red-700 hover:underline px-1 py-0.5"
          >
            מחק פריט
          </button>
        </div>

        <form onSubmit={handleSave} className="space-y-3.5 text-right">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              שם המוצר *
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:border-slate-400"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">
                כמות
              </label>
              <input
                type="text"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:border-slate-400"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">
                יחידה
              </label>
              <input
                type="text"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:border-slate-400"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              הערה
            </label>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:border-slate-400"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              קטגוריה (שינוי ילמד את המערכת לעתיד)
            </label>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(Number(e.target.value))}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-800 bg-white focus:outline-none focus:border-slate-400"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-2 pt-3">
            <button
              type="submit"
              disabled={loading || !name.trim()}
              className="flex-1 bg-slate-800 hover:bg-slate-900 text-white font-medium py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              {loading ? 'שומר...' : 'שמור שינויים'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-slate-200 text-slate-600 rounded-lg text-sm hover:bg-slate-50 transition-colors"
            >
              ביטול
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
