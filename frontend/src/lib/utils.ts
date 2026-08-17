import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// The backend stores every timestamp as a naive UTC instant (see
// backend/app/services/matching_engine.py and scripts/generate_synthetic_data.py)
// and FastAPI serializes naive datetimes without a "Z"/offset suffix. JS
// treats an offset-less ISO string as *local* time, so we normalize here to
// make sure it's always interpreted as UTC before converting to a display zone.
function asUtcDate(iso: string): Date {
  const hasOffset = /Z$|[+-]\d{2}:\d{2}$/.test(iso);
  return new Date(hasOffset ? iso : `${iso}Z`);
}

export function formatDateTime(iso: string, timeZone?: string): string {
  const d = asUtcDate(iso);
  return d.toLocaleString("en-US", {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: timeZone || "UTC",
  });
}

export function formatDate(iso: string, timeZone?: string): string {
  const d = asUtcDate(iso);
  return d.toLocaleDateString("en-US", {
    day: "numeric",
    month: "short",
    timeZone: timeZone || "UTC",
  });
}

export function formatTime(iso: string, timeZone?: string): string {
  const d = asUtcDate(iso);
  return d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: timeZone || "UTC",
  });
}
