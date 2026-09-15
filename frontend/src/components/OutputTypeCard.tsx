import { Check, Clock3, type LucideIcon } from 'lucide-react'
import { cn, duration } from '@/lib/utils'

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
      data-selected={selected}
      className="output-card"
    >
      <span className="flex w-full items-center justify-between">
        <span
          className={cn(
            'icon-tile !size-8 !rounded-lg',
            !selected && '!bg-bg-2 !text-text-1',
          )}
        >
          <Icon className="size-4" strokeWidth={1.65} />
        </span>
        <span
          aria-hidden="true"
          className={cn(
            'flex size-4 items-center justify-center rounded-[5px] border',
            selected
              ? 'border-accent bg-accent text-[var(--on-accent)]'
              : 'border-border-2',
          )}
        >
          {selected && <Check className="size-2.5" strokeWidth={3} />}
        </span>
      </span>
      <span className="text-[14px] font-medium leading-tight tracking-[-.02em]">
        {label}
      </span>
      <span className="text-[13px] leading-[1.7] text-text-1">
        {description}
      </span>
      <span className="mt-auto flex w-full flex-wrap items-center justify-between gap-1.5 pt-1">
        <span className="flex gap-1">
          {formats.map((format) => (
            <span key={format} className="format-tag">
              {format}
            </span>
          ))}
        </span>
        <span className="tabular flex items-center gap-1 text-[12px] text-text-1">
          <Clock3 className="size-2.5" />~{duration(seconds)}
        </span>
      </span>
    </button>
  )
}
