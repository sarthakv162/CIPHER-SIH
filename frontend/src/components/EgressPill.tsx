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

  if (isError || !data) {
    return (
      <span
        role="status"
        className="flex items-center gap-2 text-[14px] text-text-1"
      >
        <ShieldAlert className="size-3.5" strokeWidth={1.75} />
        <span className="hidden sm:inline">
          {isError ? 'Engine unavailable' : 'Checking status…'}
        </span>
      </span>
    )
  }

  const clean = data.clean
  const count = data.violations.length

  return (
    <span
      role="status"
      className={cn(
        'flex items-center gap-2 text-[14px] transition-colors duration-200',
        clean ? 'text-text-1' : 'text-danger',
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
            <span className="hidden sm:inline">On-device · Offline</span>
            <span className="sm:hidden">Offline</span>
          </>
        ) : (
          `Egress violation · ${count}`
        )}
      </span>
    </span>
  )
}
