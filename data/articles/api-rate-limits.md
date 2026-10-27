# API rate limits

Rate limits stop bursts of traffic from slowing the API down for everyone. Limits apply per workspace and are counted over a rolling 60-second window, across all tokens in that workspace.

## Limits by plan

- Free workspaces can make 60 requests per minute.
- Team workspaces can make 300 requests per minute.
- Business workspaces can make 600 requests per minute.
- Enterprise workspaces can make 1,200 requests per minute, and higher limits can be arranged with your account team.

Some endpoints have their own limits on top of the plan limit:

- Search (`GET /v2/search`) allows 30 requests per minute per token on every plan.
- Batch (`POST /v2/batch`) accepts up to 50 operations, and each operation counts as one request toward the plan limit.
- SCIM endpoints allow 100 requests per minute per workspace and do not count toward the plan limit.

Webhook deliveries from Wrenfield to your servers never count toward any limit.

## Concurrency

Each token can have at most 10 requests in flight at once. A request beyond that is rejected with `WF-4291` and HTTP 429, even if the per-minute limit has room left. Reuse connections and queue work on your side instead of opening many parallel requests.

## Response headers

Every API response includes these headers:

- `X-RateLimit-Limit` is the plan limit for the current window.
- `X-RateLimit-Remaining` is the number of requests left in the current window.
- `X-RateLimit-Reset` is the Unix time, in seconds, when the window resets.

## When you hit the limit

A request over the limit returns HTTP 429 with the error code `WF-4290`. The `Retry-After` header gives the number of seconds to wait before sending another request. Wait at least that long, then retry with exponential backoff and some random jitter so that several workers do not retry at the same moment.

If you hit the limit often, look for polling loops. Subscribing to webhooks is usually cheaper than polling for changes, and the batch endpoint cuts the number of requests needed for bulk updates.
