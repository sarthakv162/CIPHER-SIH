import { useQuery } from '@tanstack/react-query'
import { Fingerprint, X } from 'lucide-react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

const EASE = [0.2, 0, 0, 1] as const

/** The manifest written beside every artefact file — see `audit/provenance.py`. */
export interface Manifest {
  source_sha256: string
  artefact_type: string
  artefact_format: string
  model_key: string
  model_sha256: string | null
  model_quant: string
  prompt_version: string
  generation_params: Record<string, unknown>
  created_at: string
  rendered_at: string
  operator: string
  app_version: string
  job_id: string
  transform_id: string
  verification?: Record<string, unknown> | null
  release?: Record<string, unknown> | null
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-2 py-1.5">
      <dt className="text-[12px] text-text-1">{label}</dt>
      <dd
        className={cn(
          'min-w-0 text-[12px] break-all text-text-0',
          mono && 'tabular font-mono text-[11px]',
        )}
      >
        {value}
      </dd>
    </div>
  )
}

interface ProvenanceDrawerProps {
  transformId: string
  jobId: string
  sources: string[]
  onClose: () => void
}

/**
 * Where an artefact came from: the source hash, which model file produced it, the
 * prompt version, the parameters, and the evidence it cites. This is the record
 * that makes a generated artefact accountable rather than merely plausible.
 */
export function ProvenanceDrawer({
  transformId,
  jobId,
  sources,
  onClose,
}: ProvenanceDrawerProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['manifest', transformId, jobId],
    queryFn: async (): Promise<Manifest> => {
      const response = await fetch(`/transforms/${transformId}/jobs/${jobId}/manifest`)
      if (!response.ok) throw new Error(`manifest unavailable (${response.status})`)
      return (await response.json()) as Manifest
    },
  })

  return (
    <motion.aside
      initial={{ x: 24, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 24, opacity: 0 }}
      transition={{ duration: 0.2, ease: EASE }}
      className="glass flex w-[340px] shrink-0 flex-col border-l border-border"
      aria-label="Provenance"
    >
      <header className="hairline-b flex items-center justify-between px-4 py-3">
        <h2 className="flex items-center gap-2 text-[13px] text-text-0">
          <Fingerprint className="size-4 text-accent" strokeWidth={1.75} />
          Provenance
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close provenance"
          className="rounded-[5px] p-1 text-text-1 transition-colors duration-150 hover:bg-bg-3 hover:text-text-0"
        >
          <X className="size-4" strokeWidth={1.75} />
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        {isLoading && <p className="text-[12px] text-text-1">Reading the manifest…</p>}

        {isError && (
          <p className="text-[12px] leading-snug text-warn">
            No manifest yet. It is written once the whole transform finishes, so a
            job that has just landed may briefly have none.
          </p>
        )}

        {data && (
          <>
            <dl className="divide-y divide-border">
              <Row label="Source SHA-256" value={data.source_sha256} mono />
              <Row label="Model" value={`${data.model_key} · ${data.model_quant}`} />
              <Row label="Model SHA-256" value={data.model_sha256 ?? 'not recorded'} mono />
              <Row label="Prompt version" value={data.prompt_version} />
              <Row label="Format" value={data.artefact_format} />
              <Row label="Operator" value={data.operator} />
              <Row label="Generated" value={new Date(data.created_at).toLocaleString()} />
              <Row label="Rendered" value={new Date(data.rendered_at).toLocaleString()} />
              <Row label="Engine" value={data.app_version} />
            </dl>

            <section className="mt-4">
              <h3 className="section-label">Generation parameters</h3>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {Object.entries(data.generation_params).map(([key, value]) => (
                  <span
                    key={key}
                    className="rounded-[5px] border border-border bg-bg-2 px-1.5 py-0.5 text-[11px] text-text-1"
                  >
                    {key}: <span className="text-text-0">{String(value)}</span>
                  </span>
                ))}
              </div>
            </section>

            <section className="mt-4">
              <h3 className="section-label">Evidence cited</h3>
              {sources.length > 0 ? (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {sources.map((id) => (
                    <span
                      key={id}
                      className="rounded-[5px] border border-accent/25 bg-accent/10 px-1.5 py-0.5 text-[11px] text-accent"
                    >
                      {id}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-1.5 text-[12px] text-text-1">
                  This artefact cites no evidence IDs.
                </p>
              )}
            </section>

            {data.release && (
              <section className="mt-4">
                <h3 className="section-label">Release</h3>
                <pre className="mt-1.5 overflow-x-auto rounded-[8px] border border-border bg-bg-0 p-2 text-[11px] text-text-1">
                  {JSON.stringify(data.release, null, 2)}
                </pre>
              </section>
            )}
          </>
        )}
      </div>
    </motion.aside>
  )
}
