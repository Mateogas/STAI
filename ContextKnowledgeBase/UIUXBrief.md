# AISHA v1.0 UI/UX Brief

## Experience promise

The interface should make a narrow promise obvious: AISHA helps the fictional Hire Alyssa Reyes navigate Payroll, Resource Access, and HR Policies using synthetic evidence. It is not affiliated with BDO Unibank, and it is support—not surveillance.

Role and destination are separate controls. The Hire destinations are **Ask AISHA**, **Certificate Check**, and **History**. **HR User** exposes only structured Cases, Attribute Change Requests, and currently shared Validation Results.

## Ask AISHA

- Use a conversation-first layout with a visible three-topic boundary and fixed simulated date.
- Render Grounded Answer, Clarification Request, Abstention, and Escalation Offer as distinct, non-color-only states.
- Show evidence as policy ID, revision, handbook version, page, and artifact identity—not a raw retrieved snippet.
- Keep an escalation offer separate from consent. Explain exactly what bounded summary HR will receive before the user creates a case.
- Never present conversation text as a confirmed Hire Profile value.

## Certificate Check

- Before file selection, state: local completeness only; not authenticity, approval, medical assessment, diagnosis, or submission.
- Require acknowledgement before processing.
- Explain accepted types, 10 MB maximum, three-page PDF maximum, local extraction/OCR, and the no-result behavior for upload rejection/check failure.
- Display `Complete`, `Incomplete`, or `Needs Human Review` with text, not color alone.
- For terminal human review, show only an ephemeral blank Manual Field Summary template.
- Keep the separate fictional Official HR Document Route visible.

## History and HR

- Hire History lists ordered Policy Conversations and safe Validation Results. It supports conversation deletion and result share, revoke, and delete.
- HR must never see Policy Conversations or certificate content. Cases show consented summaries; attribute requests show one proposed field; Validation Results show only currently shared safe metadata.
- Version conflicts should produce actionable refresh guidance without raw technical errors.

## Accessibility and responsiveness

- Rehearse at desktop and 320 CSS pixels with no horizontal page overflow.
- Maintain visible keyboard focus and at least 44-pixel action targets.
- Use headings, labels, status/live regions, and meaningful empty states.
- Do not encode applicability, consent, share, or validation state by color alone.
- Keep primary actions in logical keyboard order and avoid hover-only instructions.

## Demo sequence

1. Open Ask AISHA as Alyssa and ask PAY-001.
2. Show a grounded answer, an unsupported abstention, and the ACC-006 unknown-Work-Site clarification.
3. Offer a human route, prove no HR case exists, then consent and close the case from HR.
4. Request and decide one Work Site profile change.
5. Acknowledge Certificate Check, upload the synthetic labelled PDF, and show `Complete`.
6. Share the safe result, view it in HR, revoke, then delete.
7. Open API docs and the integrated acceptance report.

The UI and API must express the same domain outcomes. A visually successful demo cannot override a failed privacy, consent, evidence, or acceptance gate.
