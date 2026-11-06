import React, { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '4xl';
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = 'md',
}) => {
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  const titleId = useId();

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;
    document.body.style.overflow = 'hidden';

    const getFocusable = () =>
      panelRef.current
        ? Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
        : [];

    const initial = getFocusable();
    (initial[0] ?? panelRef.current)?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onCloseRef.current();
        return;
      }
      if (event.key !== 'Tab') return;

      const focusable = getFocusable();
      if (focusable.length === 0) {
        event.preventDefault();
        panelRef.current?.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
      previouslyFocused?.focus?.();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const maxWidthClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
    '4xl': 'max-w-4xl',
  }[maxWidth];

  return createPortal(
    <div className="overlay-enter fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cn(
          'dialog-enter w-full bg-white dark:bg-[#2F3349] rounded-xl shadow-2xl border border-slate-200 dark:border-white/[0.08] overflow-hidden flex flex-col max-h-[90vh] focus:outline-none',
          maxWidthClasses
        )}
      >
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3.5 dark:border-white/[0.08] sm:px-6 sm:py-4">
          <h2
            id={titleId}
            className="min-w-0 text-sm font-bold text-slate-800 dark:text-white sm:text-base"
          >
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Kapat"
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.05] transition-colors"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>
        <div className="overflow-y-auto p-4 sm:p-6">{children}</div>
      </div>
    </div>,
    document.body
  );
};
