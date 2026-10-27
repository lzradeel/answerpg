# Offline mode

The Wrenfield desktop and mobile apps keep working without an internet connection. You can read and edit cached pages, check off tasks and write new pages, and your changes sync when the connection comes back.

## What is available offline

The apps automatically cache your 200 most recently opened pages. To keep more content on hand, use Make available offline:

- On desktop, right-click a space and choose Make available offline. Every page in the space is downloaded and kept up to date.
- On mobile, open a page and tap Download in the page menu.

File attachments larger than 50 MB are not cached and show a placeholder until you are back online. Offline search only covers cached pages.

Some actions need a connection: creating spaces, inviting people, changing sharing settings and exporting.

## Cache size

The desktop cache is limited by the `offline.max_cache_mb` setting in `~/.wrenfield/config.toml`, or `%APPDATA%\Wrenfield\config.toml` on Windows. The default value of `offline.max_cache_mb` is 2048, which is 2 GB. When the cache is full, the least recently opened pages are removed first, but pages in spaces marked for offline use are kept.

The `offline.prefetch_spaces` setting lists space keys to download at startup, which helps when you set up many computers the same way.

On mobile, the cache size is set in Settings > Storage. See Mobile apps for the limits.

## How offline edits sync

Edits made offline are queued on the device and uploaded in order when you reconnect. If someone else changed the same page in the meantime, Wrenfield keeps both versions so nothing is lost.

Offline edits must sync within 14 days. Changes that stay on a device longer than that are not uploaded, but they are saved as recovery copies. Sync troubleshooting explains how to find them.
