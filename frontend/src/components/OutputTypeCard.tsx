import { motion } from 'framer-motion'
import { Check, type LucideIcon } from 'lucide-react'
import { cn, duration } from '@/lib/utils'

const EASE = [0.2, 0, 0, 1] as const

interface OutputTypeCardProps {
  label: string
  description: string
  formats: string[]
  seconds: number
  icon: LucideIcon
  selected: boolean
  disabled?: boolean
  onToggle: () => void
}

/**
 * One selectable output type.
 *
 * Selection is an accent border plus a check, never a filled background — seven
 * filled cards at once is noise, and the operator needs to read the grid at a
 * glance rather than decode it.
 */
export function OutputTypeCard({
  label,
  description,
  formats,
  seconds,
  icon: Icon,
  selected,
  disabled = false,
  onToggle,
}: OutputTypeCardProps) {
  return (
    <motion.button
      type="button"
      role="checkbox"
      aria-checked={selected}
      aria-label={label}
      disabled={disabled}
      onClick={onToggle}
      whileHover={disabled ? undefined : { y: -2 }}
      whileTap={disabled ? undefined : { scale: 0.985 }}
      transition={{ duration: 0.15, ease: EASE }}
      className={cn(
        'group relative flex flex-col items-start gap-2 overflow-hidden rounded-[12px] border p-4 text-left',
        'transition-[border-color,background-color,box-shadow] duration-200 ease-[cubic-bezier(0.2,0,0,1)]',
        disabled && 'cursor-not-allowed opacity-40',
        selected
          ? 'border-accent/70 bg-bg-3 shadow-[0_0_0_1px_rgba(91,141,239,0.35),0_10px_28px_-14px_rgba(91,141,239,0.75)]'
          : 'border-border bg-bg-2 hover:border-accent/45 hover:bg-bg-3 hover:shadow-[0_10px_26px_-16px_rgba(0,0,0,0.9)]',
      )}
    >
      {/* A selected card gets a lit top edge rather than a filled panel: seven filled
          cards would be noise, but a flat outline reads as inert. */}
      <span
        aria-hidden="true"
        className={cn(
          'pointer-events-none absolute inset-x-0 top-0 h-px transition-opacity duration-200',
          'bg-gradient-to-r from-transparent via-accent to-transparent',
          selected ? 'opacity-90' : 'opacity-0 group-hover:opacity-40',
        )}
      />

      <span className="flex w-full items-start justify-between gap-2">
        <span
          className={cn(
            'flex size-8 shrink-0 items-center justify-center rounded-[8px] border transition-colors duration-200',
            selected
              ? 'border-accent/45 bg-accent/18'
              : 'border-border bg-bg-0 group-hover:border-accent/30 group-hover:bg-accent/10',
          )}
        >
          <Icon
            className={cn('size-4', selected ? 'text-accent' : 'text-text-1')}
            strokeWidth={1.75}
          />
        </span>
        <span
          className={cn(
            'flex size-4 shrink-0 items-center justify-center rounded-full border transition-all duration-150',
            selected
              ? 'border-accent bg-accent text-bg-0'
              : 'border-border bg-transparent text-transparent',
          )}
          aria-hidden="true"
        >
          <Check className="size-2.5" strokeWidth={3} />
        </span>
      </span>

      <span className="text-[17px] leading-tight font-medium text-text-0">{label}</span>
      <span className="text-[15px] leading-snug text-text-1">{description}</span>

      <span className="mt-auto flex w-full items-center justify-between gap-2 pt-1.5">
        <span className="flex gap-1">
          {formats.map((format) => (
            <span
              key={format}
              className="rounded-[4px] border border-border px-1.5 py-0.5 text-[13px] uppercase tracking-wide text-text-1"
            >
              {format}
            </span>
          ))}
        </span>
        <span className="tabular text-[14px] text-text-1">~{duration(seconds)}</span>
      </span>
    </motion.button>
  )
}
