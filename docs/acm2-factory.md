# ACM2 Software Factory

> How ACM2 gets built with no human writing code. This is the operational
> contract binding the agent workforce, the task board, and the ACM repo.
> Companion to docs/acm2-implementation-plan.md Section 10 (agent-native
> development model). Adopted 2026-07-04. ASCII only.

## 1. The Factory Floor

```
HUMAN (architect/approver)
  |  approves merges, sets direction, resolves escalations
  v
TASK BOARD: hermes kanban, board "acm2"
  (workdir: C:\Users\Admin\Documents\ACM - every task is a brief:
   goal, executor, acceptance criteria, out-of-scope)
  |
  +--> CLAUDE CODE sessions ......... architect + validity-critical author
  |     (this repo, direct)          e-process layer, memory invariants,
  |                                  interface contracts, final review
  |
  +--> CODEX (profile "default") .... implementation fleet
  |     quota ledger REQUIRED        multi-file features, salvage-adaptation,
  |                                  hard debugging
  |
  +--> LOCAL PROFILES (LM Studio,    the day crew and night shift
        qwopus3.5-9b-coder-mtp at
        http://100.111.69.102:1235)
        - local-coder ....... small low-risk code (always reviewed up-chain)
        - reviewer .......... first-pass review triage on every PR
        - tester ............ run test suites, summarize failures
        - repo-inspector .... context packets for briefs (files, line refs)
        - kb-curator ........ AGENTS.md / KB / docs maintenance
        - orchestrator ...... board grooming, routing audit
  |
  v
ACM REPO (this repo) -- branches per task -> CI lanes -> human-approved merge
```

## 2. Roles and What They May Touch

| Executor | May author | May NOT author | Reviewed by |
|---|---|---|---|
| Claude Code | anything; ONLY it authors validity-critical modules (e-process math, memory/mergeability invariants, calibration) | - | human + adversarial tests authored by a different agent |
| Codex (default profile) | implementation briefs marked Codex-grade | validity-critical modules | Claude Code (or reviewer profile first-pass, then Claude Code) |
| local-coder | small, low-risk, well-briefed code | anything validity-critical or multi-file architectural | reviewer profile first-pass, then Codex or Claude Code |
| reviewer / tester / repo-inspector / kb-curator | reviews, test runs, context packets, docs | production code | n/a (outputs are inputs to others) |

Hard rules (from implementation plan 10.3):
- Author != reviewer, always. No agent merges its own work.
- CI is the arbiter: red statistical lane blocks any merge regardless of author.
- Property tests for validity-critical modules are written by a DIFFERENT agent
  than the implementation, from the spec alone.
- Local agents are never a substitute for frontier review - their output is
  triage input, not certification.

## 3. The Task Lifecycle

```
brief created (hermes kanban create, on board acm2)
  -> routed: EXECUTOR line in the body + --assignee for Hermes profiles
  -> executed on a branch (worktree tasks: --workspace worktree)
  -> fast lane green (unit + ASCII) - mandatory
  -> statistical lane green (from S2 onward) - mandatory
  -> cross-review (Section 2 table)
  -> human approves merge to main
  -> kb-curator posts the task report; board task completed
```

Codex tasks additionally bracket with the quota ledger (existing Hermes
policy, unchanged):

```powershell
python "$env:LOCALAPPDATA\hermes\scripts\codex_quota_ledger.py" start --task-id <id> --reason "..." --estimated-units <n> --model codex
python "$env:LOCALAPPDATA\hermes\scripts\codex_quota_ledger.py" finish --task-id <id> --result "..."
```

## 4. Brief Format (every task, no exceptions)

```
EXECUTOR: <who runs this - Claude Code session / Codex-grade / profile name>
BUILD: <what to produce, with file/module targets>
ACCEPTANCE: <machine-checkable criteria - the tests/gates that define done>
OUT OF SCOPE: <explicit exclusions, incl. relevant never-built entries>
DEPENDS: <task ids, if any>
```

A brief an executor cannot act on without asking questions is a defective
brief - fix the brief, not the chat.

## 5. Standing Constraints (bind every agent)

- ASCII-only in all files.
- The never-built list (implementation plan Section 5) is a hard filter and a
  review checklist item on every PR.
- Config philosophy: alpha + documented structural constants. Nothing else.
- Thread caps at import time in every entrypoint (the BLAS lesson).
- README-sync and KB-update rules apply to every user-facing change.
- New spine lives in acm2/ (new top-level package in THIS repo, D9 as revised
  2026-07-04: same ACM repo, no new repository). Old pipeline code is quarry:
  copied deliberately, deleted when superseded, never imported live into acm2/.

## 6. The Dev Box GPU Calendar

One machine (RTX 4060 8GB, Ryzen 5, 16GB RAM) serves three roles. VRAM is
single-tenant:

- Day: LM Studio serves qwopus3.5-9b-coder-mtp for the local profiles.
- Night: evidence-lane runs / Tier 2-S model experiments own the GPU; the
  local LLM is unloaded (Hermes' model guard keeps one model loaded at most).
- Evidence workers <= 2, BLAS caps enforced in the runner.

Night-shift automation (hermes cron) is added when there is an evidence lane
to run (S2 onward) - not before.

## 7. Bootstrap State (2026-07-04)

- Board acm2 created, workdir set to the ACM repo, active.
- S0 parent goal + seven child briefs filed (t_179b14d2 and children),
  routed per Section 2.
- Verified: LM Studio endpoint serves qwopus3.5-9b-coder-mtp; Hermes v0.18.0
  profiles local-coder/reviewer/tester/repo-inspector/kb-curator/orchestrator
  exist; Codex reachable via the default profile with the quota ledger.
- First human action each session: hermes kanban list (board acm2), pick the
  frontier work for Claude Code, dispatch the rest.
