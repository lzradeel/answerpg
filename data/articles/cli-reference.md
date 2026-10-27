# CLI reference

The `wrenfield` command-line tool works with pages, tasks and tokens from a terminal, and can sync a folder of Markdown files with a space. The current version is 3.4.0.

## Install

- macOS and Linux with Homebrew: `brew install wrenfield/tap/wrenfield`
- Windows: `winget install Wrenfield.CLI`
- Any platform with Node.js 20 or later: `npm install -g @wrenfield/cli`

Run `wrenfield --version` to check the installed version and `wrenfield upgrade` to update it.

## Signing in

`wrenfield login` opens your browser to approve access and stores the credentials in the keychain of your operating system. Run `wrenfield whoami` to see the account and workspace in use.

In CI and other non-interactive environments, set the `WRENFIELD_TOKEN` environment variable instead of running `wrenfield login`. When `WRENFIELD_TOKEN` is set, it overrides any stored credentials. A service token is the usual choice here.

Profiles let you switch between accounts. Define them in `~/.wrenfield/config.toml` under `[profiles.<name>]`, then pass `--profile <name>` or set `WRENFIELD_PROFILE`.

## Global flags

- `--workspace <id>` runs the command against a specific workspace.
- `--json` prints machine-readable output. Set `cli.output = "json"` in the config file to make it the default.
- `--quiet` hides progress output, and `--verbose` prints each API request.

## Common commands

- `wrenfield pages list --space ENG` lists the pages in a space.
- `wrenfield pages get <page-id> --format markdown` prints a page as Markdown.
- `wrenfield tasks create --title "Prepare Q4 report" --due 2026-11-20` creates a task.
- `wrenfield tokens create --name ci --scope pages:read --expires-in 30d` creates a personal access token.
- `wrenfield import` and `wrenfield export` are covered in the Import and export article.

## Folder sync

`wrenfield sync ./docs --space ENG` keeps a local folder of Markdown files and a space in step.

- `--dry-run` prints the pages that would be created, updated or deleted, without uploading or writing anything.
- `--direction` accepts `push`, `pull` or `both`, and the default is `both`.
- `--delete` removes pages from the space when their files are deleted locally. It asks for confirmation unless you also pass `--yes`.
- `--batch-size` overrides the `sync.batch_size` setting for one run.

## Rate limits and exit codes

When the API rejects a request for exceeding the rate limit, the CLI waits and retries it automatically, up to 3 times. Exit codes:

- 0 means success.
- 1 means a general error.
- 2 means an invalid command or flag.
- 3 means authentication failed.
- 4 means the request was still rate limited after the retries.
