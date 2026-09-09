import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, Loader2, ShieldCheck } from 'lucide-react'
import { ConflictDiff } from '@/components/ConflictDiff'
import type { ArtefactType } from '@/lib/api'
import {
  type VerificationReport,
  claimsFor,
  relationsFor,
} from '@/lib/verification'
import { cn } from '@/lib/utils'

interface OversightPanelProps {
  transformId: string
  jobId: string
  artefactType: ArtefactType
  report: VerificationReport
  released: boolean
  onReleased: () => void
}

/**
 * The review gate for an artefact whose verification found a conflict.
 *
 * Every conflict must be acknowledged individually before release is possible.
 * This is deliberate friction: the check flags risk and escalates to a person,
 * who takes named responsibility for releasing anyway. The acknowledgement is
 * written into the artefact's manifest, so the decision is part of the record.
 */
export function OversightPanel({
  transformId,
  jobId,
  artefactType,
  report,
  released,
  onReleased,
}: OversightPanelProps) {
  const queryClient = useQueryClient()
  const conflicts = relationsFor(report, artefactType, 'CONFLICT')
  const claims = claimsFor(report, artefactType)

  const [acked, setAcked] = useState<Set<string>>(new Set())
  const [operator, setOperator] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)

  const keyFor = (index: number) => `${conflicts[index].subject}#${index}`
  const allAcked = conflicts.every((_, index) => acked.has(keyFor(index)))
  const canRelease = allAcked && operator.trim().length > 0

  const release = useMutation({
    mutationFn: async () => {
      const response = await fetch(
        `/transforms/${transformId}/jobs/${jobId}/release`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            operator: operator.trim(),
            acknowledged_claim_ids: conflicts.flatMap((c) => c.claim_ids),
            acknowledged_relations: conflicts.map((c) => c.subject),
            note: note.trim(),
          }),
        },
      )
      if (!response.ok) {
        throw new Error((await response.text()).slice(0, 240) || 'Release failed')
      }
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['manifest', transformId, jobId] })
      onReleased()
    },
    onError: (err: Error) => setError(err.message),
  })

  if (conflicts.length === 0) return null

  if (released) {
    return (
      <section className="flex items-start gap-2.5 rounded-[8px] border border-ok/25 bg-ok/8 p-3">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-ok" strokeWidth={1.75} />
        <div>
          <h3 className="text-[13px] text-text-0">Released for use</h3>
          <p className="mt-0.5 text-[12px] leading-snug text-text-1">
            An operator acknowledged {conflicts.length} conflict
            {conflicts.length === 1 ? '' : 's'} and took responsibility for release.
            The acknowledgement is recorded in this artefact’s manifest.
          </p>
        </div>
      </section>
    )
  }

  return (
    <section className="rounded-[8px] border border-danger/30 bg-danger/5 p-3">
      <header className="flex items-start gap-2.5">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" strokeWidth={1.75} />
        <div className="min-w-0 flex-1">
          <h3 className="text-[13px] text-text-0">Needs review</h3>
          <p className="mt-0.5 text-[12px] leading-snug text-text-1">
            Verification found {conflicts.length} conflict
            {conflicts.length === 1 ? '' : 's'} between this artefact and another in
            the same transform. Acknowledge each one to release it.
          </p>
        </div>
        <span className="tabular shrink-0 rounded-full border border-danger/30 bg-danger/10 px-2 py-0.5 text-[11px] text-danger">
          {acked.size} / {conflicts.length}
        </span>
      </header>

      <div className="mt-3 flex flex-col gap-2">
        {conflicts.map((relation, index) => (
          <ConflictDiff
            key={keyFor(index)}
            relation={relation}
            claims={claims.concat(
              report.claims.filter((c) => c.artefact_type !== artefactType),
            )}
            acknowledged={acked.has(keyFor(index))}
            onAcknowledge={() =>
              setAcked((current) => new Set(current).add(keyFor(index)))
            }
          />
        ))}
      </div>

      <div className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
        <label className="flex flex-col gap-1">
          <span className="text-[12px] text-text-1">
            Releasing operator <span className="text-danger">*</span>
          </span>
          <input
            value={operator}
            onChange={(event) => setOperator(event.target.value)}
            placeholder="Your name or identifier"
            className="rounded-[8px] border border-border bg-bg-0 px-2.5 py-1.5 text-[12px] text-text-0 placeholder:text-text-2 focus:border-border-2 focus:outline-none"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[12px] text-text-1">Note (optional)</span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={2}
            placeholder="Why this is releasable despite the conflict."
            className="resize-y rounded-[8px] border border-border bg-bg-0 px-2.5 py-1.5 text-[12px] leading-relaxed text-text-0 placeholder:text-text-2 focus:border-border-2 focus:outline-none"
          />
        </label>

        {error && <p className="text-[12px] text-danger">{error}</p>}

        <button
          type="button"
          disabled={!canRelease || release.isPending}
          onClick={() => {
            setError(null)
            release.mutate()
          }}
          className={cn(
            'flex items-center justify-center gap-2 rounded-[8px] border px-3 py-2 text-[13px]',
            'transition-colors duration-200',
            canRelease && !release.isPending
              ? 'border-ok/40 bg-ok/12 text-text-0 hover:border-ok/60 hover:bg-ok/18'
              : 'cursor-not-allowed border-border bg-bg-2 text-text-1',
          )}
        >
          {release.isPending ? (
            <Loader2 className="size-4 animate-spin" strokeWidth={1.75} />
          ) : (
            <Check className="size-4" strokeWidth={2} />
          )}
          {allAcked
            ? operator.trim()
              ? 'Release for use'
              : 'Name the releasing operator'
            : `Acknowledge ${conflicts.length - acked.size} more to release`}
        </button>
      </div>
    </section>
  )
}
