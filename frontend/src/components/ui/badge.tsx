import React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 select-none",
  {
    variants: {
      variant: {
        default: "bg-blue-50 text-blue-700 border border-blue-200",
        secondary: "bg-slate-100 text-slate-800 border border-slate-200",
        outline: "border border-slate-300 text-slate-700 bg-white",
        success: "bg-emerald-50 text-emerald-800 border border-emerald-200",
        warning: "bg-amber-50 text-amber-800 border border-amber-200",
        danger: "bg-rose-50 text-rose-800 border border-rose-200",
        work_remote: "bg-indigo-50 text-indigo-700 border border-indigo-200",
        work_hybrid: "bg-sky-50 text-sky-700 border border-sky-200",
        work_onsite: "bg-slate-50 text-slate-700 border border-slate-300",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge: React.FC<BadgeProps> = ({ className, variant, ...props }) => {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
};
