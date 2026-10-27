# Sync troubleshooting

The sync indicator in the bottom-left corner of the desktop app shows the state of your changes. Green means everything is synced, yellow means changes are waiting to upload, and red means sync stopped with an error. Click the indicator to see the error code and the number of pending changes.

## First checks

- Check status.wrenfield.app for open incidents.
- Make sure your network allows HTTPS to `*.wrenfield.app` on port 443 and WebSocket connections to `wss://sync.wrenfield.app`.
- If you are behind a corporate proxy, set `sync.proxy` in `~/.wrenfield/config.toml`, for example `sync.proxy = "http://proxy.internal:8080"`.
- Restart the app after changing the config file.

## Slow or stalled sync

Sync uploads changes in batches. The `sync.batch_size` setting controls how many changes go into each sync request. The default `sync.batch_size` is 200 and the maximum is 500. On slow or unstable connections, lower it to 50 so each request can finish before the connection drops.

When WebSocket connections are blocked, the app falls back to polling. The `sync.interval_seconds` setting controls how often it polls, and the default is 30 seconds.

## Error codes

- `WF-4091`: sync conflict. The page was changed on another device while you were editing it. Both versions are kept, and yours is saved as a copy with "(conflicted copy)" at the end of the title.
- `WF-4092`: offline edits older than 14 days were not uploaded. They are saved as recovery copies in `~/.wrenfield/recovery`, where you can open them and paste the content back into the page.
- `WF-5030`: the sync service is temporarily unavailable. The app retries on its own, so no action is needed.

## Reset the local cache

If the indicator stays red after the checks above, choose Help > Troubleshooting > Reset local cache. Unsynced changes are copied to the recovery folder first, then the app downloads your pages again.

## Contacting support

Choose Help > Troubleshooting > Export sync log. This saves `wrenfield-sync.log` with the last 7 days of sync activity. Attach it to your support request along with your workspace ID.
