import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return value;
  }
}

export function severityLabel(severity: number): string {
  if (severity >= 7) return "CRITICAL";
  if (severity >= 5) return "HIGH";
  if (severity >= 3) return "MEDIUM";
  if (severity >= 1) return "LOW";
  return "INFO";
}

export function severityClass(severity: number): string {
  return `severity-pill severity-${Math.max(
    0,
    Math.min(7, Math.floor(severity)),
  )}`;
}

export function fpScoreLabel(score: number | null | undefined): string {
  if (score === null || score === undefined) return "—";
  if (score >= 0.8) return "likely FP";
  if (score >= 0.6) return "soft FP";
  if (score <= 0.2) return "likely TP";
  if (score <= 0.4) return "soft TP";
  return "unmarked";
}
