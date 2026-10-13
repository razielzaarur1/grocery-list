export interface Item {
  id: number;
  name: string;
  quantity: string;
  unit: string;
  note: string;
  category_id: number;
  is_checked: boolean;
  checked_at: string | null;
  global_add_order: number;
  created_at: string | null;
}

export interface CategoryWithItems {
  id: number;
  name: string;
  order_index: number;
  total_count: number;
  remaining_count: number;
  items: Item[];
}

export interface GroceryListResponse {
  categories: CategoryWithItems[];
  total_count: number;
  remaining_count: number;
}

export interface Category {
  id: number;
  name: string;
  order_index: number;
}

export interface GeminiModel {
  id: number;
  model_id: string;
  display_name: string;
  rank: number;
  is_active: boolean;
  last_tested: string | null;
}

export interface AppSettings {
  gemini_api_key: string;
  masked_gemini_key: string;
  telegram_bot_token: string;
  telegram_chat_id_1: string;
  telegram_chat_id_2: string;
  gemini_models: GeminiModel[];
}
