# AISHA Onboarding Support

AISHA is a fictionalized educational onboarding assistant that gives new hires
grounded guidance within a deliberately narrow policy scope while routing
unsupported questions to a human owner.

## Language

### People and applicability

**Hire**:
The fictional employee receiving onboarding guidance from AISHA.
_Avoid_: End user, associate, subject

**Hire Attribute**:
A Hire's role, department, Employment Classification, or Work Site when used
to determine whether an Onboarding Policy applies directly to that Hire.
_Avoid_: Hire Persona, user segment, access role

**Hire Profile**:
The HR-confirmed current record of the Hire Attributes used for Policy
Applicability; conversation memory is not authoritative profile state.
_Avoid_: Chat memory, inferred profile, Hire Persona

**Attribute Claim**:
A provisional Hire statement that a Hire Attribute may differ from the Hire
Profile; it cannot change Policy Applicability until HR confirms it.
_Avoid_: Profile update, verified fact, memory preference

**Attribute Change Request**:
A Hire-approved request for an HR User to confirm or reject one proposed Hire
Attribute change without retaining the private conversation that prompted it.
_Avoid_: Automatic profile mutation, chat export, Escalation Case

**Hire Attribute Revision**:
An HR-confirmed replacement of one Hire Attribute in the Hire Profile, retaining
the previous value, new value, confirming HR User, and effective timestamp.
_Avoid_: Chat-memory update, inferred attribute, document extraction

**Role Key**:
The closed, normalized identifier for a Hire's job function when evaluating
Policy Applicability: Branch Banking Associate, Client Service Associate, or
Digital Banking Support Associate. A display title or program label is not
authoritative.
_Avoid_: Display role, job-description text, Hire Persona

**Department Key**:
The closed, normalized identifier for the organizational area used in Policy
Applicability: Branch Banking, Branch Operations, or Digital Channels. Its
human-readable department label is display-only.
_Avoid_: Department label, team name, free-text department

**Employment Classification**:
The non-sensitive category describing the Hire's employment arrangement for
policy-applicability purposes. Its closed values are Probationary, Regular,
and Fixed Term.
_Avoid_: Hire Persona, performance status

**Work Site**:
The Hire's branch, head-office, or remote assignment category for
policy-applicability purposes. Its closed values are Branch, Head Office, and
Remote.
_Avoid_: Live location, attendance tracking

**HR User**:
A fictional HR staff member who uses AISHA's HR view to see privacy-safe
support information and act on Escalation Routes.
_Avoid_: Manager, administrator, supervisor

**Manager**:
A Hire's human people leader and possible escalation contact; a Manager is not
an AISHA app role in the current product scope.
_Avoid_: HR User, support-view user

**Onboarding Buddy**:
A human relationship that provides social and mentorship support beyond
policy answers; AISHA does not replace this human role outside its three topics.
_Avoid_: AI buddy, bot buddy

### Policy knowledge

**Onboarding Topic**:
One of exactly three supported policy areas: Payroll, Resource Access, or HR
Policies. This is a closed product-scope taxonomy.
_Avoid_: Knowledge category, department

**Policy Subarea**:
An organizational tag within an Onboarding Topic, such as attendance, leave,
office hours, or dress within HR Policies; it does not expand product scope.
_Avoid_: Topic, policy category

**Onboarding Policy**:
The smallest authoritative unit in the synthetic handbook, identified by a
stable policy ID, belonging to exactly one Onboarding Topic, and explicitly
scoped by its applicability rules.
_Avoid_: Document chunk, answer

**Procedure**:
An ordered sequence of guidance belonging to exactly one Onboarding Policy; it
is distinct from the authoritative policy and any Company Resource it references.
_Avoid_: Policy, answer, workflow implementation

**Company Resource**:
A system, account, device, facility, or information asset referenced by
Resource Access policies and procedures; AISHA neither provisions it nor
tracks its real access state, and multiple policies may reference it.
_Avoid_: Person, policy source, handbook document

**Philippine Public Holiday Calendar**:
External calendar context listing Philippine public-holiday names and dates for
the current and following year; it is never an Onboarding Policy or authority
for eligibility, pay, leave, or procedure.
_Avoid_: Holiday Policy, payroll calendar, official company schedule

**External Calendar Attribution**:
The concise statement "Based on Nager." shown with facts from the Philippine
Public Holiday Calendar; it is distinct from a Policy Citation, while retrieval
and cache metadata remain internal.
_Avoid_: Policy Citation, handbook source, official-company citation

**Calendar Conflict**:
A mismatch between a holiday date from the Philippine Public Holiday Calendar
and the Active Policy Revision; AISHA identifies the mismatch and makes no
date-dependent policy conclusion until a human resolves it.
_Avoid_: Policy Conflict, silent override, calendar correction

**Holiday Calendar Result**:
The validated outcome of a Philippine Public Holiday Calendar lookup: live,
cached, or unavailable, with calendar facts and External Calendar Attribution
when available; it never states an employment consequence.
_Avoid_: Policy Response, Policy Citation, holiday-pay decision

**Policy Applicability**:
The deterministic result of evaluating an Onboarding Policy against allowed
Hire Attributes for the current Hire: Applies, Does Not Apply, or Needs
Clarification. AISHA may explain a rule abstractly but does not produce a
personalized result for another person or hypothetical Hire.
_Avoid_: Persona match, semantic relevance, model inference

**Applicability Snapshot**:
The retained Policy Applicability used for one validated Policy Response,
identified by its Policy Revision, Hire Profile revision, and handbook version.
_Avoid_: Global applicability state, applicability cache, current profile

**Applicability Rule**:
An explicit four-attribute constraint in which each Hire Attribute allows all
values or a closed set; values are ORed within an attribute and attributes are
ANDed together, with no separate exclusion rule. `all` is rule syntax, never a
stored Hire Attribute value; missing data is absent rather than stored as
`unknown`.
_Avoid_: Semantic filter, inferred audience, exclusion override

**Applicability Ambiguity**:
Missing or contradictory Hire Attributes that constrain the policy and prevent
a deterministic Policy Applicability result; attributes allowed as `all` are
irrelevant, and AISHA never asks for an attribute it already knows.
_Avoid_: Low retrieval score, model uncertainty, persona mismatch

**Active Handbook Version**:
The one explicitly published handbook version AISHA treats as current; every
new answer uses only its Policy Revisions until a newer version is activated.
_Avoid_: Latest file, simulated-date version

**Policy Revision**:
The effective form of an Onboarding Policy in one handbook version, retaining
the policy's stable identity while recording its version, effective date, and pages.
_Avoid_: Document chunk, file version

**Active Policy Revision**:
The Policy Revision belonging to the Active Handbook Version; older or future
revisions are not used as current guidance for a new answer.
_Avoid_: Most recently retrieved chunk, newest file

**Handbook Page Record**:
The immutable retrievable representation of exactly one generated handbook page,
sharing its policy, version, page identity, applicability, authority, and content identity.
_Avoid_: Document chunk, source file, free-form embedding record

**Handbook Omission**:
The confirmed absence of a relevant policy from the authoritative Active Handbook
Version; an empty or failed retrieval alone does not establish it.
_Avoid_: No search result, Knowledge Index Outage, unsupported guess

**Knowledge Index Outage**:
An operational state in which the Active Handbook Version cannot be searched or
its indexed records cannot be trusted; it is distinct from a Handbook Omission.
_Avoid_: No policy exists, empty answer, Handbook Omission

**Active Retrieval Build**:
The one verified Knowledge Index build currently serving the Active Handbook
Version; staged, archived, evaluation, and rollback builds are not active.
_Avoid_: Latest collection, collection name, cached retriever

**Policy Conflict**:
Two applicable Active Policy Revisions that prescribe incompatible guidance
without an explicit superseding relationship; AISHA identifies both and abstains.
_Avoid_: Model tie-break, silent override

**Policy Citation**:
The policy ID, handbook version, and page reference supporting a factual claim
in an AISHA response, drawn from the exact retrieved Policy Revision.
_Avoid_: Source filename alone, Chroma chunk, reference link

**Policy Claim**:
An atomic factual statement about a policy, procedure, Company Resource, or
Escalation Route that requires exact retrieved support.
_Avoid_: Answer paragraph, conversational statement, model inference

**Claim Support**:
The validated relationship between one Policy Claim and the exact retrieved
Active Policy Revision evidence identified by its Policy Citation.
_Avoid_: Related source, appended citation, semantic similarity alone

**Evidence Sufficiency**:
The internal determination that eligible retrieved evidence covers a Policy
Claim strongly enough to state it; it never determines Policy Applicability.
_Avoid_: Retrieval score, eligibility, model confidence

**Version Disclosure**:
The concise statement "Based on AISHA Handbook v{version}" shown with grounded
policy guidance; it identifies the basis without adding a general warning.
_Avoid_: Version warning, currency disclaimer

**Grounded Answer**:
An answer whose every factual policy claim maps to retrieved Policy Citations
from the Active Handbook Version; unsupported claims are omitted or abstained
from rather than paired with invented or unrelated citations.
_Avoid_: Best-effort answer, likely answer

**Policy Response**:
The outcome of a Hire's policy conversation: a Grounded Answer, Clarification
Request, Abstention, or Escalation Offer, tied to the Active Handbook Version.
_Avoid_: Free-form answer, unvalidated chat response

**Policy Conversation**:
An AISHA-managed sequence of a Hire's policy messages and validated Policy
Responses; it remains Hire-private unless the Hire explicitly links it to a
Case Thread, while certificate contents always belong to a Medical Certificate Check.
_Avoid_: Client-supplied history, certificate submission, implicit HR transcript

**Abstention**:
A Policy Response that withholds a conclusion because required support or a
resolvable interpretation is unavailable, while stating the safe known boundary.
_Avoid_: Guess, generic refusal, unsupported answer

**Clarification Request**:
One focused question used to resolve intent or Applicability Ambiguity before
AISHA states a policy conclusion or creates an Escalation Case.
_Avoid_: Guess, generic follow-up, interrogation

**Resource Guidance**:
An explanation of the simulated process, requirements, and owner for gaining a
Company Resource; it never provisions, changes, or confirms access in a real
system.
_Avoid_: Access provisioning, integration

**Escalation Route**:
The appropriate fictional owner and contact channel selected from a
policy-specific route, Policy Subarea route, Onboarding Topic route, then HR fallback.
_Avoid_: Agent handoff, support ticket

**Escalation Offer**:
A preview of the selected Escalation Route and privacy-safe proposed summary;
it creates no Escalation Case until the Hire explicitly approves that summary.
_Avoid_: Automatic escalation, Escalation Case, hidden handoff

**Escalation Case**:
A stored request for human help created only after the Hire explicitly agrees;
it retains the Hire-approved summary, route, lifecycle, and its Case Thread,
but never certificate or medical-document contents.
_Avoid_: Escalation Route, automatic alert, chat export

**Case Thread**:
The shared conversation nested beneath the Policy Conversation that produced an
Escalation Case; after explicit consent it contains the parent history, future
parent messages while the case is open, HR replies, and case status updates.
_Avoid_: Private Policy Conversation, HR internal notes, separate support chat

**Parent Conversation Sharing Consent**:
The Hire's explicit agreement that creating an Escalation Case copies the parent
Policy Conversation into its Case Thread and mirrors future parent messages until
the case closes.
_Avoid_: One-message summary consent, permanent HR transcript access, implicit sharing

**Case Update**:
A Hire-visible message in a Case Thread authored by the Hire, AISHA, or an HR User;
HR-only working notes are not Case Updates.
_Avoid_: Private HR note, telemetry event, Policy Response

**Case Notification**:
A durable unread signal that a Case Thread was created or received a Hire-visible
update; it can later be delivered by an external notification channel.
_Avoid_: Ephemeral toast, raw chat alert, telemetry record

### Document validation and evaluation

**Absence Medical Certificate**:
A document presented to support an ordinary sickness-related absence or rest
period; fit-to-work, return-to-work, prescriptions, test results, and clinical records are different document types.
_Avoid_: Medical document, fit-to-work certificate, clinical record

**Medical Certificate Check**:
A local completeness and consistency check of an Absence Medical Certificate;
it first asks for a clearer image or original PDF when OCR confidence is too
low, and it never authenticates the document or makes a medical judgment.
_Avoid_: Medical verification, certificate approval

**Certificate Validation Requirements**:
The structured required-field and consistency rules declared by the applicable
Active Policy Revision; they exclude diagnosis, symptoms, treatment, and medication.
_Avoid_: LLM checklist, hardcoded field list, clinical requirements

**Extraction Ambiguity**:
Two different values that remain equally plausible for one required field after
label association and normalization; AISHA cannot choose between them.
_Avoid_: OCR error, highest-confidence winner, guessed value

**Upload Rejection**:
A refusal before validation because an uploaded file violates the accepted
type, size, structural, or safety envelope; it is not a Validation Result.
_Avoid_: Incomplete, Needs Human Review, Check Failure

**Check Failure**:
An operational failure in AISHA's local validation path rather than a judgment
about the certificate; it produces no Validation Result.
_Avoid_: Needs Human Review, Upload Rejection, invalid certificate

**Document Fingerprint**:
An installation-local HMAC-SHA-256 identifier for byte-identical upload
deduplication within the same Hire, policy version, and Hire Profile revision;
it is neither document authenticity evidence nor a user-visible value.
_Avoid_: File hash, authenticity proof, fraud signal

**Official HR Document Route**:
The separate company-controlled process that receives and retains an original
certificate for HR; AISHA may point to it but never stores, transmits, or confirms submission.
_Avoid_: AISHA upload storage, Validation Result, Escalation Case

**Validation Result**:
The retained outcome of a Medical Certificate Check: Complete, Incomplete, or
Needs Human Review, with missing fields, warnings, Policy Citations, timestamp,
and a non-reversible file fingerprint. A failed OCR retry produces Needs Human Review.
_Avoid_: Medical record, OCR record

**Result Share**:
A Hire's explicit permission for an HR User to view result-only validation
metadata; it never grants access to the certificate, OCR text, or fingerprint.
_Avoid_: Automatic HR visibility, document sharing, Escalation Case

**Manual Field Summary**:
An optional, ephemeral summary produced from fields the Hire pastes after an
OCR retry fails; it may aid HR review but cannot change the Validation Result
from Needs Human Review or replace submission through the Official HR Document Route.
_Avoid_: Validation Result, transcribed certificate, medical record

**Composite Safety Score**:
A conservative weighted-harmonic benchmark summary across grounding, retrieval,
applicability, dialogue safety, medical validation, and external calendar behavior;
it cannot override a failed safety-critical requirement.
_Avoid_: Accuracy, hallucination rate

**Benchmark Case**:
A frozen synthetic scenario with declared inputs, expected typed outcome,
permitted evidence and actions, and privacy-safe scoring expectations.
_Avoid_: Test prompt, demo question, production conversation

**Safety-Critical Case**:
A Benchmark Case whose protected citation, consent, privacy, applicability,
medical, or external-tool boundary must pass completely regardless of aggregate scores.
_Avoid_: High-weight case, optional edge case, average-score penalty

**Calibration Partition**:
The declared subset of Benchmark Cases used to choose retrieval thresholds and
other tunable settings before final evaluation.
_Avoid_: Training data, acceptance set, hidden test set

**Locked Acceptance Partition**:
The frozen subset of Benchmark Cases not used for tuning and evaluated only
after the candidate prompt and settings are fixed.
_Avoid_: Calibration set, development results, production proof

**Prompt Variant**:
One frozen AISHA prompting strategy compared under the same model, handbook,
index, tools, cases, and runtime settings.
_Avoid_: Model variant, configuration drift, prompt revision during evaluation

**Module Acceptance Claim**:
A declaration that one course module is Met only when final code, passing
automated tests, current documentation, a live-demo step, and a named owner agree.
_Avoid_: Partial credit, legacy evidence, planned capability

**Operational Telemetry Record**:
A privacy-safe account of one AISHA operation using closed outcomes, counts,
durations, and non-sensitive version identities rather than user or content data.
_Avoid_: Audit log, conversation record, Escalation Case, Validation Result

**Telemetry Outcome**:
The closed operational result category of an AISHA operation; it describes
system behavior without reproducing the policy answer, document, or user action content.
_Avoid_: Answer text, free-form error, case summary

**Telemetry Error Category**:
A closed privacy-safe classification of where and why an operation failed,
without raw exception text, paths, endpoints, payloads, or extracted content.
_Avoid_: Exception message, failure transcript, diagnostic dump

**Full Demo Reset**:
A deliberate return of the fictional AISHA installation to its seeded Alyssa
and verified-handbook baseline, removing product state and derived caches.
_Avoid_: User deletion, schema migration, MLflow erasure
