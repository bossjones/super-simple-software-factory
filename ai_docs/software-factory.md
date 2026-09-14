# Software Factory Baseline

verified_on: 2026-09-14
scope: This page defines why SSSF is a software factory and does not document Copilot- or Pi-specific runtime mechanics.

- A software factory is not just an agent prompt; it is a delivery system that combines repeatable process, automation, policy, and evidence across the software lifecycle. That framing is explicit in the [NIST NCCoE DevSecOps reference model](https://pages.nist.gov/nccoe-devsecops/notational-reference-model.html), the [NIST Secure Software Development Framework](https://csrc.nist.gov/pubs/sp/800/218/final), and the [DoD Enterprise DevSecOps Reference Design](https://dodcio.defense.gov/Portals/0/Documents/Library/DoD-Enterprise-DevSecOps-Reference-Design-v1.0.pdf).
- For this repository, "deterministic" applies to the control plane and evidence trail, not to model text being perfectly repeatable. The current seams that supply that control plane are the stamped workflow graph, typed envelopes, gates, write-policy enforcement, and trace persistence described in [sssf-architecture.md](sssf-architecture.md).
- A later port can swap the coding-agent harness without changing the factory definition as long as code still owns sequencing, validation, and acceptance. The Copilot port spec preserves that boundary and treats documentation, tests, and traceability as first-class artifacts rather than optional prompt guidance; see the approved design in [`docs/superpowers/specs/2026-09-14-copilot-software-factory-design.md`](../docs/superpowers/specs/2026-09-14-copilot-software-factory-design.md).

Refresh from the live standards above before changing the factory definition, then re-read [sssf-architecture.md](sssf-architecture.md) to map those standards back onto this repo.
