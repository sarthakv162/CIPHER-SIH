import { useQuery } from '@tanstack/react-query'
import { Check } from 'lucide-react'
import { api, type ArtefactType } from '@/lib/api'
import { cn } from '@/lib/utils'

export function useTemplates() {
  return useQuery({ queryKey: ['templates'], queryFn: api.templates, staleTime: 60_000 })
}

/** Thumbnail grid of the document templates that support `supports`, with a selected state. */
export function TemplatePicker({
  value,
  onChange,
  supports,
  disabled,
}: {
  value: string
  onChange: (id: string) => void
  supports: ArtefactType
  disabled?: boolean
}) {
  const { data, isLoading } = useTemplates()
  const templates = (data ?? []).filter((t) => t.supports.includes(supports))

  if (isLoading) {
    return (
      <p role="status" className="text-[14px] text-text-1">
        Loading templates…
      </p>
    )
  }
  if (!templates.length) return null

  return (
    <div role="radiogroup" aria-label="Output template" className="grid grid-cols-3 gap-2.5">
      {templates.map((template) => {
        const active = template.id === value
        return (
          <button
            key={template.id}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled}
            onClick={() => onChange(template.id)}
            title={template.description}
            className={cn(
              'group overflow-hidden rounded-[10px] border text-left transition-colors',
              'disabled:cursor-not-allowed disabled:opacity-60',
              active
                ? 'border-accent ring-2 ring-accent/25'
                : 'border-border hover:border-border-2',
            )}
          >
            <div className="aspect-[16/10] w-full bg-bg-2">
              {template.thumbnail_url && (
                <img
                  src={template.thumbnail_url}
                  alt=""
                  className="size-full object-cover"
                  loading="lazy"
                />
              )}
            </div>
            <div className="flex items-center justify-between gap-1 px-2 py-1.5">
              <span className="truncate text-[13px] font-medium text-text-0">
                {template.label}
              </span>
              {active && <Check className="size-3.5 shrink-0 text-accent" strokeWidth={2.5} />}
            </div>
          </button>
        )
      })}
    </div>
  )
}
