import {
  createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode,
} from 'react';
import { Icon } from '@iconify/react';
import dangerTriangleBold from '@iconify/icons-solar/danger-triangle-bold';
import checkCircleBold from '@iconify/icons-solar/check-circle-bold';
import infoCircleBold from '@iconify/icons-solar/info-circle-bold';
import closeCircleBold from '@iconify/icons-solar/close-circle-bold';

type ToastColor = 'default' | 'success' | 'warning' | 'danger';

type Toast = {
  id: number;
  title: string;
  description?: string;
  color?: ToastColor;
  duration?: number;
};

type ToastContextValue = {
  addToast: (toast: Omit<Toast, 'id'>) => void;
};

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

function colorStyles(color: ToastColor | undefined) {
  switch (color) {
    case 'success':
      return 'border-success-200 bg-success-50 text-success-800';
    case 'warning':
      return 'border-warning-200 bg-warning-50 text-warning-800';
    case 'danger':
      return 'border-danger-200 bg-danger-50 text-danger-800';
    default:
      return 'border-default-200 bg-default-50 text-default-800';
  }
}

function colorIcon(color: ToastColor | undefined) {
  if (color === 'success') return checkCircleBold;
  if (color === 'danger') return closeCircleBold;
  if (color === 'warning') return dangerTriangleBold;
  return infoCircleBold;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  const addToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = ++idRef.current;
    const duration = toast.duration ?? 6000;
    setToasts(prev => [...prev, { ...toast, id }]);
    window.setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, duration);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const value = useMemo(() => ({ addToast }), [addToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-3 max-w-sm">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={`flex w-full items-start gap-3 rounded-2xl border p-3 shadow-lg backdrop-blur ${colorStyles(toast.color)}`}
          >
            <div className="mt-0.5 shrink-0">
              <Icon icon={colorIcon(toast.color)} fontSize={20} />
            </div>
            <div className="flex-1 space-y-1">
              <p className="font-semibold leading-tight">{toast.title}</p>
              {toast.description && <p className="text-sm leading-relaxed text-default-600">{toast.description}</p>}
            </div>
            <button
              type="button"
              aria-label="Dismiss"
              onClick={() => dismiss(toast.id)}
              className="rounded-full p-1 text-default-500 hover:text-default-800 transition-colors"
            >
              <Icon icon={closeCircleBold} fontSize={18} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
