import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { EgressPill } from '@/components/EgressPill'
import { KineticGrid } from '@/components/KineticGrid'

/**
 * Entry screen. Product name, what it does in one line, one action.
 * The kinetic grid canvas lands here in 9b-7 — and only here.
 */
export function Entry() {
  return (
    <div className="relative flex h-dvh w-full flex-col overflow-hidden bg-bg-0">
      <KineticGrid className="pointer-events-none absolute inset-0 size-full" />
      <div className="ambient-wash" aria-hidden="true" />
      <div className="ambient-vignette" aria-hidden="true" />

      <div className="relative z-10 flex items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2.5">
          <div className="flex size-7 items-center justify-center rounded-[8px] bg-bg-2 ring-1 ring-border">
            <span className="text-[16px] leading-none text-accent">◈</span>
          </div>
          <span className="text-[16px] text-text-1">Rupantar</span>
        </div>
        <EgressPill />
      </div>

      <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 pb-10">
        <h1 className="text-center text-[56px] leading-[1.1] tracking-[-0.02em] text-text-0">
          Rupantar
        </h1>
        <p className="mt-4 max-w-[46ch] text-center text-[18px] leading-relaxed text-text-1">
          An offline content transformation engine. Source material in,
          communication artefacts out — generated locally, traced to evidence,
          and recorded with provenance.
        </p>

        <Link
          to="/workspace"
          className="group mt-9 flex items-center gap-2 rounded-[8px] border border-accent/35 bg-accent/12 px-4 py-2.5 text-[16px] text-text-0 shadow-[0_0_0_1px_rgba(91,141,239,0.06),0_8px_28px_-10px_rgba(91,141,239,0.55)] transition-all duration-200 ease-[cubic-bezier(0.2,0,0,1)] hover:border-accent/55 hover:bg-accent/18 hover:shadow-[0_0_0_1px_rgba(91,141,239,0.1),0_12px_34px_-10px_rgba(91,141,239,0.7)]"
        >
          New transform
          <ArrowRight
            className="size-4 text-accent transition-transform duration-200 ease-[cubic-bezier(0.2,0,0,1)] group-hover:translate-x-0.5"
            strokeWidth={1.75}
          />
        </Link>

        <dl className="mt-16 flex items-center gap-8 text-[15px] text-text-1">
          <div className="flex flex-col items-center gap-1">
            <dt className="tabular text-[24px] text-text-0">7</dt>
            <dd>artefact types</dd>
          </div>
          <div className="h-8 w-px bg-border" aria-hidden="true" />
          <div className="flex flex-col items-center gap-1">
            <dt className="tabular text-[24px] text-text-0">1</dt>
            <dd>model resident at a time</dd>
          </div>
          <div className="h-8 w-px bg-border" aria-hidden="true" />
          <div className="flex flex-col items-center gap-1">
            <dt className="tabular text-[24px] text-text-0">0</dt>
            <dd>external connections</dd>
          </div>
        </dl>
      </div>
    </div>
  )
}
