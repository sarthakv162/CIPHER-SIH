import { useQuery } from '@tanstack/react-query'
import type { ArtefactType } from './api'

/** The full report from `GET /transforms/{id}/verification` — see `verify/report.py`. */

export interface ClaimAssessment {
  claim_id: string
  claim: string
  artefact_type: ArtefactType
  /** SUPPORTED, or anything else meaning it could not be substantiated. */
  status: string
  evidence_ids: string[]
  cited_sources: string[]
  note: string
}

export interface Relation {
  kind: 'AGREE' | 'CONFLICT' | 'ORPHAN'
  claim_ids: string[]
  subject: string
  detail: string
}

export interface VerificationReport {
  transform_id: string
  generated_at: string
  disclaimer: string
  claims: ClaimAssessment[]
  relations: Relation[]
  summary: {
    total: number
    supported: number
    unsupported: number
    agree: number
    conflict: number
    orphan: number
  }
  warnings: string[]
  ok: boolean
}

export function useVerification(transformId: string | undefined) {
  return useQuery({
    queryKey: ['verification', transformId],
    queryFn: async (): Promise<VerificationReport | null> => {
      const response = await fetch(`/transforms/${transformId}/verification`)
      // 404 means "not finished yet", which is a state, not an error.
      if (response.status === 404) return null
      if (!response.ok) throw new Error(`verification unavailable (${response.status})`)
      return (await response.json()) as VerificationReport
    },
    enabled: Boolean(transformId),
    retry: false,
  })
}

/** Relations of a given kind that involve any claim belonging to this artefact. */
export function relationsFor(
  report: VerificationReport | null | undefined,
  artefactType: ArtefactType,
  kind: Relation['kind'],
): Relation[] {
  if (!report) return []
  const owned = new Set(
    report.claims.filter((c) => c.artefact_type === artefactType).map((c) => c.claim_id),
  )
  return report.relations.filter(
    (r) => r.kind === kind && r.claim_ids.some((id) => owned.has(id)),
  )
}

/** An artefact needs review when any conflict touches one of its claims. */
export function needsReview(
  report: VerificationReport | null | undefined,
  artefactType: ArtefactType,
): boolean {
  return relationsFor(report, artefactType, 'CONFLICT').length > 0
}

export function claimsFor(
  report: VerificationReport | null | undefined,
  artefactType: ArtefactType,
): ClaimAssessment[] {
  return (report?.claims ?? []).filter((c) => c.artefact_type === artefactType)
}
