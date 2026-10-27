# Import and export

You can bring content into Wrenfield from other tools and export your workspace at any time. Imports and exports run in the background, and you get an email when one finishes.

## Importing

Open Settings > Import, or choose Import from the menu of a space in the sidebar. Members can import into any space where they can edit. Supported sources:

- Notion: in Notion, export the workspace as Markdown and CSV, then upload the zip file. Databases become task lists, and nested pages keep their structure.
- Confluence: upload an HTML space export. Page hierarchy, attachments and comments are kept.
- Markdown: upload a folder as a zip file. Folders become parent pages, and relative links between files are preserved.
- CSV: create tasks from a CSV file. Map the columns to title, assignee, due date and status during the import.

A single import can include up to 10,000 pages, and the uploaded file can be up to 5 GB.

## Import errors

- `WF-4131`: the import file is larger than 5 GB. Split the export into smaller files, for example one per space, and import them one at a time.
- `WF-4150`: the file format is not supported. Check that you uploaded a zip file for Notion, Confluence and Markdown imports, or a CSV file for tasks.

## Importing from the CLI

The CLI runs the same imports: `wrenfield import --source notion --file notion-export.zip --space ENG`. Use `--on-conflict` to decide what happens when a page with the same title already exists. The options are `skip`, `rename` and `overwrite`, and the default is `rename`.

## Exporting

Any member can export a page or space they can view as Markdown, HTML or PDF. Owners and admins can also export the whole workspace as Markdown, HTML or JSON. The JSON format includes comments and task metadata.

A full workspace export can run once every 24 hours. When it is ready, a download link is emailed to the person who requested it. The link is valid for 7 days.

To export a space from the CLI, run `wrenfield export --space ENG --format markdown --out ./backup`.
