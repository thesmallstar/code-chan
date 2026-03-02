# AGENTS.md — code-chan

## Global Rules

> Read `~/.agents/global-rules.md` for universal preferences (working style, coding standards, documentation conventions). Those rules apply here.

## How You Work on This Project

### Knowledge Base

This project maintains a `knowledge-base/` folder as the source of truth for all decisions and context. Every AI agent working on this project must follow these rules:

1. **Read before you act.** Before starting any work, read the relevant files in `knowledge-base/` to understand current state.

2. **Write after you act.** After completing meaningful work — a feature, a decision, an architecture choice, a bug fix — update or create the appropriate file in `knowledge-base/`.

3. **What goes in the knowledge base:**
   - **Product decisions** — why we chose a feature scope, what we deferred, what we prioritized
   - **Tech decisions** — framework choices, architecture patterns, database schema reasoning, API design rationale
   - **Implementation notes** — how a feature works, key files involved, non-obvious logic
   - **Trade-offs** — what alternatives were considered and why we picked what we did
   - **Open questions** — unresolved decisions that need future input

4. **Keep it scannable.** Use headers, bullets, short paragraphs. Someone should be able to skim a file and get the key points quickly.

5. **No stale docs.** If a decision changes, update the file. Don't leave contradictions.

### What the Knowledge Base Is NOT

- Not a changelog or git log replacement — git tracks code; knowledge base tracks *decisions and understanding*
- Not auto-generated API docs — it's human-readable context that explains the *why*

---

## Clean Code Standards

All code in this project must follow clean code principles. This is non-negotiable.

### Naming

- **Intention-revealing names:** `elapsedTimeInDays` not `d`
- **No disinformation:** don't use `accountList` if it's a Map
- **Meaningful distinctions:** no `ProductData` vs `ProductInfo`
- **Pronounceable, searchable names:** no `genymdhms`
- **Class names:** nouns (`Customer`, `WikiPage`). Avoid `Manager`, `Data`, `Helper`
- **Method names:** verbs (`postPayment`, `deletePage`, `isEligible`)

### Functions

- **Small** — shorter than you think. Under 20 lines
- **Do one thing** — a function does one thing, does it well, does it only
- **One level of abstraction** — don't mix business logic with low-level details
- **Descriptive names:** `isPasswordValid` not `check`
- **Minimal arguments:** 0 is ideal, 1-2 is fine, 3+ needs strong justification
- **No side effects** — don't secretly change global state

### Comments

- **Don't comment bad code — rewrite it.** Most comments are failure to express intent in code
- **Explain in code:** `if employee.isEligibleForFullBenefits()` not `# check if employee is eligible for full benefits` followed by a complex conditional
- **Good comments:** legal, informative (regex intent), clarification for external libs, TODOs
- **Bad comments:** mumbling, redundant, misleading, mandated noise, position markers

### Formatting

- **Newspaper metaphor:** high-level concepts at the top, details at the bottom
- **Vertical density:** related lines stay close together
- **Declare near usage:** variables close to where they're used

### Objects & Data Structures

- **Hide implementation** behind interfaces
- **Law of Demeter:** no `a.getB().getC().doSomething()` chains
- **DTOs** are fine — classes with data and no behavior when that's the intent

### Error Handling

- **Exceptions over return codes** — keeps logic clean
- **Write try-catch-finally first** — defines the scope
- **Don't return null** — forces null checks everywhere
- **Don't pass null** — leads to null pointer errors

### Testing

- **TDD laws:** (1) failing test first, (2) only enough test to fail, (3) only enough code to pass
- **F.I.R.S.T.:** Fast, Independent, Repeatable, Self-Validating, Timely

### Classes

- **Small** — single responsibility (SRP)
- **Stepdown rule** — code reads like a top-down narrative

### Code Smell Checklist

Before submitting any code, verify:

- [ ] Is every function under 20 lines?
- [ ] Does every function do exactly one thing?
- [ ] Are all names searchable and intention-revealing?
- [ ] Have I avoided comments by making the code self-explanatory?
- [ ] Am I passing too many arguments (3+)?
- [ ] Is there a failing test for this change?
- [ ] No rigidity (hard to change), fragility (breaks elsewhere), or needless complexity?

---

## Project Context

- **Product:** code-chan
- **Description:** Open source toolkit for AI-assisted code reviews
- **Knowledge base:** `knowledge-base/`
