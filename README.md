# Vida Open Archive

An open repository that bundles three things together:

- a local archive of Vida's public Zhihu content
- a reusable `vida-perspective` skill distilled from that corpus
- the source code for the exhibition-style website that presents the archive

## Live Website

- https://vida-exhibit.pages.dev/

## Repository Layout

- `archive/vida_articles_extract/`
  - extracted markdown corpus
  - extracted inline images
  - extraction manifest
- `skills/vida-perspective/`
  - the distilled Vida skill
  - research notes used to build it
- `web/`
  - the React + Vite source for the exhibition website
- `scripts/`
  - helper scripts used to extract and prepare the dataset

## What's Included

- `564` archived Zhihu items
- `82` extracted images
- a local markdown archive at `archive/vida_articles_extract/extracted.md`
- a structured website dataset at `web/src/data/articles.json`
- a distilled skill at `skills/vida-perspective/SKILL.md`

## Skill Installation

For Codex / skills-based environments, install the skill from this repo path:

```bash
npx skills add Noahuto/vida-open-archive --path skills/vida-perspective
```

After installation, restart your agent session and trigger it with prompts like:

```text
切到 Vida
```

or:

```text
用 Vida 的视角，帮我判断现在还有哪些适合年轻人的轻资产套利机会
```

## Website Development

```bash
cd web
pnpm install
pnpm dev
```

Build:

```bash
cd web
pnpm build
```

## Data Provenance

The archive is built from a local Vida corpus extracted into:

- `archive/vida_articles_extract/extracted.md`
- `archive/vida_articles_extract/manifest.json`

The website dataset lives at:

- `web/src/data/articles.json`

## Notices

- Code and skill materials in this repository are released under the MIT License.
- Archived article text and media are preserved with original source URLs for research and archival purposes; see `CONTENT_NOTICE.md`.

