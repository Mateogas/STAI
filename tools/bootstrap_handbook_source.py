"""Create the initial explicit 108-page YAML source.

This is an authoring bootstrap only. ``handbook/source.yaml`` is the canonical
published source consumed by the build; generated artifacts never call this
script or infer pages from prose files.
"""

from __future__ import annotations

from pathlib import Path

import yaml


ALL = {"role_keys": ["all"], "department_keys": ["all"], "employment_classifications": ["all"], "work_sites": ["all"]}


def policy(policy_id, topic, title, points, applicability=None, subareas=None, route="hr_general"):
    return {
        "policy_id": policy_id,
        "topic": topic,
        "title": title,
        "points": points,
        "applicability": applicability or ALL,
        "subareas": subareas or [],
        "route": route,
    }


POLICIES = [
    policy("PAY-001", "payroll", "First-pay schedule", [
        "Payroll enrolls an eligible new Hire after the required onboarding payroll details are recorded through the fictional HR route.",
        "The first-pay timing follows the published semi-monthly schedule and may move when a public holiday affects the processing calendar.",
        "Alyssa should review the displayed pay-period boundary and ask Payroll Support when a start date falls near a cutoff.",
        "A public-holiday date may come from the approved calendar tool, but any employment consequence remains governed by this policy.",
        "AISHA guides and explains; it cannot change payroll enrollment, bank details, deductions, or payment status.",
    ], {**ALL, "employment_classifications": ["probationary", "regular", "fixed_term"]}, ["pay_schedule"], "payroll_support"),
    policy("PAY-002", "payroll", "Payslip access and explanation", [
        "Payslips are available through the fictional employee self-service portal after payroll publishes the period.",
        "A payslip explanation may define gross pay, deductions, and net pay without asserting that any displayed amount is correct.",
        "Resource-access problems are routed to Access Support while questions about figures are routed to Payroll Support.",
        "AISHA never requests or stores bank account numbers, government identifiers, or a copy of a real payslip.",
    ], subareas=["payslip"], route="payroll_support"),
    policy("PAY-003", "payroll", "Payroll details and corrections", [
        "Payroll detail changes must use the fictional official payroll route and are never performed inside AISHA.",
        "A Hire should report a suspected error using only the minimum safe summary needed to identify the pay period and issue category.",
        "AISHA does not ask for full bank details or government identifiers and does not retain financial documents.",
        "Payroll Support confirms any correction; AISHA cannot promise a correction date or outcome.",
    ], subareas=["payroll_changes"], route="payroll_support"),
    policy("PAY-004", "payroll", "Deductions and statutory items", [
        "AISHA may explain the fictional handbook labels for common deduction categories at a high level.",
        "It must not calculate tax, legal entitlement, or a personalized statutory obligation.",
        "Questions requiring account-specific figures are routed to Payroll Support with Hire consent.",
        "A grounded answer distinguishes handbook explanation from the Hire-provided values in the question.",
    ], subareas=["deductions"], route="payroll_support"),
    policy("PAY-005", "payroll", "Holiday calendar context", [
        "Philippine public-holiday names and dates may be obtained from the approved read-only calendar provider.",
        "Holiday pay, office closure, eligibility, and reporting consequences require separate active handbook support.",
        "If the provider and active handbook disagree, AISHA makes no date-dependent conclusion and offers HR escalation.",
        "When calendar evidence is unavailable, AISHA uses an explicit cited handbook date or requests human review.",
    ], subareas=["holiday_calendar"], route="payroll_support"),
    policy("PAY-006", "payroll", "Regular-employee payroll-change cutoff", [
        "This cutoff applies only to a Hire whose confirmed Employment Classification is regular.",
        "A probationary or fixed-term Hire receives a cited non-applicability explanation rather than the regular procedure.",
        "A statement that classification may have changed is provisional until HR confirms an Attribute Change Request.",
        "While confirmation is pending, AISHA may explain conditional outcomes but cannot personalize the regular cutoff.",
        "Payroll Support is the policy route; HR remains the fallback for a disputed Employment Classification.",
    ], {**ALL, "employment_classifications": ["regular"]}, ["payroll_changes"], "payroll_support"),
    policy("ACC-001", "resource_access", "Branch training-sandbox access", [
        "The training sandbox applies to confirmed branch banking associates in Branch Banking at a branch work site.",
        "Access guidance identifies the fictional request route and prerequisites but does not provision or confirm access.",
        "Alyssa may use the sandbox only for the educational workflow described in this fictional handbook.",
        "A missing prerequisite is explained with its owner; AISHA cannot bypass approval or security controls.",
        "Access Support handles unresolved setup while the branch manager remains a human contact, not an app role.",
    ], {"role_keys": ["branch_banking_associate"], "department_keys": ["branch_banking"], "employment_classifications": ["all"], "work_sites": ["branch"]}, ["training_access"], "access_support"),
    policy("ACC-002", "resource_access", "Employee self-service access", [
        "The fictional self-service account is the route for handbook-listed onboarding records and payslip access.",
        "AISHA can describe sign-in recovery steps but cannot see credentials, reset passwords, or confirm account state.",
        "A Hire should never paste a password, one-time code, or recovery answer into AISHA.",
        "Repeated sign-in failure is routed to Access Support using a concise non-secret summary.",
        "The account remains a Company Resource governed by security and acceptable-use requirements.",
    ], subareas=["employee_portal"], route="access_support"),
    policy("ACC-003", "resource_access", "Branch device setup", [
        "Branch device setup follows the fictional asset handoff and local sign-in guidance.",
        "AISHA may identify the owner and ordered setup steps but cannot inventory, unlock, or manage a device.",
        "Device serial numbers and authentication secrets are not needed in ordinary Dialogue history.",
        "Lost or damaged equipment requires immediate use of the official human reporting route.",
        "Security controls are never weakened to complete onboarding more quickly.",
    ], {**ALL, "work_sites": ["branch"]}, ["devices"], "access_support"),
    policy("ACC-004", "resource_access", "Information security access", [
        "Access is least-privilege and tied to the confirmed role, department, classification, and work site.",
        "AISHA does not infer entitlement from semantic similarity or from another Hire's access.",
        "Requests for credentials, bypasses, or confidential data are refused and routed safely.",
        "Procedure pages explain subordinate steps and never establish a new entitlement.",
        "Only the fictional system owner can confirm completion of an access request.",
    ], subareas=["information_security"], route="access_support"),
    policy("ACC-005", "resource_access", "Facility and branch entry", [
        "Facility entry guidance applies to the confirmed Work Site and does not establish real physical access.",
        "AISHA may explain where the fictional branch contact appears in the directory.",
        "A temporary visit does not change the confirmed Work Site used for future applicability.",
        "A lost badge or unsafe situation is routed immediately without exposing identifying details.",
        "The educational demo never connects to a building access-control system.",
    ], subareas=["facility_access"], route="branch_operations"),
    policy("ACC-006", "resource_access", "Remote-access kit", [
        "The remote-access kit applies only when Remote is the Hire's HR-confirmed Work Site.",
        "A temporary work-from-home day does not by itself establish eligibility.",
        "When the assigned Work Site is unclear, AISHA asks one focused question before providing personalized guidance.",
        "An Attribute Change Request requires explicit Hire consent and HR approval.",
        "AISHA never provisions a kit, VPN, account, device, or other Company Resource.",
    ], {**ALL, "work_sites": ["remote"]}, ["remote_access"], "access_support"),
    policy("HRP-001", "hr_policies", "Branch attendance and office hours", [
        "This branch attendance guidance applies only to a Hire with Branch as the confirmed Work Site.",
        "A temporary Head Office visit does not automatically update the Hire Profile.",
        "Questions about a possible permanent move require one focused clarification and optional Attribute Change Request.",
        "AISHA explains reporting steps but cannot approve leave, attendance corrections, or schedule changes.",
        "Attendance support is framed as humane onboarding help rather than surveillance or performance scoring.",
    ], {**ALL, "work_sites": ["branch"]}, ["attendance", "office_hours"], "hr_general"),
    policy("HRP-002", "hr_policies", "Leave guidance", [
        "AISHA provides guide-plus-validate support and does not approve or deny leave.",
        "Leave types and required steps must be supported by active policy evidence before a conclusion.",
        "The Hire uses the separate fictional official route for a leave request or original document submission.",
        "A private conversation is not an official filing and is not visible to HR by default.",
        "Unsupported eligibility questions abstain and offer the active HR route.",
    ], subareas=["leave"], route="hr_leave"),
    policy("HRP-003", "hr_policies", "Workplace conduct and support", [
        "The fictional conduct policy promotes respectful, safe, and inclusive workplace behavior.",
        "AISHA can identify support routes but is not an emergency service, investigator, or disciplinary system.",
        "Private chat transcripts are not shown to HR by default.",
        "A case summary must be displayed and explicitly approved before a consented escalation is created.",
        "Immediate safety concerns are redirected to appropriate local emergency and human channels.",
    ], subareas=["conduct"], route="hr_general"),
    policy("HRP-004", "hr_policies", "Medical certificate completeness requirements", [
        "The local check requires patient full name, consultation date, issue date, absence start, and an end date or positive whole-day duration.",
        "It also requires clinician full name, facility name, professional license or registration number presence, signature indication, and an explicit rest recommendation.",
        "Dates use month-day-four-digit-year and are checked only for deterministic calendar and ordering consistency.",
        "The patient first and last name must match the Hire Profile after conservative normalization; AISHA never guesses identity.",
        "Every OCR-derived required field must be unambiguous at or above the configured threshold, with exactly one clearer-copy retry.",
        "The check never authenticates a document, verifies a clinician, assesses a diagnosis, or approves leave.",
        "Certificate bytes and extracted content are discarded; only closed result codes, citations, timing, and an installation-local fingerprint may remain.",
        "The original certificate must still use the separate Official HR Document Route; result sharing with HR requires explicit consent.",
    ], subareas=["medical_certificate", "leave"], route="hr_leave"),
    policy("HRP-005", "hr_policies", "Privacy and consent", [
        "AISHA gives HR enough structured signal to offer support, not private conversation content for surveillance.",
        "Escalation cases, attribute requests, and result sharing each require their own explicit consent action.",
        "Medical documents, OCR text, diagnoses, filenames, and extracted values never enter ordinary chat or telemetry.",
        "Alyssa may delete a conversation or Validation Result through the supported resource operation.",
        "Operational telemetry is content-free and is not a product audit trail.",
    ], subareas=["privacy"], route="hr_privacy"),
    policy("HRP-006", "hr_policies", "HR escalation and attribute confirmation", [
        "Routes resolve by policy, then subarea, then topic, then the HR fallback.",
        "An Escalation Offer creates no case until the Hire approves the displayed route and summary.",
        "Attribute Change Requests contain one closed attribute and no chat transcript or free-form private reason.",
        "Only the fictional HR User view may approve or reject a pending attribute request.",
        "A Manager is a human contact and never an AISHA app role.",
    ], subareas=["escalation", "profile"], route="hr_general"),
    policy("HRP-007", "hr_policies", "Head-office dress standard", [
        "This standard applies only when Head Office is the confirmed Work Site.",
        "Alyssa's seeded Branch Work Site therefore receives a cited Does Not Apply explanation.",
        "A temporary Head Office visit may be explained abstractly without changing the Hire Profile.",
        "A permanent move remains provisional until HR approves the one-attribute request.",
        "AISHA does not invent appearance rules beyond the active policy text.",
    ], {**ALL, "work_sites": ["head_office"]}, ["dress"], "hr_general"),
]


FRONT = [
    ("Welcome and educational boundary", "AISHA is a fictional educational capstone prototype and is not affiliated with, endorsed by, or representative of BDO Unibank."),
    ("How to use this handbook", "Use stable policy IDs, handbook version, and page together. Current guidance comes only from the explicitly active immutable edition."),
    ("Three-topic scope", "The closed onboarding topics are Payroll, Resource Access, and HR Policies. Unsupported topics abstain and route to a human."),
    ("Hire attributes", "Applicability uses only role, department, employment classification, and work site from the HR-confirmed Hire Profile."),
    ("Evidence and citations", "Every material policy claim requires claim-local support from an active authoritative applicable page."),
    ("Privacy and human support", "AISHA is support, not surveillance. HR receives consented structured records rather than raw private conversations."),
]

BACK = [
    ("Glossary: policy responses", "Grounded Answer, Clarification Request, Abstention, and Escalation Offer are the four typed Dialogue outcomes."),
    ("Glossary: applicability", "Applies, Does Not Apply, and Needs Clarification are deterministic outcomes; retrieval similarity never decides eligibility."),
    ("Glossary: retrieval", "A Handbook Omission differs from a Knowledge Index Outage or integrity failure, and each fails closed with a distinct outcome."),
    ("Directory: Payroll Support", "Payroll Support is the fictional route for pay schedule, payslip, deduction, and payroll correction questions."),
    ("Directory: Access Support", "Access Support is the fictional route for accounts, devices, and other Company Resource guidance."),
    ("Directory: HR routes", "HR General, HR Leave, and HR Privacy are fictional human routes selected by policy and subarea."),
    ("Version and supersession", "Handbook v1.0 is the initial immutable edition. Only explicit supersession can establish precedence between revisions."),
    ("Official document route", "AISHA never stores or submits an original medical certificate. The separate fictional Official HR Document Route remains required."),
]


def main() -> None:
    pages = []
    for index, (title, body) in enumerate(FRONT, 1):
        pages.append({"page_key": f"front-{index:02d}", "section": "front", "kind": "directory", "title": title, "body": body})
    counters = {"payroll": 0, "resource_access": 0, "hr_policies": 0}
    for item in POLICIES:
        for index, point in enumerate(item.pop("points"), 1):
            counters[item["topic"]] += 1
            pages.append({
                "page_key": f"{item['policy_id'].lower()}-{index:02d}",
                "section": item["topic"], "kind": "policy" if index == 1 else "procedure",
                "policy_id": item["policy_id"], "policy_revision": "1",
                "topic": item["topic"], "subareas": item["subareas"],
                "title": f"{item['title']} - {index}", "body": point,
                "applicability": item["applicability"], "route": item["route"],
                "status": "active", "effective_date": "2026-08-10",
                "claim_types": ["policy"] if index == 1 else ["procedure"],
            })
    assert counters == {"payroll": 26, "resource_access": 30, "hr_policies": 38}
    for index, (title, body) in enumerate(BACK, 1):
        pages.append({"page_key": f"back-{index:02d}", "section": "back", "kind": "directory", "title": title, "body": body})
    assert len(pages) == 108
    output = Path(__file__).parents[1] / "handbook" / "source.yaml"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump({"schema_version": 1, "handbook_version": "1.0", "active": True, "pages": pages}, sort_keys=False, allow_unicode=True), encoding="utf-8")


if __name__ == "__main__":
    main()
