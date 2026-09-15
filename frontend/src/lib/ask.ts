import type { SourceInput } from './api'

/**
 * "Ask about sources" mode: streamed, grounded question answering over an evidence pack.
 * Mirrors `POST /transforms/{id}/ask` and `POST /qa/sessions[...]/ask` — see
 * `orchestrator/qa.py`. No new model, no retrieval, no persistence as a transform.
 */

export interface AskTurn {
  question: string
  answer: string
  status: 'streaming' | 'done' | 'error'
  error?: string
}

interface SseFrame {
  event: string
  data: string
}

async function* sseFrames(response: Response): AsyncGenerator<SseFrame> {
  const reader = response.body?.getReader()
  if (!reader) return
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let boundary: number
    while ((boundary = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      let event = 'message'
      let data = ''
      for (const line of raw.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data = line.slice(5).trim()
      }
      if (data) yield { event, data }
    }
  }
}

async function errorDetail(response: Response): Promise<string> {
  const body = (await response.json().catch(() => null)) as { detail?: string } | null
  return body?.detail ?? `Could not ask that (${response.status})`
}

/** POST `url` with `{question}` and stream the answer's text deltas to `onDelta`. */
export async function askStream(
  url: string,
  question: string,
  onDelta: (text: string) => void,
): Promise<void> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!response.ok) throw new Error(await errorDetail(response))
  for await (const frame of sseFrames(response)) {
    if (frame.event === 'delta') {
      onDelta((JSON.parse(frame.data) as { text: string }).text)
    } else if (frame.event === 'error') {
      throw new Error((JSON.parse(frame.data) as { detail: string }).detail)
    }
  }
}

/** Assemble a session-scoped evidence pack from `sources`; never persisted as a transform. */
export async function createAskSession(sources: SourceInput[]): Promise<string> {
  const response = await fetch('/qa/sessions', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ sources }),
  })
  if (!response.ok) throw new Error(await errorDetail(response))
  return (await response.json() as { session_id: string }).session_id
}
