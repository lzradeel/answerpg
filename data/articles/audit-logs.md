# Audit logs

The audit log records security-relevant activity in your workspace, so you can answer who did what and when. Audit logs are available to owners and admins on the Business and Enterprise plans.

## What is recorded

Each event includes the actor, the event name, the time, the IP address and the affected object. Common events include:

- `member.invited`, `member.removed` and `member.role_changed`
- `page.permissions_changed` and `page.exported`
- `workspace.export_requested` and `workspace.settings_changed`
- `token.created` and `token.revoked`
- `sso.config_updated` and `sso.sign_in_failed`

Events usually appear within 5 minutes. Entries cannot be edited or deleted, even by owners.

## Viewing and exporting

Open Settings > Security > Audit log to browse events. You can filter by actor, event name, date range and IP address. To download events, click Export CSV. Each export holds up to 100,000 events, so split long date ranges into several exports.

## API access

Audit events are also available from `GET /v2/audit-events`. The endpoint needs a service token with the `admin` scope. It returns events newest first, with up to 500 events per page and a cursor for the next page.

## Streaming to a SIEM

Enterprise workspaces can stream audit events to Splunk, Datadog or an Amazon S3 bucket. Streamed events are delivered within 60 seconds of being recorded. Set up a stream in Settings > Security > Audit log > Streaming, and a test event is sent when you save.

## Retention

- Business plan: audit events are kept for 180 days.
- Enterprise plan: audit events are kept for 2 years.

To keep events longer, export them on a schedule or stream them to your own storage, where your own retention rules apply.
