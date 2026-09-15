import {
  FileText,
  Image,
  type LucideIcon,
  MessageSquare,
  Share2,
  Presentation,
  ShieldAlert,
  Video,
} from 'lucide-react'
import type { ArtefactType } from './api'

export const CATEGORIES = [
  { id: 'all', label: 'All formats' },
  { id: 'documents', label: 'Documents' },
  { id: 'social', label: 'Social' },
  { id: 'visual', label: 'Visual & video' },
] as const
export type ArtefactCategory = (typeof CATEGORIES)[number]['id']

export interface ArtefactMeta {
  type: ArtefactType
  label: string
  description: string
  formats: string[]
  /** Measured wall seconds on the reference M4 Air — see MEMORY.md §8, the
   *  7-artefact run at ~14.5 tok/s. Not a guess, and not a round number. */
  seconds: number
  icon: LucideIcon
  category: Exclude<ArtefactCategory, 'all'>
}

export const ARTEFACTS: ArtefactMeta[] = [
  {
    type: 'executive_summary',
    label: 'Executive summary',
    description: 'A decision-maker’s one-page read of the source.',
    formats: ['md', 'docx'],
    seconds: 40,
    icon: FileText,
    category: 'documents',
  },
  {
    type: 'advisory',
    label: 'Advisory',
    description: 'Severity, indicators of compromise, and prioritised actions.',
    formats: ['md', 'docx', 'pdf'],
    seconds: 47,
    icon: ShieldAlert,
    category: 'documents',
  },
  {
    type: 'linkedin_post',
    label: 'LinkedIn post',
    description: 'Hook, body, hashtags and a call to action.',
    formats: ['md'],
    seconds: 31,
    icon: Share2,
    category: 'social',
  },
  {
    type: 'x_thread',
    label: 'X thread',
    description: 'Three to eight posts with a thread hook.',
    formats: ['md'],
    seconds: 24,
    icon: MessageSquare,
    category: 'social',
  },
  {
    type: 'presentation',
    label: 'Presentation',
    description: 'Five to twelve slides with speaker notes.',
    formats: ['md', 'pptx'],
    seconds: 55,
    icon: Presentation,
    category: 'visual',
  },
  {
    type: 'infographic_spec',
    label: 'Infographic',
    description: 'Layout, stat blocks and copy, rendered to SVG.',
    formats: ['md', 'svg'],
    seconds: 32,
    icon: Image,
    category: 'visual',
  },
  {
    type: 'video_package',
    label: 'Video package',
    description: 'Scene plan, narration and subtitles, assembled to MP4.',
    formats: ['md', 'srt', 'mp4'],
    seconds: 75,
    icon: Video,
    category: 'visual',
  },
]

export const ARTEFACT_BY_TYPE = new Map(ARTEFACTS.map((a) => [a.type, a]))

/** Brain warm-up before the first artefact — measured cold boot is ~2.5s, but the
 *  first agent also pays the full dossier prompt-eval. */
const WARMUP_SECONDS = 12

/** Estimated wall time for a selection, on the reference hardware. */
export function estimateSeconds(selected: ArtefactType[]): number {
  if (selected.length === 0) return 0
  const generation = selected.reduce(
    (total, type) => total + (ARTEFACT_BY_TYPE.get(type)?.seconds ?? 40),
    0,
  )
  return generation + WARMUP_SECONDS
}
