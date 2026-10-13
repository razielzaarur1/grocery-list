import React, { useRef } from 'react';
import { Item } from '../types';
import { Check } from 'lucide-react';

interface ItemRowProps {
  item: Item;
  onToggle: (item: Item) => void;
  onDelete: (itemId: number) => void;
  onLongPress: (item: Item) => void;
}

export const ItemRow: React.FC<ItemRowProps> = ({
  item,
  onToggle,
  onDelete,
  onLongPress,
}) => {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isLongPressRef = useRef(false);

  const startPress = () => {
    isLongPressRef.current = false;
    timerRef.current = setTimeout(() => {
      isLongPressRef.current = true;
      if (typeof navigator !== 'undefined' && navigator.vibrate) {
        navigator.vibrate(40);
      }
      onLongPress(item);
    }, 500);
  };

  const cancelPress = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const handleClick = (e: React.MouseEvent) => {
    if (isLongPressRef.current) {
      e.preventDefault();
      return;
    }
  };

  const quantityString = [item.quantity, item.unit].filter(Boolean).join(' ').trim();

  return (
    <div
      className="flex items-center justify-between py-1 px-0.5 select-none transition-colors group cursor-pointer"
      onTouchStart={startPress}
      onTouchEnd={cancelPress}
      onTouchMove={cancelPress}
      onMouseDown={startPress}
      onMouseUp={cancelPress}
      onMouseLeave={cancelPress}
      onClick={handleClick}
    >
      {/* Right side in RTL: Checkbox + Name with Quantity next to it, and Note directly below */}
      <div
        className="flex items-start gap-2.5 flex-1 min-w-0"
        onClick={() => onToggle(item)}
      >
        {/* Compact Checkbox */}
        <div
          className={`w-[19px] h-[19px] rounded-[4px] flex items-center justify-center transition-all flex-shrink-0 mt-0.5 ${
            item.is_checked
              ? 'bg-[#15803d] border border-transparent text-white'
              : 'border border-[#cbd5e1] bg-white hover:border-[#9ca3af]'
          }`}
        >
          {item.is_checked && <Check size={13} strokeWidth={3} className="text-white" />}
        </div>

        {/* Column: Top row (Name + Quantity), Bottom row (Note) */}
        <div className="flex flex-col min-w-0 leading-tight">
          <div className="flex items-baseline gap-1.5 truncate">
            <span
              className={`text-[15px] tracking-tight font-normal ${
                item.is_checked
                  ? 'line-through text-[#9ca3af]'
                  : 'text-[#1e232a]'
              }`}
            >
              {item.name}
            </span>

            {quantityString && (
              <span
                className={`text-[13px] font-normal tracking-tight ${
                  item.is_checked
                    ? 'line-through text-[#b0b8c1]'
                    : 'text-[#8c9ba5]'
                }`}
              >
                {quantityString}
              </span>
            )}
          </div>

          {/* Note directly tightly underneath item */}
          {item.note && (
            <span
              className={`text-[11.5px] font-normal leading-tight mt-0.5 ${
                item.is_checked ? 'line-through text-[#cbd5e1]' : 'text-[#8c9ba5]'
              }`}
            >
              {item.note}
            </span>
          )}
        </div>
      </div>

      {/* Left side in RTL: Small faint '×' */}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onDelete(item.id);
        }}
        className="text-[#cbd5e1] hover:text-[#64748b] text-[15px] font-light px-1.5 py-0.5 transition-colors flex-shrink-0"
        title="מחק"
      >
        ×
      </button>
    </div>
  );
};
