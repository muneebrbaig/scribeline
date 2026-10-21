# QA run report

A page that tells Product and QA what a hands-on pass found. Sections in this order.

1. **H1:** `<Platform> QA Run: <Scope> (<YYYY-MM-DD>)`.
2. **Opening paragraph.** What was run, on what, and the question it set out to answer.
3. **Bottom line.** Bold lead-in. Does the core flow work? Name the one or two findings to fix first by ID. Say how the rest rank.
4. **How to read this page.** Grouping, sort order, and a severity table: Critical 🔴, High 🟠, Medium 🟡, Low ⚪, each with a one-line meaning. A profile may rename them.
5. **All findings at a glance.** One table: `#`, Severity, Area, Finding. Each ID links to its heading anchor.
6. **Test setup.** Two-column table (Build, Device, Account, Data set). Then "What we did, in order" as one arrow-joined sentence (`launched → toured → created …`). Then "Test data left behind", with IDs, so someone can clean up.
7. **Findings by area**, sorted by severity inside each area. Per finding:
   - `### AREA-N: <plain-language title>`. Area prefixes come from the profile (for example FIN, TRN).
   - Severity line with its emoji.
   - **What we saw.** Facts, the steps taken, exact values.
   - **Why it matters.** Impact in money, time or risk. Link a related ticket or finding.
   - **Suggested direction.** One concrete proposal, not a menu.
   - A collapsed `<details>` with `📷 Screenshots (N)` holding a table: header row is the captions, one image per cell.
   - Low items may collapse to one short paragraph plus screenshots. Group trivia as "Small items".
8. **What worked well.** Short and specific, with screenshots.
9. **Not covered.** An honest list of what the run did not exercise (real device, other platforms, other flows).
10. **Suggested follow-ups.** Which findings to file first, which test suites any fix must run, whether issues exist yet.

## Tone

- Say plainly when something is a **product gap** and when it is a **bug**. Say when something is untested instead of guessing.
- A real bug in the test tooling found along the way is noted separately from product gaps.
- Narrate scenarios as the steps taken, in order, so a reader knows what was clicked, not just the assertion.

## Evidence

- One file per screenshot, and one JSON per scenario where one exists. Never a zip.
- Where a scenario has no JSON, say so in the table instead of leaving the cell blank.
- Each file name carries the platform, date and step, so a reader can find it again.
