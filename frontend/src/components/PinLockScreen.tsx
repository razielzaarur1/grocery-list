import React, { useState, useEffect, useCallback } from 'react';
import { Lock, ShieldAlert, Delete, RefreshCw, KeyRound, Loader2 } from 'lucide-react';
import { apiFetch, setAuthToken } from '../api';

interface PinLockScreenProps {
  onSuccess: () => void;
}

export const PinLockScreen: React.FC<PinLockScreenProps> = ({ onSuccess }) => {
  const [pin, setPin] = useState('');
  const [pinLength, setPinLength] = useState(4);
  const [isLocked, setIsLocked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [shake, setShake] = useState(false);

  const checkStatus = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const res = await apiFetch('/api/auth/status');
      if (res.ok) {
        const data = await res.json();
        if (data.is_authenticated) {
          onSuccess();
          return;
        }
        setIsLocked(data.is_locked);
        if (data.pin_length) {
          setPinLength(data.pin_length);
        }
      }
    } catch (err: any) {
      console.error('Failed to check auth status:', err);
    } finally {
      setLoading(false);
    }
  }, [onSuccess]);

  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  const verifyPin = useCallback(
    async (codeToVerify: string) => {
      if (verifying || isLocked) return;
      setVerifying(true);
      setErrorMessage(null);

      try {
        const res = await apiFetch('/api/auth/verify-pin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            pin: codeToVerify,
            device_name: navigator.userAgent.includes('Mobile') ? 'טלפון נייד' : 'דפדפן מחשב',
          }),
        });

        const data = await res.json();

        if (res.ok && data.success && data.token) {
          // Success: save device token permanently
          setAuthToken(data.token);
          onSuccess();
        } else {
          // Mismatch or locked
          setShake(true);
          setTimeout(() => setShake(false), 500);
          setErrorMessage(data.message || data.detail || 'קוד PIN שגוי');
          if (data.is_locked) {
            setIsLocked(true);
          }
          // Clear input after short delay
          setTimeout(() => setPin(''), 400);
        }
      } catch (err: any) {
        setErrorMessage('שגיאת תקשורת עם השרת');
        setTimeout(() => setPin(''), 400);
      } finally {
        setVerifying(false);
      }
    },
    [verifying, isLocked, onSuccess]
  );

  // Auto-submit when PIN length is reached
  useEffect(() => {
    if (pin.length > 0 && pin.length === pinLength) {
      verifyPin(pin);
    }
  }, [pin, pinLength, verifyPin]);

  // Physical keyboard listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (loading || verifying || isLocked) return;

      if (/^[0-9]$/.test(e.key)) {
        if (pin.length < pinLength) {
          setPin((prev) => prev + e.key);
        }
      } else if (e.key === 'Backspace') {
        setPin((prev) => prev.slice(0, -1));
      } else if (e.key === 'Escape') {
        setPin('');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [pin, pinLength, loading, verifying, isLocked]);

  const handleDigitClick = (digit: string) => {
    if (pin.length < pinLength && !verifying && !isLocked) {
      setPin((prev) => prev + digit);
    }
  };

  const handleBackspace = () => {
    if (!verifying && !isLocked) {
      setPin((prev) => prev.slice(0, -1));
    }
  };

  const handleClear = () => {
    if (!verifying && !isLocked) {
      setPin('');
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-[#f6f8f6] flex flex-col items-center justify-center p-4 z-50">
        <Loader2 className="w-8 h-8 text-emerald-600 animate-spin mb-2" />
        <p className="text-xs text-slate-500 font-medium">בודק הרשאת מכשיר...</p>
      </div>
    );
  }

  // Lockout Screen
  if (isLocked) {
    return (
      <div className="fixed inset-0 bg-[#0f172a] text-white flex flex-col items-center justify-center p-6 z-50 select-none">
        <div className="max-w-sm w-full bg-slate-800/90 border border-rose-500/40 rounded-3xl p-6 text-center space-y-5 shadow-2xl">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-rose-500/20 text-rose-400 mx-auto">
            <ShieldAlert size={36} />
          </div>

          <div className="space-y-2">
            <h2 className="text-xl font-bold text-rose-400">המערכת ננעלה!</h2>
            <p className="text-xs text-slate-300 leading-relaxed">
              הוקש קוד שגוי 3 פעמים. מטעמי אבטחה, הגישה לאתר נחסמה.
            </p>
          </div>

          <div className="bg-slate-900/90 border border-slate-700 rounded-2xl p-4 text-right space-y-2">
            <p className="text-xs font-semibold text-emerald-400">כיצד לשחרר את הנעילה?</p>
            <p className="text-[11.5px] text-slate-300 leading-normal">
              היכנס מהרשת הביתית (LAN) לפורט החילוץ <strong>8889</strong>:
            </p>
            <div className="p-2 bg-black/40 rounded-xl text-center font-mono text-xs text-emerald-300 select-all border border-emerald-500/30">
              http://{window.location.hostname}:8889
            </div>
            <p className="text-[10.5px] text-slate-400">
              שם תוכל לשחרר את הנעילה מיד או לאפס את הסיסמה.
            </p>
          </div>

          <button
            type="button"
            onClick={checkStatus}
            className="w-full py-3 bg-slate-700 hover:bg-slate-600 active:scale-95 text-white text-xs font-bold rounded-2xl transition-all flex items-center justify-center gap-2"
          >
            <RefreshCw size={14} />
            <span>בדוק שוב לאחר שחרור</span>
          </button>
        </div>
      </div>
    );
  }

  // Normal PIN Entry Screen
  return (
    <div className="fixed inset-0 bg-[#f6f8f6] text-[#1e232a] flex flex-col items-center justify-center p-4 z-50 select-none">
      <div className="max-w-xs w-full flex flex-col items-center space-y-6">
        
        {/* Top Icon & Title */}
        <div className="text-center space-y-1.5">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-[#1e232a] text-white shadow-lg mb-1">
            <Lock size={26} />
          </div>
          <h1 className="text-lg font-bold text-slate-900">הקש קוד PIN לכניסה</h1>
          <p className="text-[11.5px] text-slate-500">
            אימות ראשוני במכשיר זה (ברירת מחדל: 1234)
            <br />
            המכשיר יישמר לצמיתות
          </p>
        </div>

        {/* PIN Indicators (Dots) */}
        <div
          className={`flex items-center justify-center gap-3 py-2 transition-transform ${
            shake ? 'translate-x-[-8px] animate-pulse' : ''
          }`}
        >
          {Array.from({ length: pinLength }).map((_, idx) => {
            const isFilled = idx < pin.length;
            return (
              <div
                key={idx}
                className={`w-4 h-4 rounded-full border-2 transition-all duration-150 ${
                  isFilled
                    ? 'bg-[#1e232a] border-[#1e232a] scale-110'
                    : 'bg-white border-slate-300 scale-100'
                }`}
              />
            );
          })}
        </div>

        {/* Error / Status Message */}
        <div className="h-6 flex items-center justify-center">
          {errorMessage ? (
            <p className="text-xs font-semibold text-rose-600 text-center animate-bounce">
              {errorMessage}
            </p>
          ) : verifying ? (
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Loader2 size={12} className="animate-spin text-emerald-600" />
              <span>בודק סיסמה...</span>
            </div>
          ) : (
            <p className="text-[11px] text-slate-400">מזהה אוטומטית בסיום ההקשה</p>
          )}
        </div>

        {/* Numeric Keypad */}
        <div className="w-full grid grid-cols-3 gap-3 px-2">
          {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((digit) => (
            <button
              key={digit}
              type="button"
              onClick={() => handleDigitClick(digit)}
              className="h-14 rounded-2xl bg-white border border-slate-200/90 text-xl font-bold text-slate-800 hover:bg-slate-100 active:scale-95 shadow-sm transition-all"
            >
              {digit}
            </button>
          ))}

          {/* Bottom row: Clear, 0, Backspace */}
          <button
            type="button"
            onClick={handleClear}
            className="h-14 rounded-2xl bg-slate-100 border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-200 active:scale-95 transition-all"
          >
            איפוס
          </button>
          <button
            type="button"
            onClick={() => handleDigitClick('0')}
            className="h-14 rounded-2xl bg-white border border-slate-200/90 text-xl font-bold text-slate-800 hover:bg-slate-100 active:scale-95 shadow-sm transition-all"
          >
            0
          </button>
          <button
            type="button"
            onClick={handleBackspace}
            className="h-14 rounded-2xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700 hover:bg-slate-200 active:scale-95 transition-all"
          >
            <Delete size={20} />
          </button>
        </div>

      </div>
    </div>
  );
};
