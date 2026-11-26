# SECURITY INCIDENT — 2026-11-27 (metadata only; NO secrets, NO account names)

> This file records counts, hashes, decisions and status ONLY.
> It must never contain a filename with credentials, an email, a password, or a key.

## Summary

During Phase 0 diagnostics (P0.6/P0.7) on `/run/media/xorthomson/My Passport/NewFolder`,
credential artifacts were identified. A prior claim of "0 password files" was a
pattern-coverage gap, NOT absence. The real exposure is larger than first assessed.

## Confirmed artifacts (counts + SHA-256 only)

### fiinote_export/ — 4 credential files (3 unique contents, 1 duplicate)
```
21d10e2fee615676b578da441721d09a034afef3b31dcfc41aea2c84e3f778be  txt  14162
447720a59cb88a05d69e1e097a766e45a8a9fd4b0201c38cbe4443109f455c79  txt  55223
a499d30b033aef3551818dd1967a3c4ce1cd62f8ce141e169b81814a33cfb8b0  txt  26962
```
(4 files, 3 distinct hashes — one content-duplicate pair.)
Format: name-embedded `email _ password _ Expiry` (name-based; the literal word
"password" is absent from filenames, which is why the `*password*` glob returned 0.)

### *fiinote* files (سلة_تحقق + وثائق) — 4 files (2 unique, 2 dup)
```
5bde82fbdc89d1716c07527da336dab38eab8259054bf72a09639f4fcd7d1198  txt  948
fade598cf9a45e29783fe9f58c9f7abfaad9497eb1b61741665903e56e606bde  txt  361
```
Format = notes/web-snippets (Title/UUID/URL/Note). NO email-password pairs.
Decision: quarantine only, NO rotation.

### Vault (~/secure/vault-2026-11-27/) — 1 file, ~318 accounts
```
8c951aba3592c09bc9e19ef3eaa90b43bf90e229ff7b6ce567047f3c3c9a695d  txt  29855
```
- Format: 4-column CSV `name,url,username,password` — a full browser password export.
- ~318 lines / 319 non-empty.
- Vault is a PLAIN btrfs subdirectory (mode 700), NOT encrypted (no LUKS/crypt).
- Hash is UNIQUE — not a copy of any fiinote_export / *fiinote* file → a 5th,
  independent, previously-unknown credential source.
- OPEN QUESTION (owner memory): where did this file originate? If unknown, assume
  another undiscovered source exists → warrants a wider scan later.

### API Key file — docs-only (NOT sensitive)
- `sk-` patterns = 0, generic api-key patterns = 0, ASCII text with CRLF.
- Verdict: saved web page / documentation about OpenAI API. EXCLUDE from quarantine.

## Exposure

- The 4 fiinote credential filenames were printed in a prior model-provider session
  (P0.6). The Vault contents were never printed (counts only).
- Treat the fiinote credentials as compromised (present in provider logs).
- The Vault file's ~318 credentials are exposed locally (unencrypted) and must be
  treated as compromised pending rotation.

## Rotation status (owner-provided; counts only)

- fiinote accounts rotated: PENDING
- Vault (~318): decision PENDING (rotate-all / rotate-subset / accept-risk)
- OpenAI keys: docs-only, no rotation needed

## Containment status

- Quarantine (age-encrypted bundle): NOT DONE — blocked on rotation confirmation.
- deny-by-default filter: NOT DONE — blocked (P0.8).
- Originals: UNCHANGED, still on disk. No deletion performed.

## Phase 1 gate (8/8) — current

| # | Condition | Status |
|---|---|---|
| 1 | fiinote rotation | PENDING (manual) |
| 2 | Vault decision + rotation | PENDING (manual) |
| 3 | Encrypted quarantine | BLOCKED (P0.8) |
| 4 | deny-by-default + 8/8 tests | BLOCKED (P0.8) |
| 5 | Dr Michel SAMAAN path | PENDING decision |
| 6 | 4 long-path files excluded | PENDING doc |
| 7 | Incident documented (this file) | DONE |
| 8 | Independent security review | PENDING (not me, not Vibe Coder) |

## Rules

- No credential content, name, email, or key may be added to this file or any commit.
- Originals are not deleted without explicit owner approval after bundle verification.
- Phase 1 stays BLOCKED until 8/8 pass.