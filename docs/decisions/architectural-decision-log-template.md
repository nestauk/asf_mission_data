## **ADL-NNN: Decision title**

*How to use this template: save a copy as a Markdown file named with the ADL ID and a short title, e.g. `adl-007-pipeline-orchestration.md`. Replace every italic instruction with your own content, and delete any that remain before the status moves to AGREED. Keep all headings exactly as they are, even if a section is short, so that people and tools can find each section. For LOW impact decisions, keep every section brief.*

*Title: a short phrase naming what is being decided, for example "Orchestration for ASF Policy pipelines"*

| Field | Value |
| :---- | :---- |
| ADL ID | *The next unused number, in the form ADL-NNN. Never reuse a number, even for a rejected decision.* |
| Status  | AGREED PROPOSED REJECTED SUPERSEDED    *The current state of this decision. PROPOSED (still under discussion); AGREED (approved and in effect); REJECTED (considered and not adopted); SUPERSEDED (replaced by a later decision \- add a link to the new ADL). Update this field if the decision changes rather than deleting the log* |
| Impact  | HIGH MEDIUM LOW   *How significant this decision is, based on how costly it would be to reverse and how widely it is felt. LOW (easy to reverse, affects a single project), MEDIUM (some rework to reverse, or affects several systems or teams/missions), or HIGH (costly or slow to reverse, or affects shared infrastructure, multiple teams/missions, or delivery timelines)* |
| Approver  | *One person accountable for signing off this decision. Name a single person, not a team e.g Jack Vines, not Data Engineering* |
| Contributors  | *The people who worked on the decision itself: researching and evaluating the options, taking part in design discussions, or reviewing the recommendation before approval. Include the approver if they contributed. This tells future readers who to ask about the reasoning behind the choice* |
| Informed | *People who need to know the outcome but were not involved in making it, such as stakeholders, downstream teams, or line managers. Make sure they are notified once the status is AGREED* |
| Decision date  | *The date the decision was approved, meaning the status moved to AGREED, in the format DD Mon YYYY. Leave this blank while the status is PROPOSED* |
| Supersedes | *The ID of the earlier ADL this decision replaces, or "None". If it replaces one, also set that ADL's status to SUPERSEDED and fill in its Superseded by field.* |
| Superseded by | *"None" for now. If a later ADL replaces this one, add its ID here and change the status to SUPERSEDED.* |
| Recommendation  | *The decision itself, in one sentence. Describe the chosen approach or technology, not the implementation details. Someone should be able to understand it without reading the rest of the document. Example: "AWS-native orchestration using managed, ephemeral compute services"* |
| Justification  | *Why this option was chosen over the alternatives, in one to three sentences. Name the main constraints or requirements that drove the choice, such as scale, complexity, timeline, cost, or team skills, and explain how this option meets them. The full comparison of options belongs in the body of the document, not here* |
| Validity  | *The conditions under which this decision should be revisited. Give concrete, observable triggers, such as growth in data volume or pipeline count, a new requirement, or a dependency becoming available. A review date also works. Avoid open-ended wording like "until further notice." The point is to tell future readers when this decision might stop holding* |

## **Background**

*Explain the situation that made this decision necessary, so that someone new to the project understands why it was needed. Describe the problem, not the solution: the options and the recommendation belong in later sections. A few short paragraphs is usually enough.*

***Current state.** What exists today and where it falls short.*

***Requirements.** The main needs any solution must meet, and where they came from (for example, user interviews or a team request). The full list goes in the Requirements section.*

***Why now.** The risks of doing nothing or waiting.*

***Wider context.** How this decision connects to team or organisational goals and principles. Write "None" if it doesn't.*

## **Requirements**

*Give every requirement a short ID: R1, R2… for business/technical requirements and O1, O2… for operational and team requirements. These IDs are reused in the comparison matrix, the option notes and the Validity field, so keep names short and don't renumber once the ADL has been shared.*

### **Business/technical requirements**

*List what the solution must do: the requirements the options will be judged against. Give each one a short name, a description specific enough to check an option against, and a priority: Must, Should, Could or Won't. Include Won't items so the scope is clear. Combine closely related needs into a single row, and settle every priority before the status moves to AGREED. For LOW impact decisions, list only the requirements that separate the options.*

| ID | Name | Description | Priority |
| :---- | :---- | :---- | :---- |
| *R1* | *Short name* | *What the solution would do, specific enough to check an option against* | *Must, Should, Could, Won’t* |
| *R2* |  |  |  |
| *R3* |  |  |  |

###

### **Operational and team requirements**

*List the requirements about cost, effort, skills and day-to-day running, as opposed to what the system must do. Give a measurable target where you can, such as a monthly cost limit or a time to first working pipeline. If you can't estimate a number, describe the expectation in words rather than leaving a blank.*

| ID | Name | Description | Priority |
| :---- | :---- | :---- | :---- |
| *O1* | *Short name* | *The expectation, ideally with a measurable target* | *Must, Should, Could, Won’t* |
| *O2* |  |  |  |
| *O3* |  |  |  |

## **Options considered**

*List every option seriously considered, including the current approach if keeping it was a realistic choice. Give each option a letter and a short name (A, B, C…), and use exactly those names everywhere else in the document. For each, write two or three sentences: what it is and how it would be used here. Keep every description about the same length, including the recommended option's; implementation detail belongs in the Decision section. Aim for the whole section to fit on about a page plus the matrix, and put deeper research in a linked note.*

### **A. Option name.**

*Two or three sentences: what it is and how it would be used here.*

### **B. Option name.**

*Two or three sentences: what it is and how it would be used here.*

### **C. Option name.**

*Two or three sentences: what it is and how it would be used here.*

### **Also considered, not assessed in detail**

*One line per option ruled out early: its name and the reason it was dropped, ideally the requirement it clearly fails. Write "None" if there were none.*

* *Option name: the reason it was dropped.*

### **Comparison against requirements**

*Rows: every Must and Should requirement from both tables, using the same ID and name. Add a Could requirement only if it separates the options. Columns: exactly the options listed above. In each cell, write Meets, Partly or Doesn't meet, followed by a note of no more than 10 words. Where a requirement has a measurable target, such as cost or effort, put your estimate in the cell. Fill every cell: if you don't know, write "Unknown" and say in the option notes how you'd find out. Mark "Doesn't meet" against a Must as "(knock-out)". Don't add scores, weights or totals, and don't write paragraphs in cells.*

| Requirement | Priority | A. Option Name | B. Option Name | C. Option Name |
| :---- | :---- | :---- | :---- | :---- |
| *R1 Name* | *Must* | *Meets: short note* | *Partly: short note* | *Doesn’t meet (knock-out): short note* |
| *R2 Name* |  |  |  |  |
| *O1 Name* |  |  |  |  |

Estimates as of: *The month and year cost and effort estimates made, or “No estimates”*

Not shown in matrix: *Any Must or Should requirements that every option meets equally just listed as one line instead of rows. Write “None” if every requirement is shown.*

### **Notes on each option**

*For each option, write 3 \- 5 bullets covering only what the matric can’t show: explain any Partly or Doesn’t meet against a Must, and note specific risks, unknowns, lock-in, knock-on effects, etc. Write each bullet as “Good, because…” or “Bad, because…” and give the requirement ID it relates to, where we have one. Be specific: instead of “too risky” write what the risk is and which requirement it threatens. Give the chosen option the same depth as the others. End each rejected option with “Rejected because” (name the deciding requirement) and, if it’s useful, “Would reconsider if:” (what conditions would have to change). End the chosen option with “Chosen because:”*

#### **A. Option name**

* *Good, because… (requirement ID)*  
* *Bad, because… (requirement ID)*  
* ***Rejected because:** one sentence naming the deciding requirement.*  
* ***Would reconsider if:** what would have to change.*

#### **B. Option name**

* *Good, because… (requirement ID)*  
* *Bad, because… (requirement ID)*  
* ***Rejected because:** one sentence naming the deciding requirement.*  
* ***Would reconsider if:** what would have to change.*

#### **C. Option name**

* *Good, because… (requirement ID)*  
* *Bad, because… (requirement ID)*  
* ***Chosen because:** one sentence naming the requirements that decided it, and any gaps accepted.*

## **Decision**

**Chosen option:** *the letter and name of the proposed solution. While the status is PROPOSED, this is the recommended option.*

## **Implementation Rules**

*Maybe this should be a separate document, intended to list the rules this decision imposes on anyone building in this area, written as instructions that can be checked. Include what not to do, such as tools or patterns ruled out by the decision. People and coding agents will follow these rules.*

## **Design Detail**

*A link to the design document covering components, diagrams, example flows, rollout plan, etc. Write “None” if there isn’t one.*
