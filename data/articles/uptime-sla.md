# Uptime SLA

The uptime service level agreement (SLA) sets the monthly availability Wrenfield commits to and the service credits you receive if it is missed. The SLA covers the Business and Enterprise plans. Free and Team workspaces are not covered by an SLA.

## Commitments

- Business workspaces are covered by a 99.9% monthly uptime commitment.
- Enterprise workspaces are covered by a 99.95% monthly uptime commitment.

Uptime is measured for the web app, the API and the sync service. External checks run every minute from three regions, and a minute counts as unavailable when the checks from at least two regions fail. Current status and past incidents are published at status.wrenfield.app.

## What does not count as downtime

- Scheduled maintenance announced at least 72 hours in advance on status.wrenfield.app, up to 4 hours per month.
- Problems caused by your network, your devices or your identity provider.
- Features labeled as beta.
- Requests rejected because they exceed the API rate limits of your plan.

## Service credits

Credits are a percentage of the monthly fee for the affected month.

- Business uptime below 99.9% earns a 10% credit.
- Business uptime below 99.0% earns a 25% credit.
- Enterprise uptime below 99.95% earns a 10% credit.
- Enterprise uptime below 99.5% earns a 25% credit.
- Enterprise uptime below 99.0% earns a 50% credit.

Credits for a single month never exceed 50% of the fee for that month.

## Claiming a credit

An owner must request the credit within 21 days after the end of the month in which the downtime happened. Open a support request with the dates and times of the incident and the affected features. Approved credits are applied to your next invoice.

Service credits cannot be exchanged for cash, and they are the only remedy for missed uptime commitments.
