import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  CircleDashed,
  FileText,
  Loader2,
  X,
} from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { BrandMark } from '@/components/Brand'
import { MemoryPanel } from '@/components/MemoryPanel'
import { ArtefactBody, type ArtefactEntry } from '@/routes/Artefacts'
import { ARTEFACT_BY_TYPE } from '@/lib/artefacts'
import { useTransformStream } from '@/lib/sse'
import { cn } from '@/lib/utils'

export function Run() {
  const { transformId } = useParams<{ transformId: string }>()
  const stream = useTransformStream(transformId)
  const jobs = stream.jobOrder
    .map((id) => stream.jobs.get(id))
    .filter((job) => job !== undefined)
  const succeeded = jobs.filter((job) => job.status === 'SUCCEEDED').length
  const request = useMemo(() => {
    try {
      return JSON.parse(
        sessionStorage.getItem(`rupantar:request:${transformId}`) ?? 'null',
      ) as { prompt: string; files: string[] } | null
    } catch {
      return null
    }
  }, [transformId])
  const { data: entries } = useQuery({
    queryKey: ['artefacts', transformId],
    queryFn: async (): Promise<ArtefactEntry[]> => {
      const response = await fetch(`/transforms/${transformId}/artefacts`)
      if (!response.ok) throw new Error('Outputs are not available yet')
      return response.json()
    },
    enabled: succeeded > 0,
    refetchInterval: stream.final ? false : 2000,
  })
  const report = stream.verification
  return (
    <>
      <Header
        title="Run"
        subtitle={
          stream.final
            ? 'Complete'
            : stream.status === 'error'
              ? 'Disconnected'
              : 'Generating'
        }
      />
      <div className="page-scroll">
        <div className="conversation">
          <h1 className="sr-only">Content transformation</h1>
          <div className="user-message">
            {request?.files?.length ? (
              <div className="mb-3 flex flex-wrap gap-2">
                {request.files.map((name, i) => (
                  <span
                    key={i}
                    className="flex items-center gap-1.5 rounded-lg border border-border bg-bg-1 px-2.5 py-1 text-[14px]"
                  >
                    <FileText className="size-3.5" />
                    {name}
                  </span>
                ))}
              </div>
            ) : null}
            {request?.prompt ? (
              request.prompt.length > 600 ? (
                <details>
                  <summary className="cursor-pointer">
                    {request.prompt.slice(0, 200)}…
                  </summary>
                  <p className="mt-3 whitespace-pre-wrap">{request.prompt}</p>
                </details>
              ) : (
                <p className="whitespace-pre-wrap">{request.prompt}</p>
              )
            ) : (
              <p>
                {jobs.length
                  ? 'Generate content from the provided source.'
                  : 'Preparing your transform…'}
              </p>
            )}
            {jobs.length > 0 && (
              <p className="mt-3 text-[14px] text-text-1">
                {jobs
                  .map((job) => ARTEFACT_BY_TYPE.get(job.artefact_type)?.label)
                  .join(' · ')}
              </p>
            )}
          </div>
          <div className="assistant-message">
            <BrandMark className="!size-8 shrink-0 text-text-0" />
            <div className="min-w-0 flex-1">
              <div className="mb-5 flex items-center gap-2 text-[16px]">
                {!stream.final && stream.status !== 'error' && (
                  <Loader2 className="size-4 animate-spin text-text-1" />
                )}
                <p>
                  {stream.final
                    ? stream.transformStatus === 'SUCCEEDED'
                      ? 'Your outputs are ready.'
                      : 'The run finished with some issues. Review the details below.'
                    : stream.status === 'error'
                      ? 'Connection to this run was interrupted.'
                      : 'Working on your content…'}
                </p>
              </div>
              <div className="space-y-3">
                {jobs.map((job, i) => {
                  const meta = ARTEFACT_BY_TYPE.get(job.artefact_type)
                  const entry = entries?.find(
                    (e) =>
                      e.job_id === job.job_id &&
                      e.status === 'SUCCEEDED' &&
                      e.artefact,
                  )
                  const StatusIcon =
                    job.status === 'SUCCEEDED'
                      ? Check
                      : job.status === 'FAILED' || job.status === 'CANCELLED'
                        ? X
                        : job.status === 'RUNNING'
                          ? Loader2
                          : CircleDashed
                  return (
                    <div
                      key={job.job_id}
                      className="overflow-hidden rounded-xl border border-border"
                    >
                      <div className="flex items-center gap-3 px-4 py-3">
                        <StatusIcon
                          className={cn(
                            'size-4 shrink-0',
                            job.status === 'RUNNING' && 'animate-spin',
                            job.status === 'FAILED'
                              ? 'text-danger'
                              : 'text-text-1',
                          )}
                        />
                        <span className="min-w-0 flex-1 text-[15px] font-medium">
                          {meta?.label ?? job.artefact_type}
                        </span>
                        <span className="text-[14px] text-text-1">
                          {job.status === 'SUCCEEDED'
                            ? 'Ready'
                            : job.status === 'RUNNING'
                              ? 'Generating'
                              : job.status === 'PENDING'
                                ? 'Queued'
                                : job.status.toLowerCase()}
                        </span>
                        {job.status === 'SUCCEEDED' && (
                          <Link
                            to={`/runs/${transformId}/artefacts?job=${job.job_id}`}
                            aria-label={`Review ${meta?.label}`}
                            title="Review and download"
                            className="icon-button !size-8"
                          >
                            <ArrowUpRight className="size-4" />
                          </Link>
                        )}
                      </div>
                      {job.error && (
                        <p
                          role="alert"
                          className="px-4 pb-4 text-[14px] text-danger"
                        >
                          {job.error}
                        </p>
                      )}
                      {entry && transformId && (
                        <details
                          open={i === 0}
                          className="border-t border-border"
                        >
                          <summary className="px-4 py-3 text-[14px] text-text-1">
                            Preview output
                          </summary>
                          <div className="overflow-hidden px-3 pb-4">
                            <ArtefactBody
                              transformId={transformId}
                              entry={entry}
                            />
                          </div>
                        </details>
                      )}
                      {job.status === 'RUNNING' &&
                        stream.tokens.get(job.job_id) && (
                          <details className="border-t border-border">
                            <summary className="px-4 py-2 text-[14px] text-text-1">
                              View live generation
                            </summary>
                            <pre className="max-h-40 overflow-y-auto bg-bg-2 p-4 text-[14px] break-words whitespace-pre-wrap">
                              {stream.tokens.get(job.job_id)?.slice(-600)}
                            </pre>
                          </details>
                        )}
                    </div>
                  )
                })}
              </div>
              {report && (
                <details className="mt-5 rounded-xl border border-border p-4">
                  <summary className="flex cursor-pointer items-center gap-2 text-[14px]">
                    {report.ok ? (
                      <Check className="size-4 text-ok" />
                    ) : (
                      <AlertTriangle className="size-4 text-warn" />
                    )}{' '}
                    {report.ok
                      ? 'Source verification'
                      : 'Verification unavailable'}
                    <span className="ml-auto text-[14px] text-text-1">
                      Details
                    </span>
                  </summary>
                  {report.ok ? (
                    <>
                      <p className="mt-3 text-[14px]">{report.line}</p>
                      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                        {[
                          ['Claims', report.summary.total],
                          ['Supported', report.summary.supported],
                          ['Unsupported', report.summary.unsupported],
                          ['Conflicts', report.summary.conflict],
                        ].map(([label, count]) => (
                          <div key={label} className="rounded-lg bg-bg-2 p-3">
                            <p className="text-[20px]">{count}</p>
                            <p className="text-[14px] text-text-1">{label}</p>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="mt-3 text-[14px] text-text-1">
                      {report.warnings[0] ??
                        'The verification pass did not complete.'}
                    </p>
                  )}
                  <p className="mt-3 text-[14px] text-text-1">
                    {report.disclaimer}
                  </p>
                </details>
              )}
              {succeeded > 0 && (
                <Link
                  to={`/runs/${transformId}/artefacts`}
                  className="secondary-button mt-5"
                >
                  Review and download <ArrowUpRight className="size-4" />
                </Link>
              )}
              <details className="mt-6">
                <summary className="text-[14px] text-text-1">
                  Local processing details
                </summary>
                <div className="mt-3">
                  <MemoryPanel
                    models={stream.models}
                    events={stream.modelEvents}
                  />
                </div>
              </details>
              {stream.status === 'error' && !stream.final && (
                <div
                  role="alert"
                  className="mt-5 rounded-xl border border-warn/20 bg-warn/5 p-4 text-[14px] text-warn"
                >
                  The run may still be processing on the local engine.{' '}
                  <button
                    type="button"
                    onClick={() => window.location.reload()}
                    className="underline underline-offset-2"
                  >
                    Reconnect
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      <footer className="flex shrink-0 items-center justify-center gap-4 border-t border-border px-4 py-4">
        <Link to="/workspace" className="secondary-button">
          Edit source & create again
        </Link>
        <span className="hidden text-[14px] text-text-1 sm:block">
          All processing stays on this device.
        </span>
      </footer>
    </>
  )
}
