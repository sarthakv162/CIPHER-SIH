/**
 * Typed client for the Rupantar API.
 *
 * Every shape here mirrors a real backend response — `core/schemas.py`,
 * `core/artefacts.py`, `verify/report.py` and the `api/routes/*` modules. Same
 * origin only: the console is served by the FastAPI process it talks to, so
 * there is no base URL to configure and no cross-origin request to make.
 */

export type ArtefactType =
  | 'executive_summary'
  | 'advisory'
  | 'linkedin_post'
  | 'x_thread'
  | 'presentation'
  | 'infographic_spec'
  | 'video_package'

export type JobStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'

export type Audience =
  | 'general_public'
  | 'technical'
  | 'executive'
  | 'policy_maker'
  | 'media'
  | 'internal'
export type Tone = 'neutral' | 'formal' | 'urgent' | 'reassuring' | 'promotional' | 'analytical'
export type Detail = 'brief' | 'standard' | 'deep'
export type Objective = 'inform' | 'warn' | 'persuade' | 'instruct' | 'announce' | 'summarise'
export type Style = 'plain' | 'narrative' | 'bulleted' | 'technical'

export interface GenerationParams {
  audience: Audience
  tone: Tone
  language: string
  detail: Detail
  objective: Objective
  style: Style
  template: string
}

export interface SourceInput {
  kind: 'text' | 'file'
  text?: string | null
  path?: string | null
}

export interface Job {
  id: string
  transform_id: string
  artefact_type: ArtefactType
  model_key: string
  status: JobStatus
  depends_on: string[]
  error: string | null
  artefact_path: string | null
  created_at: string
  updated_at: string
}

/** Counts folded across every claim and relation in a transform. */
export interface VerificationSummary {
  ok: boolean
  line: string
  total: number
  supported: number
  unsupported: number
  agree: number
  conflict: number
  orphan: number
}

export interface TransformStatus {
  transform_id: string
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'
  jobs: Job[]
  verification: VerificationSummary | null
}

export interface ModelRow {
  key: string
  state: 'NOT_LOADED' | 'LOADING' | 'READY' | 'EVICTING' | 'FAILED'
  pid: number | null
  port: number | null
  rss_mb: number | null
  refcount: number
  loaded_at: string | null
  last_used: string | null
}

export interface HealthReport {
  status: string
  profile: string
  profile_source: string
  platform: string
  python: string
  models_resident: number
}

export interface EgressReport {
  checked_at: string
  clean: boolean
  violations: unknown[]
  scanned_pids: number
}

export interface TemplateRow {
  id: string
  label: string
  description: string
  supports: ArtefactType[]
  thumbnail_url: string | null
}

class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { accept: 'application/json' } })
  if (!response.ok) {
    throw new ApiError(`${path} returned ${response.status}`, response.status)
  }
  return (await response.json()) as T
}

export const api = {
  health: () => get<HealthReport>('/health'),
  egress: () => get<EgressReport>('/health/egress'),
  models: () => get<ModelRow[]>('/models/status'),
  templates: () => get<TemplateRow[]>('/templates'),
  transform: (id: string) => get<TransformStatus>(`/transforms/${id}`),
}

export { ApiError }
