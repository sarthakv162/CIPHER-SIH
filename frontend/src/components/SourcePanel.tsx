import { useState } from 'react'
import { FileAudio, FileText, FileVideo, Image, Plus, Trash2, Type } from 'lucide-react'
import type { SourceInput } from '@/lib/api'
import { UploadButton } from '@/components/UploadButton'
import { LottieMark } from '@/components/Lottie'
import emptyMark from '@/assets/lottie/workspace-empty.json'
import { cn } from '@/lib/utils'

/**
 * What each file type costs and yields, so the operator knows what a five-minute
 * run is about to do before starting it. These mirror the real ingestion paths in
 * `ingest/` — keyframes are scene-change detected, PDFs keep page and heading.
 */
const KINDS: Record<string, { icon: typeof FileText; plan: string }> = {
  pdf: { icon: FileText, plan: 'pages and headings preserved' },
  docx: { icon: FileText, plan: 'split on heading styles' },
  md: { icon: FileText, plan: 'read as one text block' },
  txt: { icon: FileText, plan: 'read as one text block' },
  html: { icon: FileText, plan: 'text extracted, markup dropped' },
  png: { icon: Image, plan: 'captioned by the vision model' },
  jpg: { icon: Image, plan: 'captioned by the vision model' },
  jpeg: { icon: Image, plan: 'captioned by the vision model' },
  wav: { icon: FileAudio, plan: 'transcribed by the speech model' },
  mp3: { icon: FileAudio, plan: 'transcribed by the speech model' },
  m4a: { icon: FileAudio, plan: 'transcribed by the speech model' },
  mp4: { icon: FileVideo, plan: 'scene keyframes + transcript' },
  mov: { icon: FileVideo, plan: 'scene keyframes + transcript' },
  mkv: { icon: FileVideo, plan: 'scene keyframes + transcript' },
}

function describe(path: string) {
  const ext = path.split('.').pop()?.toLowerCase() ?? ''
  return { ext, ...(KINDS[ext] ?? { icon: FileText, plan: 'read as text if possible' }) }
}

interface SourcePanelProps {
  sources: SourceInput[]
  prompt: string
  onPromptChange: (value: string) => void
  onAdd: (path: string) => void
  onRemove: (index: number) => void
}

export function SourcePanel({
  sources,
  prompt,
  onPromptChange,
  onAdd,
  onRemove,
}: SourcePanelProps) {
  const [draft, setDraft] = useState('')

  const files = sources.filter((s) => s.kind === 'file')

  const submit = () => {
    const value = draft.trim()
    if (!value) return
    onAdd(value)
    setDraft('')
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start gap-2">
        {files.length === 0 && !prompt.trim() && (
          <LottieMark
            animationData={emptyMark}
            size={28}
            className="mt-0.5 shrink-0"
            fallback={
              <div className="flex size-full items-center justify-center">
                <span className="size-2 rounded-full bg-accent/70" />
              </div>
            }
          />
        )}
        <div>
        <h2 className="text-[16px] text-text-0">Sources</h2>
        <p className="mt-1 text-[15px] leading-snug text-text-1">
          Text, PDF, image, audio or video. Uploads are written to this machine —
          nothing leaves it.
        </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="flex flex-col gap-2">
          <UploadButton onUploaded={onAdd} />

      {/* Still available for a file already sitting on this machine. */}
      <details className="group">
        <summary className="cursor-pointer list-none text-[14px] text-text-1 transition-colors duration-150 hover:text-text-0">
          or reference a path already on this machine
        </summary>
        <div className="mt-2 flex gap-1.5">
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && submit()}
            placeholder="data/samples/incident.pdf"
            aria-label="Source path"
            className="min-w-0 flex-1 rounded-[8px] border border-border bg-bg-0 px-2.5 py-1.5 text-[15px] text-text-0 placeholder:text-text-2 focus:border-border-2 focus:outline-none"
          />
          <button
            type="button"
            onClick={submit}
            disabled={!draft.trim()}
            className="flex items-center gap-1 rounded-[8px] border border-border bg-bg-2 px-2.5 py-1.5 text-[15px] text-text-0 transition-colors duration-150 hover:border-border-2 hover:bg-bg-3 disabled:opacity-40"
          >
            <Plus className="size-3.5" strokeWidth={1.75} />
            Add
          </button>
        </div>
      </details>
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="prompt"
            className="flex items-center gap-1.5 text-[15px] text-text-1"
          >
            <Type className="size-3.5" strokeWidth={1.75} />
            Text source
          </label>
          <textarea
            id="prompt"
            value={prompt}
            onChange={(event) => onPromptChange(event.target.value)}
            placeholder="Paste or write source material here."
            className={cn(
              'min-h-[132px] flex-1 resize-y rounded-[12px] border border-border bg-bg-0 px-3 py-2.5 text-[15px] leading-relaxed',
              'text-text-0 placeholder:text-text-2 focus:border-border-2 focus:outline-none',
            )}
          />
        </div>
      </div>

      <ul className="flex max-h-[136px] flex-col gap-1.5 overflow-y-auto">
        {files.map((source, index) => {
          const path = source.path ?? ''
          const { ext, icon: Icon, plan } = describe(path)
          return (
            <li
              key={`${path}-${index}`}
              className="group flex items-start gap-2.5 rounded-[8px] border border-border bg-bg-2 px-2.5 py-2"
            >
              <Icon className="mt-0.5 size-4 shrink-0 text-text-1" strokeWidth={1.75} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] text-text-0">
                  {path.split('/').pop()}
                </span>
                <span className="block truncate text-[14px] text-text-1">
                  {ext || 'file'} · {plan}
                </span>
              </span>
              <button
                type="button"
                onClick={() => onRemove(sources.indexOf(source))}
                aria-label={`Remove ${path}`}
                className="rounded-[5px] p-1 text-text-2 opacity-0 transition-opacity duration-150 group-hover:opacity-100 hover:bg-bg-3 hover:text-danger focus-visible:opacity-100"
              >
                <Trash2 className="size-3.5" strokeWidth={1.75} />
              </button>
            </li>
          )
        })}
        {files.length === 0 && (
          <li className="rounded-[8px] border border-border/60 px-2.5 py-3 text-center text-[15px] text-text-1">
            No files added
          </li>
        )}
      </ul>

    </div>
  )
}
