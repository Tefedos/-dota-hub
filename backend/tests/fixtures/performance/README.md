# RI-04 regression input

`9057722463_ruiner_legacy.json` is the **actual saved ruiner report** read from the existing local API on 2026-10-23, before RI-04 was implemented:

`GET http://127.0.0.1:8000/api/v1/local-alpha/matches/9057722463/ruiner`

Only the envelope's `data` is stored. No statistics or scores were invented, no new OpenDota fetch or re-analysis was requested. The fixture has no `preliminary_selection` and exercises backward compatibility. Its existing indices are `[50, 0, 0, 0, 42]` for Radiant and `[0, 0, 0, 31, 6]` for Dire, in slot order. The new projection must yield Radiant group `[0, 4]` (margin 8), Dire single `[131]` (margin 25).

This is not a raw match snapshot and cannot validate normalization or reconstruct the scoring inputs. Formula regression is independently covered by the existing `draft/9051271323/evidence.json` snapshot and `docs/audits/9051271323-ruiner-v1.json` baseline.

`9051271323_live_ri04_envelope.json` is the actual **read-only local-alpha GET envelope** captured for the backend QA audit on 2026-10-23. It was obtained from the already stored report via `GET /api/v1/local-alpha/matches/9051271323/ruiner`; there was no re-analysis or OpenDota request. Its player indices differ from the older minimal `draft/9051271323/evidence.json` projection because the stored local report has more player data. Tests explicitly distinguish the live API contract from the older formula regression fixture.
