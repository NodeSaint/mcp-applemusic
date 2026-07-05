# Publishing

How this package reaches users: **PyPI** (the installable artifact) → **the official MCP Registry** (the discovery listing that maps to it). The registry only stores metadata; it points at the PyPI package.

Everything in the repo is already prepared:
- `pyproject.toml` — package name `mcp-applemusic-nodesaint`, console script of the same name, PyPI metadata.
- `README.md` — contains the ownership marker `<!-- mcp-name: io.github.nodesaint/mcp-applemusic -->` (becomes the PyPI description; the registry checks for it).
- `server.json` — the registry manifest, `name` = `io.github.nodesaint/mcp-applemusic`, pointing at the PyPI package.

Two steps need **your** accounts and can't be automated (credentials, device auth):

## 1. Publish to PyPI

One-time: create a [PyPI account](https://pypi.org/account/register/) and a [project-scoped API token](https://pypi.org/manage/account/token/) (or, better, set up [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) from the GitHub repo so no token is needed).

```bash
cd ~/mcp-applemusic
git checkout main            # publish the released branch
uv build                    # produces dist/*.whl and dist/*.tar.gz
uv publish                  # prompts for the token, or reads UV_PUBLISH_TOKEN
```

Verify: <https://pypi.org/project/mcp-applemusic-nodesaint/>

After this, anyone can install with `uvx mcp-applemusic-nodesaint`.

## 2. List on the MCP Registry

One-time: install the publisher CLI.

```bash
brew install mcp-publisher      # or download the binary from the registry releases
```

Then, from the repo root (where `server.json` lives):

```bash
mcp-publisher login github      # device-auth flow; proves you own the io.github.nodesaint namespace
mcp-publisher publish           # reads ./server.json and publishes
```

Verify:

```bash
curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.nodesaint/mcp-applemusic"
```

## On every release

Bump the version in **three** places so they stay in lockstep (the registry rejects a mismatch):
1. `pyproject.toml` → `version`
2. `server.json` → `version` **and** `packages[0].version`

Then re-run `uv build && uv publish`, followed by `mcp-publisher publish`.

## Other directories (index from GitHub, no PyPI needed)

These scrape public MCP repos; the repo's description + topics (already set) help discovery. Submit the repo URL when convenient:
- Glama — <https://glama.ai/mcp/servers>
- PulseMCP — <https://www.pulsemcp.com/submit>
- mcp.so — <https://mcp.so/submit>
- Smithery — <https://smithery.ai/new> (can run from the repo; a `smithery.yaml` improves the listing)
