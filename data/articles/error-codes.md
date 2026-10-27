# API error codes

When a request fails, the API returns an HTTP status and a JSON body with a Wrenfield error code:

`{"error": {"code": "WF-4031", "message": "You do not have access to this page", "request_id": "req_8f2c41"}}`

The code is stable across API versions, while the message text can change. Match on the code in your integration, and log the `request_id`, which is also returned in the `X-Request-Id` header.

## Request errors

- `WF-4000`: the request body is not valid JSON.
- `WF-4001`: validation failed. The `fields` list in the response names each invalid field and the reason.
- `WF-4090`: revision conflict. The `If-Match` revision you sent is older than the current one. Fetch the latest version, reapply your change and retry.
- `WF-4130`: payload too large. The uploaded file is bigger than the per-file limit of your plan.

## Authentication and access

- `WF-4010`: the `Authorization` header is missing or malformed.
- `WF-4011`: the token has expired or was revoked.
- `WF-4013`: the token lacks the scope this endpoint needs.
- `WF-4031`: access denied. The request is authenticated, but the member or token does not have permission for the page, space or workspace. Ask an admin or the page owner to share it.

Sign-in errors from SAML single sign-on use other codes in the WF-403x range and are listed in the SSO article.

## Missing resources

- `WF-4040`: the resource does not exist, or its ID is wrong.
- `WF-4041`: the resource is in Trash. Restore it from Trash before reading or editing it.

## Limits

- `WF-4290`: the rate limit for your plan was exceeded. See API rate limits for the limits per plan and the headers that tell you when to retry.

## Server errors

- `WF-5000`: an internal error on our side. These errors are rare and are reported to our on-call team automatically. Retry once, and contact support with the `request_id` if the error continues.
- `WF-5030`: the service is temporarily unavailable because of maintenance or heavy load. Retry with exponential backoff. Planned maintenance is announced on status.wrenfield.app.
