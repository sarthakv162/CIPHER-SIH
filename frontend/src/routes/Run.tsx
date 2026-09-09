import { Link, useParams } from 'react-router-dom'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { AlertTriangle, Check, CircleDashed, Loader2, X } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { MemoryPanel } from '@/components/MemoryPanel'
import { ARTEFACT_BY_TYPE } from '@/lib/artefacts'
import { type JobFrame, type VerificationFrame, useTransformStream } from '@/lib/sse'
import { cn } from '@/lib/utils'

const EASE = [0.2, 0, 0, 1] as const

export function Run() {
  const { transformId } = useParams<{ transformId: string }>()
  const stream = useTransformStream(transformId)
  const reduced = useReducedMotion()

  const jobs = stream.jobOrder
    .map((id) => stream.jobs.get(id))
    .filter((job): job is JobFrame => Boolean(job))

  return (
    <>
      <Header
        title="Run"
        subtitle={
          stream.status === 'error'
            ? 'Stream interrupted'
            : stream.final
              ? 'Complete'
              : 'Live'
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="mx-auto flex max-w-[1100px] flex-col gap-4">
          <MemoryPanel models={stream.models} events={stream.modelEvents} />

          {stream.verification && <VerificationSummary report={stream.verification} />}

          <section className="surface-card overflow-hidden">
            <div className="hairline-b flex items-baseline justify-between px-4 py-3">
              <h2 className="text-[13px] text-text-0">Artefacts</h2>
              <span className="tabular text-[12px] text-text-1">
                {jobs.filter((j) => j.status === 'SUCCEEDED').length} of {jobs.length} done
              </span>
            </div>

            <ul className="divide-y divide-border">
              <AnimatePresence initial={false}>
                {jobs.map((job) => (
                  <motion.li
                    key={job.job_id}
                    layout={!reduced}
                    initial={reduced ? false : { opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2, ease: EASE }}
                  >
                    <JobRow
                      job={job}
                      tokens={stream.tokens.get(job.job_id) ?? ''}
                      transformId={transformId}
                    />
                  </motion.li>
                ))}
              </AnimatePresence>
              {jobs.length === 0 && (
                <li className="px-4 py-6 text-center text-[12px] text-text-1">
                  Waiting for the first job…
                </li>
              )}
            </ul>
          </section>

          {stream.status === 'error' && !stream.final && (
            <p className="flex items-center gap-2 rounded-[8px] border border-warn/25 bg-warn/10 px-3 py-2 text-[12px] text-warn">
              <AlertTriangle className="size-3.5 shrink-0" strokeWidth={1.75} />
              The event stream dropped. The run continues on the server — reload to
              rejoin it.
            </p>
          )}
        </div>
      </div>
    </>
  )
}

function StatusMark({ status }: { status: JobFrame['status'] }) {
  if (status === 'RUNNING')
    return <Loader2 className="size-4 shrink-0 animate-spin text-accent" strokeWidth={1.75} />
  if (status === 'SUCCEEDED')
    return <Check className="size-4 shrink-0 text-ok" strokeWidth={2} />
  if (status === 'FAILED' || status === 'CANCELLED')
    return <X className="size-4 shrink-0 text-danger" strokeWidth={2} />
  return <CircleDashed className="size-4 shrink-0 text-text-2" strokeWidth={1.75} />
}

function JobRow({
  job,
  tokens,
  transformId,
}: {
  job: JobFrame
  tokens: string
  transformId: string | undefined
}) {
  const meta = ARTEFACT_BY_TYPE.get(job.artefact_type)
  const streaming = job.status === 'RUNNING' && tokens.length > 0
  const done = job.status === 'SUCCEEDED' && transformId

  return (
    <div className="flex flex-col gap-2 px-4 py-3">
      <div className="flex items-center gap-3">
        <StatusMark status={job.status} />
        {done ? (
          <Link
            to={`/runs/${transformId}/artefacts?job=${job.job_id}`}
            className="min-w-0 flex-1 truncate text-[13px] text-text-0 underline decoration-border underline-offset-4 transition-colors duration-150 hover:decoration-accent"
          >
            {meta?.label ?? job.artefact_type}
          </Link>
        ) : (
          <span className="min-w-0 flex-1 truncate text-[13px] text-text-0">
            {meta?.label ?? job.artefact_type}
          </span>
        )}
        <span
          className={cn(
            'rounded-full border px-2 py-0.5 text-[11px]',
            job.status === 'SUCCEEDED'
              ? 'border-ok/25 bg-ok/10 text-ok'
              : job.status === 'FAILED' || job.status === 'CANCELLED'
                ? 'border-danger/25 bg-danger/10 text-danger'
                : job.status === 'RUNNING'
                  ? 'border-accent/25 bg-accent/10 text-accent'
                  : 'border-border bg-bg-3 text-text-1',
          )}
        >
          {job.status.toLowerCase()}
        </span>
      </div>

      {job.error && (
        <p className="pl-7 text-[12px] leading-snug text-danger">{job.error}</p>
      )}

      {/* Token deltas as they arrive. This is the raw JSON the model is emitting,
          shown so a five-minute wait is visibly alive, not so it can be read. */}
      {streaming && (
        <pre className="ml-7 max-h-20 overflow-hidden rounded-[8px] border border-border bg-bg-0 px-2.5 py-2 text-[11px] leading-relaxed text-text-1">
          <code className="break-all whitespace-pre-wrap">{tokens.slice(-320)}</code>
        </pre>
      )}
    </div>
  )
}

function VerificationSummary({ report }: { report: VerificationFrame }) {
  // ok=false means verification did not finish — never that problems were found.
  if (!report.ok) {
    return (
      <section className="surface-card flex items-start gap-2.5 p-4">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" strokeWidth={1.75} />
        <div>
          <h2 className="text-[13px] text-text-0">Verification unavailable</h2>
          <p className="mt-1 text-[12px] leading-snug text-text-1">
            {report.warnings[0] ?? 'The verification pass did not complete.'} The
            artefacts themselves are unaffected.
          </p>
        </div>
      </section>
    )
  }

  const { summary } = report
  return (
    <section className="surface-card p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <h2 className="shrink-0 text-[13px] text-text-0">Verification</h2>
        <span className="tabular text-[12px] text-text-1 sm:text-right">{report.line}</span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="claims" value={summary.total} />
        <Stat label="supported" value={summary.supported} tone="ok" />
        <Stat label="unsupported" value={summary.unsupported} tone="warn" />
        <Stat label="conflicts" value={summary.conflict} tone="danger" />
      </div>

      <p className="mt-3 text-[11px] leading-snug text-text-1">{report.disclaimer}</p>
    </section>
  )
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone?: 'ok' | 'warn' | 'danger'
}) {
  const lit = value > 0
  return (
    <div
      className={cn(
        'rounded-[8px] border px-2.5 py-2',
        lit && tone === 'ok' && 'border-ok/25 bg-ok/5',
        lit && tone === 'warn' && 'border-warn/25 bg-warn/5',
        lit && tone === 'danger' && 'border-danger/25 bg-danger/5',
        (!lit || !tone) && 'border-border bg-bg-0',
      )}
    >
      <div
        className={cn(
          'tabular text-[18px] leading-none',
          lit && tone === 'ok' && 'text-ok',
          lit && tone === 'warn' && 'text-warn',
          lit && tone === 'danger' && 'text-danger',
          (!lit || !tone) && 'text-text-0',
        )}
      >
        {value}
      </div>
      <div className="mt-1 text-[11px] text-text-1">{label}</div>
    </div>
  )
}
