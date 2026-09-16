import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowLeftRight,
  ArrowRight,
  Check,
  Download,
  Loader2,
  LockKeyhole,
  RefreshCw,
} from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { Dropdown } from '@/components/Dropdown'
import { UploadButton } from '@/components/UploadButton'
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
  download_name: string | null
  duration_seconds: number
  ok: boolean
}

export function Parivartan() {
  const [selected, setSelected] = useState<Conversion | null>(null)
  const [inputPath, setInputPath] = useState('')
  const [error, setError] = useState<string | null>(null)
  const {
    data: conversions,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['conversions'],
    queryFn: async (): Promise<Conversion[]> => {
      const response = await fetch('/conversions')
      if (!response.ok) throw new Error('Conversions unavailable')
      return response.json()
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
  const current = selected ?? conversions?.[0]
  const convert = useMutation({
    mutationFn: async (): Promise<ConversionReport> => {
      if (!current) throw new Error('Choose a conversion first')
      const response = await fetch('/convert', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          input_path: inputPath.trim(),
          src_format: current.src,
          dst_format: current.dst,
        }),
      })
      if (!response.ok)
        throw new Error(
          (await response.text()).slice(0, 240) || 'Conversion failed',
        )
      return response.json()
    },
    onError: (err: Error) => setError(err.message),
  })
  const choose = (pair: Conversion | undefined) => {
    setSelected(pair ?? null)
    setError(null)
    convert.reset()
  }
  const updatePath = (path: string) => {
    setInputPath(path)
    setError(null)
    convert.reset()
  }

  return (
    <>
      <Header title="Format converter" subtitle="Parivartan" />
      <div className="page-scroll">
        <div className="mx-auto max-w-[800px] space-y-6">
          <div>
            <h1 className="page-heading">Convert files</h1>
            <p className="mt-2 text-[16px] text-text-1">
              Choose a format and upload your file. Conversion runs locally.
            </p>
          </div>
          {isError ? (
            <div role="alert" className="surface-card p-6">
              <p className="text-[14px]">
                The local conversion service is unavailable.
              </p>
              <button
                type="button"
                className="secondary-button mt-3"
                onClick={() => void refetch()}
              >
                <RefreshCw className="size-3.5" /> Try again
              </button>
            </div>
          ) : isLoading ? (
            <div
              className="surface-card flex h-52 items-center justify-center gap-2 text-text-1"
              role="status"
            >
              <Loader2 className="size-4 animate-spin" /> Loading available
              formats…
            </div>
          ) : current ? (
            <div>
              <section className="surface-card p-5 md:p-6">
                <div className="mb-5 flex items-center gap-2.5">
                  <span className="step-number">01</span>
                  <h2 className="text-[14px]">Choose your conversion</h2>
                </div>
                <fieldset
                  disabled={convert.isPending}
                  className="grid grid-cols-[1fr_24px_1fr] items-end gap-3"
                >
                  <Dropdown
                    label="From format"
                    value={current.src}
                    options={sources.map((value) => ({
                      value,
                      label: value.toUpperCase(),
                    }))}
                    onChange={(src) =>
                      choose(conversions?.find((c) => c.src === src))
                    }
                  />
                  <ArrowRight className="mb-3 size-5 text-accent" />
                  <Dropdown
                    label="To format"
                    value={current.dst}
                    options={(conversions ?? [])
                      .filter((c) => c.src === current.src)
                      .map((c) => ({
                        value: c.dst,
                        label: c.dst.toUpperCase(),
                      }))}
                    onChange={(dst) =>
                      choose(index.get(`${current.src}>${dst}`))
                    }
                  />
                </fieldset>
                <p className="mt-3 rounded-lg bg-bg-0 px-3 py-2.5 text-[14px] leading-relaxed text-text-1">
                  {current.notes || current.label}
                </p>
                <div className="mt-7 mb-4 flex items-center gap-2.5">
                  <span className="step-number">02</span>
                  <h2 className="text-[14px]">Add your file</h2>
                </div>
                <fieldset disabled={convert.isPending}>
                  <UploadButton onUploaded={updatePath} purpose="conversion" />
                  <label
                    htmlFor="convert-path"
                    className="mt-4 mb-1.5 block text-[14px] text-text-1"
                  >
                    Or enter a file path on this machine
                  </label>
                  <input
                    id="convert-path"
                    value={inputPath}
                    onChange={(e) => updatePath(e.target.value)}
                    placeholder="data/samples/data.csv"
                    className="w-full rounded-lg border border-border bg-bg-0 px-3 py-2.5 text-[14px]"
                  />
                </fieldset>
                {error && (
                  <p role="alert" className="mt-3 text-[14px] text-danger">
                    {error}
                  </p>
                )}
                <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
                  <span className="flex items-center gap-1.5 text-[13px] text-text-1">
                    <LockKeyhole className="size-3" /> Converted on this machine
                  </span>
                  <button
                    type="button"
                    disabled={!inputPath.trim() || convert.isPending}
                    onClick={() => {
                      setError(null)
                      convert.mutate()
                    }}
                    className="primary-button"
                  >
                    {convert.isPending ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <ArrowLeftRight className="size-4" />
                    )}
                    {convert.isPending ? 'Converting…' : 'Convert file'}
                  </button>
                </div>
                {convert.data && <ReportView report={convert.data} />}
              </section>
            </div>
          ) : (
            <div className="surface-card p-6 text-text-1">
              No converters are installed in this build.
            </div>
          )}
          {conversions && conversions.length > 0 && (
            <details className="surface-card overflow-hidden">
              <summary className="px-5 py-4 text-[14px] font-medium">
                Explore all {conversions.length} supported conversions
              </summary>
              <div className="border-t border-border p-5">
                <p className="mb-4 text-[14px] text-text-1">
                  Choose a highlighted cell to select its source and destination
                  formats.
                </p>
                <div className="overflow-x-auto">
                  <table className="border-separate border-spacing-1 text-[13px]">
                    <thead>
                      <tr>
                        <th
                          scope="col"
                          className="sticky left-0 z-10 bg-bg-1 p-2 text-left text-text-1"
                        >
                          From ↓ / To →
                        </th>
                        {targets.map((target) => (
                          <th
                            key={target}
                            scope="col"
                            className="px-2 font-normal uppercase text-text-1"
                          >
                            {target}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sources.map((source) => (
                        <tr key={source}>
                          <th
                            scope="row"
                            className="sticky left-0 z-10 bg-bg-1 p-2 text-left font-normal uppercase text-text-1"
                          >
                            {source}
                          </th>
                          {targets.map((target) => {
                            const pair = index.get(`${source}>${target}`)
                            const active =
                              current?.src === source && current?.dst === target
                            return (
                              <td key={target} className="text-center">
                                {pair ? (
                                  <button
                                    type="button"
                                    disabled={convert.isPending}
                                    onClick={() => choose(pair)}
                                    title={pair.label}
                                    aria-label={`${source} to ${target}`}
                                    aria-pressed={active}
                                    className={cn(
                                      'inline-flex size-8 items-center justify-center rounded-md border transition-colors',
                                      active
                                        ? 'border-accent bg-accent text-[var(--on-accent)]'
                                        : 'border-accent/15 bg-accent/8 text-accent hover:bg-accent/20',
                                    )}
                                  >
                                    <Check className="size-3" />
                                  </button>
                                ) : (
                                  <span
                                    aria-label="Not supported"
                                    className="inline-block size-8 rounded-md bg-bg-0"
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
              </div>
            </details>
          )}
        </div>
      </div>
    </>
  )
}

function ReportView({ report }: { report: ConversionReport }) {
  return (
    <div
      role="status"
      className={cn(
        'mt-5 rounded-xl border p-4',
        report.ok ? 'border-ok/25 bg-ok/5' : 'border-danger/25 bg-danger/5',
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        {report.ok ? (
          <Check className="size-4 text-ok" />
        ) : (
          <AlertTriangle className="size-4 text-danger" />
        )}
        <span className="text-[14px] font-medium">
          {report.ok ? 'Your file is ready' : 'Conversion failed'}
        </span>
        <span className="tabular ml-auto text-[13px] text-text-1">
          {report.rows} rows · {duration(report.duration_seconds)}
        </span>
      </div>
      {report.download_name && (
        <a
          href={`/conversions/download/${encodeURIComponent(report.download_name)}`}
          download
          className="secondary-button mt-3 inline-flex"
        >
          <Download className="size-3.5" /> Download {report.download_name}
        </a>
      )}
      {report.warnings.length > 0 && (
        <ul className="mt-3 space-y-1">
          {report.warnings.map((warning, i) => (
            <li key={i} className="flex gap-1.5 text-[14px] text-warn">
              <AlertTriangle className="mt-0.5 size-3 shrink-0" />
              {warning}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
