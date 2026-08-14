# AISHA v1.0 UI/UX Brief

## Experience promise

The interface should make a narrow promise obvious: AISHA helps the fictional Hire Alyssa Reyes navigate Payroll, Resource Access, and HR Policies using synthetic evidence. It is not affiliated with BDO Unibank, and it is support—not surveillance.

Role and destination are separate controls. The Hire destinations are **Ask AISHA**, **Certificate Check**, and **History**. **HR User** exposes only structured Cases, Attribute Change Requests, and currently shared Validation Results.

## Ask AISHA

- Use a conversation-first layout with a visible three-topic boundary and fixed simulated date.
- Render Grounded Answer, Clarification Request, Abstention, and Escalation Offer as distinct, non-color-only states.
- Show evidence as policy ID, revision, handbook version, page, and artifact identity—not a raw retrieved snippet.
- Keep an escalation offer separate from consent. Explain that creating the case shares the parent conversation's existing history and future messages with HR until the case closes.
- Offer HR only when the UI can show the supported handbook portion and name the material Evidence Gap. A bare request for HR, an unsupported subject, or a system outage must not create an offer.
- Never present conversation text as a confirmed Hire Profile value.
- List reopenable Policy Conversations in the left rail. Nest each HR Case Thread beneath its originating conversation with unread count and text status such as Waiting for HR, Waiting for Hire, or Resolved.
- While a parent conversation is feeding an open case, show a persistent sharing banner in both the parent and Case Thread. The thread keeps the current AISHA visual language rather than becoming a separate ticketing-app theme.

## Certificate Check

- Before file selection, state: local completeness only; not authenticity, approval, medical assessment, diagnosis, or submission.
- Require acknowledgement before processing.
- Explain accepted types, 10 MB maximum, three-page PDF maximum, local extraction/OCR, and the no-result behavior for upload rejection/check failure.
- Display `Complete`, `Incomplete`, or `Needs Human Review` with text, not color alone.
- For terminal human review, show only an ephemeral blank Manual Field Summary template.
- Keep the separate fictional Official HR Document Route visible.

## History and HR

- Hire History lists ordered Policy Conversations and safe Validation Results. It supports conversation deletion and result share, revoke, and delete.
- HR sees only the copied content in consented Case Threads, never a direct browser for unrelated Policy Conversations or any certificate content. Cases show HR-visible replies and status; HR-only notes remain hidden from the Hire. Attribute requests show one proposed field; Validation Results show only currently shared safe metadata.
- A Hire can reply directly in the Case Thread or continue the parent conversation. While the case is open, both the Hire's and AISHA's new parent messages appear in the Case Thread. Resolution posts a visible summary, marks the nested thread Resolved, and stops mirroring.
- HR resolution requires a Resolution Type and Resolution Scope. Only a non-case-only Policy Clarification can be proposed for reuse, and a separate review action must approve it.
- A resolved Case Thread keeps a dedicated “Ask AISHA about this HR resolution” input. Answers must identify Case Resolution Memory and reject unrelated questions back to the parent policy conversation.
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
3. Ask for the unspecified official payroll route, show the supported policy plus Evidence Gap, prove a bare human request cannot bypass eligibility, consent after the sharing notice, continue the parent conversation, resolve with type/scope, and ask one related resolved-thread follow-up.
4. Propose an Organization-wide Policy Clarification, approve it in the demo policy-owner review, then show a later policy answer with separate handbook and HR-clarification evidence.
5. Request and decide one Work Site profile change.
6. Acknowledge Certificate Check, upload the synthetic labelled PDF, and show `Complete`.
7. Share the safe result, view it in HR, revoke, then delete.
8. Open API docs and the integrated acceptance report.

The UI and API must express the same domain outcomes. A visually successful demo cannot override a failed privacy, consent, evidence, or acceptance gate.
