import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, FileStack, Search, Plus, RefreshCw } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { useRecentTransforms } from '@/lib/transforms'
import { ARTEFACT_BY_TYPE, CATEGORIES, type ArtefactCategory } from '@/lib/artefacts'
import { ArtefactVisual, CategoryFilters } from '@/components/ArtefactCatalog'
import { cn } from '@/lib/utils'

export function Library() {
  const { data, isLoading, isError, refetch } = useRecentTransforms()
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [category, setCategory] = useState<ArtefactCategory>('all')
  const rows = data ?? []
  const visible = rows.filter(
    (row) =>
      `${row.transform_id} ${row.output_types.map((t) => ARTEFACT_BY_TYPE.get(t)?.label).join(' ')}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (category === 'all' || row.output_types.some(type => ARTEFACT_BY_TYPE.get(type)?.category === category)) &&
      (filter === 'all' ||
        (filter === 'review' ? row.conflicts > 0 : row.status === filter)),
  )
  return (
    <>
      <Header title="Library" />
      <div className="page-scroll">
        <div className="mx-auto max-w-[960px]">
          <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="welcome-eyebrow !text-left mb-2">THE THINGS YOU MAKE</p>
              <h1 className="page-heading">Your creative library.</h1>
              <p className="mt-2 text-[15px] text-text-1">
                Browse, review, and export your latest 25 transforms.
              </p>
            </div>
            <Link to="/workspace" className="primary-button">
              <Plus className="size-4" /> Create new
            </Link>
          </div>
          <div className="relative mb-6">
            <Search className="pointer-events-none absolute top-1/2 left-4 size-[18px] -translate-y-1/2 text-text-1" />
            <input
              aria-label="Search transforms"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search your outputs"
              className="w-full rounded-xl border border-border bg-bg-2 py-3 pr-4 pl-11 text-[16px]"
            />
          </div>
          <CategoryFilters value={category} onChange={setCategory} />
          <div className="mb-5 flex flex-wrap gap-2">
            {[
              { value: 'all', label: 'All transforms' },
              { value: 'SUCCEEDED', label: 'Completed' },
              { value: 'RUNNING', label: 'Generating' },
              { value: 'FAILED', label: 'Failed' },
              { value: 'review', label: 'With conflicts' },
            ].map((item) => (
              <button
                key={item.value}
                type="button"
                aria-pressed={filter === item.value}
                onClick={() => setFilter(item.value)}
                className={cn(
                  'rounded-lg px-4 py-2 text-[14px]',
                  filter === item.value
                    ? 'bg-bg-3 text-text-0'
                    : 'text-text-1 hover:bg-bg-2',
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
          {isError ? (
            <div role="alert" className="py-16 text-center">
              <p>Unable to load your library</p>
              <p className="mt-2 text-[14px] text-text-1">
                Check that the local engine is running.
              </p>
              <button
                type="button"
                onClick={() => void refetch()}
                className="secondary-button mt-5"
              >
                <RefreshCw className="size-4" /> Try again
              </button>
            </div>
          ) : isLoading ? (
            <p role="status" className="py-12 text-center text-text-1">
              Loading your outputs…
            </p>
          ) : visible.length ? (
            <div className="library-grid">
              {visible.map((row) => (
                <Link
                  key={row.transform_id}
                  to={
                    row.status === 'SUCCEEDED'
                      ? `/runs/${row.transform_id}/artefacts`
                      : `/runs/${row.transform_id}`
                  }
                  className="library-card group"
                >
                  <div className="library-card-preview" data-category={ARTEFACT_BY_TYPE.get(row.output_types[0])?.category}>
                    {row.output_types.slice(0, 3).map(type => <ArtefactVisual key={type} type={type} />)}
                    <span className="library-open"><ArrowUpRight className="size-4" /></span>
                  </div>
                  <div className="library-card-body">
                  <div className="mb-3 flex flex-wrap gap-1.5">{[...new Set(row.output_types.map(type => ARTEFACT_BY_TYPE.get(type)?.category))].map(id => <span className="format-tag" key={id}>{CATEGORIES.find(c => c.id === id)?.label ?? 'Content'}</span>)}</div>
                  <div className="min-w-0 flex-1">
                    <h2 className="text-[16px] font-medium">
                      {row.output_types.length === 1
                        ? ARTEFACT_BY_TYPE.get(row.output_types[0])?.label
                        : `${row.output_types.length} content formats`}
                    </h2>
                    <p className="mt-1 truncate text-[14px] text-text-1">
                      {row.output_types
                        .map((t) => ARTEFACT_BY_TYPE.get(t)?.label)
                        .join(' · ')}
                    </p>
                    <p className="mt-1 text-[14px] text-text-1">
                      {new Date(row.created_at).toLocaleDateString(undefined, {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                      })}
                      {row.conflicts > 0 && (
                        <span className="ml-3 text-danger">
                          {row.conflicts} conflict
                          {row.conflicts === 1 ? '' : 's'}
                        </span>
                      )}
                    </p>
                  </div>
                  <span
                    className={cn(
                      'mt-4 inline-flex rounded-md px-2.5 py-1 text-[12px]',
                      row.status === 'SUCCEEDED'
                        ? 'bg-bg-3 text-text-1'
                        : row.status === 'FAILED'
                          ? 'bg-danger/8 text-danger'
                          : 'bg-accent/8 text-accent',
                    )}
                  >
                    {row.status === 'SUCCEEDED'
                      ? 'Completed'
                      : row.status === 'RUNNING'
                        ? 'Generating'
                        : row.status === 'FAILED'
                          ? 'Failed'
                          : 'Queued'}
                  </span>
                  </div>
                  <span className="sr-only">
                    {row.status === 'SUCCEEDED' ? 'View outputs' : 'View run'}
                  </span>
                </Link>
              ))}
            </div>
          ) : (
            <div className="py-20 text-center">
              <div className="empty-art">
                <FileStack className="size-7" strokeWidth={1.4} />
              </div>
              <h2 className="text-[22px]">
                {rows.length ? 'No matching transforms' : 'No outputs yet'}
              </h2>
              <p className="mx-auto mt-2 max-w-sm text-[15px] text-text-1">
                {rows.length
                  ? 'Try a different search or filter.'
                  : 'Add a source to create your first summary, presentation, or post.'}
              </p>
              {rows.length ? (
                <button
                  type="button"
                  onClick={() => {
                    setSearch('')
                    setFilter('all')
                    setCategory('all')
                  }}
                  className="secondary-button mt-6"
                >
                  Clear filters
                </button>
              ) : (
                <Link to="/workspace" className="primary-button mt-6">
                  Create a transform
                </Link>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
