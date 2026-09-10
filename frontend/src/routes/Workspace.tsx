import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { AlertTriangle, Loader2, Play } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { OutputTypeCard } from '@/components/OutputTypeCard'
import { Dropdown } from '@/components/Dropdown'
import { SourcePanel } from '@/components/SourcePanel'
import { ARTEFACTS, estimateSeconds } from '@/lib/artefacts'
import { AUDIENCES, DETAILS, LANGUAGES, OBJECTIVES, STYLES, TONES } from '@/lib/params'
import { buildRequest, useWorkspace } from '@/store/workspace'
import { cn, duration } from '@/lib/utils'

export function Workspace() {
  const navigate = useNavigate()
  const state = useWorkspace()
  const [error, setError] = useState<string | null>(null)

  const hasSource = state.sources.length > 0 || state.prompt.trim().length > 0
  const seconds = estimateSeconds(state.selected)
  const ready = hasSource && state.selected.length > 0

  const submit = useMutation({
    mutationFn: async () => {
      const response = await fetch('/transforms', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(buildRequest(state)),
      })
      if (!response.ok) {
        const detail = await response.text()
        throw new Error(detail.slice(0, 300) || `Request failed (${response.status})`)
      }
      return (await response.json()) as { transform_id: string }
    },
    onSuccess: (data) => navigate(`/runs/${data.transform_id}`),
    onError: (err: Error) => setError(err.message),
  })

  return (
    <>
      <Header title="Workspace" subtitle="Compose a transform" />

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto md:flex-row md:overflow-hidden">
        <div className="flex min-w-0 flex-1 flex-col gap-px overflow-y-auto bg-border">
        <section className="shrink-0 bg-bg-1 p-4">
          <SourcePanel
            sources={state.sources}
            prompt={state.prompt}
            onPromptChange={state.setPrompt}
            onAdd={state.addFile}
            onRemove={state.removeSource}
          />
        </section>

        <section className="min-h-0 flex-1 bg-bg-1 p-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[16px] text-text-0">Output types</h2>
            <span className="tabular text-[15px] text-text-1">
              {state.selected.length} of {ARTEFACTS.length} selected
            </span>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
            {ARTEFACTS.map((artefact) => (
              <OutputTypeCard
                key={artefact.type}
                label={artefact.label}
                description={artefact.description}
                formats={artefact.formats}
                seconds={artefact.seconds}
                icon={artefact.icon}
                selected={state.selected.includes(artefact.type)}
                onToggle={() => state.toggle(artefact.type)}
              />
            ))}
          </div>
        </section>

        </div>

        <aside className="flex w-full shrink-0 flex-col border-t border-border bg-bg-1 p-4 md:w-[320px] md:border-t-0 md:border-l md:overflow-y-auto">
          <h2 className="text-[16px] text-text-0">Parameters</h2>
          <div className="mt-3 flex flex-col gap-3.5">
            <Dropdown
              label="Audience"
              value={state.params.audience}
              options={AUDIENCES}
              onChange={(v) => state.setParam('audience', v)}
            />
            <Dropdown
              label="Tone"
              value={state.params.tone}
              options={TONES}
              onChange={(v) => state.setParam('tone', v)}
            />
            <Dropdown
              label="Detail"
              value={state.params.detail}
              options={DETAILS}
              onChange={(v) => state.setParam('detail', v)}
            />
            <Dropdown
              label="Objective"
              value={state.params.objective}
              options={OBJECTIVES}
              onChange={(v) => state.setParam('objective', v)}
            />
            <Dropdown
              label="Style"
              value={state.params.style}
              options={STYLES}
              onChange={(v) => state.setParam('style', v)}
            />
            <Dropdown
              label="Language"
              value={state.params.language}
              options={LANGUAGES}
              onChange={(v) => state.setParam('language', v)}
            />
            {state.params.language !== 'en' && (
              <p className="flex gap-1.5 text-[14px] leading-snug text-warn">
                <AlertTriangle className="mt-px size-3.5 shrink-0" strokeWidth={1.75} />
                Speech and narration are English-only. Written artefacts honour this
                best-effort; a note is recorded in the manifest.
              </p>
            )}
          </div>
        </aside>
      </div>

      <div className="hairline-t flex shrink-0 items-center justify-between gap-4 bg-bg-1 px-4 py-3">
        <div className="min-w-0">
          {error ? (
            <p className="truncate text-[15px] text-danger">{error}</p>
          ) : (
            <p className="tabular text-[15px] text-text-1">
              {state.selected.length === 0
                ? 'Select at least one output type'
                : !hasSource
                  ? 'Add a source to begin'
                  : `${state.selected.length} artefact${state.selected.length === 1 ? '' : 's'} · ~${duration(seconds)}`}
            </p>
          )}
          {ready && !error && (
            <p className="mt-0.5 text-[14px] text-text-1">
              Estimated on this hardware. Verification adds time after generation.
            </p>
          )}
        </div>

        <button
          type="button"
          disabled={!ready || submit.isPending}
          onClick={() => {
            setError(null)
            submit.mutate()
          }}
          className={cn(
            'flex shrink-0 items-center gap-2 rounded-[8px] border px-3.5 py-2 text-[16px]',
            'transition-all duration-200 ease-[cubic-bezier(0.2,0,0,1)]',
            ready && !submit.isPending
              ? 'border-accent/40 bg-accent/15 text-text-0 shadow-[0_6px_20px_-8px_rgba(91,141,239,0.6)] hover:border-accent/60 hover:bg-accent/20'
              : 'cursor-not-allowed border-border bg-bg-2 text-text-1',
          )}
        >
          {submit.isPending ? (
            <Loader2 className="size-4 animate-spin text-accent" strokeWidth={1.75} />
          ) : (
            <Play className="size-4 text-accent" strokeWidth={1.75} />
          )}
          Generate
        </button>
      </div>
    </>
  )
}
