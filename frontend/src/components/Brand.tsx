import { cn } from '@/lib/utils'

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      className={cn('size-9', className)}
      aria-hidden="true"
    >
      <path d="M7 11 19 4l12 7-12 7L7 11Z" fill="currentColor" />
      <path
        d="m7 19 12 7 14-8v8l-14 8L7 27v-8Z"
        fill="currentColor"
        opacity=".7"
      />
      <path d="m7 12 12 7v6L7 18v-6Z" fill="currentColor" opacity=".4" />
    </svg>
  )
}
