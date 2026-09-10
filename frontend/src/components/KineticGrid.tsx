import { useEffect, useRef } from 'react'

/**
 * The entry screen's kinetic grid. This is the only render loop in the console.
 *
 * It runs beside inference on a fanless 16 GB machine, so the loop is bounded on
 * every side it can be: it exists only on this route, it is capped well below
 * display refresh, it stops entirely when the tab is hidden or the canvas leaves
 * the viewport, and under `prefers-reduced-motion` it paints one static frame and
 * never schedules a second.
 */

/** Deliberately below 60: the motion is a slow drift, and the model needs the CPU. */
const TARGET_FPS = 24
const FRAME_MS = 1000 / TARGET_FPS
const SPACING = 34
const DOT = 1.1

interface Point {
  x: number
  y: number
  phase: number
}

export function KineticGrid({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const context = canvas.getContext('2d')
    if (!context) return

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let points: Point[] = []
    let width = 0
    let height = 0
    let frame = 0
    let last = 0
    let running = false

    const accent = getComputedStyle(document.documentElement)
      .getPropertyValue('--color-accent')
      .trim()

    const layout = () => {
      const rect = canvas.getBoundingClientRect()
      // Cap the backing store at 2x: a 3x retina buffer costs fill rate for no
      // visible gain on 1px dots.
      const scale = Math.min(window.devicePixelRatio || 1, 2)
      width = rect.width
      height = rect.height
      canvas.width = Math.floor(width * scale)
      canvas.height = Math.floor(height * scale)
      context.setTransform(scale, 0, 0, scale, 0, 0)

      points = []
      for (let x = SPACING / 2; x < width; x += SPACING) {
        for (let y = SPACING / 2; y < height; y += SPACING) {
          points.push({ x, y, phase: (x * 0.014 + y * 0.021) % (Math.PI * 2) })
        }
      }
    }

    const draw = (time: number) => {
      context.clearRect(0, 0, width, height)
      for (const point of points) {
        // A slow travelling wave: brightness and size follow the same phase, so
        // the grid reads as breathing rather than twinkling.
        const wave = reduced ? 0.35 : (Math.sin(point.phase + time * 0.0006) + 1) / 2
        const alpha = 0.08 + wave * 0.32
        const radius = DOT * (0.75 + wave * 0.75)
        context.beginPath()
        context.fillStyle = accent
        context.globalAlpha = alpha
        context.arc(point.x, point.y, radius, 0, Math.PI * 2)
        context.fill()
      }
      context.globalAlpha = 1
    }

    const tick = (time: number) => {
      if (!running) return
      if (time - last >= FRAME_MS) {
        last = time
        draw(time)
      }
      frame = window.requestAnimationFrame(tick)
    }

    const start = () => {
      if (running || reduced) return
      running = true
      frame = window.requestAnimationFrame(tick)
    }

    const stop = () => {
      running = false
      window.cancelAnimationFrame(frame)
    }

    layout()
    draw(0)

    if (reduced) {
      // One static frame, no loop scheduled at all.
      const onResize = () => {
        layout()
        draw(0)
      }
      window.addEventListener('resize', onResize)
      return () => window.removeEventListener('resize', onResize)
    }

    // Off-screen or background tab: no reason to burn a core.
    const observer = new IntersectionObserver(
      ([entry]) => (entry?.isIntersecting ? start() : stop()),
      { threshold: 0 },
    )
    observer.observe(canvas)

    const onVisibility = () => {
      if (document.hidden) stop()
      else if (canvas.isConnected) start()
    }
    const onResize = () => {
      layout()
      draw(performance.now())
    }

    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('resize', onResize)

    return () => {
      stop()
      observer.disconnect()
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className={className}
      aria-hidden="true"
      // The grid carries no information; it is texture behind the product name.
      role="presentation"
    />
  )
}
