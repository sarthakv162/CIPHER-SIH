import { Header } from '@/components/layout/Header'

interface PlaceholderProps {
  title: string
  subtitle: string
  note: string
}

/** Structural stand-in for a screen that lands in a later sub-phase. */
export function Placeholder({ title, subtitle, note }: PlaceholderProps) {
  return (
    <>
      <Header title={title} subtitle={subtitle} />
      <div className="flex flex-1 items-center justify-center p-6">
        <p className="max-w-[52ch] text-center text-[16px] leading-relaxed text-text-1">
          {note}
        </p>
      </div>
    </>
  )
}
