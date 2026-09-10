import { NavLink } from 'react-router-dom'
import { ArrowLeftRight, FileStack, type LucideIcon, Plus, ShieldCheck } from 'lucide-react'
import { RecentTransforms } from '@/components/RecentTransforms'
import { cn } from '@/lib/utils'

interface NavItemProps {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
}

function NavItem({ to, label, icon: Icon, end }: NavItemProps) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          'group flex items-center gap-2.5 rounded-[8px] px-2.5 py-2 text-[13px] transition-colors',
          'duration-150 ease-[cubic-bezier(0.2,0,0,1)]',
          isActive
            ? 'bg-bg-3 text-text-0'
            : 'text-text-1 hover:bg-bg-2 hover:text-text-0',
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon
            className={cn('size-4 shrink-0', isActive ? 'text-accent' : 'text-text-1')}
            strokeWidth={1.75}
          />
          <span className="truncate">{label}</span>
        </>
      )}
    </NavLink>
  )
}

/** Left rail: new transform, recent work, then the standing tools at the bottom. */
export function Sidebar() {
  return (
    <aside className="flex w-[232px] shrink-0 flex-col gap-5 px-3 py-4">
      <div className="flex items-center gap-2.5 px-2.5 pt-1">
        <div className="relative flex size-7 items-center justify-center rounded-[8px] bg-bg-3 ring-1 ring-border">
          <span className="text-[13px] leading-none text-accent">◈</span>
        </div>
        <div className="min-w-0">
          <div className="truncate text-[13px] leading-tight text-text-0">Rupantar</div>
          <div className="truncate text-[11px] leading-tight text-text-1">Operator console</div>
        </div>
      </div>

      <NavLink
        to="/workspace"
        className={cn(
          'mx-0.5 flex items-center gap-2 rounded-[8px] border border-border bg-bg-2 px-2.5 py-2',
          'text-[13px] text-text-0 transition-colors duration-150 hover:border-border-2 hover:bg-bg-3',
        )}
      >
        <Plus className="size-4 text-accent" strokeWidth={1.75} />
        New transform
      </NavLink>

      <nav className="flex min-h-0 flex-1 flex-col gap-1.5">
        <div className="section-label px-2.5">Recent</div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <RecentTransforms />
        </div>
      </nav>

      <nav className="flex flex-col gap-0.5 border-t border-border pt-3">
        <NavItem to="/artefacts" label="Artefacts" icon={FileStack} />
        <NavItem to="/parivartan" label="Parivartan" icon={ArrowLeftRight} />
        <NavItem to="/system" label="System" icon={ShieldCheck} />
      </nav>
    </aside>
  )
}
