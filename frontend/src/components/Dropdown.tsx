import { useId } from 'react'
import { ChevronDown } from 'lucide-react'

interface DropdownProps<T extends string> {
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}

/** Native selection supports arrows, type-ahead, screen readers, and touch. */
export function Dropdown<T extends string>({
  label,
  value,
  options,
  onChange,
}: DropdownProps<T>) {
  const id = useId()
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="text-[14px] text-text-1">
        {label}
      </label>
      <div className="relative">
        <select
          id={id}
          value={value}
          onChange={(event) => onChange(event.target.value as T)}
          className="w-full appearance-none rounded-lg border border-border bg-bg-2 py-2.5 pr-8 pl-3 text-[14px] text-text-0 transition-colors hover:border-border-2 focus:border-accent"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 right-3 size-3 -translate-y-1/2 text-text-1"
        />
      </div>
    </div>
  )
}
