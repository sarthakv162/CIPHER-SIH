import { cn } from '@/lib/utils'

/** Severity drives the banner colour. Amber and red keep their meanings from the
 *  rest of the console: unverified and conflict-or-danger respectively. */
const SEVERITY: Record<string, string> = {
  critical: 'border-danger/30 bg-danger/10 text-danger',
  high: 'border-danger/25 bg-danger/8 text-danger',
  medium: 'border-warn/25 bg-warn/10 text-warn',
  low: 'border-accent/25 bg-accent/10 text-accent',
  informational: 'border-border bg-bg-3 text-text-1',
}

interface Advisory {
  title: string
  advisory_id: string
  severity: string
  issued_for: string
  summary: string
  background: string
  technical_details: { heading: string; body: string }[]
  affected_entities: string[]
  indicators: {
    type?: string
    ioc_type?: string
    value: string
    note?: string
  }[]
  recommended_actions: { priority: string; action: string }[]
  references: string[]
  handling_caveat: string
}

const TEMPLATE_STYLES: Record<string, { border: string; badge: string; takeawayBg: string; label: string }> = {
  'ntro-formal': {
    border: 'border-t-accent',
    badge: 'border-accent/25 bg-accent/10 text-accent',
    takeawayBg: 'border-accent/25 bg-accent/8',
    label: 'NTRO FORMAL',
  },
  executive: {
    border: 'border-t-emerald-600',
    badge: 'border-emerald-600/30 bg-emerald-600/10 text-emerald-700 dark:text-emerald-400',
    takeawayBg: 'border-emerald-600/25 bg-emerald-600/8',
    label: 'EXECUTIVE BRIEFING',
  },
  technical: {
    border: 'border-t-purple-600',
    badge: 'border-purple-600/30 bg-purple-600/10 text-purple-700 dark:text-purple-400',
    takeawayBg: 'border-purple-600/25 bg-purple-600/8',
    label: 'TECHNICAL REPORT',
  },
}

export function AdvisoryView({
  artefact,
  template = 'ntro-formal',
}: {
  artefact: Advisory
  template?: string
}) {
  const style = TEMPLATE_STYLES[template] ?? TEMPLATE_STYLES['ntro-formal']
  return (
    <article className={cn('surface-card mx-auto w-full max-w-[76ch] border-t-4 p-5 md:p-9', style.border)}>
      <div className="mb-3 flex items-center justify-between">
        <span className={cn('rounded-[6px] border px-2 py-0.5 text-[12px] font-semibold tracking-wider uppercase', style.badge)}>
          {style.label}
        </span>
      </div>
      <div
        className={cn(
          'flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[8px] border px-3 py-2',
          SEVERITY[artefact.severity] ?? SEVERITY.informational,
        )}
      >
        <span className="text-[15px] tracking-wide uppercase">
          {artefact.severity}
        </span>
        <span className="tabular text-[15px] opacity-80">
          {artefact.advisory_id}
        </span>
        <span className="ml-auto text-[15px] opacity-80">
          {artefact.issued_for}
        </span>
      </div>

      <h1 className="mt-4 text-[26px] leading-tight text-balance break-words text-text-0">
        {artefact.title}
      </h1>
      <p className="mt-3 text-[16px] leading-relaxed text-text-1">
        {artefact.summary}
      </p>

      <Section title="Background">
        <p className="text-[16px] leading-relaxed text-text-0">
          {artefact.background}
        </p>
      </Section>

      <Section title="Technical detail">
        {artefact.technical_details.map((detail) => (
          <div key={detail.heading} className="mt-3 first:mt-0">
            <h3 className="text-[16px] text-text-0">{detail.heading}</h3>
            <p className="mt-1 text-[16px] leading-relaxed text-text-1">
              {detail.body}
            </p>
          </div>
        ))}
      </Section>

      {artefact.affected_entities.length > 0 && (
        <Section title="Affected">
          <ul className="flex flex-wrap gap-1.5">
            {artefact.affected_entities.map((entity) => (
              <li
                key={entity}
                className="rounded-[5px] border border-border bg-bg-2 px-2 py-1 text-[15px] text-text-0"
              >
                {entity}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {artefact.indicators.length > 0 && (
        <Section title="Indicators of compromise">
          <ul className="flex flex-col gap-1">
            {artefact.indicators.map((ioc, index) => (
              <li
                key={`${ioc.value}-${index}`}
                className="flex items-baseline gap-2 rounded-[5px] border border-border bg-bg-0 px-2 py-1.5"
              >
                <span className="shrink-0 text-[14px] text-text-1">
                  {ioc.type ?? ioc.ioc_type}
                </span>
                <code className="min-w-0 flex-1 font-mono text-[15px] break-all text-text-0">
                  {ioc.value}
                </code>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Recommended actions">
        <ol className="flex flex-col gap-1.5">
          {artefact.recommended_actions.map((action, index) => (
            <li key={index} className="flex items-baseline gap-2">
              <span
                className={cn(
                  'shrink-0 rounded-[4px] border px-1.5 py-0.5 text-[14px] uppercase',
                  action.priority === 'immediate'
                    ? 'border-danger/30 bg-danger/10 text-danger'
                    : action.priority === 'high'
                      ? 'border-warn/30 bg-warn/10 text-warn'
                      : 'border-border bg-bg-2 text-text-1',
                )}
              >
                {action.priority}
              </span>
              <span className="text-[16px] leading-relaxed text-text-0">
                {action.action}
              </span>
            </li>
          ))}
        </ol>
      </Section>

      <p className="mt-6 rounded-[8px] border border-border bg-bg-0 px-3 py-2 text-[15px] leading-snug text-text-1">
        {artefact.handling_caveat}
      </p>
    </article>
  )
}

interface ExecutiveSummary {
  title: string
  headline: string
  key_points: string[]
  context: string
  implications: string[]
  recommended_actions: string[]
  one_line_takeaway: string
}

export function ExecutiveSummaryView({
  artefact,
  template = 'ntro-formal',
}: {
  artefact: ExecutiveSummary
  template?: string
}) {
  const style = TEMPLATE_STYLES[template] ?? TEMPLATE_STYLES['ntro-formal']
  return (
    <article className={cn('surface-card mx-auto w-full max-w-[76ch] border-t-4 p-5 md:p-9', style.border)}>
      <div className="mb-4 flex items-center justify-between">
        <span className={cn('rounded-[6px] border px-2.5 py-1 text-[12px] font-semibold tracking-wider uppercase', style.badge)}>
          {style.label}
        </span>
      </div>
      <h1 className="text-[26px] leading-tight text-balance break-words text-text-0">
        {artefact.title}
      </h1>
      <p className="mt-2 text-[18px] leading-relaxed text-text-1">
        {artefact.headline}
      </p>

      <p className={cn('mt-4 rounded-[8px] border px-3 py-2.5 text-[16px] leading-relaxed text-text-0', style.takeawayBg)}>
        {artefact.one_line_takeaway}
      </p>

      <Section title="Key points">
        <ul className="flex flex-col gap-1.5">
          {artefact.key_points.map((point, index) => (
            <li
              key={index}
              className="flex gap-2 text-[16px] leading-relaxed text-text-0"
            >
              <span className="text-text-2">—</span>
              {point}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Context">
        <p className="text-[16px] leading-relaxed text-text-0">
          {artefact.context}
        </p>
      </Section>

      <Section title="Implications">
        <ul className="flex flex-col gap-1.5">
          {artefact.implications.map((item, index) => (
            <li
              key={index}
              className="flex gap-2 text-[16px] leading-relaxed text-text-0"
            >
              <span className="text-text-2">—</span>
              {item}
            </li>
          ))}
        </ul>
      </Section>

      {artefact.recommended_actions.length > 0 && (
        <Section title="Recommended actions">
          <ol className="flex flex-col gap-1.5">
            {artefact.recommended_actions.map((action, index) => (
              <li
                key={index}
                className="flex gap-2 text-[16px] leading-relaxed text-text-0"
              >
                <span className="tabular text-text-2">{index + 1}.</span>
                {action}
              </li>
            ))}
          </ol>
        </Section>
      )}
    </article>
  )
}

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="mt-5">
      <h2 className="section-label">{title}</h2>
      <div className="mt-2">{children}</div>
    </section>
  )
}
