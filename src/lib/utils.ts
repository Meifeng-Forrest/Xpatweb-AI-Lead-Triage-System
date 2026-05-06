import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString: string) {
  const date = new Date(dateString);
  return date.toLocaleString('en-ZA', { 
    hour: '2-digit', 
    minute: '2-digit',
    day: '2-digit',
    month: 'short'
  });
}
