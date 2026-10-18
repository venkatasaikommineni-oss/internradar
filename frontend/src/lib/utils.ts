import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatINR(val?: number | null): string {
  if (val == null || isNaN(val)) return "Unspecified";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(val);
}

export function formatDate(dateString?: string | null): string {
  if (!dateString) return "Rolling / Unspecified";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "Unspecified";
    return d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateString;
  }
}

export function getDaysRemaining(dateString?: string | null): number | null {
  if (!dateString) return null;
  try {
    const deadline = new Date(dateString).getTime();
    const now = Date.now();
    const diff = deadline - now;
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
  } catch {
    return null;
  }
}
