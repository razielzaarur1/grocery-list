import React, { useState, useEffect, useRef } from 'react';
import { ArrowUp, Plus, Loader2 } from 'lucide-react';

interface AddItemInputProps {
  onSend: (text: string) => Promise<any>;
  onOpenManualAdd: () => void;
  isLoading: boolean;
}

const STORAGE_KEY = 'grocery_draft_text';

export const AddItemInput: React.FC<AddItemInputProps> = ({
  onSend,
  onOpenManualAdd,
  isLoading,
}) => {
  const [text, setText] = useState('');
  const [isScrollable, setIsScrollable] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Restore draft from localStorage
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      setText(saved);
    }
  }, []);

  // Save draft on change
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setText(val);
    localStorage.setItem(STORAGE_KEY, val);
    adjustHeight();
  };

  const adjustHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollH = textareaRef.current.scrollHeight;
      const exceeds = scrollH > 96;
      setIsScrollable(exceeds);
      const newHeight = Math.min(scrollH, 96);
      textareaRef.current.style.height = `${Math.max(newHeight, 34)}px`;
    }
  };

  useEffect(() => {
    adjustHeight();
  }, [text]);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!text.trim() || isLoading) return;
    const value = text;
    setText('');
    setIsScrollable(false);
    localStorage.removeItem(STORAGE_KEY);
    if (textareaRef.current) {
      textareaRef.current.style.height = '34px';
    }
    await onSend(value);
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 p-3 pb-[calc(env(safe-area-inset-bottom)+0.6rem)] bg-gradient-to-t from-[#f6f8f6] via-[#f6f8f6]/95 to-transparent z-30 pointer-events-none">
      <div className="max-w-md mx-auto pointer-events-auto">
        {/* Status indicator directly anchored right above text box */}
        {isLoading && (
          <div className="flex justify-center mb-1.5 animate-in fade-in slide-in-from-bottom-1 duration-150">
            <div className="inline-flex items-center gap-1.5 py-1 px-3 bg-white/95 border border-[#e0e6e0] shadow-sm rounded-full text-[12px] text-[#475569] animate-pulse">
              <Loader2 size={13} className="animate-spin text-[#15803d]" />
              <span>מנתח ומסווג פריטים בבינה מלאכותית...</span>
            </div>
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="flex items-center bg-[#edf2ed] border border-[#e0e6e0] rounded-full px-2 py-1 shadow-sm focus-within:border-[#cbd5cb] focus-within:bg-white transition-all"
        >
          {/* Send Up-Arrow Button (on the LEFT side) */}
          <button
            type="button"
            onClick={() => handleSubmit()}
            disabled={!text.trim() || isLoading}
            className={`w-[34px] h-[34px] rounded-full flex items-center justify-center transition-all flex-shrink-0 ${
              text.trim() && !isLoading
                ? 'bg-[#1e232a] text-white hover:bg-black active:scale-95'
                : 'bg-[#dce3dc] text-[#8c9ba5] cursor-not-allowed'
            }`}
            title="שלח"
          >
            {isLoading ? (
              <Loader2 size={16} className="animate-spin text-[#64748b]" />
            ) : (
              <ArrowUp size={17} strokeWidth={2.4} />
            )}
          </button>

          {/* Multiline Textarea: Scrollbar only appears if text exceeds 4 lines */}
          <textarea
            ref={textareaRef}
            rows={1}
            dir="rtl"
            value={text}
            onChange={handleChange}
            placeholder=""
            className={`flex-1 bg-transparent border-none outline-none px-2.5 py-1.5 text-[15px] text-[#1e232a] resize-none leading-relaxed text-right placeholder-transparent ${
              isScrollable ? 'overflow-y-auto' : 'overflow-hidden'
            }`}
            disabled={isLoading}
          />

          {/* Plus Manual Add Button (on the RIGHT side) */}
          <button
            type="button"
            onClick={onOpenManualAdd}
            className="w-8 h-8 rounded-full flex items-center justify-center text-[#8c9ba5] hover:text-[#4b5563] hover:bg-[#dce3dc]/50 transition-colors flex-shrink-0"
            title="הוספה ידנית"
          >
            <Plus size={19} strokeWidth={2.2} />
          </button>
        </form>
      </div>
    </div>
  );
};
