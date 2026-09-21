import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

type ToastVariant = 'success' | 'error' | 'info' | 'warning';

interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
}

interface ToastContextType {
  toast: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextType>({ toast: () => {} });

export const useToast = () => useContext(ToastContext);

const ICONS: Record<ToastVariant, string> = {
  success: '✓',
  error: '✕',
  info: 'ℹ',
  warning: '⚠',
};

const COLORS: Record<ToastVariant, { bg: string; border: string; icon: string }> = {
  success: { bg: 'rgba(5,150,105,0.12)', border: 'rgba(5,150,105,0.3)', icon: '#34d399' },
  error: { bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)', icon: '#f87171' },
  info: { bg: 'rgba(124,58,237,0.12)', border: 'rgba(124,58,237,0.3)', icon: '#a78bfa' },
  warning: { bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.3)', icon: '#fbbf24' },
};

let counter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, variant: ToastVariant = 'info') => {
    const id = ++counter;
    setToasts(t => [...t, { id, message, variant }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500);
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-5 right-5 flex flex-col gap-2 z-[100]" style={{ maxWidth: 360 }}>
        {toasts.map(t => {
          const c = COLORS[t.variant];
          return (
            <div
              key={t.id}
              className="flex items-center gap-3 px-4 py-3 rounded-xl border shadow-2xl text-sm"
              style={{ background: 'var(--card)', borderColor: c.border }}
            >
              <div
                className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                style={{ background: c.bg, color: c.icon }}
              >
                {ICONS[t.variant]}
              </div>
              <span style={{ color: 'var(--foreground)' }}>{t.message}</span>
              <button
                onClick={() => setToasts(ts => ts.filter(x => x.id !== t.id))}
                className="ml-auto flex-shrink-0 text-xs"
                style={{ color: 'var(--muted-foreground)' }}
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
