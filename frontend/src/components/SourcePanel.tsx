import { useState } from 'react'
import {
  FileAudio,
  FileText,
  FileVideo,
  Image,
  LockKeyhole,
  Plus,
  Trash2,
} from 'lucide-react'
import type { SourceInput } from '@/lib/api'
import { UploadButton } from '@/components/UploadButton'

const SAMPLE =
  'On 12 August 2026, the National Digital Literacy Initiative completed its pilot across 120 rural schools in three states. The programme trained 8,400 students and 360 teachers in safe internet use, identifying misinformation, and protecting personal information. Each school received an offline learning kit with interactive lessons in English and Hindi. An independent assessment found that 78% of participating students could correctly identify a phishing message after training, compared with 34% before the programme. The next phase will expand to 500 schools, with teacher training beginning in October. Programme coordinators recommend monthly refresher sessions and a dedicated digital safety contact in each school.'

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
    if (draft.trim()) {
      onAdd(draft.trim())
      setDraft('')
    }
  }
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="step-number">01</span>
          <div>
            <h2 className="text-[14px] tracking-[-.02em]">Add your source</h2>
            <p className="mt-0.5 text-[13px] text-text-1">
              Every great output starts with a little input.
            </p>
          </div>
        </div>
        {!prompt.trim() && (
          <button
            type="button"
            onClick={() => onPromptChange(SAMPLE)}
            className="rounded px-1 py-1 text-[13px] font-medium text-accent hover:underline"
          >
            Try a sample
          </button>
        )}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-2">
          <UploadButton onUploaded={onAdd} />
          <details>
            <summary className="text-[13px] text-text-1 hover:text-accent">
              Use a file path on this machine
            </summary>
            <div className="mt-2 flex gap-1.5">
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    submit()
                  }
                }}
                placeholder="data/samples/report.pdf"
                aria-label="Source path"
                className="min-w-0 flex-1 rounded-lg border border-border bg-bg-1 px-2 py-2 text-[14px] placeholder:text-text-2"
              />
              <button
                type="button"
                onClick={submit}
                disabled={!draft.trim()}
                aria-label="Add source path"
                className="rounded-lg border border-border px-2 text-accent disabled:opacity-40"
              >
                <Plus className="size-4" />
              </button>
            </div>
          </details>
        </div>
        <div className="flex min-h-[176px] flex-col overflow-hidden rounded-xl border border-border bg-bg-1 focus-within:border-accent">
          <label
            htmlFor="prompt"
            className="flex items-center gap-1.5 px-3 pt-3 text-[13px] font-medium text-text-1"
          >
            <FileText className="size-3" /> OR PASTE YOUR TEXT
          </label>
          <textarea
            id="prompt"
            value={prompt}
            onChange={(e) => onPromptChange(e.target.value)}
            placeholder={
              'An article, a report, a thought worth sharing…\n\nPaste your source material or describe what you have in mind.'
            }
            className="min-h-[112px] flex-1 resize-y bg-transparent px-3 py-2 text-[14px] leading-[1.8] text-text-0 placeholder:text-text-2 focus:outline-none"
          />
          <div className="flex justify-between border-t border-border/60 px-3 py-1.5 text-[12px] text-text-1">
            <span>Text & ideas</span>
            <span className="tabular">
              {prompt.trim() ? prompt.trim().split(/\s+/).length : 0} words
            </span>
          </div>
        </div>
      </div>
      {files.length > 0 && (
        <ul className="mt-3 max-h-40 space-y-1.5 overflow-y-auto">
          {files.map((source, index) => {
            const path = source.path ?? ''
            const ext = path.split('.').pop()?.toLowerCase() ?? ''
            const Icon = ['png', 'jpg', 'jpeg'].includes(ext)
              ? Image
              : ['mp4', 'mov', 'mkv'].includes(ext)
                ? FileVideo
                : ['wav', 'mp3', 'm4a'].includes(ext)
                  ? FileAudio
                  : FileText
            return (
              <li
                key={`${path}-${index}`}
                className="flex items-center gap-2 rounded-lg border border-border bg-bg-0 px-3 py-2"
              >
                <Icon className="size-4 shrink-0 text-accent" />
                <span className="min-w-0 flex-1 truncate text-[14px]">
                  {path.split('/').pop()}
                </span>
                <span className="format-tag">{ext || 'file'}</span>
                <button
                  type="button"
                  onClick={() => onRemove(sources.indexOf(source))}
                  aria-label={`Remove ${path}`}
                  className="rounded p-1 text-text-1 hover:bg-danger/10 hover:text-danger"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </li>
            )
          })}
        </ul>
      )}
      <p className="mt-3 flex items-center gap-1.5 text-[12px] text-text-1">
        <LockKeyhole className="size-2.5" /> Files are stored locally and never
        sent to a cloud service.
      </p>
    </div>
  )
}
