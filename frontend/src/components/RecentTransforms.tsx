import { NavLink } from 'react-router-dom'
import { useRecentTransforms } from '@/lib/transforms'
import { cn } from '@/lib/utils'

/** Recent work, newest first. A red dot means verification found a conflict that
 *  nobody has released yet — visible before the operator opens the run. */
export function RecentTransforms() {
  const { data, isLoading, isError } = useRecentTransforms()

  if (isLoading) {
    return (
      <p className="px-3 py-2 text-[14px] text-text-1">Loading activity…</p>
    )
  }

  if (!data || data.length === 0) {
    return (
      <p className="px-3 py-2 text-[14px] leading-relaxed text-text-1">
        {isError
          ? 'Local engine unavailable.'
          : 'Your transforms will appear here.'}
      </p>
    )
  }

  return (
    <ul className="flex flex-col gap-0.5">
      {data.slice(0, 8).map((row) => (
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
              <span className="tabular truncate text-[14px] capitalize text-text-0">
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
            <span className="tabular truncate pl-3 text-[12px] text-text-1">
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
