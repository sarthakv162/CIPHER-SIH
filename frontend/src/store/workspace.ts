import { create } from 'zustand'
import type { ArtefactType, GenerationParams, SourceInput } from '@/lib/api'
import { DEFAULT_PARAMS } from '@/lib/params'

interface WorkspaceState {
  sources: SourceInput[]
  prompt: string
  selected: ArtefactType[]
  params: GenerationParams
  addFile: (path: string) => void
  removeSource: (index: number) => void
  setPrompt: (value: string) => void
  toggle: (type: ArtefactType) => void
  setParam: <K extends keyof GenerationParams>(key: K, value: GenerationParams[K]) => void
  reset: () => void
}

/** UI-only state for composing a transform. Server state lives in TanStack Query. */
export const useWorkspace = create<WorkspaceState>((set) => ({
  sources: [],
  prompt: '',
  selected: ['executive_summary'],
  params: DEFAULT_PARAMS,

  addFile: (path) =>
    set((state) =>
      state.sources.some((s) => s.path === path)
        ? state
        : { sources: [...state.sources, { kind: 'file', path }] },
    ),

  removeSource: (index) =>
    set((state) => ({ sources: state.sources.filter((_, i) => i !== index) })),

  setPrompt: (prompt) => set({ prompt }),

  toggle: (type) =>
    set((state) => ({
      selected: state.selected.includes(type)
        ? state.selected.filter((t) => t !== type)
        : [...state.selected, type],
    })),

  setParam: (key, value) => set((state) => ({ params: { ...state.params, [key]: value } })),

  reset: () => set({ sources: [], prompt: '', selected: ['executive_summary'] }),
}))

/** The request body, assembled exactly as `TransformRequest` expects it. */
export function buildRequest(state: WorkspaceState) {
  const sources: SourceInput[] = [...state.sources]
  if (state.prompt.trim()) sources.push({ kind: 'text', text: state.prompt.trim() })
  return { sources, output_types: state.selected, params: state.params }
}
