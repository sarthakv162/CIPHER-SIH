import { useEffect } from 'react'
import { Menu } from 'lucide-react'
import { EgressPill } from '@/components/EgressPill'
import { Appearance } from '@/components/Appearance'
import { useOpenNavigation } from './AppShell'

export function Header({
  title,
  subtitle,
}: {
  title: string
  subtitle?: string
}) {
  const openNavigation = useOpenNavigation()
  useEffect(() => {
    document.title = `${title} · CIPHER`
  }, [title])
  return (
    <header className="studio-header z-20 flex h-[72px] shrink-0 items-center justify-between gap-3 px-4 md:px-7">
      <div className="flex min-w-0 items-center gap-2">
        <button
          type="button"
          onClick={openNavigation}
          aria-label="Open navigation"
          className="icon-button lg:hidden"
        >
          <Menu className="size-5" />
        </button>
        <span className="hidden text-[13px] text-text-1 xl:block">Workspace <span className="mx-2 opacity-40">/</span></span>
        <span className="truncate text-[14px] font-medium tracking-[-.02em]">
          {title}
        </span>
        {subtitle && (
          <span className="ml-1 hidden rounded-md bg-bg-2 px-2 py-0.5 text-[14px] text-text-1 sm:block">
            {subtitle}
          </span>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2 md:gap-5"><EgressPill /><Appearance /></div>
    </header>
  )
}
