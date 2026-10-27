# Release notes 2026

This page lists the main changes in each Wrenfield release this year. The desktop and mobile apps update automatically, and the web app always runs the latest version.

## 6.5, October 13, 2026

- Keyboard shortcuts can now be customized in the desktop app, including the quick capture shortcut.
- The GitHub integration supports GitHub Enterprise Server 3.10 or later on the Enterprise plan.
- The iOS app now requires iOS 17 or later.

## 6.4, September 8, 2026

- CLI 3.4.0 adds folder sync with the `--dry-run` and `--direction` flags.
- Enterprise audit log streaming now supports Amazon S3, alongside Splunk and Datadog.
- Task boards can be filtered by assignee and due date.

## 6.3, July 14, 2026

- A new data region in Australia, hosted in Sydney, is available for Enterprise workspaces.
- Mobile offline storage can now be set anywhere from 250 MB to 2 GB.
- Slack link previews now show the last editor of a page.

## 6.2, April 1, 2026

- API version `2026-04-01` adds the batch endpoint, with up to 50 operations per request, and cursor pagination on every list endpoint.
- Webhook signatures in the `X-Wrenfield-Signature` header now include a timestamp to block replayed deliveries. The legacy `X-Wrenfield-Hmac` header will be removed on December 1, 2026.

## 6.1, March 3, 2026

- SCIM provisioning now supports groups, so groups pushed from your identity provider can control access to spaces.
- Microsoft Entra ID customers can add Wrenfield from the Entra app gallery with SSO and SCIM preconfigured.

## 6.0, January 20, 2026

- Task boards with swimlanes and work-in-progress limits.
- A new editor engine that opens large pages up to three times faster.
- Personal access tokens now expire after 90 days by default. Existing tokens keep their original expiry date.

## Coming up

API v1 will be turned off on January 31, 2027. Requests to `/v1` endpoints will fail after that date, so move integrations to `/v2` before then.
