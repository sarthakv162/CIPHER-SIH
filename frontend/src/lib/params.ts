import type { Audience, Detail, GenerationParams, Objective, Style, Tone } from './api'

/**
 * Segmented-control options. Every value here is an enum member from
 * `core/schemas.py` — the backend rejects anything else, so these lists must
 * stay in step with `GenerationParams`.
 */

interface Option<T> {
  value: T
  label: string
}

export const AUDIENCES: Option<Audience>[] = [
  { value: 'general_public', label: 'Public' },
  { value: 'technical', label: 'Technical' },
  { value: 'executive', label: 'Executive' },
  { value: 'policy_maker', label: 'Policy' },
  { value: 'media', label: 'Media' },
  { value: 'internal', label: 'Internal' },
]

export const TONES: Option<Tone>[] = [
  { value: 'neutral', label: 'Neutral' },
  { value: 'formal', label: 'Formal' },
  { value: 'urgent', label: 'Urgent' },
  { value: 'reassuring', label: 'Reassuring' },
  { value: 'promotional', label: 'Promotional' },
  { value: 'analytical', label: 'Analytical' },
]

export const DETAILS: Option<Detail>[] = [
  { value: 'brief', label: 'Brief' },
  { value: 'standard', label: 'Standard' },
  { value: 'deep', label: 'Deep' },
]

export const OBJECTIVES: Option<Objective>[] = [
  { value: 'inform', label: 'Inform' },
  { value: 'warn', label: 'Warn' },
  { value: 'persuade', label: 'Persuade' },
  { value: 'instruct', label: 'Instruct' },
  { value: 'announce', label: 'Announce' },
  { value: 'summarise', label: 'Summarise' },
]

export const STYLES: Option<Style>[] = [
  { value: 'plain', label: 'Plain' },
  { value: 'narrative', label: 'Narrative' },
  { value: 'bulleted', label: 'Bulleted' },
  { value: 'technical', label: 'Technical' },
]

/** ASR and TTS are English-only; the brain honours other languages best-effort. */
export const LANGUAGES: Option<string>[] = [
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'हिन्दी' },
]

export const DEFAULT_PARAMS: GenerationParams = {
  audience: 'general_public',
  tone: 'neutral',
  language: 'en',
  detail: 'standard',
  objective: 'inform',
  style: 'plain',
}
