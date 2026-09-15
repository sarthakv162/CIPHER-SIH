import { create } from 'zustand'

export const PALETTES = [
  { id: 'aurora', label: 'Aurora', description: 'Mint & lime', colors: ['#70e1cc', '#c3eb91'] },
  { id: 'iris', label: 'Iris', description: 'Violet & rose', colors: ['#b8a1ff', '#efa6cf'] },
  { id: 'ocean', label: 'Ocean', description: 'Blue & cyan', colors: ['#7abaff', '#7ce2ed'] },
  { id: 'ember', label: 'Ember', description: 'Apricot & gold', colors: ['#ffb28c', '#f2cf76'] },
] as const
export type Palette = (typeof PALETTES)[number]['id']
export type Mode = 'light' | 'dark' | 'system'
type Preferences = { mode: Mode; palette: Palette; effects: boolean }
const KEY = 'rupantar:appearance'
const defaults: Preferences = { mode: 'dark', palette: 'aurora', effects: true }

function readPreferences(): Preferences {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || '{}')
    return {
      mode: ['light', 'dark', 'system'].includes(saved?.mode) ? saved.mode : defaults.mode,
      palette: PALETTES.some((p) => p.id === saved?.palette) ? saved.palette : defaults.palette,
      effects: typeof saved?.effects === 'boolean' ? saved.effects : defaults.effects,
    }
  } catch { return defaults }
}

export const useAppearance = create<Preferences & {
  setMode: (mode: Mode) => void
  setPalette: (palette: Palette) => void
  setEffects: (effects: boolean) => void
}>(set => ({
  ...readPreferences(),
  setMode: mode => set({ mode }),
  setPalette: palette => set({ palette }),
  setEffects: effects => set({ effects }),
}))

/** Apply before React mounts; all theme assets and preferences stay local. */
export function initializeAppearance() {
  const system = window.matchMedia('(prefers-color-scheme: dark)')
  const apply = () => {
    const { mode, palette, effects } = useAppearance.getState()
    const resolved = mode === 'system' ? (system.matches ? 'dark' : 'light') : mode
    document.documentElement.dataset.mode = resolved
    document.documentElement.dataset.palette = palette
    document.documentElement.dataset.effects = effects ? 'on' : 'off'
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', resolved === 'dark' ? '#15181d' : '#f3f5f3')
  }
  apply()
  system.addEventListener('change', apply)
  useAppearance.subscribe(({ mode, palette, effects }) => {
    apply()
    try { localStorage.setItem(KEY, JSON.stringify({ mode, palette, effects })) } catch { /* In-memory themes still work. */ }
  })
}
