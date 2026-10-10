# AppHub 4.0 — Copilot / Agent Instructions

These repo-level instructions are read automatically by GitHub Copilot (and
compatible agents) for everyone who opens this repository. They make isolated,
multi-developer-safe work the default.

## AUTO-TRIGGER: Isolated module work (multi-dev safe) — DEFAULT

Whenever a task will **edit AppHub 4.0 module files** (any blueprint `*.py`,
`templates/*.html`, `static/*`, `modules.py`, `nav.py`, module packages, etc.),
do **NOT** work directly on `main` in the shared working tree. Default to an
isolated **git worktree + feature branch** so multiple developers can work on
different modules at the same time without clobbering each other.

On the first AppHub edit in a session:
1. Identify the developer from `git config user.email`:
   - `cpell@peakmade.com` = **craig**
   - `rmahaffey@peakmade.com` = **ryan**
   - `rmadhu@peakmade.com` = **rohit**
   - `agraham@peakmade.com` = **austin**
   - `eyourse@peakmade.com` = **elliott**
   If the email isn't mapped, ask the developer for their name.
2. Create/reuse the isolated worktree + branch by running the helper:
   ```
   py _apphub_worktree.py <module> [dev]
   ```
   → worktree `../APPHUB_4__<dev>-<module>`, branch `feat/<module>-<dev>` from `origin/main`.
3. Do **all** edits in that worktree folder only, and tell the developer the folder + branch.

## Commit / deploy rules (NON-NEGOTIABLE)
- **Never** `git add -A` / `git add .` — always `git add <specific files>`.
- `git pull --rebase origin main` before every push; resolve conflicts.
- Bump `config.py` `APP_VERSION` as the **last** change before push (minor `x.Y.0` for
  features/new modules, patch `x.y.Z` for small fixes). Never ship a deploy without bumping it.
- Push the **feature branch** automatically. **Merging to `main` (= the Azure deploy) is an
  explicit, human-approved step** — do not merge or deploy without the developer saying
  "deploy"/"merge". With 2+ active developers, open a PR into `main` for review.
- Auto-deploy = GitHub Actions `.github/workflows/main_apphub40.yml` on push to `main`.
  It is cumulative (deploys the tip of `main`). Verify a deploy by **runtime** (in-app version
  badge / a route check), NOT Kudu VFS — `/site/wwwroot` reads stale because the App Service
  runs from a package.

## Shared-resource cautions (git branches do NOT isolate these)
- Databases `DB_APP_SUPPORT` / `WH_PROD2` are shared — schema/data changes need explicit
  human coordination across developers.
- Collision hot-spots (coordinate / expect rebase conflicts): `modules.py`, `nav.py`,
  `requirements.txt`, `config.py`.
- Each worktree's dev server needs a distinct port
  (craig 5001 / ryan 5002 / rohit 5003 / austin 5004 / elliott 5005).

## One-time per developer
- Clone this repo, use VS Code + GitHub Copilot (custom instructions enabled — default on).
- Ensure `git config user.email` is your Peak email (used to auto-detect your dev tag).
- Nothing else — the behavior above applies automatically because it lives in this repo.
