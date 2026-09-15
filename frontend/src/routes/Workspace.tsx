import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import * as Dialog from '@radix-ui/react-dialog'
import {
  ArrowUp,
  Check,
  ChevronDown,
  FileText,
  Loader2,
  MessageCircleQuestion,
  Paperclip,
  Plus,
  SlidersHorizontal,
  X,
  Sparkles,
  LockKeyhole,
} from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { Dropdown } from '@/components/Dropdown'
import { ArtefactCatalog } from '@/components/ArtefactCatalog'
import { askStream, createAskSession, type AskTurn } from '@/lib/ask'
import { api } from '@/lib/api'
import { ARTEFACTS, ARTEFACT_BY_TYPE, CATEGORIES, estimateSeconds } from '@/lib/artefacts'
import {
  AUDIENCES,
  DETAILS,
  LANGUAGES,
  OBJECTIVES,
  STYLES,
  TONES,
} from '@/lib/params'
import { buildRequest, useWorkspace } from '@/store/workspace'
import { cn, duration } from '@/lib/utils'

type ComposerMode = 'source' | 'ask'

const SAMPLE =
  'The National Digital Literacy Initiative completed a pilot across 120 rural schools. It trained 8,400 students and 360 teachers in safe internet use, identifying misinformation, and protecting personal information. Each school received an offline learning kit in English and Hindi. After training, 78% of students could identify a phishing message, compared with 34% before. The next phase will reach 500 schools. Coordinators recommend monthly refresher sessions and a digital safety contact in each school.'

export function Workspace() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const category = CATEGORIES.find(c => c.id === searchParams.get('category'))?.id ?? 'all'
  const state = useWorkspace()
  const input = useRef<HTMLInputElement>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const [panel, setPanel] = useState<'outputs' | 'settings' | 'path' | null>(
    null,
  )
  const [path, setPath] = useState('')
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<ComposerMode>('source')
  const [turns, setTurns] = useState<AskTurn[]>([])
  const [asking, setAsking] = useState(false)
  const [askSessionId, setAskSessionId] = useState<string | null>(null)
  const hasSource = Boolean(state.prompt.trim() || state.sources.length)
  const ready = hasSource && state.selected.length > 0 && !busy

  // A new or removed source invalidates the evidence pack behind any open ask session.
  useEffect(() => {
    setAskSessionId(null)
  }, [state.sources])

  const { data: templates } = useQuery({
    queryKey: ['templates'],
    queryFn: api.templates,
    staleTime: 60_000,
  })
  const submit = useMutation({
    mutationFn: async () => {
      const response = await fetch('/transforms', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(buildRequest(state)),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(
          typeof body?.detail === 'string'
            ? body.detail
            : 'Could not start the transform. Check the local engine and try again.',
        )
      }
      return response.json() as Promise<{ transform_id: string }>
    },
    onSuccess: (data) => {
      try {
        sessionStorage.setItem(
          `rupantar:request:${data.transform_id}`,
          JSON.stringify({
            prompt: state.prompt,
            files: state.sources.map((s) => s.path?.split('/').pop()),
          }),
        )
      } catch {
        /* The transform can proceed when browser storage is unavailable. */
      }
      navigate(`/runs/${data.transform_id}`)
    },
    onError: (err: Error) => setError(err.message),
  })
  const upload = async (files: FileList | null) => {
    if (!files?.length || busy || submit.isPending) return
    setBusy(true)
    setError(null)
    try {
      for (const file of Array.from(files)) {
        const response = await fetch(
          `/sources?filename=${encodeURIComponent(file.name)}`,
          {
            method: 'POST',
            headers: { 'content-type': 'application/octet-stream' },
            body: file,
          },
        )
        const result = await response.json()
        if (!response.ok)
          throw new Error(result.detail || `Could not upload ${file.name}`)
        state.addFile(result.path)
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Upload failed. Please try again.',
      )
    } finally {
      setBusy(false)
    }
  }
  const generate = () => {
    if (ready && !submit.isPending) {
      setError(null)
      submit.mutate()
    }
  }
  const canAsk = state.sources.length > 0 && Boolean(state.prompt.trim()) && !asking
  const askQuestion = async () => {
    const question = state.prompt.trim()
    if (!canAsk) return
    state.setPrompt('')
    setAsking(true)
    setTurns((prev) => [...prev, { question, answer: '', status: 'streaming' }])
    const setLast = (patch: Partial<AskTurn>) =>
      setTurns((prev) => {
        const next = [...prev]
        next[next.length - 1] = { ...next[next.length - 1], ...patch }
        return next
      })
    try {
      let sessionId = askSessionId
      if (!sessionId) {
        sessionId = await createAskSession(state.sources)
        setAskSessionId(sessionId)
      }
      let answer = ''
      await askStream(`/qa/sessions/${sessionId}/ask`, question, (delta) => {
        answer += delta
        setLast({ answer })
      })
      setLast({ status: 'done' })
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Could not answer that question.'
      setLast({ status: 'error', error: message })
      setAskSessionId(null)
    } finally {
      setAsking(false)
    }
  }
  const outputLabel =
    state.selected.length === 1
      ? ARTEFACT_BY_TYPE.get(state.selected[0])?.label
      : `${state.selected.length} outputs`

  return (
    <>
      <Header title="New transform" />
      <div className="workspace-body">
        <div className="chat-start">
          <div className="studio-welcome">
            <p className="welcome-eyebrow">OFFLINE • AIR-GAPPED • ON-DEVICE AI</p>
            <h1 className="chat-greeting">Source material, <span>transformed.</span></h1>
            <p className="welcome-description">Turn documents, audio, video, and text into verified communication artefacts.</p>
          </div>
          <div
            className={cn('composer', dragging && 'is-dragging')}
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node))
                setDragging(false)
            }}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              void upload(e.dataTransfer.files)
            }}
          >
            <div className="composer-heading">
              <div role="tablist" aria-label="Composer mode" className="mode-toggle">
                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === 'source'}
                  onClick={() => setMode('source')}
                  className={cn('mode-toggle-option', mode === 'source' && 'active')}
                >
                  <Sparkles className="size-3.5" />
                  Add as source
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === 'ask'}
                  onClick={() => setMode('ask')}
                  className={cn('mode-toggle-option', mode === 'ask' && 'active')}
                >
                  <MessageCircleQuestion className="size-3.5" />
                  Ask about sources
                </button>
              </div>
              <span className="composer-private">
                <LockKeyhole className="size-3" />
                Private by design
              </span>
            </div>
            {mode === 'ask' && turns.length > 0 && (
              <ul className="ask-transcript" aria-live="polite">
                {turns.map((turn, i) => (
                  <li key={i} className="ask-turn">
                    <p className="ask-question">{turn.question}</p>
                    <p className="ask-answer">
                      {turn.answer}
                      {turn.status === 'streaming' && (
                        <Loader2 className="ml-1.5 inline size-3.5 animate-spin align-middle" />
                      )}
                    </p>
                    {turn.status === 'error' && (
                      <p role="alert" className="ask-error">
                        {turn.error}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {state.sources.length > 0 && (
              <ul className="mb-3 flex flex-wrap gap-2">
                {state.sources.map((source, i) => (
                  <li
                    key={`${source.path}-${i}`}
                    className="flex max-w-full items-center gap-2 rounded-xl border border-border bg-bg-2 py-2 pr-1 pl-3"
                  >
                    <FileText className="size-4 shrink-0 text-text-1" />
                    <span className="min-w-0 truncate text-[14px]">
                      {source.path?.split('/').pop()}
                    </span>
                    <button
                      type="button"
                      aria-label={`Remove ${source.path?.split('/').pop()}`}
                      onClick={() => state.removeSource(i)}
                      disabled={submit.isPending}
                      className="icon-button !size-8"
                    >
                      <X className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <label htmlFor="chat-source" className="sr-only">
              {mode === 'ask' ? 'Question about your sources' : 'Source text or instructions'}
            </label>
            <textarea
              ref={textarea}
              id="chat-source"
              className="composer-input"
              value={state.prompt}
              onChange={(e) => {
                state.setPrompt(e.target.value)
                e.target.style.height = 'auto'
                e.target.style.height = `${Math.min(260, Math.max(100, e.target.scrollHeight))}px`
              }}
              placeholder={
                mode === 'ask'
                  ? 'Ask a question about your attached sources…'
                  : 'Paste your source, describe an idea, or add a file…'
              }
              disabled={submit.isPending || (mode === 'ask' && asking)}
              onKeyDown={(e) => {
                if (
                  e.key === 'Enter' &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault()
                  if (mode === 'ask') void askQuestion()
                  else generate()
                }
              }}
              aria-describedby="composer-help"
            />
            <div className="composer-tools">
              <button
                type="button"
                className="icon-button"
                aria-label="Attach files"
                title="Attach files"
                disabled={busy || submit.isPending}
                onClick={() => input.current?.click()}
              >
                {busy ? (
                  <Loader2 className="size-5 animate-spin" />
                ) : (
                  <Plus className="size-6" strokeWidth={1.6} />
                )}
              </button>
              {mode === 'source' && (
                <>
                  <button
                    type="button"
                    className="composer-pill"
                    onClick={() => setPanel('outputs')}
                    aria-label="Choose output formats"
                    aria-haspopup="dialog"
                  >
                    <span className="truncate">
                      {outputLabel || 'Choose outputs'}
                    </span>
                    <ChevronDown className="size-3.5 shrink-0" />
                  </button>
                  <button
                    type="button"
                    className="icon-button"
                    onClick={() => setPanel('settings')}
                    aria-label="Generation settings"
                    title="Generation settings"
                  >
                    <SlidersHorizontal className="size-[18px]" strokeWidth={1.7} />
                  </button>
                </>
              )}
              {mode === 'ask' ? (
                <button
                  type="button"
                  className="send-button ml-auto"
                  onClick={() => void askQuestion()}
                  disabled={!canAsk}
                  aria-label="Ask"
                  title="Ask"
                >
                  <span className="send-label">Ask</span>
                  {asking ? (
                    <Loader2 className="size-5 animate-spin" />
                  ) : (
                    <ArrowUp className="size-5" strokeWidth={2} />
                  )}
                </button>
              ) : (
                <button
                  type="button"
                  className="send-button"
                  onClick={generate}
                  disabled={!ready || submit.isPending}
                  aria-label="Generate content"
                  title="Generate content"
                >
                  <span className="send-label">Create</span>
                  {submit.isPending ? (
                    <Loader2 className="size-5 animate-spin" />
                  ) : (
                    <ArrowUp className="size-5" strokeWidth={2} />
                  )}
                </button>
              )}
            </div>
            <input
              ref={input}
              type="file"
              multiple
              hidden
              accept=".txt,.md,.html,.htm,.pdf,.docx,.png,.jpg,.jpeg,.webp,.gif,.wav,.mp3,.m4a,.flac,.ogg,.mp4,.mov,.mkv,.webm"
              onChange={(e) => {
                void upload(e.target.files)
                e.target.value = ''
              }}
            />
          </div>
          {error && (
            <p
              role="alert"
              className="mt-3 rounded-lg bg-danger/5 px-3 py-2 text-[14px] text-danger"
            >
              {error}
            </p>
          )}
          {busy && (
            <p role="status" className="mt-3 text-[14px] text-text-1">
              Adding files to your local workspace…
            </p>
          )}
          <div className="source-hints"><div
            id="composer-help"
            className="composer-help"
          >
            {mode === 'ask' ? (
              <span>
                {state.sources.length
                  ? 'Answers cite [En] evidence tags and say plainly when a source doesn’t cover something.'
                  : 'Attach at least one source to ask about it.'}
                {' '}
                <span className="mx-1">·</span> Enter to ask, Shift + Enter for a new line
              </span>
            ) : hasSource ? (
              <span>
                {state.selected.length} output
                {state.selected.length === 1 ? '' : 's'} · ~
                {duration(estimateSeconds(state.selected))} generation{' '}
                <span className="mx-1">·</span> Enter to send, Shift + Enter for
                a new line
              </span>
            ) : (
              <span>
                Start with your own material or{' '}
                <button
                  type="button"
                  className="underline decoration-border-2 underline-offset-4 hover:text-text-0"
                  onClick={() => {
                    state.setPrompt(SAMPLE)
                    textarea.current?.focus()
                  }}
                >
                  try a sample
                </button>
                .
              </span>
            )}
          </div>
          <div className="path-helper">
            <button
              type="button"
              onClick={() => setPanel('path')}
              className="rounded px-2 py-1 text-[14px] text-text-1 hover:text-text-0"
            >
              Use a local file path
            </button>
          </div>
          </div>
          {mode === 'source' && (
            <ArtefactCatalog
              category={category}
              onCategoryChange={value => setSearchParams(value === 'all' ? {} : { category: value }, { replace: true })}
              selected={state.selected}
              onToggle={state.toggle}
              disabled={submit.isPending}
            />
          )}
        </div>
      </div>
      <footer className="studio-footer">
        <span><LockKeyhole className="size-3" />Made here. Stays here.</span><span>Review generated content before sharing.</span>
      </footer>
      <Dialog.Root
        open={panel !== null}
        onOpenChange={(open) => {
          if (!open) setPanel(null)
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="settings-dialog">
            <div className="mb-2 flex items-center justify-between gap-3">
              <Dialog.Title className="text-[21px] font-medium tracking-[-.025em]">
                {panel === 'outputs'
                  ? 'Choose your outputs'
                  : panel === 'settings'
                    ? 'Generation settings'
                    : 'Use a local file'}
              </Dialog.Title>
              <Dialog.Close className="icon-button" aria-label="Close settings">
                <X className="size-5" />
              </Dialog.Close>
            </div>
            <Dialog.Description className="mb-5 text-[14px] text-text-1">
              {panel === 'outputs'
                ? 'Create one or several formats from the same source.'
                : panel === 'settings'
                  ? 'Set the audience, voice, level of detail, and output template.'
                  : 'Enter the path to a source file already on this machine.'}
            </Dialog.Description>
            {panel === 'outputs' && (
              <>
                <div className="mb-2 flex justify-end">
                  <button
                    type="button"
                    onClick={() =>
                      state.setSelected(
                        state.selected.length === ARTEFACTS.length
                          ? []
                          : ARTEFACTS.map((a) => a.type),
                      )
                    }
                    className="rounded px-2 py-1 text-[14px] text-text-1 hover:text-text-0"
                  >
                    {state.selected.length === ARTEFACTS.length
                      ? 'Clear selection'
                      : 'Select all'}
                  </button>
                </div>
                <div className="space-y-4">
                  {CATEGORIES.filter(c => c.id !== 'all').map(c => <fieldset key={c.id}><legend className="nav-label !px-0">{c.label}</legend>{ARTEFACTS.filter(a => a.category === c.id).map((a) => (
                    <button
                      type="button"
                      role="checkbox"
                      aria-checked={state.selected.includes(a.type)}
                      aria-label={a.label}
                      key={a.type}
                      onClick={() => state.toggle(a.type)}
                      className="output-choice"
                    >
                      <a.icon
                        className="size-5 shrink-0 text-text-1"
                        strokeWidth={1.7}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block text-[15px] font-medium">
                          {a.label}
                        </span>
                        <span className="mt-0.5 block text-[14px] leading-relaxed text-text-1">
                          {a.description}
                        </span>
                      </span>
                      <span
                        className={cn(
                          'flex size-5 shrink-0 items-center justify-center rounded-md border',
                          state.selected.includes(a.type)
                            ? 'border-accent bg-accent text-[var(--on-accent)]'
                            : 'border-border-2',
                        )}
                      >
                        {state.selected.includes(a.type) && (
                          <Check className="size-3.5" />
                        )}
                      </span>
                    </button>
                  ))}</fieldset>)}
                </div>
              </>
            )}
            {panel === 'settings' && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Dropdown
                  label="Audience"
                  value={state.params.audience}
                  options={AUDIENCES}
                  onChange={(v) => state.setParam('audience', v)}
                />
                <Dropdown
                  label="Tone of voice"
                  value={state.params.tone}
                  options={TONES}
                  onChange={(v) => state.setParam('tone', v)}
                />
                <Dropdown
                  label="Level of detail"
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
                  label="Writing style"
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
                {templates && templates.length > 0 && (
                  <Dropdown
                    label="Output template"
                    value={state.params.template}
                    options={templates.map((t) => ({ value: t.id, label: t.label }))}
                    onChange={(v) => state.setParam('template', v)}
                  />
                )}
                {state.params.language !== 'en' && (
                  <p className="text-[14px] text-warn sm:col-span-2">
                    Written outputs follow your language on a best-effort basis.
                    Speech and narration are English-only.
                  </p>
                )}
              </div>
            )}
            {panel === 'path' && (
              <div>
                <label htmlFor="source-path" className="mb-2 block text-[14px]">
                  File path
                </label>
                <input
                  id="source-path"
                  value={path}
                  onChange={(e) => setPath(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && path.trim()) {
                      state.addFile(path.trim())
                      setPath('')
                      setPanel(null)
                    }
                  }}
                  placeholder="data/samples/report.pdf"
                  className="w-full rounded-xl border border-border px-3 py-3 text-[16px]"
                />
              </div>
            )}
            <div className="mt-6 flex justify-end border-t border-border pt-4">
              <button
                type="button"
                className="primary-button"
                disabled={panel === 'path' && !path.trim()}
                onClick={() => {
                  if (panel === 'path') {
                    state.addFile(path.trim())
                    setPath('')
                  }
                  setPanel(null)
                }}
              >
                {panel === 'path' ? (
                  <>
                    <Paperclip className="size-4" />
                    Add file
                  </>
                ) : (
                  'Done'
                )}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  )
}
