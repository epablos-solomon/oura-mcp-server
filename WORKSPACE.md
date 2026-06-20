# Workspace Guide

This is a persistent Linux workspace. Files here survive across sessions and
may be shared with other agents.

## Rules

1. Read this file at the start of every session before doing workspace work.
2. Keep this file updated: whenever you add, move, or remove important
   content, reflect it here.
3. Layout:
   - `repos/` — cloned repositories
   - `notes/` — durable knowledge worth keeping across sessions
   - `scratch/` — temporary files (safe to delete at any time)

## Delegating coding tasks to a CLI agent

This workspace has three coding-agent CLIs installed. You can hand off a
self-contained coding task to any of them through your tools:

- `run_claude` — Claude Code (`claude`)
- `run_codex` — OpenAI Codex (`codex`)
- `run_cursor` — Cursor (`cursor-agent`)

All three run headless inside this container (which is the sandbox), so they
execute without asking for approvals. Each needs credentials, provided as
workspace secrets (set by the operator):

- Claude: `ANTHROPIC_API_KEY` env, or `~/.claude/.credentials.json` (OAuth file).
- Codex: `OPENAI_API_KEY` env, or `~/.codex/auth.json` (OAuth file).
- Cursor: `CURSOR_API_KEY` env, or `~/.cursor/` login (OAuth file).

Because `HOME` lives on this persistent volume, an OAuth login done once
survives across sessions and the CLIs refresh their tokens in place. If a CLI
reports it is not authenticated, tell the user which secret is missing.

## Exposing a web preview (public link)

To let the user view a web server running in this workspace:

1. Start your server in the background, e.g.
   `cd /workspace/repos/myapp && (python3 -m http.server 3000 > /workspace/scratch/server.log 2>&1 &)`
2. Open a public tunnel and capture the URL:
   `(cloudflared tunnel --url http://localhost:3000 > /workspace/scratch/tunnel.log 2>&1 &) ; sleep 5; grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /workspace/scratch/tunnel.log | head -1`
3. Share the printed `https://….trycloudflare.com` link with the user.

The tunnel lives only while this container runs; restart it if the link dies.

## Current contents

- `/workspace/repos/SCG-Landing-Page` — cloned GitHub repository for the SCG landing page.
- `/workspace/repos/oura-mcp-server` — new Python MCP server scaffold for Oura Ring integration.
- `/workspace/scratch/scg-landing.log` — Vite dev server log for the SCG landing page.
- `/workspace/scratch/scg-tunnel.log` — cloudflared tunnel log for the public preview.

## Active projects / notes

- `SCG-Landing-Page` is running locally via Vite on port 5173 and is exposed through a Cloudflare Tunnel.
- `oura-mcp-server` is the new MCP scaffold for Oura Ring, with FastAPI, MCP tools, OAuth2 hooks, and base tests.
