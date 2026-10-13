import React, { useState, useEffect } from 'react';
import { AppSettings, Category } from '../types';
import { ChevronDown, ChevronUp, ArrowUp, ArrowDown, Trash2, Download, Loader2, AlertTriangle, Clock, ShieldCheck } from 'lucide-react';

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
  const [newApiKey, setNewApiKey] = useState('');
  const [addingKey, setAddingKey] = useState(false);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
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
    setSaveStatus('סורק ומאמת מודלים ומפתחות מול Google Gemini...');
    await onScanModels();
    setScanning(false);
    setSaveStatus('סריקת המודלים והמפתחות הושלמה בהצלחה!');
    setTimeout(() => setSaveStatus(null), 3500);
  };

  const handleAddApiKey = async () => {
    if (!newApiKey.trim()) return;
    const keyToAdd = newApiKey.trim();
    setAddingKey(true);
    try {
      const res = await fetch('/api/settings/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: keyToAdd })
      });
      if (res.ok) {
        setNewApiKey('');
        await onScanModels();
      }
    } catch (err) {
      console.error('Failed to add API key:', err);
    } finally {
      setAddingKey(false);
    }
  };

  const handleDeleteApiKey = async (keyToDelete: string) => {
    setDeletingKey(keyToDelete);
    try {
      const res = await fetch('/api/settings/keys', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: keyToDelete })
      });
      if (res.ok) {
        await onScanModels();
      }
    } catch (err) {
      console.error('Failed to delete API key:', err);
    } finally {
      setDeletingKey(null);
    }
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
              <div className="flex items-center gap-1.5">
                <a
                  href="/ca.crt"
                  download="root.crt"
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 rounded-lg text-xs font-medium transition-colors"
                  title="הורד תעודת אבטחה לטלפון"
                >
                  <ShieldCheck size={14} className="text-emerald-600" />
                  <span>הורד תעודה</span>
                </a>
                <button
                  type="button"
                  onClick={handleInstallPWA}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#1e232a] text-white rounded-lg text-xs font-medium hover:bg-black transition-colors"
                >
                  <Download size={14} />
                  <span>התקן</span>
                </button>
              </div>
            </div>
            <div className="p-2 bg-emerald-50/80 border border-emerald-200/60 rounded-lg text-[10.5px] text-emerald-800 leading-normal">
              <strong>להעלמת השורה השחורה למעלה:</strong>
              <br />
              • <strong>בטלפון סמסונג:</strong> פתח את הכתובת ב-<strong>Samsung Internet</strong> ובחר &quot;הוסף עמוד אל מסך הבית&quot; – נפתח מיד נקי ללא שום שורה!
              <br />
              • <strong>ב-Chrome:</strong> לחץ על &quot;הורד תעודה&quot; למעלה, גש בהגדרות הטלפון ל-<em>אבטחה &gt; התקנת תעודת CA</em>, והתקן את הקובץ. השורה תעלם לחלוטין!
            </div>
          </div>

          {/* Gemini AI Settings */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                בינה מלאכותית (Google Gemini)
              </h3>
              <button
                type="button"
                onClick={handleScan}
                disabled={scanning}
                className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 whitespace-nowrap flex items-center gap-1.5"
              >
                {scanning && <Loader2 size={12} className="animate-spin" />}
                <span>{scanning ? 'סורק מפתחות ומודלים...' : 'סרוק ובדוק הכל'}</span>
              </button>
            </div>

            {/* List of Configured API Keys */}
            <div className="space-y-2">
              <label className="block text-[11px] font-semibold text-slate-700">
                מפתחות API מוגדרים ({settings?.gemini_api_keys?.length || (geminiKey ? 1 : 0)})
              </label>

              <div className="space-y-1.5 max-h-36 overflow-y-auto">
                {settings?.gemini_api_keys && settings.gemini_api_keys.length > 0 ? (
                  settings.gemini_api_keys.map((kItem, idx) => (
                    <div
                      key={kItem.key || idx}
                      className="flex items-center justify-between p-2 rounded-xl border border-slate-200/80 bg-slate-50/70 text-xs"
                    >
                      <div className="flex items-center gap-2 min-w-0 pr-1">
                        <span className="font-mono text-[11.5px] text-slate-700 tracking-wider" dir="ltr">
                          {kItem.masked_key}
                        </span>
                        {kItem.is_primary && (
                          <span className="px-1.5 py-0.5 rounded text-[9.5px] bg-slate-200 text-slate-700 font-medium">
                            ראשי
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => handleDeleteApiKey(kItem.key)}
                          disabled={deletingKey === kItem.key}
                          title="מחק מפתח זה"
                          className="p-1 text-slate-400 hover:text-rose-500 rounded-lg transition-colors hover:bg-rose-50"
                        >
                          {deletingKey === kItem.key ? (
                            <Loader2 size={13} className="animate-spin text-rose-500" />
                          ) : (
                            <Trash2 size={13} />
                          )}
                        </button>
                      </div>
                    </div>
                  ))
                ) : geminiKey ? (
                  <div className="flex items-center justify-between p-2 rounded-xl border border-slate-200/80 bg-slate-50/70 text-xs">
                    <span className="font-mono text-[11.5px] text-slate-700 tracking-wider" dir="ltr">
                      {settings?.masked_gemini_key || (geminiKey.slice(0, 4) + '...' + geminiKey.slice(-4))}
                    </span>
                    <span className="px-1.5 py-0.5 rounded text-[9.5px] bg-slate-200 text-slate-700 font-medium">
                      ראשי
                    </span>
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-400 italic">לא הוגדר עדיין אף מפתח API.</p>
                )}
              </div>

              {/* Add New API Key Input */}
              <div className="pt-1 bg-slate-50 border border-slate-200/70 rounded-xl p-2.5 space-y-1.5">
                <label className="block text-[10.5px] font-medium text-slate-600">
                  הוספת מפתח API נוסף (לניתוב אוטומטי כשנגמרת המכסה):
                </label>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={newApiKey}
                    onChange={(e) => setNewApiKey(e.target.value)}
                    placeholder="הדבק מפתח חדש מחשבון נוסף..."
                    className="flex-1 px-3 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-slate-400 text-left font-mono bg-white"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAddApiKey();
                      }
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleAddApiKey}
                    disabled={addingKey || !newApiKey.trim()}
                    className="px-3 py-1.5 bg-[#1e232a] hover:bg-black text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50 whitespace-nowrap flex items-center gap-1 shadow-sm"
                  >
                    {addingKey && <Loader2 size={12} className="animate-spin" />}
                    <span>{addingKey ? 'מוסיף...' : '+ הוסף מפתח'}</span>
                  </button>
                </div>
                <p className="text-[10px] text-slate-500 leading-normal">
                  💡 <strong>ניתוב אוטומטי:</strong> ניתן להוסיף מפתחות מחשבונות Google שונים ב-Google AI Studio. כשאחד מגיע ל-20 בקשות/יום, המערכת תעבור מיד למפתח הבא!
                </p>
              </div>
            </div>

            {/* Minimized Models Accordion */}
            <div className="border border-slate-200/80 rounded-xl overflow-hidden bg-slate-50/60">
              <button
                type="button"
                onClick={() => setModelsExpanded(!modelsExpanded)}
                className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span>
                    מודלים שזוהו ב-Gemini ({settings?.gemini_models?.length || 0})
                  </span>
                  {(() => {
                    const activeCount = settings?.gemini_models?.filter(m => m.status === 'active' || (!m.status && m.is_active)).length || 0;
                    const quotaCount = settings?.gemini_models?.filter(m => m.status === 'quota_exhausted').length || 0;
                    if (activeCount > 0) {
                      return <span className="text-[10px] bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded-full font-normal">🟢 {activeCount} פעילים</span>;
                    }
                    if (quotaCount > 0) {
                      return <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded-full font-normal">🟡 הגיעו למגבלת מכסה</span>;
                    }
                    return null;
                  })()}
                </div>
                {modelsExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
              </button>

              {modelsExpanded && (
                <div className="p-2.5 bg-white border-t border-slate-100 space-y-2">
                  {/* Warning banner if quota exhausted on all or most models */}
                  {settings?.gemini_models && settings.gemini_models.some(m => m.status === 'quota_exhausted') && !settings.gemini_models.some(m => m.status === 'active') && (
                    <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-[11px] text-amber-900 leading-normal flex items-start gap-2">
                      <AlertTriangle size={15} className="text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-bold">המכסה היומית של גוגל מוצתה (שגיאה 429):</span>
                        <p className="text-[10.5px] text-amber-800 mt-0.5">
                          בחשבון Gemini חינמי, גוגל מגבילה את השימוש ל-20 בקשות ליום לכל מודל. כל המודלים הגיעו לתקרה זו. המכסה תתאפס אוטומטית על ידי גוגל ביממה הבאה, או שניתן להזין מפתח API נוסף.
                        </p>
                      </div>
                    </div>
                  )}

                  <div className="space-y-1.5 max-h-64 overflow-y-auto pr-0.5">
                    {settings?.gemini_models && settings.gemini_models.length > 0 ? (
                      settings.gemini_models.map((m) => {
                        const status = m.status || (m.is_active ? 'active' : 'unavailable');
                        return (
                          <div
                            key={m.id}
                            className="flex items-center justify-between text-xs p-2 rounded-lg border border-slate-100 bg-slate-50/50 hover:bg-slate-50 transition-colors"
                          >
                            <div className="min-w-0 pr-1 text-right">
                              <p className="font-semibold text-slate-800 text-[11px] truncate">
                                {m.display_name || m.model_id.replace('models/', '')}
                              </p>
                              <p className="font-mono text-[9.5px] text-slate-400 truncate" dir="ltr">
                                {m.model_id.replace('models/', '')}
                              </p>
                            </div>

                            <div className="flex items-center gap-1.5 shrink-0">
                              {status === 'active' && (
                                <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                  <span>פעיל {m.latency ? `(${m.latency}s)` : ''}</span>
                                </span>
                              )}
                              {status === 'quota_exhausted' && (
                                <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-amber-50 text-amber-800 border border-amber-200 font-medium" title={m.status_message || "הגיע למגבלת מכסה יומית (שגיאה 429)"}>
                                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                                  <span>מגבלת מכסה (429)</span>
                                </span>
                              )}
                              {status === 'overloaded' && (
                                <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-orange-50 text-orange-800 border border-orange-200 font-medium" title={m.status_message || "עומס זמני בשרת (שגיאה 503)"}>
                                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                                  <span>עומס זמני (503)</span>
                                </span>
                              )}
                              {status === 'timeout' && (
                                <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200 font-medium" title={m.status_message || "זמן תגובה איטי"}>
                                  <Clock size={11} className="text-slate-400" />
                                  <span>חריגת זמן</span>
                                </span>
                              )}
                              {status === 'unavailable' && (
                                <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-slate-100 text-slate-400 border border-slate-200" title={m.status_message || "אינו זמין"}>
                                  <span>לא נתמך</span>
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <p className="text-xs text-slate-400 text-center py-3">
                        הזן מפתח ולחץ על "סרוק מודלים" לגילוי וסריקת כל המודלים.
                      </p>
                    )}
                  </div>
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
