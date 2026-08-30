# Required Documents

> **MOCK / DEMONSTRATION DATA — not real current law.** All statute names, section numbers, and thresholds below are invented for the GovFlow AI hackathon demo and must never be treated as legal advice or a real government source.

## Overview

This is the document checklist referenced by DocumentAgent when validating an applicant's submission for each service in the demo catalog.

## Numbered Requirements

- REQ-DOC-1: Proof of identity (government-issued ID) is required for business registration. (Service: business_registration) (Source: Demo Municipal Business Code §4.9 (MOCK))
- REQ-DOC-2: Proof of registered office address (utility bill or lease agreement) is required for business registration. (Service: business_registration) (Source: Demo Municipal Business Code §4.10 (MOCK))
- REQ-DOC-3: The approved Business Registration Certificate is required for tax registration. (Service: tax_registration) (Source: Demo Revenue Code §7.3 (MOCK))
- REQ-DOC-4: A bank account confirmation letter is required for tax registration. (Service: tax_registration) (Source: Demo Revenue Code §7.6 (MOCK))
- REQ-DOC-5: The approved Business Registration Certificate is required for a food license application. (Service: food_license) (Source: Demo State Food Safety Act §3.2 (MOCK))
- REQ-DOC-6: A Food Safety Supervisor training certificate is required for a food license application. (Service: food_license) (Source: Demo State Food Safety Act §3.4 (MOCK))
- REQ-DOC-7: A water quality test certificate dated within the last 12 months is required for a food license application. (Service: food_license) (Source: Demo State Food Safety Act §3.10 (MOCK))
- REQ-DOC-8: Approved Tax Registration and Food License certificates are both required before local approval can be submitted. (Service: local_approval) (Source: Demo Municipal Zoning Ordinance §9.4 (MOCK))
- REQ-DOC-9: A site plan or floor layout of the proposed premises is required for local approval. (Service: local_approval) (Source: Demo Municipal Zoning Ordinance §9.6 (MOCK))

## Notes for DocumentAgent

If a document listed above is not present in the applicant's provided document metadata, DocumentAgent must treat it as missing and trigger the DOCUMENT_MISSING event rather than assuming it will be supplied later.
