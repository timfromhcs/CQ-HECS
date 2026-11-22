# Wave F - web production verification (HEAD f880d0a5da4eaa143fff15b86de18456cab98fbd, uncommitted working-tree edits)

| Check | Result |
|---|---|
| `npm test` (web unit) | PASS 167/167 |
| `npm run build` (tsc, vite, bundle budget, token contrast) | PASS |
| Local E2E chromium + mobile-360 + mobile-390, before fixes | 125 passed, 1 skipped, 3 failed under load (app.spec:25, conformance.spec:65 bell, visual lab-light-360: 5 s timeouts); all 3 passed on isolated re-run (38/38) - load timing, root cause not further pinned |
| Local E2E, after fixes, `--workers=2` | PASS 128 passed, 1 skipped (pre-existing skip), 0 failed |
| states.spec.ts x12 repeat, 4 workers, after fixes | PASS 168/168 (before fixes: 8 failures of 168) |
| Preview E2E (https://cq-hecs-jzc60pemb-hcsmediacorp.vercel.app, built from f880d0a, anonymous access worked) | 127 passed, 1 failed (qg.spec:112, see below), 1 skipped; after test fix qg.spec 14/14 against preview |
| `scripts/verify_deployment.py` against the preview | PASS: version 7.0.0 and source SHA f880d0a5... literals found in main-BK4ojLIb.js |
| `tests/test_verify_deployment.py` | PASS 7/7 (fake local server: match, wrong sha, wrong version, protection page -> exit 3, unreachable, no script, short sha) |
| firefox / webkit projects | NOT_RUN: browsers not installed, no such projects in playwright.config.ts, and downloading was not authorized |

## states.spec.ts:56 flake: root cause found
`updateEstimate` hides `#code-error`. The editor change handler schedules it 250 ms after the last
keystroke. If Run is clicked within that window, `runCurrent` shows the error, then the pending
estimate fires and hides it. This is an app bug (a user who types and runs quickly loses the message),
not only a test timing issue. Fix: `web/src/main.ts` keeps the timer in a module variable and
`runCurrent` cancels it. No retries added. Repeat runs: 8 failures before, 0 after.

Second cause, test-only: `importText` in states.spec.ts wrote one shared file per name, so parallel
repeats raced (wrong schema/bad shots/round-trip failures). Now one file per `parallelIndex`.

## qg.spec.ts:112 on preview
The "no request sent" probe counted every non-GET. On Vercel previews the toolbar posts to
`vercel.live/login/validate` and issues a same-origin HEAD. The probe now ignores GET, HEAD and
vercel.live only; any other state-changing request still fails. Passes locally and on the preview.

## Not verified
Preview was built before the main.ts fix; production redeploy of the fix is unverified until the next
deployment, after which re-run `python scripts/verify_deployment.py <url> --sha <new head>`.
