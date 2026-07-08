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

## Question 4 - Should the story stay with Meridian Labs or move to P&G?

Recommended answer:

Move the presentation story to a P&G-style setting if the goal is a more
relatable, sellable narrative. Keep the code's fictional Meridian Labs data
unless there is time to safely rename the synthetic dataset. The story can say
"imagine this deployed at P&G" without requiring a full data migration.

## Question 5 - What should be cut if time gets tight?

Recommended answer:

Do not cut API, LLMOps, Docker, or evaluation docs because they are explicit
requirements. Cut deep UI polish or SQL Agent ambitions first.
