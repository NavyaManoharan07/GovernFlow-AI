# Eligibility Rules

> **MOCK / DEMONSTRATION DATA — not real current law.** All statute names, section numbers, and thresholds below are invented for the GovFlow AI hackathon demo and must never be treated as legal advice or a real government source.

## Overview

These rules determine whether an applicant is eligible to proceed with a government service application, independent of the document checklist. Eligibility is evaluated once, early in the workflow, against the applicant's declared profile.

## Numbered Requirements

- REQ-EL-1: The applicant must be at least 18 years of age. (Service: general) (Source: Demo Municipal Business Code §2.1 (MOCK))
- REQ-EL-2: The applicant must not have an active business registration revocation on record within Demo Municipality. (Service: general) (Source: Demo Municipal Business Code §2.3 (MOCK))
- REQ-EL-3: The proposed business location must be zoned for commercial or light-industrial use; purely residential zoning is ineligible for food-processing operations. (Service: local_approval) (Source: Demo Municipal Zoning Ordinance §9.2 (MOCK))
- REQ-EL-4: A food-processing applicant must designate a Food Safety Supervisor before eligibility can be confirmed for the food license track. (Service: food_license) (Source: Demo State Food Safety Act §3.3 (MOCK))
- REQ-EL-5: An applicant whose declared annual turnover is unknown or unspecified is marked "needs_information" rather than approved, since the correct tax tier (REQ-TX-3) cannot be determined. (Service: tax_registration) (Source: Demo Revenue Code §7.4 (MOCK))
- REQ-EL-6: Local approval requires that business registration, tax registration, and food license all be approved first; local approval eligibility cannot be assessed independently of those outcomes. (Service: local_approval) (Source: Demo Municipal Zoning Ordinance §9.5 (MOCK))
- REQ-EL-7: An applicant with an unresolved health code violation on record at the proposed premises is ineligible for a food license until the violation is cleared. (Service: food_license) (Source: Demo State Food Safety Act §3.12 (MOCK))

## Guidance for automated eligibility checks

When the applicant's goal statement clearly identifies a business location, approximate size, and product type, treat that as sufficient to evaluate eligibility. Only fall back to "needs_information" when the goal is genuinely too vague to apply the rules above (for example, no indication at all of what is being sold or where). Do not invent specific figures the applicant never provided.
