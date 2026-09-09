import { Check, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { duration } from '@/lib/utils'

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
    <button
      type="button"
      role="checkbox"
      aria-checked={selected}
      aria-label={label}
      disabled={disabled}
      onClick={onToggle}
      className={cn(
        'group relative flex flex-col items-start gap-2 rounded-[12px] border p-3.5 text-left',
        'transition-all duration-150 ease-[cubic-bezier(0.2,0,0,1)]',
        disabled && 'cursor-not-allowed opacity-40',
        !disabled && 'hover:border-border-2 hover:bg-bg-3',
        selected
          ? 'border-accent/60 bg-bg-2 shadow-[0_0_0_1px_rgba(91,141,239,0.25)]'
          : 'border-border bg-bg-2',
      )}
    >
      <span className="flex w-full items-start justify-between gap-2">
        <Icon
          className={cn('size-4 shrink-0', selected ? 'text-accent' : 'text-text-1')}
          strokeWidth={1.75}
        />
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

      <span className="text-[13px] leading-tight text-text-0">{label}</span>
      <span className="text-[12px] leading-snug text-text-1">{description}</span>

      <span className="mt-auto flex w-full items-center justify-between gap-2 pt-1.5">
        <span className="flex gap-1">
          {formats.map((format) => (
            <span
              key={format}
              className="rounded-[4px] border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-text-1"
            >
              {format}
            </span>
          ))}
        </span>
        <span className="tabular text-[11px] text-text-1">~{duration(seconds)}</span>
      </span>
    </button>
  )
}
