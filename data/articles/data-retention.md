# Data retention

Wrenfield keeps different kinds of data for different lengths of time. This article lists the retention period for each type of data and what happens when it ends.

## Trash

Deleted pages, tasks and files go to Trash. Anyone who had edit access can restore them from Trash for 30 days. After 30 days, items in Trash are permanently deleted and cannot be recovered by support. Owners can empty Trash early from Settings > Workspace.

## Page version history

Wrenfield saves a new version of a page as it is edited, grouped into snapshots every few minutes. How far back you can browse depends on your plan:

- Free plan: 7 days of version history.
- Team plan: 90 days of version history.
- Business plan: 1 year of version history.
- Enterprise plan: unlimited version history.

Restoring an old version creates a new version, so a restore never loses later edits.

## Logs

API request logs, shown in Settings > API > Request log, are kept for 30 days. They include the endpoint, status code, token name and response time, but not request bodies.

Audit log retention depends on your plan and is described in the Audit logs article.

## Backups

Wrenfield keeps encrypted backups of all workspace data for 35 days. Backups are used only for disaster recovery. They cannot be used to restore a single page, so use Trash or version history for that.

## Deleted workspaces

When an owner deletes a workspace, support can restore it for 14 days. After 14 days, the workspace is purged from live systems, and the remaining copies are removed as backups age out over the following 35 days.

## Departing members

Suspending or removing a member does not delete their content. Pages and tasks they created stay in the workspace until someone deletes them.

## Deletion requests

Owners can ask for the data of a workspace to be deleted under GDPR or similar laws by emailing privacy@wrenfield.app. These requests are completed within 30 days.
