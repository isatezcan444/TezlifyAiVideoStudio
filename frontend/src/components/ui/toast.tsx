import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';

export type ToastVariant = 'success' | 'error' | 'info' | 'warning';

export interface ToastOptions {
  title: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
}

interface ToastItem {
  id: number;
  title: string;
  description?: string;
  variant: ToastVariant;
  duration: number;
}

interface ToastContextValue {
  notify: (options: ToastOptions) => number;
  dismiss: (id: number) => void;
}

const NOOP_CONTEXT: ToastContextValue = {
  notify: () => 0,
  dismiss: () => {},
};

const ToastContext = createContext<ToastContextValue>(NOOP_CONTEXT);

export const useToast = (): ToastContextValue => useContext(ToastContext);

const DEFAULT_DURATION = 5000;

const VARIANT_META: Record<
  ToastVariant,
  { icon: typeof Info; iconClass: string }
> = {
  success: {
    icon: CheckCircle2,
    iconClass: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  },
  error: {
    icon: AlertCircle,
    iconClass: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
  },
  warning: {
    icon: AlertTriangle,
    iconClass: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  },
  info: {
    icon: Info,
    iconClass: 'bg-[#7367F0]/10 text-[#7367F0]',
  },
};

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [items, setItems] = useState<ToastItem[]>([]);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
    setItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const notify = useCallback(
    (options: ToastOptions) => {
      const id = nextId.current++;
      const item: ToastItem = {
        id,
        title: options.title,
        description: options.description,
        variant: options.variant ?? 'info',
        duration: options.duration ?? DEFAULT_DURATION,
      };
      setItems((prev) => [...prev.slice(-3), item]);

      if (item.duration > 0) {
        timers.current.set(
          id,
          setTimeout(() => dismiss(id), item.duration)
        );
      }
      return id;
    },
    [dismiss]
  );

  useEffect(() => {
    const activeTimers = timers.current;
    return () => {
      activeTimers.forEach((timer) => clearTimeout(timer));
      activeTimers.clear();
    };
  }, []);

  const value = useMemo(() => ({ notify, dismiss }), [notify, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 top-0 z-[100] flex flex-col items-end gap-2 p-4 sm:inset-x-auto sm:right-0"
      >
        {items.map((item) => {
          const meta = VARIANT_META[item.variant];
          const Icon = meta.icon;
          return (
            <div
              key={item.id}
              role={item.variant === 'error' ? 'alert' : 'status'}
              className="toast-enter pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-lg shadow-slate-900/10 dark:border-white/[0.08] dark:bg-[#2F3349] dark:shadow-black/30"
            >
              <span
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${meta.iconClass}`}
              >
                <Icon className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                  {item.title}
                </p>
                {item.description && (
                  <p className="mt-0.5 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
                    {item.description}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismiss(item.id)}
                aria-label="Bildirimi kapat"
                className="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-white/[0.06] dark:hover:text-white"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};
