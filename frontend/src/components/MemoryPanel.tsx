import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import type { ModelRow } from '@/lib/api'
import type { ModelFrame } from '@/lib/sse'
import { cn } from '@/lib/utils'

/** Total machine memory the bar represents. The reference laptop is 16 GB. */
const TOTAL_MB = 16_000

const EASE = [0.2, 0, 0, 1] as const

interface MemoryPanelProps {
  models: ModelRow[]
  events: ModelFrame[]
}

/**
 * Residency bar plus the swap timeline.
 *
 * This is the screen's central claim made visible: exactly one heavy model is in
 * memory at a time, and unloading is a process dying, not a hopeful garbage
 * collection. A block appears as a model loads and animates out on evict; the
 * timeline beneath records the sequence as it happened.
 */
export function MemoryPanel({ models, events }: MemoryPanelProps) {
  const reduced = useReducedMotion()
  const resident = models.filter((m) => m.state === 'READY' || m.state === 'LOADING')
  const usedMb = resident.reduce((total, m) => total + (m.rss_mb ?? 0), 0)

  return (
    <section className="surface-card p-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-[13px] text-text-0">Model residency</h2>
        <p className="tabular text-[12px] text-text-1">
          {(usedMb / 1000).toFixed(2)} / 16.0 GB
        </p>
      </div>

      <div className="relative mt-3 h-11 w-full overflow-hidden rounded-[8px] border border-border bg-bg-0">
        {/* 4 GB gridlines, so the bar reads as a scale rather than a progress bar. */}
        <div className="absolute inset-0 flex" aria-hidden="true">
          {[1, 2, 3].map((n) => (
            <div key={n} className="flex-1 border-r border-border/60" />
          ))}
          <div className="flex-1" />
        </div>

        <div className="absolute inset-0 flex items-stretch p-1">
          <AnimatePresence initial={false}>
            {resident.map((model) => (
              <motion.div
                key={model.key}
                layout={!reduced}
                initial={reduced ? false : { opacity: 0, scaleX: 0.85 }}
                animate={{ opacity: 1, scaleX: 1 }}
                exit={reduced ? { opacity: 0 } : { opacity: 0, scaleX: 0.9 }}
                transition={{ duration: 0.2, ease: EASE }}
                style={{
                  width: `${((model.rss_mb ?? 0) / TOTAL_MB) * 100}%`,
                  minWidth: '104px',
                  transformOrigin: 'left',
                }}
                title={
                  model.pid
                    ? `${model.key} — pid ${model.pid}, a supervised child process`
                    : `${model.key} — starting`
                }
                className={cn(
                  'flex min-w-0 flex-col justify-center gap-0.5 rounded-[5px] border px-2.5',
                  model.state === 'LOADING'
                    ? 'animate-pulse border-model/30 bg-model/10'
                    : 'border-model/40 bg-model/20',
                )}
              >
                <span className="truncate text-[12px] leading-none text-text-0">
                  {model.key}
                </span>
                <span className="tabular truncate text-[11px] leading-none text-model">
                  {model.rss_mb ? `${(model.rss_mb / 1000).toFixed(2)} GB` : 'loading…'}
                  {/* The pid is the evidence that a model is a real supervised
                      process, not an in-process load — kept unless space is tight. */}
                  {model.pid ? <span className="hidden lg:inline"> · pid {model.pid}</span> : null}
                </span>
              </motion.div>
            ))}
          </AnimatePresence>

          {resident.length === 0 && (
            <div className="flex w-full items-center px-2">
              <span className="text-[12px] text-text-1">No model resident</span>
            </div>
          )}
        </div>
      </div>

      <SwapTimeline events={events} />
    </section>
  )
}

/** Compact record of the load/evict sequence, newest last. */
function SwapTimeline({ events }: { events: ModelFrame[] }) {
  const steps = events.filter(
    (e) => e.kind === 'LOAD_READY' || e.kind === 'EVICT_DONE' || e.kind === 'PROCESS_DIED',
  )
  if (steps.length === 0) {
    return (
      <p className="mt-3 text-[12px] text-text-1">
        The swap sequence appears here as models load and are evicted.
      </p>
    )
  }

  return (
    <ol className="mt-3 flex flex-wrap items-center gap-x-1.5 gap-y-2">
      <AnimatePresence initial={false}>
        {steps.map((step, index) => (
          <motion.li
            key={`${step.kind}-${step.model_key}-${step.ts}-${index}`}
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15, ease: EASE }}
            className="flex items-center gap-1.5"
          >
            <span
              className={cn(
                'rounded-full border px-2 py-0.5 text-[11px]',
                step.kind === 'LOAD_READY'
                  ? 'border-model/30 bg-model/10 text-model'
                  : step.kind === 'PROCESS_DIED'
                    ? 'border-danger/30 bg-danger/10 text-danger'
                    : 'border-border bg-bg-3 text-text-1',
              )}
              title={
                step.kind === 'EVICT_DONE'
                  ? `Process ${step.pid ?? ''} terminated — unload is a process kill (INV-8)`
                  : undefined
              }
            >
              {step.kind === 'LOAD_READY'
                ? step.model_key
                : step.kind === 'PROCESS_DIED'
                  ? `${step.model_key} died`
                  : 'evict'}
            </span>
            {index < steps.length - 1 && (
              <ArrowRight className="size-3 text-text-2" strokeWidth={1.75} aria-hidden="true" />
            )}
          </motion.li>
        ))}
      </AnimatePresence>
    </ol>
  )
}
