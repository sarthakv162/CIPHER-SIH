import { AlertTriangle, Check, HelpCircle } from 'lucide-react'
import type { ArtefactType } from '@/lib/api'
import { type ClaimAssessment, type VerificationReport, claimsFor } from '@/lib/verification'
import { cn } from '@/lib/utils'

/** Status pill. The colours are the console's, and they mean the same here as
 *  everywhere else: green supported, amber unverified, red conflict. */
export function VerificationBadge({
  status,
  conflicted,
}: {
  status: string
  conflicted?: boolean
}) {
  const tone = conflicted
    ? 'border-danger/30 bg-danger/10 text-danger'
    : status === 'SUPPORTED'
      ? 'border-ok/25 bg-ok/10 text-ok'
      : 'border-warn/25 bg-warn/10 text-warn'

  const Icon = conflicted ? AlertTriangle : status === 'SUPPORTED' ? Check : HelpCircle

  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[13px]',
        tone,
      )}
    >
      <Icon className="size-2.5" strokeWidth={2} />
      {conflicted ? 'conflict' : status.toLowerCase()}
    </span>
  )
}

interface ClaimsListProps {
  report: VerificationReport
  artefactType: ArtefactType
}

/**
 * Every claim this artefact makes, with what could be substantiated.
 *
 * A supported claim carries a subtle underline that reveals its evidence on
 * hover; unsupported is amber; a claim caught in a conflict is red. The point is
 * that the operator can see which sentences are load-bearing and which are the
 * model's own, without leaving the artefact.
 */
export function ClaimsList({ report, artefactType }: ClaimsListProps) {
  const claims = claimsFor(report, artefactType)
  const conflicted = new Set(
    report.relations
      .filter((relation) => relation.kind === 'CONFLICT')
      .flatMap((relation) => relation.claim_ids),
  )

  if (claims.length === 0) return null

  return (
    <section className="surface-card p-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-[16px] text-text-0">Claims traced</h3>
        {/* A claim can be grounded AND in conflict with another artefact, so a bare
            "n of m supported" would sit next to a visible conflict badge and read
            as a contradiction. Count the conflicted ones separately. */}
        <span className="tabular text-[14px] text-text-1">
          {claims.filter((c) => c.status === 'SUPPORTED' && !conflicted.has(c.claim_id))
            .length}{' '}
          supported
          {claims.filter((c) => c.status !== 'SUPPORTED').length > 0 &&
            ` · ${claims.filter((c) => c.status !== 'SUPPORTED').length} unsupported`}
          {claims.filter((c) => conflicted.has(c.claim_id)).length > 0 &&
            ` · ${claims.filter((c) => conflicted.has(c.claim_id)).length} in conflict`}
        </span>
      </div>

      <ul className="mt-2 flex flex-col">
        {claims.map((claim) => (
          <ClaimRow
            key={claim.claim_id}
            claim={claim}
            conflicted={conflicted.has(claim.claim_id)}
          />
        ))}
      </ul>

      <p className="mt-2.5 text-[14px] leading-snug text-text-1">{report.disclaimer}</p>
    </section>
  )
}

function ClaimRow({
  claim,
  conflicted,
}: {
  claim: ClaimAssessment
  conflicted: boolean
}) {
  const supported = claim.status === 'SUPPORTED' && !conflicted

  return (
    <li className="group border-b border-border py-2 last:border-b-0">
      <div className="flex items-start gap-2">
        <p
          className={cn(
            'min-w-0 flex-1 text-[16px] leading-relaxed',
            conflicted
              ? 'text-danger decoration-danger/50'
              : supported
                ? 'text-text-0 decoration-ok/40'
                : 'text-warn decoration-warn/40',
            'underline decoration-dotted underline-offset-4',
          )}
        >
          {claim.claim}
        </p>
        <VerificationBadge status={claim.status} conflicted={conflicted} />
      </div>

      {/* Evidence and reasoning are revealed rather than always shown — the list
          stays scannable, and the detail is one hover or focus away. */}
      <div className="mt-1 max-h-0 overflow-hidden opacity-0 transition-all duration-200 ease-[cubic-bezier(0.2,0,0,1)] group-hover:max-h-24 group-hover:opacity-100 group-focus-within:max-h-24 group-focus-within:opacity-100">
        <div className="flex flex-wrap items-center gap-1.5">
          {claim.evidence_ids.length > 0 ? (
            claim.evidence_ids.map((id) => (
              <span
                key={id}
                className="rounded-[4px] border border-accent/25 bg-accent/10 px-1.5 py-0.5 text-[13px] text-accent"
              >
                {id}
              </span>
            ))
          ) : (
            <span className="text-[14px] text-text-1">No evidence unit entails this.</span>
          )}
        </div>
        {claim.note && (
          <p className="mt-1 text-[14px] leading-snug text-text-1">{claim.note}</p>
        )}
      </div>
    </li>
  )
}
