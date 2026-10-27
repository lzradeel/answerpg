# Data residency

Data residency lets Enterprise workspaces choose the region where their content is stored and processed. Workspaces on the Free, Team and Business plans are hosted in the United States.

## Available regions

- United States, hosted in Virginia. The API host is `api.wrenfield.app`.
- European Union, hosted in Frankfurt, Germany. The API host is `api.eu.wrenfield.app`.
- United Kingdom, hosted in London. The API host is `api.uk.wrenfield.app`.
- Australia, hosted in Sydney. The API host is `api.au.wrenfield.app`.

The region is chosen when an Enterprise workspace is created and is shown in Settings > Workspace > Region.

## What stays in the region

These types of data are stored only in the region of your workspace, including their backups:

- Pages, tasks, comments and file attachments.
- Search indexes and page version history.
- Workspace exports created by members.

A small amount of data is stored in the United States for every workspace: account emails and sign-in metadata, billing records, and support tickets. This data is needed to route sign-ins and run billing across regions.

## Using the API in another region

API calls for a regional workspace must go to the API host of that region. A request sent to the wrong host fails with HTTP 421 and error code `WF-4210`, and the response names the correct host. The CLI and the desktop and mobile apps pick the right host automatically after sign-in.

## Moving a workspace to another region

To move an existing workspace, the workspace owner opens a request with support. Migrations run in a scheduled window, and the workspace is read-only during the move. For workspaces under 100 GB, the move usually takes less than 4 hours.

Each Enterprise contract includes one region migration per contract year at no cost. Additional migrations are quoted by your account team.
