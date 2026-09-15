import { useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence } from 'framer-motion'
import {
  ArrowLeft,
  Download,
  Fingerprint,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { ProvenanceDrawer } from '@/components/ProvenanceDrawer'
import { TemplatePicker } from '@/components/TemplatePicker'
import { LinkedInPreview, XThreadPreview } from '@/components/PlatformPreview'
import {
  AdvisoryView,
  ExecutiveSummaryView,
} from '@/components/viewers/DocumentView'
import {
  InfographicView,
  PresentationView,
  type Scene,
  VideoView,
} from '@/components/viewers/MediaView'
import { ClaimsList } from '@/components/ClaimsList'
import { OversightPanel } from '@/components/OversightPanel'
import { ARTEFACT_BY_TYPE } from '@/lib/artefacts'
import type { ArtefactType } from '@/lib/api'
import { needsReview, useVerification } from '@/lib/verification'
import { cn } from '@/lib/utils'
import { Library } from '@/routes/Library'

const TEMPLATED_TYPES: ArtefactType[] = ['presentation', 'advisory', 'executive_summary']

export interface ArtefactEntry {
  job_id: string
  artefact_type: ArtefactType
  status: string
  path: string | null
  artefact: Record<string, unknown> | null
}

interface FileEntry {
  name: string
  size_bytes: number
  format: string
  content_type: string
  has_manifest: boolean
}

const HUMAN_SIZE = (bytes: number) =>
  bytes >= 1_000_000
    ? `${(bytes / 1_000_000).toFixed(1)} MB`
    : bytes >= 1000
      ? `${Math.round(bytes / 1000)} KB`
      : `${bytes} B`

export function Artefacts() {
  const { transformId } = useParams<{ transformId: string }>()
  const [params, setParams] = useSearchParams()
  const [showProvenance, setShowProvenance] = useState(false)

  const {
    data: entries,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['artefacts', transformId],
    queryFn: async (): Promise<ArtefactEntry[]> => {
      const response = await fetch(`/transforms/${transformId}/artefacts`)
      if (!response.ok)
        throw new Error(`artefacts unavailable (${response.status})`)
      return (await response.json()) as ArtefactEntry[]
    },
    enabled: Boolean(transformId),
  })

  const succeeded = useMemo(
    () =>
      (entries ?? []).filter(
        (entry) => entry.status === 'SUCCEEDED' && entry.artefact,
      ),
    [entries],
  )

  const { data: report } = useVerification(transformId)
  const [released, setReleased] = useState<Set<string>>(new Set())

  const activeId = params.get('job') ?? succeeded[0]?.job_id
  const active = succeeded.find((entry) => entry.job_id === activeId)

  if (!transformId) {
    return <Library />
  }

  return (
    <>
      <Header
        title="Output review"
        subtitle={`${succeeded.length} outputs generated`}
      />

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row">
        <nav
          aria-label="Generated outputs"
          className="flex shrink-0 gap-1 overflow-x-auto border-b border-border bg-bg-1 p-2 lg:w-[205px] lg:flex-col lg:overflow-x-visible lg:overflow-y-auto lg:border-r lg:border-b-0 lg:p-4"
        >
          <Link
            to={`/runs/${transformId}`}
            className="flex shrink-0 items-center gap-1.5 rounded-[8px] px-2 py-2 text-[14px] whitespace-nowrap text-text-1 transition-colors duration-150 hover:bg-bg-2 hover:text-text-0 lg:mb-3"
          >
            <ArrowLeft className="size-3.5" strokeWidth={1.75} />
            Back to run
          </Link>

          {succeeded.map((entry) => {
            const meta = ARTEFACT_BY_TYPE.get(entry.artefact_type)
            const Icon = meta?.icon
            const current = entry.job_id === activeId
            return (
              <button
                key={entry.job_id}
                type="button"
                onClick={() => setParams({ job: entry.job_id })}
                className={cn(
                  'flex shrink-0 items-center gap-2 rounded-[8px] px-2.5 py-3 text-left text-[14px] whitespace-nowrap transition-colors duration-150',
                  current
                    ? 'bg-bg-3 text-text-0'
                    : 'text-text-1 hover:bg-bg-2 hover:text-text-0',
                )}
              >
                {Icon && (
                  <Icon
                    className={cn(
                      'size-4 shrink-0',
                      current ? 'text-accent' : 'text-text-1',
                    )}
                    strokeWidth={1.75}
                  />
                )}
                <span className="truncate">
                  {meta?.label ?? entry.artefact_type}
                </span>
                {needsReview(report, entry.artefact_type) &&
                  !released.has(entry.job_id) && (
                    <span
                      className="ml-auto size-1.5 shrink-0 rounded-full bg-danger"
                      title="Needs review — verification found a conflict"
                    />
                  )}
              </button>
            )
          })}

          {isLoading && (
            <p className="px-2 py-1.5 text-[15px] text-text-1">Loading…</p>
          )}
          {!isLoading && !isError && succeeded.length === 0 && (
            <p className="px-2 py-1.5 text-[15px] leading-snug text-text-1">
              No artefacts landed for this run.
            </p>
          )}
        </nav>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {active ? (
            <>
              <FileBar
                transformId={transformId}
                jobId={active.job_id}
                onProvenance={() => setShowProvenance((open) => !open)}
                provenanceOpen={showProvenance}
                gated={
                  needsReview(report, active.artefact_type) &&
                  !released.has(active.job_id)
                }
              />
              <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-8">
                <div className="mx-auto flex max-w-[860px] flex-col gap-4">
                  {report && (
                    <OversightPanel
                      key={`${transformId}-${active.job_id}`}
                      transformId={transformId}
                      jobId={active.job_id}
                      artefactType={active.artefact_type}
                      report={report}
                      released={released.has(active.job_id)}
                      onReleased={() =>
                        setReleased((current) =>
                          new Set(current).add(active.job_id),
                        )
                      }
                    />
                  )}
                  {TEMPLATED_TYPES.includes(active.artefact_type) && (
                    <TemplateSection
                      key={`template-${active.job_id}`}
                      transformId={transformId}
                      jobId={active.job_id}
                      artefactType={active.artefact_type}
                    />
                  )}
                  <ArtefactBody
                    key={active.job_id}
                    transformId={transformId}
                    entry={active}
                  />
                  {report && (
                    <ClaimsList
                      report={report}
                      artefactType={active.artefact_type}
                    />
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center p-6">
              {isError ? (
                <div role="alert" className="text-center">
                  <h1 className="text-[20px]">Unable to load these outputs</h1>
                  <p className="mt-2 text-[14px] text-text-1">
                    Check the local engine connection and try again.
                  </p>
                  <button
                    type="button"
                    onClick={() => void refetch()}
                    className="secondary-button mt-4"
                  >
                    <RefreshCw className="size-3.5" /> Try again
                  </button>
                </div>
              ) : isLoading ? (
                <p
                  role="status"
                  className="flex items-center gap-2 text-[14px] text-text-1"
                >
                  <Loader2 className="size-4 animate-spin" /> Loading your
                  outputs…
                </p>
              ) : (
                <div className="text-center">
                  <h1 className="text-[20px]">
                    {succeeded.length
                      ? 'Choose an output to review'
                      : 'No outputs are ready yet'}
                  </h1>
                  <Link
                    to={`/runs/${transformId}`}
                    className="secondary-button mt-4"
                  >
                    <ArrowLeft className="size-3.5" /> Back to run
                  </Link>
                </div>
              )}
            </div>
          )}
        </div>

        <AnimatePresence>
          {showProvenance && active && (
            <ProvenanceDrawer
              transformId={transformId}
              jobId={active.job_id}
              sources={(active.artefact?.sources as string[]) ?? []}
              onClose={() => setShowProvenance(false)}
            />
          )}
        </AnimatePresence>
      </div>
    </>
  )
}

function useFiles(transformId: string, jobId: string) {
  return useQuery({
    queryKey: ['files', transformId, jobId],
    queryFn: async (): Promise<FileEntry[]> => {
      const response = await fetch(
        `/transforms/${transformId}/jobs/${jobId}/files`,
      )
      if (!response.ok)
        throw new Error(`files unavailable (${response.status})`)
      return (await response.json()) as FileEntry[]
    },
  })
}

function FileBar({
  transformId,
  jobId,
  onProvenance,
  provenanceOpen,
  gated,
}: {
  transformId: string
  jobId: string
  onProvenance: () => void
  provenanceOpen: boolean
  gated: boolean
}) {
  const { data: files } = useFiles(transformId, jobId)

  return (
    <div className="hairline-b flex shrink-0 flex-wrap items-center gap-2 px-4 py-2.5">
      <span className="text-[15px] text-text-1">
        {gated ? 'Download (unreleased)' : 'Download'}
      </span>
      {(files ?? [])
        .filter((file) => file.format !== 'json')
        .map((file) => (
          <a
            key={file.name}
            href={`/transforms/${transformId}/jobs/${jobId}/files/${encodeURIComponent(file.name)}`}
            download={file.name}
            className={cn(
              'flex items-center gap-1.5 rounded-[8px] border border-border px-2 py-1 text-[14px] transition-colors duration-150 hover:border-border-2 hover:bg-bg-3',
              // Still downloadable under review — an operator may need the file to
              // judge it — but never the visually primary action while gated.
              gated
                ? 'bg-transparent text-text-1 opacity-70'
                : 'bg-bg-2 text-text-0',
            )}
          >
            <Download className="size-3" strokeWidth={1.75} />
            <span className="uppercase">{file.format}</span>
            <span className="tabular text-text-1">
              {HUMAN_SIZE(file.size_bytes)}
            </span>
          </a>
        ))}
      {files && files.length === 0 && (
        <span className="text-[14px] text-text-1">No files on disk yet.</span>
      )}

      <button
        type="button"
        onClick={onProvenance}
        className={cn(
          'ml-auto flex items-center gap-1.5 rounded-[8px] border px-2 py-1 text-[14px] transition-colors duration-150',
          provenanceOpen
            ? 'border-accent/40 bg-accent/10 text-accent'
            : 'border-border bg-bg-2 text-text-0 hover:border-border-2 hover:bg-bg-3',
        )}
      >
        <Fingerprint className="size-3" strokeWidth={1.75} />
        Provenance
      </button>
    </div>
  )
}

interface RerenderResult {
  files: string[]
  template: string
  warnings: string[]
}

/**
 * Swap the document template and regenerate the file in place. Deterministic and
 * model-free: the existing artefact JSON is re-rendered through the new template,
 * never re-run through the brain — see `api/routes/rerender.py`.
 */
function TemplateSection({
  transformId,
  jobId,
  artefactType,
}: {
  transformId: string
  jobId: string
  artefactType: ArtefactType
}) {
  const [selected, setSelected] = useState('ntro-formal')
  const queryClient = useQueryClient()
  const rerender = useMutation({
    mutationFn: async (template: string): Promise<RerenderResult> => {
      const response = await fetch(
        `/transforms/${transformId}/jobs/${jobId}/render?template=${encodeURIComponent(template)}`,
        { method: 'POST' },
      )
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(
          typeof body?.detail === 'string'
            ? body.detail
            : `Could not re-render (${response.status})`,
        )
      }
      return (await response.json()) as RerenderResult
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['files', transformId, jobId] })
    },
  })

  return (
    <section className="surface-card p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-[15px] text-text-0">Output template</h2>
          <p className="mt-0.5 text-[14px] text-text-1">
            Re-render with a different template — no model call, the content is unchanged.
          </p>
        </div>
        <button
          type="button"
          onClick={() => rerender.mutate(selected)}
          disabled={rerender.isPending}
          className="secondary-button shrink-0"
        >
          {rerender.isPending ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <RefreshCw className="size-3.5" />
          )}
          Apply template
        </button>
      </div>
      <TemplatePicker
        value={selected}
        onChange={setSelected}
        supports={artefactType}
        disabled={rerender.isPending}
      />
      {rerender.isSuccess && (
        <p role="status" className="mt-2.5 text-[14px] text-ok">
          Re-rendered with {rerender.data.template}.
          {rerender.data.warnings.length > 0 && ` ${rerender.data.warnings.join(' ')}`}
        </p>
      )}
      {rerender.isError && (
        <p role="alert" className="mt-2.5 text-[14px] text-danger">
          {(rerender.error as Error).message}
        </p>
      )}
    </section>
  )
}

export function ArtefactBody({
  transformId,
  entry,
}: {
  transformId: string
  entry: ArtefactEntry
}) {
  const { data: files } = useFiles(transformId, entry.job_id)
  const a: Record<string, unknown> = entry.artefact ?? {}
  const str = (key: string) => (typeof a[key] === 'string' ? (a[key] as string) : '')
  const arr = <T,>(key: string): T[] => (Array.isArray(a[key]) ? (a[key] as T[]) : [])

  const url = (predicate: (file: FileEntry) => boolean) => {
    const file = (files ?? []).find(predicate)
    return file
      ? `/transforms/${transformId}/jobs/${entry.job_id}/files/${encodeURIComponent(file.name)}`
      : null
  }

  switch (entry.artefact_type) {
    case 'linkedin_post':
      return (
        <LinkedInPreview
          body={str('body')}
          hook={str('hook')}
          hashtags={arr<string>('hashtags')}
          callToAction={str('call_to_action')}
        />
      )
    case 'x_thread':
      return (
        <XThreadPreview
          tweets={arr<{ text: string }>('tweets')}
          hashtags={arr<string>('hashtags')}
          threadHook={str('thread_hook')}
        />
      )
    case 'advisory':
      return <AdvisoryView artefact={a as never} />
    case 'executive_summary':
      return <ExecutiveSummaryView artefact={a as never} />
    case 'presentation':
      return <PresentationView artefact={a as never} />
    case 'infographic_spec':
      return (
        <InfographicView
          src={url((file) => file.format === 'svg')}
          headline={str('headline')}
          subhead={str('subhead')}
        />
      )
    case 'video_package':
      return (
        <VideoView
          src={url((file) => file.format === 'mp4')}
          scenes={arr<Scene>('scenes')}
          logline={str('logline')}
          panels={(files ?? [])
            .filter((file) => file.format === 'png')
            .map(
              (file) =>
                `/transforms/${transformId}/jobs/${entry.job_id}/files/${encodeURIComponent(file.name)}`,
            )}
        />
      )
  }
}
