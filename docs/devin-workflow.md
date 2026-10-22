# The Devin workflow tested in this prototype

This is a synthetic Cognition take-home, not a production financial system. Devin wrote the application code. Codex assisted with research, orchestration, independent review/checks and presentation preparation. The reusable workflow required an engineering brief, repository setup and test instructions before the shorter business requests were useful.

## Replay the workflow

1. Connect Devin to your own repository and verify the identity used by sessions can read/write it. Configure a development environment using the README.
2. Save the task instructions in [playbooks/](playbooks/) as Devin Playbooks: Create, Update, Variant and Health. Attach the relevant Playbook when starting each fresh session. The repository's `AGENTS.md` and verification Skill supply the app-specific procedure.
3. For creation, describe the users, records and permitted decisions. Keep synthetic data and explicit demo boundaries while prototyping. Review the initial result before adopting it as a shared foundation.
4. For an update, give the business request and observable acceptance criteria. For example: “Show pending refunds older than 48 hours, oldest first. Exclude approved and rejected requests. Keep search working.” Have Devin return tests, browser evidence and a PR.
5. For another tool, use the Variant Playbook: “Create a Merchant Reviews queue with independent records and the same review workflow.” Reuse configuration and shared components rather than copy the whole repository. Test isolation and both modules after a shared change.
6. For maintenance, use the Health Playbook against the current commit. Automations can launch this process, but validate the actual trigger, execution identity, network access and budget in your own account. This demo does not establish unattended operation.

Production changes should receive engineering review and normal release controls. The synthetic demo explicitly authorized merges after local checks. No GitHub CI checks or branch-protection policy were configured in this exercise.

## Completed evidence

| Step | Session | Result |
| --- | --- | --- |
| Build | [Initial session](https://app.devin.ai/sessions/26b81377eab8450a87f6f7e83a18dc39) | Refund queue, persistence, demo roles, decision history; `demo-v1` |
| Change | [Fresh update automation session](https://app.devin.ai/sessions/24231258635a47d3a55874ece07f5119) | Overdue feature and tests; original session published its patch in [PR #2](https://github.com/Soham4001A/devin-internal-tools-demo/pull/2); `demo-v2` |
| Reuse | [Fresh variant session](https://app.devin.ai/sessions/f1291ed3d6ed4cc7b163759b739cc259) | Merchant Reviews, shared components and isolation tests in [PR #3](https://github.com/Soham4001A/devin-internal-tools-demo/pull/3); `demo-v3` |
| Review fix | Same variant session | Independent visual review found an offscreen status column; wrapping fixed in [PR #4](https://github.com/Soham4001A/devin-internal-tools-demo/pull/4); `demo-v3.1` |
| Maintain | [Health-check automation session](https://app.devin.ai/sessions/f1a1adeb3d1545df855b06d1a90e0d5e) | 26 tests, frontend checks and browser journey passed on final app code; trigger timing caveat below |

Session links require access to the personal Devin organization. API-created build/variant sessions belong to its Test2 service account and may appear under All sessions rather than My sessions. Screenshots and recordings in this repository remain available independently of the account.

## Interventions and limitations

- The GitHub App could push but could not create a repository. The orchestrator created the empty repository first.
- Native deployment tools were unavailable. Cloud URLs were authenticated, VM-bound previews; local startup is documented. A permanent hosted app was not demonstrated.
- Adding the GitHub issue label did not launch a session during observation. The update automation was manually invoked. Its organization identity could build the change but could not push; the original session imported the patch and published it.
- The health session reports a scheduled event for the18:05UTC window but started at18:07:40UTC, after a manual retry had also been accepted. Only one session was observed. The completed checks are useful evidence; this overlapping test does not isolate scheduled dispatch reliability. Both automation configurations were disabled after the demonstration.
- The first attempts to tag v2 and v3 followed a blocked merge and pointed at the prior commit. Devin corrected those tags immediately. Final tag targets were independently checked. This is why command exit status and published artifacts need review.
- Independent final behavior verification passed 26 backend tests, frontend build/lint and the browser journey through both tools, including the overdue boundary. The final small layout fix passed frontend checks and the same browser journey again. An initial local test attempt raced a simultaneous frontend build; rerunning sequentially resolved the missing build-assets error without a source change.
- Demo personas are client-selectable, the reset route is intentionally accessible, and history is an ordinary mutable table. These are not production authentication, authorization boundaries between real tenants, or a tamper-resistant audit system.
- No real payments, customer data, production data connectors, load testing or recovery exercise were included.

The prototype clock began 2026-10-22 17:31:50 UTC. Application changes were merged by 18:02:04 UTC (about 30 minutes); subsequent verification and documentation remained within the two-hour prototype limit. This measures elapsed experiment time, not human effort saved. Interim usage counters were not suitable for a billed-cost claim.

## Security configuration added after the prototype

At the user’s follow-up request, an `Internal Tools — Read-only Review` profile was saved and pinned to the disabled Health automation. It specifies read-only Git, removal of the GitHub CLI token, no external MCP servers, read-only Devin management access, and a restricted network allowlist. Its enforcement level is mandatory when bound. Organization defaults and build workflows were not changed. Saved settings and the automation binding were read back; no session has been tested under this profile. It governs the agent and does not supply application authentication, audit or payment controls. See the [configuration export](presentation/security-profile.json). Earlier session results are not evidence of this profile’s enforcement.
