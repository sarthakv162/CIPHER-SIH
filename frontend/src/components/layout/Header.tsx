import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { EgressPill } from '@/components/EgressPill'
import { cn } from '@/lib/utils'

/** Profile chip: which hardware profile the backend resolved, and how. */
function ProfileChip() {
  const { data } = useQuery({ queryKey: ['health'], queryFn: api.health, staleTime: 60_000 })
  if (!data) return null
  return (
    <span
      className="flex items-center gap-1.5 rounded-full border border-border bg-bg-2 px-2.5 py-1 text-[15px] text-text-1"
      title={`Profile chosen by ${data.profile_source} · ${data.platform} · Python ${data.python}`}
    >
      <span className="size-1.5 rounded-full bg-accent" />
      {data.profile}
    </span>
  )
}

/** Residency chip: purple whenever a model is in memory, neutral when none is. */
function ResidencyChip() {
  const { data } = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 10_000,
  })
  const resident = data?.models_resident ?? 0
  return (
    <span
      className={cn(
        'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[15px] transition-colors duration-200',
        resident > 0
          ? 'border-model/25 bg-model/10 text-model'
          : 'border-border bg-bg-2 text-text-1',
      )}
      title="At most one heavy model is ever resident (INV-2)"
    >
      <span
        className={cn('size-1.5 rounded-full', resident > 0 ? 'bg-model' : 'bg-text-2')}
      />
      <span className="tabular">
        {resident > 0 ? `${resident} model resident` : 'No model resident'}
      </span>
    </span>
  )
}

interface HeaderProps {
  title: string
  subtitle?: string
}

export function Header({ title, subtitle }: HeaderProps) {
  return (
    <header className="glass sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border px-5">
      <div className="flex min-w-0 shrink items-baseline gap-2.5">
        <h1 className="shrink-0 text-[17px] text-text-0">{title}</h1>
        {subtitle && (
          <span className="truncate text-[15px] text-text-1">{subtitle}</span>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span className="hidden xl:flex">
          <ProfileChip />
        </span>
        <span className="hidden lg:flex">
          <ResidencyChip />
        </span>
        <EgressPill />
      </div>
    </header>
  )
}
