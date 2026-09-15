import { NavLink, Link, useNavigate, useLocation } from 'react-router-dom'
import {
  ArrowLeftRight,
  FileStack,
  PanelLeft,
  Settings2,
  SquarePen,
  FileText,
  MessageSquare,
  Shapes,
} from 'lucide-react'
import { RecentTransforms } from '@/components/RecentTransforms'
import { BrandMark } from '@/components/Brand'
import { useWorkspace } from '@/store/workspace'
import { cn } from '@/lib/utils'

export function Sidebar({
  onNavigate,
  collapsed = false,
  onCollapse,
}: {
  onNavigate?: () => void
  collapsed?: boolean
  onCollapse?: () => void
}) {
  const navigate = useNavigate()
  const location = useLocation()
  const category = new URLSearchParams(location.search).get('category')
  const reset = useWorkspace((s) => s.reset)
  return (
    <aside
      className={cn('studio-sidebar', collapsed && 'is-collapsed')}
      onClick={(e) => {
        if ((e.target as HTMLElement).closest('a')) onNavigate?.()
      }}
    >
      <div
        className={cn(
          'mb-6 flex h-10 items-center',
          collapsed ? 'justify-center' : 'justify-between px-1',
        )}
      >
        {!collapsed && (
          <Link
            to="/"
            aria-label="Cipher home"
            className="flex items-center gap-2 text-[17px] font-medium tracking-[-.025em]"
          >
            <span className="brand-symbol"><BrandMark className="!size-6" /></span>
            <span>CIPHER<span className="text-accent">.</span><span className="brand-caption">CREATIVE STUDIO</span></span>
          </Link>
        )}
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            className="icon-button"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <PanelLeft className="size-[19px]" strokeWidth={1.7} />
          </button>
        )}
      </div>
      <nav aria-label="Main navigation" className="w-full space-y-1">
        <button
          type="button"
          onClick={() => {
            reset()
            navigate('/')
            onNavigate?.()
          }}
          className="studio-nav-link new-transform w-full"
          title="New transform"
          aria-label="New transform"
        >
          <SquarePen className="size-[18px] shrink-0" strokeWidth={1.7} />
          {!collapsed && 'New transform'}
        </button>
        {[
          { to: '/artefacts', label: 'Library', icon: FileStack },
          { to: '/parivartan', label: 'Convert files', icon: ArrowLeftRight },
        ].map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            title={label}
            aria-label={label}
            className={({ isActive }) =>
              cn('studio-nav-link', isActive && 'active')
            }
          >
            <Icon className="size-[18px] shrink-0" strokeWidth={1.7} />
            {!collapsed && label}
          </NavLink>
        ))}
      </nav>
      {!collapsed && <div className="sidebar-features">
        <p className="nav-label">Create something</p>
        {[
          { id: 'documents', label: 'Documents', icon: FileText, count: 2 },
          { id: 'social', label: 'Social content', icon: MessageSquare, count: 2 },
          { id: 'visual', label: 'Visuals & video', icon: Shapes, count: 3 },
        ].map(({ id, label, icon: Icon, count }) => <Link key={id} to={`/?category=${id}`} className={cn('studio-nav-link', (location.pathname === '/' || location.pathname === '/workspace') && category === id && 'active')}><Icon className="size-[18px]" strokeWidth={1.6} />{label}<span className="nav-count">{count}</span></Link>)}
      </div>}
      {!collapsed && (
        <div className="mt-8 flex min-h-0 flex-1 flex-col">
          <p className="nav-label">Recent transforms</p>
          <nav
            aria-label="Recent transforms"
            className="min-h-0 overflow-y-auto"
          >
            <RecentTransforms />
          </nav>
        </div>
      )}
      <div
        className={cn(
          'mt-auto w-full pt-5',
          !collapsed && 'border-t border-border',
        )}
      >
        <NavLink
          to="/system"
          className={({ isActive }) =>
            cn('studio-nav-link', isActive && 'active')
          }
          title="System settings"
          aria-label="System settings"
        >
          <Settings2 className="size-[18px] shrink-0" strokeWidth={1.7} />
          {!collapsed && 'System settings'}
        </NavLink>
        {!collapsed && (
          <p className="mt-3 px-3 text-[14px] text-text-1">
            Local workspace · On-device AI
          </p>
        )}
      </div>
    </aside>
  )
}
