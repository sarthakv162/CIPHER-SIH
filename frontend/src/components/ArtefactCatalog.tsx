import { Check, Clock3, Layers3, Plus } from 'lucide-react'
import { ARTEFACTS, CATEGORIES, type ArtefactCategory, type ArtefactMeta } from '@/lib/artefacts'
import type { ArtefactType } from '@/lib/api'
import { duration } from '@/lib/utils'

const ORDER: ArtefactType[] = ['executive_summary', 'presentation', 'infographic_spec', 'advisory', 'linkedin_post', 'x_thread', 'video_package']

export function CategoryFilters({ value, onChange, counts = false }: { value: ArtefactCategory; onChange: (category: ArtefactCategory) => void; counts?: boolean }) {
  return <div className="category-filters" role="group" aria-label="Artifact categories">
    {CATEGORIES.map(category => <button key={category.id} type="button" aria-pressed={value === category.id} onClick={() => onChange(category.id)}>
      {category.id === 'all' && <Layers3 className="size-3.5" />}{category.label}
      {counts && <span>{category.id === 'all' ? ARTEFACTS.length : ARTEFACTS.filter(a => a.category === category.id).length}</span>}
    </button>)}
  </div>
}

export function ArtefactCatalog({ category, onCategoryChange, selected, onToggle, disabled }: {
  category: ArtefactCategory
  onCategoryChange: (category: ArtefactCategory) => void
  selected: ArtefactType[]
  onToggle: (type: ArtefactType) => void
  disabled: boolean
}) {
  const visible = ORDER.map(type => ARTEFACTS.find(a => a.type === type)!).filter(a => category === 'all' || a.category === category)
  return <section className="artifact-catalog" aria-labelledby="catalog-title">
    <div className="catalog-heading">
      <div><h2 id="catalog-title">What will you make?</h2><p>Choose your formats. Give your source a new life.</p></div>
      <span className="selection-count" role="status"><span />{selected.length} selected</span>
    </div>
    <CategoryFilters value={category} onChange={onCategoryChange} counts />
    <div className="artifact-grid" data-category={category}>
      {visible.map(artefact => <FeatureCard key={artefact.type} artefact={artefact} selected={selected.includes(artefact.type)} onToggle={() => onToggle(artefact.type)} disabled={disabled} />)}
    </div>
    <p className="catalog-note">Select multiple cards to create a complete content set from one source.</p>
  </section>
}

function FeatureCard({ artefact: a, selected, onToggle, disabled }: { artefact: ArtefactMeta; selected: boolean; onToggle: () => void; disabled: boolean }) {
  return <button type="button" role="checkbox" aria-checked={selected} aria-label={a.label} disabled={disabled} onClick={onToggle} className="feature-card" data-category={a.category} data-kind={a.type}>
    <span className="feature-top"><span className="feature-icon"><a.icon className="size-[19px]" strokeWidth={1.6} /></span><span className="feature-category">{CATEGORIES.find(c => c.id === a.category)?.label}</span><span className="feature-check" aria-hidden="true">{selected ? <Check className="size-3.5" /> : <Plus className="size-3.5" />}</span></span>
    <span className="feature-content"><span className="feature-copy"><span className="feature-title">{a.label}</span><span className="feature-description">{a.description}</span></span><ArtefactVisual type={a.type} /></span>
    <span className="feature-footer"><span className="flex gap-1.5">{a.formats.map(format => <span className="format-tag" key={format}>{format}</span>)}</span><span className="flex items-center gap-1 text-[11px] text-text-1"><Clock3 className="size-3" />~{duration(a.seconds)}</span></span>
  </button>
}

/** Small, local vector previews describe formats without implying generated content. */
export function ArtefactVisual({ type }: { type: ArtefactType }) {
  return <svg className="artefact-visual" viewBox="0 0 100 84" fill="none" aria-hidden="true">
    {type === 'executive_summary' || type === 'advisory' ? <>
      <rect x="22" y="8" width="57" height="70" rx="6" fill="currentColor" opacity=".08" transform="rotate(9 50 42)" />
      <rect x="16" y="5" width="57" height="70" rx="6" fill="var(--color-bg-1)" stroke="currentColor" strokeOpacity=".45" />
      <rect x="25" y="16" width="18" height="5" rx="2" fill="currentColor" opacity=".7" />
      <path d="M25 30h38M25 37h30M25 44h35M25 60h22" stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity=".25" />
      {type === 'advisory' && <path d="m67 42 13 5v10c0 9-13 16-13 16S54 66 54 57V47l13-5Z" fill="var(--color-bg-1)" stroke="currentColor" />}
    </> : type === 'presentation' ? <>
      <rect x="5" y="12" width="88" height="57" rx="6" fill="var(--color-bg-1)" stroke="currentColor" strokeOpacity=".45" />
      <path d="M40 70v8m20-8v8M30 78h40" stroke="currentColor" strokeOpacity=".4" strokeLinecap="round" />
      <rect x="15" y="23" width="32" height="4" rx="2" fill="currentColor" opacity=".7" /><path d="M15 35h24m-24 7h18m-18 7h24" stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity=".2" />
      <rect x="56" y="41" width="7" height="16" rx="2" fill="currentColor" opacity=".25" /><rect x="66" y="33" width="7" height="24" rx="2" fill="currentColor" opacity=".5" /><rect x="76" y="23" width="7" height="34" rx="2" fill="currentColor" opacity=".8" />
    </> : type === 'infographic_spec' ? <>
      <rect x="12" y="6" width="76" height="72" rx="8" fill="var(--color-bg-1)" stroke="currentColor" strokeOpacity=".35" />
      <circle cx="39" cy="34" r="15" stroke="currentColor" strokeWidth="7" opacity=".16" /><path d="M39 19a15 15 0 0 1 13 22" stroke="currentColor" strokeWidth="7" strokeLinecap="round" opacity=".8" />
      <path d="M65 23h12m-12 8h9m-12 9h12" stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity=".35" /><rect x="24" y="59" width="13" height="8" rx="2" fill="currentColor" opacity=".2" /><rect x="42" y="54" width="13" height="13" rx="2" fill="currentColor" opacity=".4" /><rect x="60" y="49" width="13" height="18" rx="2" fill="currentColor" opacity=".7" />
    </> : type === 'video_package' ? <>
      <rect x="4" y="11" width="92" height="62" rx="9" fill="var(--color-bg-1)" stroke="currentColor" strokeOpacity=".45" /><path d="M4 23h92M4 61h92" stroke="currentColor" strokeOpacity=".2" />
      {[14, 32, 50, 68, 86].map(x => <path key={x} d={`M${x} 15v4m0 46v4`} stroke="currentColor" strokeWidth="5" opacity=".2" />)}
      <circle cx="50" cy="42" r="15" fill="currentColor" opacity=".15" /><path d="m46 34 12 8-12 8V34Z" fill="currentColor" opacity=".85" />
    </> : <>
      <rect x="8" y="8" width="74" height="49" rx="7" fill="var(--color-bg-1)" stroke="currentColor" strokeOpacity=".4" /><circle cx="22" cy="22" r="5" fill="currentColor" opacity=".45" /><path d="M34 20h26M18 36h51m-51 8h34" stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity=".25" />
      <rect x="32" y="47" width="61" height="28" rx="7" fill="var(--color-bg-1)" stroke="currentColor" strokeOpacity=".5" /><path d="M43 57h37m-37 8h23" stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity=".5" />
    </>}
  </svg>
}
