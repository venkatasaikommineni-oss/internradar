import React, { createContext, useContext, useState, useCallback } from "react";
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from "lucide-react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
}

interface ToastContextType {
  toast: (options: { type?: ToastType; title: string; message?: string }) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    ({ type = "info", title, message }: { type?: ToastType; title: string; message?: string }) => {
      const id = Math.random().toString(36).slice(2, 9);
      setToasts((prev) => [...prev, { id, type, title, message }]);
      setTimeout(() => {
        removeToast(id);
      }, 4000);
    },
    [removeToast]
  );

  const success = useCallback((title: string, message?: string) => toast({ type: "success", title, message }), [toast]);
  const error = useCallback((title: string, message?: string) => toast({ type: "error", title, message }), [toast]);
  const info = useCallback((title: string, message?: string) => toast({ type: "info", title, message }), [toast]);
  const warning = useCallback((title: string, message?: string) => toast({ type: "warning", title, message }), [toast]);

  return (
    <ToastContext.Provider value={{ toast, success, error, info, warning }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
        {toasts.map((t) => {
          const config = {
            success: {
              icon: CheckCircle2,
              style: "bg-white border-slate-200 text-slate-800",
              iconColor: "text-emerald-600",
              accent: "border-l-4 border-l-emerald-600",
            },
            error: {
              icon: AlertCircle,
              style: "bg-white border-slate-200 text-slate-800",
              iconColor: "text-rose-600",
              accent: "border-l-4 border-l-rose-600",
            },
            warning: {
              icon: AlertTriangle,
              style: "bg-white border-slate-200 text-slate-800",
              iconColor: "text-amber-600",
              accent: "border-l-4 border-l-amber-600",
            },
            info: {
              icon: Info,
              style: "bg-white border-slate-200 text-slate-800",
              iconColor: "text-blue-600",
              accent: "border-l-4 border-l-blue-600",
            },
          }[t.type];

          const IconComponent = config.icon;

          return (
            <div
              key={t.id}
              className={`pointer-events-auto flex items-start gap-3 p-4 rounded shadow-md border ${config.style} ${config.accent} transition-all duration-200 ease-in-out`}
            >
              <IconComponent className={`h-5 w-5 shrink-0 mt-0.5 ${config.iconColor}`} />
              <div className="flex-1 text-sm">
                <p className="font-semibold text-slate-900 leading-tight">{t.title}</p>
                {t.message && <p className="mt-1 text-slate-600 leading-normal text-xs">{t.message}</p>}
              </div>
              <button
                onClick={() => removeToast(t.id)}
                className="text-slate-400 hover:text-slate-600 transition-colors p-0.5"
                aria-label="Close notification"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
