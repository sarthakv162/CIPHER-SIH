import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'

interface TransformRow {
  transform_id: string
  created_at: string
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'
  output_types: string[]
  job_count: number
  has_verification: boolean
  verification_ok: boolean
  conflicts: number
}

/** Recent work, newest first. A red dot means verification found a conflict that
 *  nobody has released yet — visible before the operator opens the run. */
export function RecentTransforms() {
  const { data, isLoading } = useQuery({
    queryKey: ['transforms'],
    queryFn: async (): Promise<TransformRow[]> => {
      const response = await fetch('/transforms?limit=25')
      if (!response.ok) throw new Error('transforms unavailable')
      return (await response.json()) as TransformRow[]
    },
    refetchInterval: 20_000,
  })

  if (isLoading) {
    return <p className="px-2.5 py-1.5 text-[15px] text-text-1">Loading…</p>
  }

  if (!data || data.length === 0) {
    return <p className="px-2.5 py-1.5 text-[15px] text-text-1">No transforms yet.</p>
  }

  return (
    <ul className="flex flex-col gap-0.5">
      {data.map((row) => (
        <li key={row.transform_id}>
          <NavLink
            to={`/runs/${row.transform_id}`}
            className={({ isActive }) =>
              cn(
                'flex flex-col gap-0.5 rounded-[8px] px-2.5 py-1.5 transition-colors duration-150',
                isActive ? 'bg-bg-3' : 'hover:bg-bg-2',
              )
            }
          >
            <span className="flex items-center gap-1.5">
              <span
                className={cn(
                  'size-1.5 shrink-0 rounded-full',
                  row.status === 'RUNNING'
                    ? 'bg-accent'
                    : row.status === 'FAILED'
                      ? 'bg-danger'
                      : row.status === 'PENDING'
                        ? 'bg-text-2'
                        : 'bg-ok',
                )}
              />
              <span className="tabular truncate text-[15px] text-text-0">
                {row.output_types.length === 1
                  ? row.output_types[0].replace(/_/g, ' ')
                  : `${row.job_count} artefacts`}
              </span>
              {row.conflicts > 0 && (
                <span
                  className="ml-auto size-1.5 shrink-0 rounded-full bg-danger"
                  title={`${row.conflicts} conflict${row.conflicts === 1 ? '' : 's'} found by verification`}
                />
              )}
            </span>
            <span className="tabular truncate pl-3 text-[14px] text-text-1">
              {new Date(row.created_at).toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </NavLink>
        </li>
      ))}
    </ul>
  )
}
