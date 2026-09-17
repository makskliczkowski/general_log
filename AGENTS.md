# CODE_AGENTS

Editing and writing rules for this repository. The file contains two independent rule sets. The first set governs code. The second set governs theory notes and readme-style documentation.

## 1. Code

## 1.1 General

- Understand the existing code and the broader problem before modifying it.
- Prefer the simplest correct solution, but think beyond the immediate patch.
- Generalize a concept only when it is genuinely shared or likely to be reused.
- Reuse existing functionality and avoid unrelated refactors.
- Ask about the broader design or intended use when it materially affects the right abstraction.

## 1.2 Style

- Match the repository's established convention for indentation, layout, and alignment, unless the tooling (formatter, linter, or language standard) requires otherwise. Where no convention exists, choose one scheme, typically tabs or four spaces, and apply it consistently.
- Keep code compact, readable, and logically structured.
- Use descriptive mathematical, physical, or algorithmic names.
- Align related assignments, declarations, and type annotations where it aids readability.

## 1.3 Comments and docstrings

- Write comments and docstrings in clear, precise, compact language with short sentences. Avoid undefined buzzwords and unnecessarily ornate phrasing.
- Start a docstring with the signature and a one-line statement of purpose. Then state the conventions, assumptions, and the return value.
- In scientific or numerical code, state the mathematical or physical setting and define notation before use. Record units, normalizations, and basis, sign, or ordering conventions explicitly.
- Distinguish exact results from approximations, heuristics, and assumptions.
- Comments explain reasoning, mathematics, assumptions, and non-obvious behavior. They do not restate what the code trivially does.
- Keep docstrings concise. Document substantial new concepts or mathematics in the readme instead of the docstring.

## 1.4 Design

- Do not overengineer.
- Generalize around meaningful concepts, shared behavior, and expected extension points.
- Avoid unnecessary wrappers, tiny helpers, duplicated functionality, deep hierarchies, and premature configuration machinery.
- Prefer coherent implementations over excessive fragmentation.
- Before adding an abstraction, understand what concept it represents and why it is useful.

## 1.5 Correctness

- Correctness and clarity take priority over elegance.
- For scientific or numerical code, preserve conventions and assumptions explicitly and use stable formulations.
- Distinguish exact results, approximations, heuristics, and assumptions.
- Never fabricate results, benchmarks, or claims.

## 1.6 Tests

- Test only crucial behavior: core workflows, important invariants, meaningful edge cases, and realistic regressions.
- Do not add tests merely for coverage or trivial implementation details.
- Prefer a few meaningful tests over many superficial ones.

## 2. Theory notes and readmes

## 2.1 Prose

- Write clear, precise, compact scientific prose in a Physical Review-style tone.
- Keep sentences short and declarative. Split clauses that pile up commas, parentheses, or subordinate phrases into separate sentences.
- Avoid first-person pronouns unless the writing intends them.
- Avoid undefined buzzwords, rhetorical flourish, and unnecessarily over-intellectual language. Prefer the plain, standard scientific term.
- Use connected prose. State the problem and its setting, define the relevant objects, then introduce the results.
- Prefer to resolve the requested point and stop. Do not pad with generic introductions, summaries, or motivational filler.

## 2.2 Mathematics

- Inline mathematics uses $...$. Display mathematics uses $$...$$ on separate lines.
- Define every symbol before or at its first use. Reuse existing notation and never silently rename symbols.
- Display equations finish with either `\;.` or `\;,` depending on whether the sentence ends or continues. Do not introduce a display equation with a colon.
- Check signs, normalization factors, dimensions, operator ordering, Hermiticity, basis conventions, index ranges, and limiting cases.
- Distinguish definitions, exact identities, approximations, asymptotic statements, heuristics, and conjectures.

## 2.3 Claims and references

- Treat scientific claims conservatively. State the range of validity when known, and avoid overstating generality.
- Never fabricate papers, authors, journals, identifiers, equation numbers, or quotations. If a source cannot be verified, say so explicitly.

## 2.4 Formatting

- Use the plain ASCII hyphen `-` for dashes. Never use Unicode em or en dashes.
- Use `- ` prefixed bullets with no leading spaces. Never use `*` for bullets.
- For tables use GitHub-flavored markdown with a header row, a delimiter row, and a blank line above the table.
- Prefer Mermaid diagrams for flows, phase spaces, and conceptual schemas when a diagram clarifies complex relationships.
- Render math inside Mermaid flowchart and sequence diagrams by wrapping the expression in `$$...$$` inside the node or edge label (KaTeX, Mermaid 10.9+). Do not use single `$...$`.
- I don't care if the line is longer, as long as it's not too long you can keep inline - I prefer this rather than very long files...
