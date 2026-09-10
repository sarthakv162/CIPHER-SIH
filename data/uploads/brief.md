# Policy Brief: Governing Foundation Models in the Public Sector

**Issued by:** National Technology Advisory Group
**Audience:** Senior policy makers and programme leads
**Status:** Draft for consultation

## Context

Foundation models are now capable enough to draft correspondence, summarise case
files, translate between languages, and answer questions over large document sets.
Departments are adopting them faster than procurement and assurance processes can
adapt. Several agencies have run pilots without a shared framework for evaluating
risk, recording provenance, or deciding what may run on premises versus in a
hosted environment.

## The Core Tension

Hosted models offer the strongest raw capability but require sending official
information to an external provider. On-premises models keep data inside the
security boundary but demand hardware, engineering effort, and acceptance that a
smaller model will sometimes produce weaker output. For material touching
national security, the brief recommends that the default posture be fully offline
deployment on government-controlled hardware, with hosted services permitted only
after an explicit data protection assessment.

## Recommendations

1. **Establish a central evaluation capability.** A single team should test
   candidate models against representative government tasks and publish scored
   results that departments can reuse.
2. **Mandate provenance records.** Every artefact produced with model assistance
   should carry a manifest naming the model, its version, the prompt template,
   and the parameters used, so that outputs can be audited later.
3. **Fund a reference offline stack.** A supported, air-gapped reference
   implementation would let smaller agencies adopt the technology without each
   building their own runtime and safety tooling.
4. **Require human sign-off for external communication.** No model-generated text
   should reach the public or a regulator without a named official approving it.

## Risks of Inaction

If the centre does not act, departments will continue to make incompatible
choices. Sensitive information will flow to hosted providers under inconsistent
terms, provenance will be lost, and a future incident will be harder to
investigate because no record of how an artefact was produced will exist.

## Next Steps

The advisory group requests approval to convene a cross-department working group
and to commission the reference offline stack described in recommendation three.
A full implementation plan would follow within eight weeks of approval.
