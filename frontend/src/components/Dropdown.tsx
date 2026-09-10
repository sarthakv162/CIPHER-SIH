import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

const EASE = [0.2, 0, 0, 1] as const

interface DropdownProps<T extends string> {
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}

/** Labelled select. Keyboard-operable, closes on Escape and on outside click. */
export function Dropdown<T extends string>({
  label,
  value,
  options,
  onChange,
}: DropdownProps<T>) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement | null>(null)
  const current = options.find((option) => option.value === value)

  useEffect(() => {
    if (!open) return
    const onDown = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={root} className="relative flex flex-col gap-1.5">
      <span className="text-[15px] text-text-1">{label}</span>

      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className={cn(
          'flex items-center justify-between gap-2 rounded-[8px] border px-2.5 py-2 text-left text-[15px]',
          'transition-colors duration-150 ease-[cubic-bezier(0.2,0,0,1)]',
          open
            ? 'border-accent/50 bg-bg-3 text-text-0'
            : 'border-border bg-bg-0 text-text-0 hover:border-border-2 hover:bg-bg-2',
        )}
      >
        <span className="truncate">{current?.label ?? value}</span>
        <ChevronDown
          className={cn(
            'size-3.5 shrink-0 text-text-1 transition-transform duration-200',
            open && 'rotate-180',
          )}
          strokeWidth={1.75}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.ul
            role="listbox"
            aria-label={label}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15, ease: EASE }}
            className="absolute top-full right-0 left-0 z-30 mt-1 max-h-56 overflow-y-auto rounded-[8px] border border-border-2 bg-bg-3 p-1 shadow-[0_16px_40px_-12px_rgb(0_0_0/0.85)]"
          >
            {options.map((option) => {
              const active = option.value === value
              return (
                <li key={option.value}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={active}
                    onClick={() => {
                      onChange(option.value)
                      setOpen(false)
                    }}
                    className={cn(
                      'flex w-full items-center justify-between gap-2 rounded-[5px] px-2 py-1.5 text-left text-[15px]',
                      'transition-colors duration-150',
                      active
                        ? 'bg-accent/15 text-text-0'
                        : 'text-text-1 hover:bg-bg-3 hover:text-text-0',
                    )}
                  >
                    {option.label}
                    {active && (
                      <Check className="size-3 shrink-0 text-accent" strokeWidth={2.5} />
                    )}
                  </button>
                </li>
              )
            })}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  )
}
