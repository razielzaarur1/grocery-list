import React, { useState } from 'react';
import { useGroceryList } from '../hooks/useGroceryList';
import { CategorySection } from './CategorySection';
import { AddItemInput } from './AddItemInput';
import { ManualAddModal } from './ManualAddModal';
import { EditItemModal } from './EditItemModal';
import { SettingsModal } from './SettingsModal';
import { Item } from '../types';

export const GroceryList: React.FC = () => {
  const {
    data,
    categories,
    settings,
    processingInput,
    error,
    sendInput,
    toggleCheck,
    deleteItem,
    updateItem,
    manualAddItem,
    saveSettings,
    scanGeminiModels,
    testTelegram,
    addCategory,
    deleteCategory,
    reorderCategories,
  } = useGroceryList();

  const [isManualAddOpen, setIsManualAddOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<Item | null>(null);

  const handleOpenEdit = (item: Item) => {
    setEditingItem(item);
  };

  return (
    <div className="max-w-md mx-auto px-3.5 pt-4 pb-24 min-h-screen select-none">
      {/* Top Header - Matching Screenshot:
          Title & Remaining on RIGHT, "הגדרות" on LEFT */}
      <div className="flex items-start justify-between mb-4 px-0.5">
        {/* Element 1: Title & Subtitle on the RIGHT (RTL start) */}
        <div className="text-right">
          <h1 className="text-[21px] font-bold text-[#1e232a] tracking-tight leading-snug">
            רשימת קניות
          </h1>
          <p className="text-[13px] text-[#8c9ba5] font-normal mt-0.5">
            {data.remaining_count} נותרו מתוך {data.total_count}
          </p>
        </div>

        {/* Element 2: "הגדרות" on the LEFT (RTL end) */}
        <button
          type="button"
          onClick={() => setIsSettingsOpen(true)}
          className="text-[13px] text-[#8c9ba5] hover:text-[#1e232a] transition-colors pt-1 cursor-pointer font-normal"
        >
          הגדרות
        </button>
      </div>

      {/* Global Error Notice if any */}
      {error && (
        <div className="mb-3 p-2.5 bg-red-50 border border-red-100 text-red-600 text-xs rounded-xl text-right">
          {error}
        </div>
      )}

      {/* Categories and Items List */}
      {data.categories.some((c) => c.items.length > 0) ? (
        <div className="flex flex-col">
          {data.categories.map((cat) => (
            <CategorySection
              key={cat.id}
              category={cat}
              onToggle={toggleCheck}
              onDelete={deleteItem}
              onLongPress={handleOpenEdit}
            />
          ))}
        </div>
      ) : (
        <div className="py-20 text-center text-[#9ca3af] text-[13.5px]">
          הרשימה ריקה. הקלד פריטים בתיבת הטקסט למטה.
        </div>
      )}

      {/* Floating Bottom Input Bar with attached status indicator */}
      <AddItemInput
        onSend={sendInput}
        onOpenManualAdd={() => setIsManualAddOpen(true)}
        isLoading={processingInput}
      />

      {/* Modals */}
      <ManualAddModal
        isOpen={isManualAddOpen}
        onClose={() => setIsManualAddOpen(false)}
        categories={categories}
        onAdd={manualAddItem}
      />

      <EditItemModal
        item={editingItem}
        categories={categories}
        isOpen={!!editingItem}
        onClose={() => setEditingItem(null)}
        onSave={updateItem}
        onDelete={deleteItem}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        categories={categories}
        onSaveSettings={saveSettings}
        onScanModels={scanGeminiModels}
        onTestTelegram={testTelegram}
        onAddCategory={addCategory}
        onDeleteCategory={deleteCategory}
        onReorderCategories={reorderCategories}
      />
    </div>
  );
};
