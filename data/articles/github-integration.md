# GitHub integration

The GitHub integration links pull requests, branches and commits to Wrenfield tasks, so a task always shows the state of the code that belongs to it. It is available on the Team, Business and Enterprise plans.

## Install the GitHub app

1. An admin opens Settings > Integrations > GitHub and clicks Install.
2. In GitHub, install the Wrenfield for GitHub app on your organization and choose the repositories it can see.
3. Back in Wrenfield, map each repository to a space.

Team workspaces can connect up to 20 repositories. Business and Enterprise workspaces can connect an unlimited number of repositories.

GitHub Enterprise Server 3.10 or later is supported on the Wrenfield Enterprise plan. The server must be able to reach `*.wrenfield.app` over HTTPS.

## Linking work to tasks

Every task has a key made of the space key and a number, such as `ENG-142`. Put the key in a branch name, a pull request title or a commit message to link it:

- Branch name: `eng-142-fix-login-redirect`
- Pull request title: `ENG-142 Fix login redirect`
- Commit message: `Closes ENG-142`

The task then shows each linked pull request with its status, review state and check results.

## Closing tasks automatically

When a pull request whose title, description or commits include `Closes`, `Fixes` or `Resolves` followed by a task key is merged, the task moves to Done. You can choose a different target status, or turn this off, in Settings > Spaces > Automations. Pull requests that are closed without merging leave the task unchanged.

## Permissions and updates

The app asks for read access to metadata, pull requests, issues and checks. It never reads the contents of your code. Updates arrive through GitHub webhooks, usually within a few seconds, and the Refresh button on a task fetches the latest state on demand.
