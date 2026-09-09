import { Heart, MessageCircle, Repeat2, Send, ThumbsUp } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Platform shells for the two artefacts whose whole point is how they will look
 * once posted. Rendering them as plain JSON hides the thing the operator is
 * actually judging: whether it reads like a real post.
 *
 * Two limits are in play and they are not the same number. The platform limit is
 * what the operator cares about when posting; the schema in `core/artefacts.py`
 * enforces a stricter one, so the count can never legitimately exceed it.
 */

const LINKEDIN_PLATFORM_LIMIT = 3000
const LINKEDIN_SCHEMA_LIMIT = 2800
const X_PLATFORM_LIMIT = 280
const X_SCHEMA_LIMIT = 275

function CharCount({
  used,
  limit,
  schemaLimit,
}: {
  used: number
  limit: number
  schemaLimit: number
}) {
  const over = used > limit
  const nearing = !over && used > limit * 0.9
  return (
    <span
      className={cn(
        'tabular text-[11px]',
        over ? 'text-danger' : nearing ? 'text-warn' : 'text-text-1',
      )}
      title={`Platform limit ${limit.toLocaleString()}. The artefact schema caps this at ${schemaLimit.toLocaleString()}, so a valid artefact is always within it.`}
    >
      {used.toLocaleString()} / {limit.toLocaleString()}
    </span>
  )
}

interface LinkedInProps {
  body: string
  hook: string
  hashtags: string[]
  callToAction: string
}

export function LinkedInPreview({ body, hook, hashtags, callToAction }: LinkedInProps) {
  const full = [hook, body, callToAction].filter(Boolean).join('\n\n')
  const used = full.length + hashtags.reduce((n, tag) => n + tag.length + 2, 0)

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-[12px] text-text-1">Post preview</span>
        <CharCount
          used={used}
          limit={LINKEDIN_PLATFORM_LIMIT}
          schemaLimit={LINKEDIN_SCHEMA_LIMIT}
        />
      </div>

      <article className="surface-card overflow-hidden">
        <header className="flex items-center gap-2.5 p-3">
          <div
            className="flex size-10 shrink-0 items-center justify-center rounded-full bg-bg-3 text-[13px] text-text-1"
            aria-hidden="true"
          >
            ◈
          </div>
          <div className="min-w-0">
            <div className="truncate text-[13px] text-text-0">Organisation</div>
            <div className="truncate text-[11px] text-text-1">
              Communications · Now · Public
            </div>
          </div>
        </header>

        <div className="px-3 pb-3">
          {/* Line breaks are load-bearing on LinkedIn — preserve them exactly. */}
          <p className="text-[13px] leading-relaxed whitespace-pre-wrap text-text-0">
            {hook}
          </p>
          <p className="mt-2.5 text-[13px] leading-relaxed whitespace-pre-wrap text-text-0">
            {body}
          </p>
          {callToAction && (
            <p className="mt-2.5 text-[13px] leading-relaxed text-text-0">{callToAction}</p>
          )}
          {hashtags.length > 0 && (
            <p className="mt-2.5 text-[13px] leading-relaxed text-accent">
              {hashtags.map((tag) => `#${tag}`).join(' ')}
            </p>
          )}
        </div>

        <footer className="hairline-t flex items-center justify-around px-3 py-1.5">
          {[
            { icon: ThumbsUp, label: 'Like' },
            { icon: MessageCircle, label: 'Comment' },
            { icon: Repeat2, label: 'Repost' },
            { icon: Send, label: 'Send' },
          ].map(({ icon: Icon, label }) => (
            <span
              key={label}
              className="flex items-center gap-1.5 px-2 py-1 text-[12px] text-text-1"
            >
              <Icon className="size-4" strokeWidth={1.75} />
              {label}
            </span>
          ))}
        </footer>
      </article>
    </div>
  )
}

interface XThreadProps {
  tweets: { text: string }[]
  hashtags: string[]
  threadHook: string
}

export function XThreadPreview({ tweets, hashtags, threadHook }: XThreadProps) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-[12px] text-text-1">Thread preview</span>
        <span className="tabular text-[11px] text-text-1">
          {tweets.length} post{tweets.length === 1 ? '' : 's'}
        </span>
      </div>

      {threadHook && (
        <p className="text-[12px] leading-snug text-text-1">Hook: {threadHook}</p>
      )}

      <div className="surface-card p-3">
        <ol>
          {tweets.map((tweet, index) => {
            const last = index === tweets.length - 1
            const used = tweet.text.length
            return (
              <li key={index} className="flex gap-2.5">
                {/* Avatar column doubles as the connecting line between posts. */}
                <div className="flex shrink-0 flex-col items-center">
                  <div
                    className="flex size-9 items-center justify-center rounded-full bg-bg-3 text-[12px] text-text-1"
                    aria-hidden="true"
                  >
                    ◈
                  </div>
                  {!last && <div className="w-px flex-1 bg-border" aria-hidden="true" />}
                </div>

                <div className={cn('min-w-0 flex-1', last ? 'pb-0' : 'pb-4')}>
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-[13px] text-text-0">Organisation</span>
                    <span className="text-[12px] text-text-1">@org · now</span>
                  </div>
                  <p className="mt-0.5 text-[13px] leading-relaxed whitespace-pre-wrap text-text-0">
                    {tweet.text}
                  </p>
                  <div className="mt-1.5 flex items-center gap-4">
                    <span className="flex items-center gap-1 text-[11px] text-text-1">
                      <MessageCircle className="size-3.5" strokeWidth={1.75} />
                    </span>
                    <span className="flex items-center gap-1 text-[11px] text-text-1">
                      <Repeat2 className="size-3.5" strokeWidth={1.75} />
                    </span>
                    <span className="flex items-center gap-1 text-[11px] text-text-1">
                      <Heart className="size-3.5" strokeWidth={1.75} />
                    </span>
                    <span className="ml-auto">
                      <CharCount
                        used={used}
                        limit={X_PLATFORM_LIMIT}
                        schemaLimit={X_SCHEMA_LIMIT}
                      />
                    </span>
                  </div>
                </div>
              </li>
            )
          })}
        </ol>

        {hashtags.length > 0 && (
          <p className="hairline-t mt-1 pt-2.5 pl-[46px] text-[13px] text-accent">
            {hashtags.map((tag) => `#${tag}`).join(' ')}
          </p>
        )}
      </div>
    </div>
  )
}
