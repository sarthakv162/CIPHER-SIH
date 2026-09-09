import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'

/**
 * Page frame: sidebar rail beside a rounded content window, over an ambient
 * accent wash. The wash is a static gradient — no canvas, no rAF — so nothing
 * behind a working screen competes with inference for CPU.
 */
export function AppShell() {
  return (
    <div className="relative flex h-dvh w-full overflow-hidden bg-bg-0">
      <div className="ambient-wash" aria-hidden="true" />
      <div className="ambient-vignette" aria-hidden="true" />
      <div className="relative z-10 flex w-full gap-0 p-2.5">
        <Sidebar />
        <main className="surface-raised relative flex min-w-0 flex-1 flex-col overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
