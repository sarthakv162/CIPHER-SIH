import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import type { ClaimAssessment, Relation } from '@/lib/verification'
import { ARTEFACT_BY_TYPE } from '@/lib/artefacts'
import { cn } from '@/lib/utils'

const EASE = [0.2, 0, 0, 1] as const

/** Numbers and quantities are what usually disagree, so mark them in both texts. */
const NUMERIC = /(\d[\d,.]*\s*(?:%|percent)?)/g

function Highlighted({ text }: { text: string }) {
  const parts = text.split(NUMERIC)
  return (
    <>
      {parts.map((part, index) =>
        NUMERIC.test(part) && index % 2 === 1 ? (
          <mark
            key={index}
            className="rounded-[3px] bg-danger/20 px-0.5 text-danger"
          >
            {part}
          </mark>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  )
}

interface ConflictDiffProps {
  relation: Relation
  claims: ClaimAssessment[]
  acknowledged: boolean
  onAcknowledge: () => void
}

/**
 * One conflict, expandable to the two artefacts that disagree, side by side.
 *
 * Acknowledgement is per conflict and deliberate: an automated check flagged
 * risk, and a person decides whether it is releasable. That is the whole point
 * of the oversight step — it must not collapse into a badge you can ignore.
 */
export function ConflictDiff({
  relation,
  claims,
  acknowledged,
  onAcknowledge,
}: ConflictDiffProps) {
  const [open, setOpen] = useState(true)
  const involved = claims.filter((claim) => relation.claim_ids.includes(claim.claim_id))

  return (
    <div
      className={cn(
        'rounded-[8px] border transition-colors duration-200',
        acknowledged ? 'border-border bg-bg-2' : 'border-danger/30 bg-danger/5',
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-start gap-2.5 px-3 py-2.5 text-left"
      >
        <ChevronDown
          className={cn(
            'mt-0.5 size-4 shrink-0 transition-transform duration-200',
            acknowledged ? 'text-text-1' : 'text-danger',
            !open && '-rotate-90',
          )}
          strokeWidth={1.75}
        />
        <span className="min-w-0 flex-1">
          <span className="block text-[16px] text-text-0">{relation.subject}</span>
          <span className="mt-0.5 block text-[15px] leading-snug text-text-1">
            {relation.detail}
          </span>
        </span>
        {acknowledged && (
          <span className="shrink-0 rounded-full border border-border bg-bg-3 px-2 py-0.5 text-[14px] text-text-1">
            acknowledged
          </span>
        )}
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: EASE }}
            className="overflow-hidden"
          >
            <div className="grid grid-cols-1 gap-2 px-3 pb-3 md:grid-cols-2">
              {involved.map((claim) => (
                <div
                  key={claim.claim_id}
                  className="rounded-[8px] border border-border bg-bg-0 p-2.5"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-[14px] text-text-1">
                      {ARTEFACT_BY_TYPE.get(claim.artefact_type)?.label ??
                        claim.artefact_type}
                    </span>
                    <span className="tabular text-[14px] text-text-2">
                      {claim.claim_id}
                    </span>
                  </div>
                  <p className="mt-1.5 text-[16px] leading-relaxed text-text-0">
                    <Highlighted text={claim.claim} />
                  </p>
                  {claim.note && (
                    <p className="mt-1.5 text-[14px] leading-snug text-text-1">
                      {claim.note}
                    </p>
                  )}
                </div>
              ))}
            </div>

            {!acknowledged && (
              <div className="px-3 pb-3">
                <button
                  type="button"
                  onClick={onAcknowledge}
                  className="rounded-[8px] border border-border bg-bg-2 px-2.5 py-1.5 text-[15px] text-text-0 transition-colors duration-150 hover:border-border-2 hover:bg-bg-3"
                >
                  Acknowledge this conflict
                </button>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
