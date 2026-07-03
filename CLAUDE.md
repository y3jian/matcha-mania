# Workspace coding guidance

This repository contains a Python data pipeline, SQL schema definitions, and YAML configuration. Keep changes practical, small, and easy to follow.

## Preferred habits

- Prefer clear, explicit code over clever abstractions.
- Keep functions focused and reuse small helpers when they improve readability.
- Use descriptive names and simple data structures.
- Make transformations and scripts predictable, idempotent, and easy to debug.
- Validate configuration and user input early, and raise errors with useful context.
- Favor small, testable changes over broad rewrites.

## Python guidance

- Use type hints for function signatures when they clarify behavior.
- Keep modules focused on one responsibility.
- Preserve existing conventions unless a change clearly improves consistency.
- Prefer readable control flow and early returns over deeply nested logic.

## Clarity first

When implementing or reviewing code, prefer the most readable option that still solves the problem well.

- Favor explicit names over clever abbreviations.
- Keep functions small and focused on one job.
- Use simple data shapes before introducing extra abstraction.
- Prefer obvious control flow over clever tricks.
- Leave comments for intent and trade-offs, not for restating the code.

## Debugging mindset

Approach bugs systematically and keep the fix as small as possible.

- Reproduce the issue before changing code.
- Isolate the smallest input or path that fails.
- Trace the flow of data and state through the relevant layers.
- Fix the root cause rather than masking the symptom.
- Add or preserve useful error context so the issue is easier to diagnose next time.

## Refactoring guidance

Refactor for clarity and maintainability, not for novelty.

- Improve structure only when it makes the code easier to understand or change.
- Prefer extracting a helper when the logic is repeated or becomes noisy.
- Keep interfaces simple and avoid over-generalizing too early.
- Preserve behavior while making the intent clearer.
- Stop when the code is straightforward enough to read and reason about quickly.
