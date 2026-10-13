import React, { useState, useEffect } from 'react';
import { AppSettings, Category } from '../types';
import { ChevronDown, ChevronUp, ArrowUp, ArrowDown, Trash2, Download, Loader2 } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: AppSettings | null;
  categories: Category[];
  onSaveSettings: (settings: Partial<AppSettings>) => Promise<boolean>;
  onScanModels: () => Promise<boolean>;
  onTestTelegram: () => Promise<{ success: boolean; errors?: string[] }>;
  onAddCategory: (name: string) => Promise<boolean>;
  onDeleteCategory: (id: number) => Promise<boolean>;
  onReorderCategories: (newOrder: { id: number; order_index: number }[]) => Promise<boolean>;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  categories,
  onSaveSettings,
  onScanModels,
  onTestTelegram,
  onAddCategory,
  onDeleteCategory,
  onReorderCategories,
}) => {
  const [geminiKey, setGeminiKey] = useState('');
  const [tgToken, setTgToken] = useState('');
  const [tgChat1, setTgChat1] = useState('');
  const [tgChat2, setTgChat2] = useState('');

  const [modelsExpanded, setModelsExpanded] = useState(false);
  const [newCatName, setNewCatName] = useState('');
  const [saving, setSaving] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [testingTg, setTestingTg] = useState(false);
  const [tgStatus, setTgStatus] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [canInstall, setCanInstall] = useState(false);

  useEffect(() => {
    if (settings) {
      setGeminiKey(settings.gemini_api_key || '');
      setTgToken(settings.telegram_bot_token || '');
      setTgChat1(settings.telegram_chat_id_1 || '');
      setTgChat2(settings.telegram_chat_id_2 || '');
    }
  }, [settings]);

  useEffect(() => {
    const handleCanInstall = () => setCanInstall(true);
    window.addEventListener('can-install-pwa', handleCanInstall);
    if ((window as any).deferredPrompt) {
      setCanInstall(true);
    }
    return () => window.removeEventListener('can-install-pwa', handleCanInstall);
  }, []);

  if (!isOpen) return null;

  const handleInstallPWA = async () => {
    const promptEvent = (window as any).deferredPrompt;
    if (promptEvent) {
      promptEvent.prompt();
      const choice = await promptEvent.userChoice;
      if (choice.outcome === 'accepted') {
        setCanInstall(false);
      }
    } else {
      alert('להתקנת האפליקציה: לחץ על תפריט הדפדפן (3 נקודות) ובחר "התקן אפליקציה" או "הוסף למסך הבית".');
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveStatus(null);
    const success = await onSaveSettings({
      gemini_api_key: geminiKey,
      telegram_bot_token: tgToken,
      telegram_chat_id_1: tgChat1,
      telegram_chat_id_2: tgChat2,
    });
    setSaving(false);
    if (success) {
      setSaveStatus('ההגדרות נשמרו בהצלחה!');
      setTimeout(() => setSaveStatus(null), 3500);
    }
  };

  const handleScan = async () => {
    setScanning(true);
    setSaveStatus('סורק ומאמת מודלים מול Google Gemini...');
    await onScanModels();
    setScanning(false);
    setSaveStatus('סריקת המודלים הושלמה בהצלחה!');
    setTimeout(() => setSaveStatus(null), 3500);
  };

  const handleTestTg = async () => {
    setTestingTg(true);
    setTgStatus(null);
    const res = await onTestTelegram();
    setTestingTg(false);
    if (res.success) {
      setTgStatus('הודעת בדיקה נשלחה בהצלחה לטלגרם!');
    } else {
      setTgStatus(`שגיאה: ${res.errors?.join(', ') || 'שליחה נכשלה'}`);
    }
    setTimeout(() => setTgStatus(null), 4000);
  };

  const handleMoveCategory = async (index: number, direction: 'up' | 'down') => {
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= categories.length) return;

    const reordered = [...categories];
    const [moved] = reordered.splice(index, 1);
    reordered.splice(targetIndex, 0, moved);

    const payload = reordered.map((cat, idx) => ({
      id: cat.id,
      order_index: idx,
    }));
    await onReorderCategories(payload);
  };

  const handleCreateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCatName.trim()) return;
    const name = newCatName.trim();
    setNewCatName('');
    await onAddCategory(name);
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-3 z-50">
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] flex flex-col shadow-2xl border border-slate-100 animate-in fade-in zoom-in-95">
        {/* Header: Title on RIGHT, Close '×' on LEFT */}
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <h2 className="text-base font-bold text-[#1e232a]">הגדרות</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 text-xl font-light"
          >
            ×
          </button>
        </div>

        {/* Content body */}
        <div className="overflow-y-auto p-4 space-y-5 text-right">
          {/* PWA Install Button */}
          <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-3 space-y-2">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-800">התקנת האפליקציה בטלפון (PWA)</p>
                <p className="text-[11px] text-slate-500">התקנה מלאה במסך הבית ללא שורת כתובת</p>
              </div>
              <button
                type="button"
                onClick={handleInstallPWA}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#1e232a] text-white rounded-lg text-xs font-medium hover:bg-black transition-colors"
              >
                <Download size={14} />
                <span>התקן עכשיו</span>
              </button>
            </div>
            <div className="p-2 bg-amber-50/80 border border-amber-200/60 rounded-lg text-[10.5px] text-amber-800 leading-normal">
              <strong>טיפ להתקנה מלאה ברשת ביתית (IP מקומי):</strong> ב-Chrome בטלפון, היכנס ל-
              <code className="bg-amber-100/80 px-1 py-0.5 rounded font-mono mx-1">chrome://flags/#unsafely-treat-insecure-origin-as-secure</code>
              הפעל את הדגל (Enabled), הזן את כתובת השרת (למשל <code className="font-mono">{window.location.origin}</code>) ולחץ Relaunch. לאחר מכן כפתור ההתקנה יפעל כאפליקציה אמיתית!
            </div>
          </div>

          {/* Gemini AI Settings */}
          <div className="space-y-2.5">
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              בינה מלאכותית (Google Gemini)
            </h3>
            <div>
              <label className="block text-[11px] text-slate-500 mb-1">
                Gemini API Key
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={geminiKey}
                  onChange={(e) => setGeminiKey(e.target.value)}
                  placeholder="AIzaSy..."
                  className="flex-1 px-3 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-slate-400 text-left font-mono"
                />
                <button
                  type="button"
                  onClick={handleScan}
                  disabled={scanning || !geminiKey}
                  className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 whitespace-nowrap flex items-center gap-1"
                >
                  {scanning && <Loader2 size={12} className="animate-spin" />}
                  <span>{scanning ? 'סורק...' : 'סרוק מודלים'}</span>
                </button>
              </div>
            </div>

            {/* Minimized Models Accordion */}
            <div className="border border-slate-100 rounded-xl overflow-hidden bg-slate-50/60">
              <button
                type="button"
                onClick={() => setModelsExpanded(!modelsExpanded)}
                className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <span>
                  מודלים פעילים ב-Gemini ({settings?.gemini_models?.length || 0})
                </span>
                {modelsExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
              </button>

              {modelsExpanded && (
                <div className="p-2.5 bg-white border-t border-slate-100 space-y-1.5 max-h-40 overflow-y-auto">
                  {settings?.gemini_models && settings.gemini_models.length > 0 ? (
                    settings.gemini_models.map((m) => (
                      <div
                        key={m.id}
                        className="flex items-center justify-between text-xs py-1 px-2 rounded bg-slate-50 text-slate-700"
                      >
                        <span className="font-mono text-[11px] truncate max-w-[200px]" dir="ltr">
                          {m.model_id.replace('models/', '')}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-slate-400">
                            עדיפות #{m.rank}
                          </span>
                          <span className="w-2 h-2 rounded-full bg-emerald-500" title="פעיל ונבדק" />
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-slate-400 text-center py-2">
                      הזן מפתח ולחץ על "סרוק מודלים" לגילוי כל המודלים הזמינים.
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>

          <hr className="border-slate-100" />

          {/* Telegram Settings */}
          <div className="space-y-2.5">
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              בוט טלגרם (Telegram)
            </h3>
            <div>
              <label className="block text-[11px] text-slate-500 mb-1">
                Bot Token
              </label>
              <input
                type="password"
                value={tgToken}
                onChange={(e) => setTgToken(e.target.value)}
                placeholder="123456789:ABCdefGhIJKlmNo..."
                className="w-full px-3 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-slate-400 text-left font-mono"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <div>
                <label className="block text-[11px] text-slate-500 mb-1">
                  Chat ID 1
                </label>
                <input
                  type="text"
                  value={tgChat1}
                  onChange={(e) => setTgChat1(e.target.value)}
                  placeholder="למשל: 123456789"
                  className="w-full px-3 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-slate-400 text-left font-mono"
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-500 mb-1">
                  Chat ID 2 (משתמש נוסף)
                </label>
                <input
                  type="text"
                  value={tgChat2}
                  onChange={(e) => setTgChat2(e.target.value)}
                  placeholder="למשל: 987654321"
                  className="w-full px-3 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-slate-400 text-left font-mono"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <button
                type="button"
                onClick={handleTestTg}
                disabled={testingTg || !tgToken}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
              >
                {testingTg ? 'בודק...' : 'שלח הודעת בדיקה לטלגרם'}
              </button>
              {tgStatus && (
                <span className="text-xs text-slate-600 font-medium">
                  {tgStatus}
                </span>
              )}
            </div>
          </div>

          <hr className="border-slate-100" />

          {/* Categories Management */}
          <div className="space-y-2.5">
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              ניהול קטגוריות וסדר תצוגה
            </h3>

            <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
              {categories.map((cat, idx) => (
                <div
                  key={cat.id}
                  className="flex items-center justify-between p-1.5 rounded-lg bg-slate-50 border border-slate-100 text-xs"
                >
                  <span className="font-medium text-slate-700">{cat.name}</span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      disabled={idx === 0}
                      onClick={() => handleMoveCategory(idx, 'up')}
                      className="p-1 text-slate-400 hover:text-slate-700 disabled:opacity-20"
                      title="העבר למעלה"
                    >
                      <ArrowUp size={13} />
                    </button>
                    <button
                      type="button"
                      disabled={idx === categories.length - 1}
                      onClick={() => handleMoveCategory(idx, 'down')}
                      className="p-1 text-slate-400 hover:text-slate-700 disabled:opacity-20"
                      title="העבר למטה"
                    >
                      <ArrowDown size={13} />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDeleteCategory(cat.id)}
                      className="p-1 text-slate-300 hover:text-red-500 transition-colors mr-1"
                      title="מחק קטגוריה"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <form onSubmit={handleCreateCategory} className="flex gap-2">
              <input
                type="text"
                value={newCatName}
                onChange={(e) => setNewCatName(e.target.value)}
                placeholder="הוסף קטגוריה חדשה..."
                className="flex-1 px-3 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-slate-400"
              />
              <button
                type="submit"
                disabled={!newCatName.trim()}
                className="px-3 py-1.5 bg-[#1e232a] text-white rounded-lg text-xs font-medium hover:bg-black transition-colors disabled:opacity-40"
              >
                הוסף
              </button>
            </form>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-slate-100 flex items-center justify-between bg-slate-50/50 rounded-b-2xl">
          <div className="text-xs text-emerald-600 font-medium">
            {saveStatus}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-1.5 bg-[#1e232a] hover:bg-black text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {saving ? 'שומר...' : 'שמור הגדרות'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 border border-slate-200 text-slate-600 text-xs rounded-lg hover:bg-slate-100 transition-colors"
            >
              סגור
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
