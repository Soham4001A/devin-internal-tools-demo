# Create an internal operations tool
You are building a small, working internal tool for a business requester. Use their plain-language brief and the repository's existing conventions. Ask only questions that block progress; make reasonable reversible choices.

## Delivery procedure
1. Establish the repository, data source and requested workflow. For a new tool create a small conventional application, with reusable queue/list, record detail and action/history components. Avoid designing a general low-code platform.
2. Use synthetic data for a prototype. Keep server-side action validation and authorization in application code. Mark demo identity and integrations honestly. Never claim compliance, real SSO, or immutable auditing unless implemented and verified.
3. Build a useful, polished UI that operators can understand. Include sensible loading, empty and error states. Persist changes server-side; explain the persistence boundary across restarts/redeployments.
4. Run meaningful tests for state transitions, authorization, repeat actions and data isolation as applicable. Browser-test the main user journey and provide a short recording if supported.
5. Commit the work, provide a GitHub URL, and publish a synthetic-data demo using native deployments when available. Respect deployment approval mechanisms. Keep credentials out of source, prompts, screenshots and logs.
6. Save exact run/test/deploy instructions in README and a repository skill at .agents/skills/verify-internal-tool/SKILL.md. Add a concise AGENTS.md so a fresh Devin session can update this app without prior conversation. Include a repeatable seed/reset command and a clearly labeled demo reset if safe.
7. Return the app URL, repo/commit or PR URL, tests actually run, any recording, time spent, and specific limitations. A green screenshot does not prove production readiness.

## Reuse
Separate per-tool labels/columns/statuses/seed records from shared rendering when that is simple. Each tool must own separate records/history. Keep an understandable extension example, not a general schema designer.

## Scope discipline
Honor the caller's time budget. Deliver one working workflow before polishing. Do not start child sessions or extra integrations unless requested. Do not add ongoing scheduled work unless requested.