import { cn } from '@/lib/utils'

interface SegmentedProps<T extends string> {
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}

/**
 * Segmented control, not a dropdown: every option stays visible, so the operator
 * sees the whole parameter space without opening anything.
 */
export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: SegmentedProps<T>) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[15px] text-text-1">{label}</span>
      <div
        role="radiogroup"
        aria-label={label}
        className="flex flex-wrap gap-1 rounded-[8px] border border-border bg-bg-0 p-1"
      >
        {options.map((option) => {
          const active = option.value === value
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(option.value)}
              className={cn(
                'flex-1 rounded-[5px] px-2 py-1.5 text-[15px] whitespace-nowrap transition-colors duration-150',
                active
                  ? 'bg-bg-3 text-text-0 shadow-[inset_0_1px_0_0_rgb(255_255_255/0.05)]'
                  : 'text-text-1 hover:bg-bg-2 hover:text-text-0',
              )}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
