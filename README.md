# Content Factory

Content Factory is a local content-production assistant for preparing posts and visual briefs for Telegram, VK, and Instagram.

The project stores a personal knowledge base, tone-of-voice rules, content workflows, and helper scripts that turn a topic into platform-specific drafts and Instagram carousel assets.

## What It Does

- Creates adapted posts for Telegram, VK, and Instagram.
- Uses a local knowledge base for positioning, audience, tone of voice, content rules, and brand style.
- Generates visual briefs for image creation.
- Renders Instagram carousel slides from structured JSON.
- Keeps publication manual: the project prepares files, but does not publish to social networks.

## Project Structure

```text
content_agent/
├── CLAUDE.md        # Main agent instructions and project workflow
├── .claude/         # Local agents and content-maker skill
├── knowledge/       # Personal knowledge base and content rules
├── scripts/         # Automation scripts for images and carousels
├── assets/fonts/    # Fonts used for carousel rendering
├── draft/           # Working drafts and content ideas
├── output/          # Generated content, ignored by git
└── tmp/             # Temporary local files, ignored by git
```

## Private And Local Files

The repository intentionally ignores local-only and personal materials:

- `.env`
- `.claude/settings.local.json`
- `assets/me/`
- `output/`
- `tmp/`
- Python cache files

This keeps secrets, personal photo references, temporary files, and generated examples out of GitHub.

## Current Status

The current version is a working local content pipeline. The next development step is to use this web/local version as the base for a desktop application.

## Safety Rules

The assistant prepares content files only. It must not publish posts, delete project files, overwrite generated assets, or perform external actions without explicit user approval.
