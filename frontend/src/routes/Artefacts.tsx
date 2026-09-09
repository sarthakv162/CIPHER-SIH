import { useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence } from 'framer-motion'
import { ArrowLeft, Download, Fingerprint } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { ProvenanceDrawer } from '@/components/ProvenanceDrawer'
import { LinkedInPreview, XThreadPreview } from '@/components/PlatformPreview'
import { AdvisoryView, ExecutiveSummaryView } from '@/components/viewers/DocumentView'
import { InfographicView, PresentationView, VideoView } from '@/components/viewers/MediaView'
import { ARTEFACT_BY_TYPE } from '@/lib/artefacts'
import type { ArtefactType } from '@/lib/api'
import { cn } from '@/lib/utils'

interface ArtefactEntry {
  job_id: string
  artefact_type: ArtefactType
  status: string
  path: string | null
  artefact: Record<string, any> | null
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

  const { data: entries, isLoading } = useQuery({
    queryKey: ['artefacts', transformId],
    queryFn: async (): Promise<ArtefactEntry[]> => {
      const response = await fetch(`/transforms/${transformId}/artefacts`)
      if (!response.ok) throw new Error(`artefacts unavailable (${response.status})`)
      return (await response.json()) as ArtefactEntry[]
    },
    enabled: Boolean(transformId),
  })

  const succeeded = useMemo(
    () => (entries ?? []).filter((entry) => entry.status === 'SUCCEEDED' && entry.artefact),
    [entries],
  )

  const activeId = params.get('job') ?? succeeded[0]?.job_id
  const active = succeeded.find((entry) => entry.job_id === activeId)

  if (!transformId) {
    return (
      <>
        <Header title="Artefacts" subtitle="No run selected" />
        <div className="flex flex-1 items-center justify-center p-6">
          <p className="max-w-[46ch] text-center text-[13px] leading-relaxed text-text-1">
            Open a run to see the artefacts it produced. A list of past transforms
            needs an endpoint that does not exist yet.
          </p>
        </div>
      </>
    )
  }

  return (
    <>
      <Header title="Artefacts" subtitle={`${succeeded.length} generated`} />

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row">
        <nav className="flex shrink-0 gap-1 overflow-x-auto border-b border-border p-2 lg:w-[188px] lg:flex-col lg:overflow-x-visible lg:overflow-y-auto lg:border-r lg:border-b-0 lg:p-3">
          <Link
            to={`/runs/${transformId}`}
            className="flex shrink-0 items-center gap-1.5 rounded-[8px] px-2 py-1.5 text-[12px] whitespace-nowrap text-text-1 transition-colors duration-150 hover:bg-bg-2 hover:text-text-0 lg:mb-1"
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
                  'flex shrink-0 items-center gap-2 rounded-[8px] px-2 py-2 text-left text-[12px] whitespace-nowrap transition-colors duration-150',
                  current
                    ? 'bg-bg-3 text-text-0'
                    : 'text-text-1 hover:bg-bg-2 hover:text-text-0',
                )}
              >
                {Icon && (
                  <Icon
                    className={cn('size-4 shrink-0', current ? 'text-accent' : 'text-text-1')}
                    strokeWidth={1.75}
                  />
                )}
                <span className="truncate">{meta?.label ?? entry.artefact_type}</span>
              </button>
            )
          })}

          {isLoading && (
            <p className="px-2 py-1.5 text-[12px] text-text-1">Loading…</p>
          )}
          {!isLoading && succeeded.length === 0 && (
            <p className="px-2 py-1.5 text-[12px] leading-snug text-text-1">
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
              />
              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                <ArtefactBody transformId={transformId} entry={active} />
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center p-6">
              <p className="text-[13px] text-text-1">Select an artefact.</p>
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
      const response = await fetch(`/transforms/${transformId}/jobs/${jobId}/files`)
      if (!response.ok) throw new Error(`files unavailable (${response.status})`)
      return (await response.json()) as FileEntry[]
    },
  })
}

function FileBar({
  transformId,
  jobId,
  onProvenance,
  provenanceOpen,
}: {
  transformId: string
  jobId: string
  onProvenance: () => void
  provenanceOpen: boolean
}) {
  const { data: files } = useFiles(transformId, jobId)

  return (
    <div className="hairline-b flex shrink-0 flex-wrap items-center gap-2 px-4 py-2.5">
      <span className="text-[12px] text-text-1">Download</span>
      {(files ?? [])
        .filter((file) => file.format !== 'json')
        .map((file) => (
          <a
            key={file.name}
            href={`/transforms/${transformId}/jobs/${jobId}/files/${encodeURIComponent(file.name)}`}
            download={file.name}
            className="flex items-center gap-1.5 rounded-[8px] border border-border bg-bg-2 px-2 py-1 text-[11px] text-text-0 transition-colors duration-150 hover:border-border-2 hover:bg-bg-3"
          >
            <Download className="size-3" strokeWidth={1.75} />
            <span className="uppercase">{file.format}</span>
            <span className="tabular text-text-1">{HUMAN_SIZE(file.size_bytes)}</span>
          </a>
        ))}
      {files && files.length === 0 && (
        <span className="text-[11px] text-text-1">No files on disk yet.</span>
      )}

      <button
        type="button"
        onClick={onProvenance}
        className={cn(
          'ml-auto flex items-center gap-1.5 rounded-[8px] border px-2 py-1 text-[11px] transition-colors duration-150',
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

function ArtefactBody({
  transformId,
  entry,
}: {
  transformId: string
  entry: ArtefactEntry
}) {
  const { data: files } = useFiles(transformId, entry.job_id)
  const a = entry.artefact ?? {}

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
          body={a.body ?? ''}
          hook={a.hook ?? ''}
          hashtags={a.hashtags ?? []}
          callToAction={a.call_to_action ?? ''}
        />
      )
    case 'x_thread':
      return (
        <XThreadPreview
          tweets={a.tweets ?? []}
          hashtags={a.hashtags ?? []}
          threadHook={a.thread_hook ?? ''}
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
          headline={a.headline ?? ''}
          subhead={a.subhead ?? ''}
        />
      )
    case 'video_package':
      return (
        <VideoView
          src={url((file) => file.format === 'mp4')}
          scenes={a.scenes ?? []}
          logline={a.logline ?? ''}
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
