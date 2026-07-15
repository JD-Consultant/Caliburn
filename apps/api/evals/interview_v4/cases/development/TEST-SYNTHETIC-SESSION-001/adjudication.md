# TEST-SYNTHETIC-SESSION-001 adjudication

Status: maintainer-checked synthetic development case; independent domain review pending.

## Allowed use

This case may be used for static claim extraction, quote grounding, source-subject separation, negative evidence, temporal consistency, and gap-state tests. It must not be used as a scored end-to-end replay case because the migrated session has no turn-zero document, state, or immutable reference snapshot.

## Episode decisions

- Employee turns 3-13 form one complete PDF upload episode: ambiguous request → prototype → observed user confusion → Loading/Disabled/file restrictions → deployment → production checks → slow-network manual test.
- Employee turn 15 is a separate change-impact episode. OCR and database changes are proposed implications, not completed outputs.
- Employee turns 17-19 form a third-party integration episode. Turn 20 asks about test coverage but has no employee response; the answer must remain unresolved.

## Critical evidence decisions

- Turn 13 explicitly denies producing a formal QA test document. The manual Slow 3G scenarios are valid verification evidence, but must not be projected as formal test-document authorship.
- Turns 5 and 7 show an observed repeated-click problem and preventative UI controls. A PostgreSQL outage was anticipated, not observed.
- `accept=".pdf"` and client-side size checks do not prove server-side file validation or security scanning.
- The employee describes asking the PM to create a ticket and move work to the next sprint. This supports technical impact communication, not final roadmap authority.

## Temporal contradiction

The session was captured in 2026, while turn 17 says the LINE Notify integration happened "今年年初". LINE's official developer notice states that LINE Notify and all of its APIs were terminated on 2025-03-31; LINE recommends Messaging API as the alternative: <https://developers.line.biz/en/news/2025/04/01/line-notify/>.

The correct consultant behavior is to preserve the employee's statement as evidence, mark it `needs_confirmation`, and ask whether the event date was earlier or the actual service was LINE Messaging API. The system must not silently rewrite the quote, and must not publish LINE Notify as a current 2026 skill or recommended architecture.

## Promotion gate

Keep `replay.ready=false` until all of the following exist:

1. genuine turn-zero document and session state;
2. immutable reference snapshot from the same start time;
3. per-turn model/tool traces sufficient to reconstruct state transitions;
4. independent domain review of claim labels and any JD projection gold.
