import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowRight, Check, Loader2 } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { cn, duration } from '@/lib/utils'

interface Conversion {
  src: string
  dst: string
  label: string
  notes: string
}

interface ConversionReport {
  src_format: string
  dst_format: string
  rows: number
  warnings: string[]
  output_path: string | null
  duration_seconds: number
  ok: boolean
}

export function Parivartan() {
  const [selected, setSelected] = useState<Conversion | null>(null)
  const [inputPath, setInputPath] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: conversions } = useQuery({
    queryKey: ['conversions'],
    queryFn: async (): Promise<Conversion[]> => {
      const response = await fetch('/conversions')
      if (!response.ok) throw new Error('conversions unavailable')
      return (await response.json()) as Conversion[]
    },
    staleTime: Infinity,
  })

  const { sources, targets, index } = useMemo(() => {
    const rows = conversions ?? []
    return {
      sources: [...new Set(rows.map((r) => r.src))].sort(),
      targets: [...new Set(rows.map((r) => r.dst))].sort(),
      index: new Map(rows.map((r) => [`${r.src}>${r.dst}`, r])),
    }
  }, [conversions])

  const convert = useMutation({
    mutationFn: async (): Promise<ConversionReport> => {
      if (!selected) throw new Error('Pick a conversion first')
      const response = await fetch('/convert', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          input_path: inputPath.trim(),
          src_format: selected.src,
          dst_format: selected.dst,
        }),
      })
      if (!response.ok) {
        throw new Error((await response.text()).slice(0, 240) || 'Conversion failed')
      }
      return (await response.json()) as ConversionReport
    },
    onError: (err: Error) => setError(err.message),
  })

  return (
    <>
      <Header title="Parivartan" subtitle={`${conversions?.length ?? 0} conversions`} />

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="mx-auto flex max-w-[1000px] flex-col gap-4">
          <section className="surface-card p-4">
            <h2 className="text-[16px] text-text-0">Conversion matrix</h2>
            <p className="mt-1 text-[15px] text-text-1">
              Source format down the side, target across the top. A filled cell is a
              conversion this build can do.
            </p>

            <div className="mt-3 overflow-x-auto">
              <table className="border-separate border-spacing-0.5 text-[14px]">
                <thead>
                  <tr>
                    <th className="sticky left-0 z-10 bg-bg-2 p-1 text-left font-normal text-text-1">
                      from ↓ / to →
                    </th>
                    {targets.map((target) => (
                      <th
                        key={target}
                        className="p-1 text-left font-normal whitespace-nowrap text-text-1"
                      >
                        {target}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sources.map((source) => (
                    <tr key={source}>
                      <th className="sticky left-0 z-10 bg-bg-2 p-1 text-left font-normal whitespace-nowrap text-text-1">
                        {source}
                      </th>
                      {targets.map((target) => {
                        const pair = index.get(`${source}>${target}`)
                        const active =
                          selected?.src === source && selected?.dst === target
                        return (
                          <td key={target} className="p-0">
                            {pair ? (
                              <button
                                type="button"
                                onClick={() => {
                                  setSelected(pair)
                                  setError(null)
                                  convert.reset()
                                }}
                                title={`${pair.label} — ${pair.notes}`}
                                aria-label={pair.label}
                                className={cn(
                                  'size-6 rounded-[4px] border transition-colors duration-150',
                                  active
                                    ? 'border-accent bg-accent/55'
                                    : 'border-accent/40 bg-accent/22 hover:border-accent/70 hover:bg-accent/35',
                                )}
                              />
                            ) : (
                              <div
                                className="size-6 rounded-[4px] border border-border/25"
                                aria-hidden="true"
                              />
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {selected && (
            <section className="surface-card p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-[5px] border border-border bg-bg-0 px-2 py-1 text-[15px] text-text-0">
                  {selected.src}
                </span>
                <ArrowRight className="size-3.5 text-text-2" strokeWidth={1.75} />
                <span className="rounded-[5px] border border-accent/30 bg-accent/10 px-2 py-1 text-[15px] text-accent">
                  {selected.dst}
                </span>
                <span className="text-[15px] text-text-1">{selected.label}</span>
              </div>
              <p className="mt-2 text-[15px] leading-snug text-text-1">{selected.notes}</p>

              <div className="mt-3 flex flex-col gap-1.5">
                <label htmlFor="convert-path" className="text-[15px] text-text-1">
                  Input file path on this machine
                </label>
                <div className="flex gap-1.5">
                  <input
                    id="convert-path"
                    value={inputPath}
                    onChange={(event) => setInputPath(event.target.value)}
                    placeholder="data/samples/iocs.csv"
                    className="min-w-0 flex-1 rounded-[8px] border border-border bg-bg-0 px-2.5 py-1.5 text-[15px] text-text-0 placeholder:text-text-2 focus:border-border-2 focus:outline-none"
                  />
                  <button
                    type="button"
                    disabled={!inputPath.trim() || convert.isPending}
                    onClick={() => {
                      setError(null)
                      convert.mutate()
                    }}
                    className={cn(
                      'flex shrink-0 items-center gap-1.5 rounded-[8px] border px-3 py-1.5 text-[15px] transition-colors duration-150',
                      inputPath.trim() && !convert.isPending
                        ? 'border-accent/40 bg-accent/15 text-text-0 hover:border-accent/60 hover:bg-accent/20'
                        : 'cursor-not-allowed border-border bg-bg-2 text-text-1',
                    )}
                  >
                    {convert.isPending ? (
                      <Loader2 className="size-3.5 animate-spin" strokeWidth={1.75} />
                    ) : null}
                    Convert
                  </button>
                </div>
              </div>

              {error && <p className="mt-2 text-[15px] text-danger">{error}</p>}

              {convert.data && <ReportView report={convert.data} />}
            </section>
          )}
        </div>
      </div>
    </>
  )
}

function ReportView({ report }: { report: ConversionReport }) {
  return (
    <div
      className={cn(
        'mt-3 rounded-[8px] border p-3',
        report.ok ? 'border-ok/25 bg-ok/5' : 'border-danger/25 bg-danger/5',
      )}
    >
      <div className="flex items-center gap-2">
        {report.ok ? (
          <Check className="size-4 shrink-0 text-ok" strokeWidth={2} />
        ) : (
          <AlertTriangle className="size-4 shrink-0 text-danger" strokeWidth={1.75} />
        )}
        <span className="text-[16px] text-text-0">
          {report.ok ? 'Converted' : 'Conversion failed'}
        </span>
        <span className="tabular ml-auto text-[14px] text-text-1">
          {report.rows} rows · {duration(report.duration_seconds)}
        </span>
      </div>

      {report.output_path && (
        <p className="mt-2 text-[14px] break-all text-text-1">
          Written to <code className="font-mono text-text-0">{report.output_path}</code>
        </p>
      )}

      {report.warnings.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1">
          {report.warnings.map((warning, index) => (
            <li
              key={index}
              className="flex gap-1.5 text-[14px] leading-snug text-warn"
            >
              <AlertTriangle className="mt-px size-3 shrink-0" strokeWidth={1.75} />
              {warning}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
