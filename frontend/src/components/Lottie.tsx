import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'framer-motion'

/**
 * Vendored Lottie, used in exactly two places: the empty workspace and a landed
 * verification.
 *
 * It drives `lottie-web`'s **light** ESM build directly rather than going through
 * `lottie-react`. Two reasons, both measured: the `lottie-react` barrel has no
 * subpath exports, so importing it pulled every player variant into a 735 kB
 * chunk; and the full and svg builds contain a direct `eval` (lottie's expression
 * engine) which has no business in an air-gapped government console. The light
 * build is 164 kB with **zero** eval, and these marks are plain shapes.
 *
 * The player is a lazy chunk, so no screen pays for it until one renders. It plays
 * **once** and is then destroyed: the empty workspace is a working screen, and a
 * loop there would be a permanent render loop behind one, which the CPU budget
 * forbids. Under `prefers-reduced-motion` the chunk is never fetched at all.
 */

interface LottieMarkProps {
  /** Vendored JSON imported from `src/assets/lottie`. Never a URL. */
  animationData: object
  size?: number
  className?: string
  /** Static stand-in: drawn under reduced motion, while loading, and once played. */
  fallback: React.ReactNode
}

export function LottieMark({
  animationData,
  size = 96,
  className,
  fallback,
}: LottieMarkProps) {
  const reduced = useReducedMotion()
  const host = useRef<HTMLDivElement | null>(null)
  const [played, setPlayed] = useState(false)

  useEffect(() => {
    if (reduced || played) return
    const container = host.current
    if (!container) return

    let destroy: (() => void) | undefined
    let cancelled = false

    void import('lottie-web/build/player/esm/lottie_light.min.js').then((mod) => {
      if (cancelled || !container.isConnected) return
      const lottie = (mod.default ?? mod) as {
        loadAnimation: (options: Record<string, unknown>) => {
          addEventListener: (name: string, handler: () => void) => void
          destroy: () => void
        }
      }
      const animation = lottie.loadAnimation({
        container,
        renderer: 'svg',
        loop: false,
        autoplay: true,
        animationData,
      })
      // Once it has played, drop the player entirely — nothing should stay mounted
      // holding a renderer it no longer needs.
      animation.addEventListener('complete', () => setPlayed(true))
      destroy = () => animation.destroy()
    })

    return () => {
      cancelled = true
      destroy?.()
    }
  }, [animationData, reduced, played])

  if (reduced || played) {
    return (
      <div className={className} style={{ width: size, height: size }}>
        {fallback}
      </div>
    )
  }

  return (
    <div
      ref={host}
      className={className}
      style={{ width: size, height: size }}
      aria-hidden="true"
    />
  )
}
