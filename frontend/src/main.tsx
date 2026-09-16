import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { App } from './App'
import './index.css'
import { initializeAppearance } from './store/appearance'

initializeAppearance()

// Retry once: the backend is local, so a failing request is a real failure, not
// a flaky network. Nothing here reaches beyond this origin.
//
// networkMode: 'always' on both queries and mutations. TanStack Query's default
// ('online') pauses every request whenever the browser's navigator.onLine flips
// false — which it does the moment Wi-Fi is switched off, even though this app's
// entire backend is loopback-only and unaffected by that. Left at the default,
// air-gapped operation (the whole point of this project) hangs every fetch and
// mutation, including "Create", indefinitely as soon as the network radio is off.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 5_000, networkMode: 'always' },
    mutations: { networkMode: 'always' },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
