# API authentication

Every request to the Wrenfield API must send a token in the `Authorization` header as a bearer token: `Authorization: Bearer <token>`. The API base URL is `https://api.wrenfield.app/v2`. Tokens passed in the query string are rejected.

## Token types

- Personal access tokens start with `wfp_` and act as you, with your permissions. Create them in Settings > Account > API tokens. They expire after 90 days by default, and you can choose any lifetime from 1 to 365 days.
- Service tokens start with `wfs_` and belong to the workspace rather than a person. Admins create them in Settings > API. They do not expire until revoked and do not use a seat, which makes them the right choice for CI jobs and internal tools.
- OAuth 2.0 is for apps that act on behalf of other Wrenfield users. Use the authorization code flow with PKCE. OAuth access tokens last 1 hour, and refresh tokens last 60 days and are rotated on every use.

On Business and Enterprise, admins can set a maximum lifetime for personal access tokens in Settings > Security.

## Scopes

Each token is limited to the scopes chosen when it was created:

- `pages:read` and `pages:write` cover pages and files.
- `tasks:read` and `tasks:write` cover tasks and boards.
- `comments:write` allows adding comments.
- `members:read` allows reading the member directory.
- `admin` allows member management and reading audit events. Only service tokens can hold this scope.

## Versioning and workspaces

The `Wrenfield-Version` header pins the API version for a request, for example `2026-04-01`. If you leave it out, the request uses the API version that was current when the token was created. Sending the header on every request means a token rotation never changes behavior.

If the owner of a personal token belongs to more than one workspace, send the `Wrenfield-Workspace` header with the workspace ID, which starts with `ws_`.

## Authentication errors

- `WF-4010`: the `Authorization` header is missing or malformed.
- `WF-4011`: the token has expired or was revoked.
- `WF-4013`: the token is valid but lacks the scope this endpoint needs.
