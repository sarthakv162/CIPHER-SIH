import { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Loader2, Upload } from 'lucide-react'
import { cn } from '@/lib/utils'

const EASE = [0.2, 0, 0, 1] as const

interface UploadButtonProps {
  /** Called with the server-side path once the file is on disk. */
  onUploaded: (path: string) => void
}

/**
 * The primary way a source gets into the engine.
 *
 * The bytes go to `POST /sources`, which writes them under `data/uploads/` and
 * returns the path — the engine reads sources from the filesystem, and a browser
 * never exposes a real one. Same-origin, so nothing leaves this machine.
 */
export function UploadButton({ onUploaded }: UploadButtonProps) {
  const input = useRef<HTMLInputElement | null>(null)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<string | null>(null)

  const send = async (file: File) => {
    setBusy(true)
    setError(null)
    setProgress(file.name)
    try {
      const response = await fetch(`/sources?filename=${encodeURIComponent(file.name)}`, {
        method: 'POST',
        headers: { 'content-type': 'application/octet-stream' },
        body: file,
      })
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null
        throw new Error(body?.detail ?? `Upload failed (${response.status})`)
      }
      const result = (await response.json()) as { path: string }
      onUploaded(result.path)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setBusy(false)
      setProgress(null)
    }
  }

  const take = (files: FileList | null) => {
    const file = files?.[0]
    if (file) void send(file)
  }

  return (
    <div className="flex flex-col gap-2">
      <motion.button
        type="button"
        disabled={busy}
        onClick={() => input.current?.click()}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          take(event.dataTransfer.files)
        }}
        whileHover={busy ? undefined : { scale: 1.012 }}
        whileTap={busy ? undefined : { scale: 0.985 }}
        transition={{ duration: 0.15, ease: EASE }}
        className={cn(
          'group relative flex w-full flex-col items-center justify-center gap-2 overflow-hidden',
          'rounded-[12px] border border-dashed px-4 py-7 transition-colors duration-200',
          dragging
            ? 'border-accent bg-accent/12'
            : 'border-border-2 bg-bg-0 hover:border-accent/60 hover:bg-accent/6',
          busy && 'cursor-progress opacity-80',
        )}
      >
        {/* Sheen that sweeps once on hover — motion as affordance, not decoration. */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-accent/10 to-transparent transition-transform duration-700 ease-[cubic-bezier(0.2,0,0,1)] group-hover:translate-x-full"
        />

        <motion.span
          animate={dragging ? { y: -3 } : { y: 0 }}
          transition={{ duration: 0.2, ease: EASE }}
          className={cn(
            'flex size-11 items-center justify-center rounded-full border transition-colors duration-200',
            dragging
              ? 'border-accent/50 bg-accent/20'
              : 'border-border bg-bg-2 group-hover:border-accent/40 group-hover:bg-accent/12',
          )}
        >
          {busy ? (
            <Loader2 className="size-5 animate-spin text-accent" strokeWidth={1.75} />
          ) : (
            <Upload className="size-5 text-accent" strokeWidth={1.75} />
          )}
        </motion.span>

        <span className="text-[16px] text-text-0">
          {busy ? `Uploading ${progress}…` : dragging ? 'Drop to upload' : 'Upload a source'}
        </span>
        <span className="text-[14px] leading-snug text-text-1">
          Drag a file here, or click to browse — pdf, docx, image, audio, video
        </span>
      </motion.button>

      <input
        ref={input}
        type="file"
        hidden
        onChange={(event) => {
          take(event.target.files)
          event.target.value = ''
        }}
      />

      <AnimatePresence>
        {error && (
          <motion.p
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15, ease: EASE }}
            className="flex items-start gap-1.5 text-[14px] leading-snug text-danger"
          >
            <AlertTriangle className="mt-px size-3 shrink-0" strokeWidth={1.75} />
            {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}
