# Webhooks

Webhooks send an HTTPS POST to your server when something changes in your workspace, so you don't have to poll the API. Admins manage webhooks in Settings > API > Webhooks, and each workspace can register up to 20 webhook endpoints.

## Events

Pick the events each endpoint receives:

- `page.created`, `page.updated` and `page.deleted`
- `task.created`, `task.assigned` and `task.completed`
- `comment.created`
- `member.joined`

Payloads include the event type, the time it occurred and the ID and metadata of the affected object, up to 256 KB. Page content is not included, so fetch it from the API if you need it. Events can arrive out of order, so sort them by the `occurred_at` field.

## Headers

- `X-Wrenfield-Event` contains the event type, such as `page.updated`.
- `X-Wrenfield-Delivery` is a unique ID for the delivery. Retries reuse the same ID, so store it to ignore duplicates.
- `X-Wrenfield-Signature` contains the timestamp and signature in the form `t=1761480000,v1=<hex digest>`.

## Verifying signatures

Each endpoint has a signing secret that starts with `whsec_`. To verify a delivery, compute an HMAC-SHA256 of the timestamp, a period and the raw request body, using the signing secret as the key. Compare the result with the `v1` value using a constant-time comparison. Reject deliveries whose timestamp is more than 5 minutes old to block replayed requests.

## Retries and failures

Your endpoint must respond with a 2xx status within 10 seconds. Any other response, or a timeout, counts as a failure. Wrenfield retries a failed delivery up to 6 times with exponential backoff, over about 12 hours.

If every delivery to an endpoint fails for 72 hours, the endpoint is disabled and workspace admins get an email. Re-enable it from the webhook settings once your server is fixed.

## Delivery logs

The delivery log of each endpoint shows the status code, response time and payload of recent deliveries. Webhook delivery logs are kept for 14 days, and you can redeliver any event from the log while it is still listed.
