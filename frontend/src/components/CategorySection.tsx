import React from 'react';
import { CategoryWithItems, Item } from '../types';
import { ItemRow } from './ItemRow';

interface CategorySectionProps {
  category: CategoryWithItems;
  onToggle: (item: Item) => void;
  onDelete: (itemId: number) => void;
  onLongPress: (item: Item) => void;
}

export const CategorySection: React.FC<CategorySectionProps> = ({
  category,
  onToggle,
  onDelete,
  onLongPress,
}) => {
  if (category.items.length === 0) {
    return null;
  }

  return (
    <div className="mb-3">
      {/* Category Header: Name on RIGHT, Counter on LEFT */}
      <div className="flex items-center justify-between pb-0.5 px-0.5">
        <h3 className="text-[13.5px] font-medium text-[#64748b] tracking-tight">
          {category.name}
        </h3>
        <span className="text-[12.5px] font-normal text-[#9ca3af]">
          {category.remaining_count}/{category.total_count}
        </span>
      </div>

      {/* Items list */}
      <div className="flex flex-col">
        {category.items.map((item) => (
          <ItemRow
            key={item.id}
            item={item}
            onToggle={onToggle}
            onDelete={onDelete}
            onLongPress={onLongPress}
          />
        ))}
      </div>
    </div>
  );
};
