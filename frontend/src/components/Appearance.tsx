import * as Dialog from '@radix-ui/react-dialog'
import { useSyncExternalStore } from 'react'
import { Check, Monitor, Moon, Palette, Sun, X } from 'lucide-react'
import { PALETTES, useAppearance } from '@/store/appearance'

function subscribeSystemTheme(onChange: () => void) {
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  media.addEventListener('change', onChange)
  return () => media.removeEventListener('change', onChange)
}

export function Appearance() {
  const { mode, palette, effects, setMode, setPalette, setEffects } = useAppearance()
  const systemDark = useSyncExternalStore(subscribeSystemTheme, () => window.matchMedia('(prefers-color-scheme: dark)').matches)
  const isLight = mode === 'light' || (mode === 'system' && !systemDark)
  return (
    <div className="appearance-controls">
      <button
        type="button" className="icon-button mode-toggle"
        aria-label={isLight ? 'Switch to dark mode' : 'Switch to light mode'}
        title={isLight ? 'Switch to dark mode' : 'Switch to light mode'}
        onClick={() => setMode(isLight ? 'dark' : 'light')}
      >
        {isLight ? <Moon className="size-[17px]" /> : <Sun className="size-[17px]" />}
      </button>
      <Dialog.Root>
        <Dialog.Trigger className="icon-button" aria-label="Customize appearance" title="Customize appearance">
          <Palette className="size-[17px]" />
        </Dialog.Trigger>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="settings-dialog appearance-dialog">
            <div className="flex items-center justify-between gap-3">
              <Dialog.Title className="text-[22px] tracking-tight">Make it your space.</Dialog.Title>
              <Dialog.Close className="icon-button" aria-label="Close appearance"><X className="size-5" /></Dialog.Close>
            </div>
            <Dialog.Description className="mt-1 mb-7 text-[14px] text-text-1">A different mood, the same creative possibilities.</Dialog.Description>
            <fieldset>
              <legend className="mb-3 text-[14px] font-medium">Appearance</legend>
              <div className="mode-options">
                {([{ value: 'light', label: 'Light', icon: Sun }, { value: 'dark', label: 'Dark', icon: Moon }, { value: 'system', label: 'System', icon: Monitor }] as const).map(({ value, label, icon: Icon }) => (
                  <button key={value} type="button" aria-pressed={mode === value} onClick={() => setMode(value)}><Icon className="size-4" />{label}</button>
                ))}
              </div>
            </fieldset>
            <fieldset className="mt-7">
              <legend className="mb-3 text-[14px] font-medium">Color palette</legend>
              <div className="palette-options">
                {PALETTES.map(p => (
                  <button key={p.id} type="button" aria-pressed={palette === p.id} onClick={() => setPalette(p.id)} aria-label={`${p.label} palette`}>
                    <span className="palette-swatch" style={{ background: `linear-gradient(125deg, ${p.colors.join(', ')})` }}>{palette === p.id && <Check className="size-5" />}</span>
                    <span className="block text-[14px] font-medium">{p.label}</span>
                    <span className="block text-[12px] text-text-1">{p.description}</span>
                  </button>
                ))}
              </div>
            </fieldset>
            <label className="mt-7 flex items-center justify-between gap-4 border-t border-border pt-5">
              <span><span className="block text-[14px] font-medium">Ambient effects</span><span className="block text-[13px] text-text-1">Animated glow and floating details. Respects reduced motion.</span></span>
              <input type="checkbox" role="switch" aria-label="Ambient effects" checked={effects} onChange={e => setEffects(e.target.checked)} className="effect-switch" />
            </label>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  )
}
