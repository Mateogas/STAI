# Open Questions

These are product and scope questions that future chats should grill before
making large changes.

## Question 1 - What is the main demo promise?

Should the live demo be judged by:

1. "It answers handbook questions," or
2. "HR catches a struggling new hire before they quit"?

Recommended answer:

Use the second promise. Handbook Q&A is the functional base, but the early
warning loop is the reason the product matters.

## Question 2 - How strict should "Tool Use" be?

The current app has strong internal tools, but the course checklist describes
external tools/APIs as examples.

Recommended answer:

Ask the instructor if internal state-changing tools count. If not, add one
small external or external-like tool only if it strengthens the story. Do not
bolt on weather/search just to tick a box.

Possible story-aligned additions:

- calendar/scheduling mock for intro chats,
- email/Slack mock for HR escalation routing,
- HRIS mock endpoint for employee lookup.

## Question 3 - Is persistent chat memory worth doing before UI polish?

Recommended answer:

Yes, if time allows after API/LLMOps/Docker. It makes the Memory module much
more defensible and also helps the API endpoint feel like a real product.

## Question 4 - Should the story stay with Meridian Labs or move to a real local enterprise anchor?

Decision:

Use BDO directly as the recognizable business-context anchor, with a clear
educational/fictional disclaimer. The presentation can use BDO because it is a
large, publicly recognizable, process-heavy Philippine enterprise where the
onboarding problem is easy to understand. The demo should still use fictional
employee names, fictional internal HR documents, fictional org contacts, and
fictional onboarding metrics.

Do not imply access to BDO internal HR systems or private onboarding data. If
the app data is renamed later, explicitly label it as fictionalized BDO demo
data for educational storytelling, not official BDO data.

Required disclaimer:

"AISHA is an educational capstone prototype. It is not affiliated with,
endorsed by, or representative of BDO Unibank. All employee records, onboarding
documents, org contacts, metrics, and demo interactions are fictionalized for
storytelling and evaluation purposes."

## Question 5 - What should be cut if time gets tight?

Recommended answer:

Do not cut API, LLMOps, Docker, or evaluation docs because they are explicit
requirements. Cut deep UI polish or SQL Agent ambitions first.

## Question 6 - Who is the main new-hire protagonist?

Decision:

Use an intern or early-career non-engineering hire in a BDO-style Philippine
banking environment. The strongest protagonist is a fresh graduate joining a
branch operations, customer service, or relationship-associate track rather
than a software engineer.

Reason:

This makes the story more relatable for a Philippine capstone audience and
better fits the onboarding problems STAI is meant to expose: contract signing,
payroll, benefits, branch or head-office assignment, IT access, compliance
training, customer service standards, manager check-ins, workplace etiquette,
and first-week overwhelm. The employee should feel capable but hesitant to ask
"basic" questions, which makes the safe companion plus HR early-warning loop
matter.

## Question 7 - What is the central struggle signal HR catches?

Decision:

Make the risk signal early overwhelm caused by fragmented onboarding,
unclear ownership, low psychological safety, and fear of asking for help. The
story should not imply that payroll, benefits, branch assignment, or policy
questions are intellectually hard. A capable new hire can understand those
topics, especially with modern AI and internal help centers. The harder
business problem is coordination and silence: many small unresolved blockers
compound across systems, people, deadlines, manager expectations, compliance
training, and team belonging.

In the Philippine banking story, frame this with cultural empathy: a fresh
graduate or provincial early-career hire may hesitate to ask for help because
they do not want to look incompetent, be judged as "bida-bida," or disrupt
group harmony.

Use this carefully as a human-centered product insight, not as a stereotype.
The point is not "Filipinos are shy" and not "new hires cannot answer simple
questions." The point is that many early-career employees, especially in
hierarchical and process-heavy workplaces, need a safe private channel before
they are comfortable surfacing uncertainty, blocked progress, or social
disconnection to a manager or HR.

Narrative anchors:

- Filipino cultural concepts such as hiya, pakikisama, and pakikiramdam help
  explain why a new hire may avoid asking "obvious" questions in public.
- Workplace research on psychological safety and employee silence supports the
  broader claim that people often withhold questions, concerns, or mistakes
  when they fear embarrassment, judgment, or negative consequences.
- A BDO-style bank setting strengthens this because banks are naturally
  hierarchical, compliance-heavy, customer-facing, and process-driven.

Concrete demo signal:

By week 2, the new hire has a cluster of small unresolved blockers: one system
access issue, uncertainty about what "good performance" looks like, a delayed
manager check-in, missed context from compliance training, and weak connection
with the buddy or team. Avoid making every risk message about "nahihiya."
Hesitation to ask questions is one possible signal, but not the only one.

Other plausible signals:

- The employee is an intern or student balancing classes, thesis, commute,
  family obligations, or part-time work.
- The employee starts well, then task completion slows sharply.
- A role-specific requirement takes much longer than the cohort norm.
- The employee repeatedly asks about the same workflow, suggesting unresolved
  context rather than lack of intelligence.
- The employee has not had a manager or buddy check-in within the expected
  onboarding window.
- The employee's pulse replies trend from confident to vague, delayed, or
  low-energy.

STAI should translate that into an HR dashboard signal such as: declining
sentiment, concerns tagged as workload/confusion/connection/access, and a
recommended low-pressure manager or buddy check-in.

Trend framing:

For the story, use synthetic internal benchmarks rather than public universal
claims. Example: "Most branch associate interns complete Day 1 access setup
within 24 hours and compliance module 1 within 3 days. This employee took twice
as long and also reported low confidence in week 2." This demonstrates
agentic/stateful capability without pretending there is a public industry
standard for every onboarding task.

Agentic framing:

Simple policy Q&A alone does not justify an agentic AI solution. The agentic
claim is that STAI retrieves grounded policy context, reads and updates the
employee's onboarding state, identifies the right human owner, remembers
progress across turns, compares progress to role/cohort expectations, initiates
pulse check-ins, classifies risk signals, and routes a human-in-the-loop
intervention to HR. The value is the closed support loop, not the fact lookup.

## Question 8 - Should risk detection be based on words or behavior?

Decision:

Use both, but make behavior over time the killer point. What the employee says
in chat or pulse replies gives context and consentful emotional color. What the
employee does over time makes the product meaningfully agentic: delayed task
completion, repeated blockers, unresolved access issues, missed manager or
buddy touchpoints, declining pulse scores, and divergence from role/cohort
expectations.

Narrative rule:

Do not make the system sound like it is diagnosing attrition from one sad
message. The stronger claim is that STAI maintains state, watches trends, and
helps HR notice a pattern while the intervention can still be small and humane.

## Question 9 - Should HR intervention feel like surveillance or support?

Decision:

Frame STAI strictly as support, not surveillance. The narrative must treat
employee privacy and psychological safety as core product requirements, not
afterthoughts. HR should not be positioned as reading every private chat or
monitoring the employee minute by minute.

What HR should see:

- task and milestone delays,
- unresolved blockers,
- missed manager or buddy touchpoints,
- pulse score trends,
- broad concern tags,
- concise rationale,
- suggested support action.

What HR should not see by default:

- full private chat transcripts,
- sensitive personal details,
- raw venting,
- speculative personality judgments,
- punitive labels such as "flight risk" or "poor performer."

Preferred wording:

"STAI gives HR enough signal to offer help, not enough detail to police the
employee."

The intervention should be humane and low-pressure: manager/buddy check-in,
clearer expectations, access unblock, workload adjustment, or a supportive HR
conversation.

## Question 10 - Should business value lead with retention or time-to-ramp?

Decision:

Lead with faster productivity/time-to-ramp. Retention and attrition prevention
remain important secondary outcomes, but the sharper business value is helping
new hires become productive sooner in a large, process-heavy bank.

Why:

Time-to-ramp is easier to visualize, measure, and defend in the demo: role-based
milestones, access completion, compliance modules, manager/buddy touchpoints,
and task completion trends. Retention is still the long-term executive upside,
but it should not be the only promise because it can sound dramatic and harder
to prove from a short prototype.

Positioning:

"STAI helps a large bank reduce onboarding drag: new hires unblock themselves
faster, managers see where support is needed, and HR gets trend signals before
small delays become disengagement."

Belonging:

Treat belonging as a supported leading indicator, not the sole KPI. STAI can
support belonging by nudging buddy/manager check-ins, helping the hire identify
the right human owner, encouraging low-pressure introductions, and tracking
whether those touchpoints happen. It should measure belonging indirectly through
pulse tags, check-in completion, connection milestones, repeated isolation
signals, and qualitative self-reports.

## Question 11 - Who benefits from STAI?

Decision:

Position STAI as a three-sided support loop rather than a tool for only HR,
only managers, or only new hires.

- New hires benefit through a safe guide, clearer next steps, faster unblocking,
  and stronger belonging.
- Managers benefit through less repetitive onboarding coordination, clearer
  blocker visibility, and better-timed check-ins.
- HR benefits through onboarding health trends, support queues, and earlier
  intervention signals.
- The organization benefits through reduced onboarding drag, faster
  time-to-ramp, increased productivity, lower support workload, and better
  employee welfare.

Preferred framing:

"STAI helps everyone spend less time guessing what is wrong and more time
helping the new hire ramp."

## Question 12 - What is the product name?

Decision:

Use AISHA as the front-facing product name. STAI may remain the repo/course
codename if needed, but the business narrative, demo script, and slides should
present the product as AISHA.

Preferred expansion:

AISHA = AI Support for Hires and Associates.

Positioning:

AISHA is a local-first agentic onboarding system for large, process-heavy
organizations. It helps new hires ramp faster, helps managers spot blockers
earlier, and helps HR support onboarding without turning the experience into
surveillance.

## Question 13 - Should the code/data remain Meridian/Maya or be fully rebranded?

Decision:

Finalize the story spine first, then fully rebrand the demo from
Meridian/Maya/Meri to BDO/AISHA. The final presentation and demo should not
contain leftover Meridian or Maya framing.

Scope for later implementation pass:

- app copy and page title,
- assistant persona name,
- employee seed data,
- org directory,
- onboarding plan templates,
- HR knowledge-base documents,
- guardrail and agent prompts,
- README/demo script/business-case docs,
- tests that assert old names or old role assumptions.

Constraint:

All BDO-specific data must remain clearly fictionalized and covered by the
educational disclaimer. Do not imply access to real BDO employee records,
private policies, internal tools, or HR systems.

## Question 14 - Who is the main demo employee?

Decision:

Use Alyssa Reyes as the main demo employee.

Profile:

- Name: Alyssa Reyes
- Role: Management Trainee / Branch Banking Associate
- Setting: fictionalized BDO onboarding demo
- Career stage: fresh graduate or early-career hire

Why:

Alyssa is more relatable than the previous software-engineer framing and fits
the BDO story. Her role naturally supports measurable ramp signals: system
access, compliance training, branch operations shadowing, customer interaction
standards, manager check-ins, buddy meetings, and first performance
milestones. She should be portrayed as capable, not helpless; the friction is
coordination, context, confidence, and fragmented onboarding.
