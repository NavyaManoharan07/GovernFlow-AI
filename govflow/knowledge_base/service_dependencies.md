# Service Dependencies

> **MOCK / DEMONSTRATION DATA — not real current law.** All statute names, section numbers, and thresholds below are invented for the GovFlow AI hackathon demo and must never be treated as legal advice or a real government source.

## Overview

This document describes the dependency ordering between the four services in the GovFlow AI demo catalog: business_registration, tax_registration, food_license, and local_approval. WorkflowPlannerAgent uses this as grounding context (via RAG) when it derives the dependency graph for a given goal -- the actual graph edges are still decided by the planner via Gemini, not hardcoded from this file.

## Numbered Requirements

- REQ-DEP-1: business_registration has no prerequisites and must be completed before any other service in the catalog. (Service: business_registration) (Source: Demo Municipal Business Code §4.1 (MOCK))
- REQ-DEP-2: tax_registration requires an approved business_registration and can run independently of food_license. (Service: tax_registration) (Source: Demo Revenue Code §7.1 (MOCK))
- REQ-DEP-3: food_license requires an approved business_registration and can run independently of tax_registration. (Service: food_license) (Source: Demo State Food Safety Act §3.1 (MOCK))
- REQ-DEP-4: local_approval requires both an approved tax_registration and an approved food_license; it cannot be submitted until both are complete. (Service: local_approval) (Source: Demo Municipal Zoning Ordinance §9.1 (MOCK))
- REQ-DEP-5: A business goal that does not involve food processing, food sale, or food storage does not require the food_license service at all. (Service: food_license) (Source: Demo State Food Safety Act §3.1 (MOCK))
- REQ-DEP-6: A purely online or home-based business with no physical customer-facing premises may be exempt from local_approval -- this exemption must be confirmed case-by-case and is not automatic. (Service: local_approval) (Source: Demo Municipal Zoning Ordinance §9.9 (MOCK))

## Demo catalog

The GovFlow AI hackathon demo supports exactly four services: business_registration, tax_registration, food_license, local_approval. WorkflowPlannerAgent selects a subset of these four (never services outside this catalog) and assigns dependency edges consistent with REQ-DEP-1 through REQ-DEP-4 above.
