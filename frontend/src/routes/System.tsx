import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Check, Loader2, RefreshCw, X } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

interface CheckResult {
  number: string
  name: string
  level: 'ok' | 'warn' | 'fail'
  detail: string
  data: Record<string, unknown>
}

interface SelfcheckReport {
  generated_at: string
  profile: string
  profile_source: string
  checks: CheckResult[]
  ok: boolean
  result: 'PASS' | 'FAIL'
}

/**
 * The selfcheck report as a screen.
 *
 * `load_model` defaults to false: running the load/unload probe would build a
 * second ModelManager inside the serving process, and two heavy models must
 * never be resident at once. The deep check is offered explicitly, and the row
 * it fills in says plainly when it was skipped.
 */
export function System() {
  const [deep, setDeep] = useState(false)

  const { data, isFetching, isError, refetch } = useQuery({
    queryKey: ['selfcheck', deep],
    queryFn: async (): Promise<SelfcheckReport> => {
      const response = await fetch(`/selfcheck?load_model=${deep}&fast=${!deep}`)
      if (!response.ok) throw new Error(`selfcheck unavailable (${response.status})`)
      return (await response.json()) as SelfcheckReport
    },
    staleTime: 30_000,
  })

  const { data: templates } = useQuery({ queryKey: ['templates'], queryFn: api.templates })

  return (
    <>
      <Header title="System" subtitle="Selfcheck" />

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="mx-auto flex max-w-[900px] flex-col gap-4">
          <section
            className={cn(
              'flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[12px] border p-4',
              !data
                ? 'border-border bg-bg-2'
                : data.ok
                  ? 'border-ok/25 bg-ok/8'
                  : 'border-danger/30 bg-danger/8',
            )}
          >
            <div className="flex items-center gap-2.5">
              {isFetching ? (
                <Loader2 className="size-5 animate-spin text-text-1" strokeWidth={1.75} />
              ) : data?.ok ? (
                <Check className="size-5 text-ok" strokeWidth={2} />
              ) : (
                <AlertTriangle className="size-5 text-danger" strokeWidth={1.75} />
              )}
              <div>
                <div className="text-[18px] text-text-0">
                  {isFetching ? 'Running checks…' : (data?.result ?? 'Unavailable')}
                </div>
                {data && (
                  <div className="text-[15px] text-text-1">
                    {data.checks.filter((c) => c.level === 'ok').length} of{' '}
                    {data.checks.length} checks passed
                  </div>
                )}
              </div>
            </div>

            {data && (
              <dl className="flex flex-wrap gap-x-5 gap-y-1 text-[15px]">
                <div>
                  <dt className="text-text-1">Profile</dt>
                  <dd className="text-text-0">{data.profile}</dd>
                </div>
                <div>
                  <dt className="text-text-1">Selected by</dt>
                  <dd className="text-text-0">{data.profile_source}</dd>
                </div>
                <div>
                  <dt className="text-text-1">Checked</dt>
                  <dd className="tabular text-text-0">
                    {new Date(data.generated_at).toLocaleTimeString()}
                  </dd>
                </div>
              </dl>
            )}

            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="ml-auto flex items-center gap-1.5 rounded-[8px] border border-border bg-bg-2 px-2.5 py-1.5 text-[15px] text-text-0 transition-colors duration-150 hover:border-border-2 hover:bg-bg-3 disabled:opacity-50"
            >
              <RefreshCw
                className={cn('size-3.5', isFetching && 'animate-spin')}
                strokeWidth={1.75}
              />
              Re-run
            </button>
          </section>

          {isError && (
            <p className="rounded-[8px] border border-warn/25 bg-warn/10 px-3 py-2 text-[15px] text-warn">
              The selfcheck endpoint did not respond.
            </p>
          )}

          <section className="surface-card overflow-hidden">
            <div className="hairline-b flex items-center justify-between px-4 py-3">
              <h2 className="text-[16px] text-text-0">Checks</h2>
              <label className="flex items-center gap-1.5 text-[15px] text-text-1">
                <input
                  type="checkbox"
                  checked={deep}
                  onChange={(event) => setDeep(event.target.checked)}
                  className="accent-[var(--color-accent)]"
                />
                Include the model load/unload probe
              </label>
            </div>

            <ul className="divide-y divide-border">
              {(data?.checks ?? []).map((check) => (
                <li key={check.number} className="flex items-start gap-3 px-4 py-2.5">
                  <StatusDot level={check.level} />
                  <span className="tabular w-6 shrink-0 text-[15px] text-text-2">
                    {check.number}
                  </span>
                  <span className="w-[170px] shrink-0 text-[16px] text-text-0">
                    {check.name}
                  </span>
                  <span className="min-w-0 flex-1 text-[15px] leading-relaxed break-words text-text-1">
                    {check.detail}
                  </span>
                </li>
              ))}
              {!data && !isFetching && (
                <li className="px-4 py-6 text-center text-[15px] text-text-1">
                  No report yet.
                </li>
              )}
            </ul>
          </section>

          <section className="surface-card p-4">
            <h2 className="text-[16px] text-text-0">Output templates</h2>
            <p className="mt-1 text-[15px] leading-snug text-text-1">
              Installed themes. Selecting one per transform is not wired up yet — the
              renderers currently use <code className="text-text-0">ntro-formal</code>{' '}
              for every artefact.
            </p>
            <ul className="mt-2.5 flex flex-col gap-1.5">
              {(templates ?? []).map((template) => (
                <li
                  key={template.name}
                  className="flex items-start gap-2.5 rounded-[8px] border border-border bg-bg-0 px-2.5 py-2"
                >
                  <span
                    className="mt-1 size-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: template.accent ?? 'var(--color-text-2)' }}
                    aria-hidden="true"
                  />
                  <span className="min-w-0">
                    <span className="block text-[15px] text-text-0">
                      {template.label || template.name}
                    </span>
                    <span className="block text-[14px] leading-snug text-text-1">
                      {template.description}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </>
  )
}

function StatusDot({ level }: { level: CheckResult['level'] }) {
  if (level === 'ok') return <Check className="mt-0.5 size-4 shrink-0 text-ok" strokeWidth={2} />
  if (level === 'warn')
    return (
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" strokeWidth={1.75} />
    )
  return <X className="mt-0.5 size-4 shrink-0 text-danger" strokeWidth={2} />
}
