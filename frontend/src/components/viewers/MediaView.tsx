import { useState } from 'react'
import { cn, duration } from '@/lib/utils'

interface Slide {
  layout: string
  title: string
  bullets: string[]
  speaker_notes: string
}

/** Thumbnail rail, large preview, speaker notes beneath — the way a deck is
 *  actually reviewed, rather than as a flat list of slide objects. */
export function PresentationView({
  artefact,
  template = 'ntro-formal',
}: {
  artefact: { title: string; slides: Slide[]; deck_summary: string }
  template?: string
}) {
  const [active, setActive] = useState(0)
  const slide = artefact.slides[active]
  if (!slide) return null

  const templateLabel =
    template === 'executive'
      ? 'Executive Briefing'
      : template === 'technical'
        ? 'Technical Deck'
        : 'NTRO Formal Deck'

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 md:flex-row">
      <ol
        aria-label="Presentation slides"
        className="flex shrink-0 gap-1.5 overflow-x-auto md:w-[132px] md:flex-col md:overflow-y-auto"
      >
        {artefact.slides.map((item, index) => (
          <li key={index} className="w-[132px] shrink-0 md:w-auto">
            <button
              type="button"
              onClick={() => setActive(index)}
              aria-current={index === active}
              className={cn(
                'w-full rounded-[8px] border p-2 text-left transition-colors duration-150',
                index === active
                  ? 'border-accent/60 bg-bg-2'
                  : 'border-border bg-bg-2 hover:border-border-2 hover:bg-bg-3',
              )}
            >
              <span className="tabular text-[14px] text-text-1">
                {index + 1}
              </span>
              <span className="mt-0.5 line-clamp-2 block text-[14px] leading-snug text-text-0">
                {item.title}
              </span>
            </button>
          </li>
        ))}
      </ol>

      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="surface-card flex aspect-video min-h-0 flex-col justify-center gap-3 p-6">
          <div className="flex items-center justify-between">
            <span className="section-label">
              {slide.layout.replace('_', ' ')}
            </span>
            <span className="rounded-[4px] border border-accent/25 bg-accent/10 px-2 py-0.5 text-[11px] font-semibold uppercase text-accent">
              {templateLabel}
            </span>
          </div>
          <h2 className="text-[26px] leading-tight text-text-0">
            {slide.title}
          </h2>
          <ul className="flex flex-col gap-1.5">
            {slide.bullets.map((bullet, index) => (
              <li
                key={index}
                className="flex gap-2 text-[16px] leading-relaxed text-text-1"
              >
                <span className="text-accent">—</span>
                {bullet}
              </li>
            ))}
          </ul>
        </div>

        <div className="surface-card p-3">
          <h3 className="section-label">Speaker notes</h3>
          <p className="mt-1.5 text-[15px] leading-relaxed text-text-1">
            {slide.speaker_notes}
          </p>
        </div>
      </div>
    </div>
  )
}

/** The rendered SVG at its own size. Loaded from the job's file route, which is
 *  same-origin — an <img> here never reaches off this machine. */
export function InfographicView({
  src,
  headline,
  subhead,
}: {
  src: string | null
  headline: string
  subhead: string
}) {
  return (
    <div className="flex flex-col gap-3">
      <div>
        <h2 className="text-[20px] leading-tight text-text-0">{headline}</h2>
        <p className="mt-1 text-[16px] text-text-1">{subhead}</p>
      </div>
      {src ? (
        <div className="surface-card flex justify-center overflow-auto p-4">
          <img src={src} alt={headline} className="max-w-full" />
        </div>
      ) : (
        <p className="rounded-[8px] border border-border bg-bg-0 px-3 py-4 text-center text-[15px] text-text-1">
          No SVG was rendered for this artefact.
        </p>
      )}
    </div>
  )
}

export interface Scene {
  duration_seconds: number
  scene_description: string
  on_screen_text: string
  narration: string
}

/** Player plus the scene plan as a filmstrip. Panels are stills the renderer
 *  produced; when the mp4 degraded to storyboard-only there is simply no player. */
export function VideoView({
  src,
  scenes,
  logline,
  panels,
}: {
  src: string | null
  scenes: Scene[]
  logline: string
  panels: string[]
}) {
  const [active, setActive] = useState(0)

  return (
    <div className="flex flex-col gap-3">
      <p className="text-[16px] leading-relaxed text-text-1">{logline}</p>

      {src ? (
        <video
          controls
          preload="metadata"
          className="surface-card w-full"
          src={src}
        />
      ) : (
        <p className="rounded-[8px] border border-warn/25 bg-warn/10 px-3 py-2.5 text-[15px] leading-snug text-warn">
          No MP4 was assembled — the renderer degraded to a storyboard. The
          scene plan below is still complete.
        </p>
      )}

      {panels.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {panels.map((panel, index) => (
            <button
              key={panel}
              type="button"
              onClick={() => setActive(index)}
              className={cn(
                'shrink-0 overflow-hidden rounded-[8px] border transition-colors duration-150',
                index === active
                  ? 'border-accent/60'
                  : 'border-border hover:border-border-2',
              )}
            >
              <img
                src={panel}
                alt={`Panel ${index + 1}`}
                className="h-20 w-auto"
              />
            </button>
          ))}
        </div>
      )}

      <ol className="flex flex-col gap-1.5">
        {scenes.map((scene, index) => (
          <li
            key={index}
            className={cn(
              'rounded-[8px] border p-3',
              index === active
                ? 'border-accent/40 bg-bg-2'
                : 'border-border bg-bg-2',
            )}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="tabular text-[14px] text-text-1">
                Scene {index + 1}
              </span>
              <span className="tabular text-[14px] text-text-1">
                {duration(scene.duration_seconds)}
              </span>
            </div>
            <p className="mt-1 text-[16px] leading-snug text-text-0">
              {scene.on_screen_text}
            </p>
            <p className="mt-1 text-[15px] leading-relaxed text-text-1">
              {scene.narration}
            </p>
          </li>
        ))}
      </ol>
    </div>
  )
}
