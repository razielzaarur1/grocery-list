import React, { useState } from 'react';
import { Category } from '../types';

interface ManualAddModalProps {
  isOpen: boolean;
  onClose: () => void;
  categories: Category[];
  onAdd: (data: {
    name: string;
    quantity?: string;
    unit?: string;
    note?: string;
    category_id: number;
  }) => Promise<boolean>;
}

export const ManualAddModal: React.FC<ManualAddModalProps> = ({
  isOpen,
  onClose,
  categories,
  onAdd,
}) => {
  const [name, setName] = useState('');
  const [quantity, setQuantity] = useState('');
  const [unit, setUnit] = useState('');
  const [note, setNote] = useState('');
  const [categoryId, setCategoryId] = useState<number>(categories[0]?.id || 1);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setLoading(true);
    const success = await onAdd({
      name: name.trim(),
      quantity: quantity.trim(),
      unit: unit.trim(),
      note: note.trim(),
      category_id: categoryId,
    });
    setLoading(false);

    if (success) {
      setName('');
      setQuantity('');
      setUnit('');
      setNote('');
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl w-full max-w-sm p-5 shadow-xl border border-slate-100 animate-in fade-in zoom-in-95">
        <h2 className="text-lg font-bold text-slate-800 mb-4 text-right">
          הוספת פריט ידנית
        </h2>

        <form onSubmit={handleSubmit} className="space-y-3.5 text-right">
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
              placeholder="לדוגמה: עגבניות"
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
                placeholder="למשל: 3"
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
                placeholder="ק״ג, יח׳, ליטר..."
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
              placeholder="למשל: בשלות / ללא סוכר"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              קטגוריה
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
              {loading ? 'מוסיף...' : 'הוסף לרשימה'}
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
