import React, { useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "../../lib/utils";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
  className?: string;
  maxWidth?: string;
}

export const Dialog: React.FC<DialogProps> = ({
  open,
  onOpenChange,
  children,
  className,
  maxWidth = "max-w-2xl",
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        onOpenChange(false);
      }
    };
    if (open) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.body.style.overflow = "unset";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity animate-in fade-in duration-200"
        onClick={() => onOpenChange(false)}
      />

      {/* Modal Card */}
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "relative z-10 w-full bg-white rounded border border-slate-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]",
          maxWidth,
          className
        )}
      >
        {children}
      </div>
    </div>
  );
};

export const DialogHeader: React.FC<{
  title: string;
  description?: string;
  onClose?: () => void;
  className?: string;
}> = ({ title, description, onClose, className }) => {
  return (
    <div className={cn("px-6 py-4 border-b border-slate-200 flex items-start justify-between bg-slate-50/50", className)}>
      <div>
        <h2 className="text-lg font-semibold text-slate-900 leading-tight">{title}</h2>
        {description && <p className="text-xs text-slate-500 mt-1">{description}</p>}
      </div>
      {onClose && (
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-700 transition-colors rounded p-1 -mr-2"
          aria-label="Close dialog"
        >
          <X className="h-5 w-5" />
        </button>
      )}
    </div>
  );
};

export const DialogBody: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className,
}) => {
  return <div className={cn("p-6 overflow-y-auto flex-1", className)}>{children}</div>;
};

export const DialogFooter: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className,
}) => {
  return (
    <div className={cn("px-6 py-3.5 border-t border-slate-200 bg-slate-50 flex items-center justify-end gap-3", className)}>
      {children}
    </div>
  );
};
