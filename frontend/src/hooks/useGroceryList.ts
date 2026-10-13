import { useState, useEffect, useCallback } from 'react';
import { GroceryListResponse, Category, AppSettings, Item } from '../types';

export function useGroceryList() {
  const [data, setData] = useState<GroceryListResponse>({
    categories: [],
    total_count: 0,
    remaining_count: 0,
  });
  const [categories, setCategories] = useState<Category[]>([]);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [processingInput, setProcessingInput] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchItems = useCallback(async () => {
    try {
      const res = await fetch('/api/items');
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (err: any) {
      console.error('Failed to fetch items:', err);
    }
  }, []);

  const fetchCategories = useCallback(async () => {
    try {
      const res = await fetch('/api/categories');
      if (res.ok) {
        const json = await res.json();
        setCategories(json);
      }
    } catch (err: any) {
      console.error('Failed to fetch categories:', err);
    }
  }, []);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await fetch('/api/settings');
      if (res.ok) {
        const json = await res.json();
        setSettings(json);
      }
    } catch (err: any) {
      console.error('Failed to fetch settings:', err);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchItems(), fetchCategories(), fetchSettings()]).finally(() => {
      setLoading(false);
    });

    // Auto-refresh every 5 seconds to sync changes (e.g. from Telegram or other user)
    const interval = setInterval(() => {
      fetchItems();
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchItems, fetchCategories, fetchSettings]);

  const sendInput = async (text: string): Promise<boolean> => {
    if (!text.trim()) return false;
    setProcessingInput(true);
    setError(null);
    try {
      const res = await fetch('/api/items/input', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });

      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const result = await res.json();
        if (!res.ok || result.success === false) {
          setError(result.message || 'שגיאה בעיבוד הקלט');
          return false;
        } else if (result.message && result.message.includes('שגיאת AI')) {
          setError(result.message);
        }
      } else if (!res.ok) {
        console.warn('Server returned non-JSON status:', res.status);
        setError('שגיאת שרת בעיבוד הבקשה');
        return false;
      }

      await fetchItems();
      await fetchCategories();
      return true;
    } catch (err: any) {
      console.warn('Error during input processing:', err);
      setError('שגיאת תקשורת עם השרת');
      await fetchItems();
      return false;
    } finally {
      setProcessingInput(false);
    }
  };

  const toggleCheck = async (item: Item) => {
    // Optimistic UI update
    const newChecked = !item.is_checked;
    setData((prev) => {
      const updatedCategories = prev.categories.map((cat) => {
        if (cat.id !== item.category_id) return cat;

        const updatedItems = cat.items.map((i) =>
          i.id === item.id ? { ...i, is_checked: newChecked, checked_at: newChecked ? new Date().toISOString() : null } : i
        );

        // Resort category items
        const unchecked = updatedItems.filter((i) => !i.is_checked);
        const checked = updatedItems.filter((i) => i.is_checked);
        unchecked.sort((a, b) => a.global_add_order - b.global_add_order);
        checked.sort((a, b) => {
          const tA = a.checked_at ? new Date(a.checked_at).getTime() : 0;
          const tB = b.checked_at ? new Date(b.checked_at).getTime() : 0;
          return tB - tA; // most recent checked first
        });

        return {
          ...cat,
          remaining_count: unchecked.length,
          items: [...unchecked, ...checked],
        };
      });

      // Sort categories: completed categories to bottom
      updatedCategories.sort((a, b) => {
        const aCompleted = a.total_count > 0 && a.remaining_count === 0 ? 1 : 0;
        const bCompleted = b.total_count > 0 && b.remaining_count === 0 ? 1 : 0;
        if (aCompleted !== bCompleted) return aCompleted - bCompleted;
        return a.order_index - b.order_index;
      });

      const remaining = updatedCategories.reduce((acc, c) => acc + c.remaining_count, 0);
      return {
        ...prev,
        remaining_count: remaining,
        categories: updatedCategories,
      };
    });

    try {
      await fetch(`/api/items/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_checked: newChecked }),
      });
      fetchItems();
    } catch (err) {
      console.error('Failed to toggle item:', err);
      fetchItems();
    }
  };

  const deleteItem = async (itemId: number) => {
    try {
      await fetch(`/api/items/${itemId}`, { method: 'DELETE' });
      fetchItems();
    } catch (err) {
      console.error('Failed to delete item:', err);
    }
  };

  const updateItem = async (itemId: number, updateData: Partial<Item>) => {
    try {
      const res = await fetch(`/api/items/${itemId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updateData),
      });
      if (res.ok) {
        await fetchItems();
        return true;
      }
    } catch (err) {
      console.error('Failed to update item:', err);
    }
    return false;
  };

  const manualAddItem = async (itemData: {
    name: string;
    quantity?: string;
    unit?: string;
    note?: string;
    category_id: number;
  }) => {
    try {
      const res = await fetch('/api/items/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(itemData),
      });
      if (res.ok) {
        await fetchItems();
        return true;
      }
    } catch (err) {
      console.error('Failed to manually add item:', err);
    }
    return false;
  };

  const saveSettings = async (newSettings: Partial<AppSettings>) => {
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings),
      });
      if (res.ok) {
        await fetchSettings();
        return true;
      }
    } catch (err) {
      console.error('Failed to save settings:', err);
    }
    return false;
  };

  const scanGeminiModels = async () => {
    try {
      const res = await fetch('/api/settings/gemini/scan', { method: 'POST' });
      if (res.ok) {
        await fetchSettings();
        return true;
      }
    } catch (err) {
      console.error('Failed to scan models:', err);
    }
    return false;
  };

  const testTelegram = async () => {
    try {
      const res = await fetch('/api/settings/telegram/test', { method: 'POST' });
      return await res.json();
    } catch (err: any) {
      return { success: false, errors: [err.message] };
    }
  };

  const addCategory = async (name: string) => {
    try {
      const res = await fetch('/api/categories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      if (res.ok) {
        await fetchCategories();
        await fetchItems();
        return true;
      }
    } catch (err) {
      console.error('Failed to add category:', err);
    }
    return false;
  };

  const deleteCategory = async (id: number) => {
    try {
      const res = await fetch(`/api/categories/${id}`, { method: 'DELETE' });
      if (res.ok) {
        await fetchCategories();
        await fetchItems();
        return true;
      }
    } catch (err) {
      console.error('Failed to delete category:', err);
    }
    return false;
  };

  const reorderCategories = async (newOrder: { id: number; order_index: number }[]) => {
    try {
      const res = await fetch('/api/categories/reorder', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ categories: newOrder }),
      });
      if (res.ok) {
        await fetchCategories();
        await fetchItems();
        return true;
      }
    } catch (err) {
      console.error('Failed to reorder categories:', err);
    }
    return false;
  };

  return {
    data,
    categories,
    settings,
    loading,
    processingInput,
    error,
    clearError: () => setError(null),
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
    refreshItems: fetchItems,
  };
}
