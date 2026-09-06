# Incident Advisory: Regional Ransomware Campaign — Endpoint Compromise Update

**Classification:** TLP:AMBER
**Issued by:** Regional CERT Coordination Cell
**Status:** Active incident, ongoing investigation

## Overview

A coordinated ransomware campaign has been affecting regional government and
utility networks since early September. The total number of endpoints
compromised across the five affected regional networks stands at **4,200**.
Initial containment measures have slowed further spread, but lateral
movement inside already-compromised subnets continues to be observed by
incident responders.

## Technical Detail

The intrusion set gained an initial foothold through a phishing email carrying
a malicious macro-enabled document, followed by credential harvesting and
lateral movement using stolen administrator credentials. Command-and-control
traffic was routed through a small set of bulletproof-hosted domains rotated
on a roughly 48-hour cycle.

## Scope and Impact

Network operator telemetry puts the total number of endpoints compromised
across the five affected regional networks at **5,000**. Recovery time for
affected organisations is currently estimated at two to four weeks depending
on backup availability.

## Recommended Posture

Regional CERT recommends that affected and at-risk organisations isolate
segments showing signs of lateral movement, rotate all administrator
credentials, and validate backup integrity before any restoration attempt.
Organisations that have not yet observed compromise indicators should still
apply the indicators of compromise distributed alongside this advisory and
monitor for the described command-and-control pattern.

## Next Steps

The coordination cell will issue a follow-up advisory once containment is
confirmed across all five regional networks. Organisations should report new
indicators of compromise to the regional CERT within 24 hours of discovery.
