# PR: Swap primary LLM to Groq

## Summary

Gemini Interactions from Modal us-east was taking ~25s TTFT on call 1 and
timing out on call 2, so live turns failed with `(llm)` / `(gate)` messages.
Primary LLM is now Groq `openai/gpt-oss-20b` (same key already used for STT).
Gemini stays available via `SARJY_LLM=gemini`.

## Problem

Measured on the live app (2026-09-21):

- `decide()` TTFT ≈ 25 s from Modal
- `segments()` then hit `LLM_TIMEOUT_S` → `turn_failed(stage=gate)` after the
  fact card had already rendered (tool path succeeded)

Raising the timeout only made slow failures slower. Local Gemini was fine
(~1.5 s); the Modal → Interactions path was not.

## Solution

- New adapter `app/providers/groq_llm.py` implementing the same `LLM`
  Protocol (`decide` + `segments`) over Chat Completions streaming.
- Converts `VISA_TOOL`'s flat Gemini shape into OpenAI nested tools at the
  adapter boundary.
- `factory.get_llm()` defaults to Groq; `SARJY_LLM=gemini` rolls back.

Measured from Modal us-east (same region as the deploy):

| Call | Gemini (broken) | Groq |
|---|---|---|
| decide TTFT | ~25 000 ms | ~550 ms |
| segments total | timeout | ~220 ms |

## Changes

- `backend/app/providers/groq_llm.py` (new)
- `backend/app/providers/factory.py`
- `backend/tests/test_groq_llm.py` (new)
- `backend/.env.example`

## How to Test

1. `cd backend && uv run pytest tests/test_groq_llm.py -q`
2. `make deploy`
3. Hard-reload the live URL; ask a visa question — fact card + spoken answer
   should arrive in a few seconds, not hang then `(gate)`.

## Changelog

- Primary LLM: Groq `openai/gpt-oss-20b` (was Gemini `gemini-3.5-flash-lite`)
- Sticky model rotation on 429 across
  `openai/gpt-oss-20b` → `openai/gpt-oss-120b` → `qwen/qwen3.8-27b`
  (override with `GROQ_LLM_MODELS`)
- Rollback: `SARJY_LLM=gemini` on Modal secret / env
