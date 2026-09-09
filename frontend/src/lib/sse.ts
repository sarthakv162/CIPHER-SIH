import { useEffect, useReducer } from 'react'
import type { ArtefactType, JobStatus, ModelRow } from './api'

/** Frame shapes emitted by `GET /transforms/{id}/events` — see `orchestrator/progress.py`. */

export interface JobFrame {
  job_id: string
  transform_id: string
  artefact_type: ArtefactType
  model_key: string
  status: JobStatus
  updated_at: string
  artefact_path: string | null
  error: string | null
}

export interface ModelFrame {
  kind: 'LOAD_START' | 'LOAD_READY' | 'EVICT_START' | 'EVICT_DONE' | 'PROCESS_DIED'
  model_key: string
  pid: number | null
  rss_mb: number | null
  ts: string
  detail: Record<string, unknown>
}

export interface VerificationFrame {
  transform_id: string
  ok: boolean
  line: string
  disclaimer: string
  summary: {
    total: number
    supported: number
    unsupported: number
    agree: number
    conflict: number
    orphan: number
  }
  warnings: string[]
  conflicts: { kind: string; claim_ids: string[]; subject: string; detail: string }[]
}

export interface StreamState {
  status: 'connecting' | 'live' | 'closed' | 'error'
  transformStatus: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'
  jobs: Map<string, JobFrame>
  jobOrder: string[]
  models: ModelRow[]
  /** Model events in arrival order — the swap timeline reads this directly. */
  modelEvents: ModelFrame[]
  /** Streamed generation text per job, capped so a long run cannot grow without bound. */
  tokens: Map<string, string>
  verification: VerificationFrame | null
  final: boolean
}

type Action =
  | { type: 'open' }
  | { type: 'error' }
  | { type: 'snapshot'; data: SnapshotFrame }
  | { type: 'job'; data: JobFrame }
  | { type: 'model'; data: ModelFrame }
  | { type: 'token'; data: { job_id: string; delta: string } }
  | { type: 'verification'; data: VerificationFrame }
  | { type: 'transform'; data: { status: StreamState['transformStatus']; final: boolean } }

/**
 * The snapshot carries `Job.model_dump()` rows, whose key is `id` — the live `job`
 * frames use `job_id` instead. Normalise here so the reducer sees one shape.
 */
interface JobRow {
  id: string
  transform_id: string
  artefact_type: ArtefactType
  model_key: string
  status: JobStatus
  updated_at: string
  artefact_path: string | null
  error: string | null
}

interface SnapshotFrame {
  status: StreamState['transformStatus']
  job_rows: JobRow[]
  models: ModelRow[]
  model_events: ModelFrame[]
  verification: VerificationFrame | null
}

function fromRow(row: JobRow): JobFrame {
  const { id, ...rest } = row
  return { job_id: id, ...rest }
}

/** Keep the visible tail only; the artefact itself is read from disk when the job lands. */
const TOKEN_TAIL = 2000

const initialState: StreamState = {
  status: 'connecting',
  transformStatus: 'PENDING',
  jobs: new Map(),
  jobOrder: [],
  models: [],
  modelEvents: [],
  tokens: new Map(),
  verification: null,
  final: false,
}

function reducer(state: StreamState, action: Action): StreamState {
  switch (action.type) {
    case 'open':
      return { ...state, status: 'live' }
    case 'error':
      return { ...state, status: state.final ? 'closed' : 'error' }
    case 'snapshot': {
      const jobs = new Map(state.jobs)
      for (const row of action.data.job_rows) jobs.set(row.id, fromRow(row))
      return {
        ...state,
        status: 'live',
        transformStatus: action.data.status,
        jobs,
        jobOrder: action.data.job_rows.map((row) => row.id),
        models: action.data.models,
        // Seeded so a late subscriber sees the swaps that already happened.
        modelEvents:
          state.modelEvents.length > 0
            ? state.modelEvents
            : (action.data.model_events ?? []),
        verification: action.data.verification ?? state.verification,
      }
    }
    case 'job': {
      const jobs = new Map(state.jobs)
      jobs.set(action.data.job_id, action.data)
      const jobOrder = state.jobOrder.includes(action.data.job_id)
        ? state.jobOrder
        : [...state.jobOrder, action.data.job_id]
      return { ...state, jobs, jobOrder }
    }
    case 'model': {
      const models = state.models.map((row) =>
        row.key === action.data.model_key
          ? { ...row, state: stateFor(action.data.kind), rss_mb: action.data.rss_mb }
          : row,
      )
      return { ...state, models, modelEvents: [...state.modelEvents, action.data] }
    }
    case 'token': {
      const tokens = new Map(state.tokens)
      const next = (tokens.get(action.data.job_id) ?? '') + action.data.delta
      tokens.set(action.data.job_id, next.slice(-TOKEN_TAIL))
      return { ...state, tokens }
    }
    case 'verification':
      return { ...state, verification: action.data }
    case 'transform':
      return {
        ...state,
        transformStatus: action.data.status,
        final: action.data.final || state.final,
        status: action.data.final ? 'closed' : state.status,
      }
  }
}

function stateFor(kind: ModelFrame['kind']): ModelRow['state'] {
  switch (kind) {
    case 'LOAD_START':
      return 'LOADING'
    case 'LOAD_READY':
      return 'READY'
    case 'EVICT_START':
      return 'EVICTING'
    default:
      return 'NOT_LOADED'
  }
}

/**
 * Subscribe to a transform's event stream.
 *
 * Same-origin `EventSource`, so there is no polling for a five-minute job. The
 * connection is closed as soon as the terminal frame arrives, which the backend
 * emits only after every manifest is on disk.
 */
export function useTransformStream(transformId: string | undefined): StreamState {
  const [state, dispatch] = useReducer(reducer, initialState)

  useEffect(() => {
    if (!transformId) return
    const source = new EventSource(`/transforms/${transformId}/events`)
    const on = <T,>(name: Action['type']) => (event: MessageEvent<string>) => {
      dispatch({ type: name, data: JSON.parse(event.data) as T } as Action)
    }

    source.onopen = () => dispatch({ type: 'open' })
    source.onerror = () => dispatch({ type: 'error' })
    source.addEventListener('snapshot', on<SnapshotFrame>('snapshot'))
    source.addEventListener('job', on<JobFrame>('job'))
    source.addEventListener('model', on<ModelFrame>('model'))
    source.addEventListener('token', on<{ job_id: string; delta: string }>('token'))
    source.addEventListener('verification', on<VerificationFrame>('verification'))
    source.addEventListener('transform', on<SnapshotFrame>('transform'))

    return () => source.close()
  }, [transformId])

  return state
}
