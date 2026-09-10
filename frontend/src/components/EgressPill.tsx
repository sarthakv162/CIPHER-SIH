import { useQuery } from '@tanstack/react-query'
import { ShieldAlert, ShieldCheck } from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

/**
 * The air-gap indicator. Green means the egress monitor found no non-loopback
 * connection; red means INV-4 was violated and the operator needs to know now.
 * A failed request is reported as unknown, never silently as healthy.
 */
export function EgressPill() {
  const { data, isError } = useQuery({
    queryKey: ['egress'],
    queryFn: api.egress,
    refetchInterval: 15_000,
    staleTime: 10_000,
  })

  if (isError) {
    return (
      <span className="flex items-center gap-1.5 rounded-full border border-border bg-bg-2 px-2.5 py-1 text-[15px] text-text-1">
        <ShieldAlert className="size-3.5" strokeWidth={1.75} />
        Egress unknown
      </span>
    )
  }

  const clean = data?.clean ?? true
  const count = data?.violations.length ?? 0

  return (
    <span
      className={cn(
        'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[15px] transition-colors duration-200',
        clean
          ? 'border-ok/25 bg-ok/10 text-ok'
          : 'border-danger/30 bg-danger/10 text-danger',
      )}
      title={
        clean
          ? 'No non-loopback connection observed in this process tree'
          : 'A non-loopback connection was observed — air-gap violated'
      }
    >
      {clean ? (
        <ShieldCheck className="size-3.5" strokeWidth={1.75} />
      ) : (
        <ShieldAlert className="size-3.5" strokeWidth={1.75} />
      )}
      <span className="tabular">
        {clean ? (
          <>
            <span className="hidden sm:inline">Offline · 0 external connections</span>
            <span className="sm:hidden">Offline</span>
          </>
        ) : (
          `Egress violation · ${count}`
        )}
      </span>
    </span>
  )
}
