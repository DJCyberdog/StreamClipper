# M13 consolidation — Owner authorization 25.11.2026

Main parent: 3689d89a15567a263705500726059779bfc7d954
M13 code parent (PR #50): 39511c486f11af7cb0eaf37e46ef8a509a0a027e
Parallel CLIP repair parent (PR #21): e17c36f0c898669a8a8678e015c176ec4a953ff7

Scope: M0–M13 code only; M14/M15 implementation remains in #51/#52.
All 36 other legacy PR heads are ancestors of the M13 head (compare ahead=0,
including identical #50): #3, #6, #7, #9, #11, #12, #14, #16, #17, #18, #19,
#23, #24, #25, #26, #27, #28, #29, #30, #31, #34, #36, #37, #38, #39,
#40, #41, #42, #43, #44, #45, #46, #47, #48, #49, #50.
#21 diverged (8 exclusive commits); reviewed all eight changed files against
#23. semantic.py and test_semantic.py identical; setup, preflight, GUI and
model validation equivalent apart from comments/messages; same seven test
cases, #23 specifically asserts explicit fallback allow-pattern. README
contains equivalent repair instructions; #23 improves path portability.
Keep evolved #23 implementation and record #21 ancestry explicitly.
No branch deletion or history rewrite.

All four main-exclusive commits concern ROADMAP.md; compared against common
ancestor ce184c27. Their feature content survives the evolved development
roadmap; P1 #32 scheduling conflict resolved by later Owner decision
(nonblocking UX wish, implemented in #41, native test remains a release gate).
Use exact latest M14 roadmap incl. owner-approved M15a–f planning; this is
planning only, not M14/M15 code integration.

CI: M13 39511c48 Linux PASS; Windows 174 passed/1 skipped then exit 1.
Split Qt and non-Qt tests into distinct Python processes, preserve every
existing selected test, print and enforce exit codes, enable faulthandler.
No suppression of failures. Fresh Linux and Windows checks must pass on
this exact integration head before main merge or closing legacy PRs.

M13 owner-local acceptance reported; independent CLIP/VACE hardware evidence
and long VOD acceptance remain pre-1.0 gates. No stable release implied.
