import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merge conditional class names, letting later Tailwind utilities win. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Format a byte count as GB with one decimal, for the memory panel. */
export function gb(bytes: number): string {
  return (bytes / 1_000_000_000).toFixed(1)
}

/** Format a whole-second duration as `2m 30s`, or `45s` under a minute. */
export function duration(seconds: number): string {
  const total = Math.round(seconds)
  if (total < 60) return `${total}s`
  const minutes = Math.floor(total / 60)
  return `${minutes}m ${String(total % 60).padStart(2, '0')}s`
}
