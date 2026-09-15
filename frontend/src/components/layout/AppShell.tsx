import { createContext, useContext, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { Sidebar } from './Sidebar'

const NavigationContext = createContext(() => {})
export const useOpenNavigation = () => useContext(NavigationContext)

export function AppShell() {
  const [open, setOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const { pathname } = useLocation()
  useEffect(() => {
    setOpen(false)
  }, [pathname])
  return (
    <NavigationContext.Provider value={() => setOpen(true)}>
      <div className="studio-frame">
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <div className="hidden lg:flex">
          <Sidebar
            collapsed={collapsed}
            onCollapse={() => setCollapsed((value) => !value)}
          />
        </div>
        <Dialog.Root open={open} onOpenChange={setOpen}>
          <Dialog.Portal>
            <Dialog.Overlay className="dialog-overlay" />
            <Dialog.Content className="mobile-nav" aria-describedby={undefined}>
              <Dialog.Title className="sr-only">Studio navigation</Dialog.Title>
              <Sidebar onNavigate={() => setOpen(false)} />
              <Dialog.Close
                aria-label="Close navigation"
                className="icon-button absolute right-2 top-2"
              >
                <X className="size-4" />
              </Dialog.Close>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
        <main
          id="main-content"
          tabIndex={-1}
          className="studio-main relative flex min-w-0 flex-1 flex-col overflow-hidden focus:outline-none"
        >
          <Outlet />
        </main>
      </div>
    </NavigationContext.Provider>
  )
}
