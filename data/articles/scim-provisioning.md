# SCIM user provisioning

SCIM lets your identity provider create, update and deactivate Wrenfield accounts automatically. SCIM provisioning is available on the Enterprise plan and requires SAML SSO to be configured first.

## Supported providers

Wrenfield implements SCIM 2.0. Okta, Microsoft Entra ID and OneLogin have prebuilt Wrenfield apps with SCIM enabled. Google Workspace supports SAML sign-in for Wrenfield but not SCIM provisioning, so Google Workspace customers manage members by hand or through the API.

## Connect your identity provider

1. Open Settings > Security > SCIM and click Generate token.
2. Copy the token, which starts with `wfscim_`. It is shown only once.
3. In your identity provider, set the SCIM base URL to `https://api.wrenfield.app/scim/v2` and paste the token as the bearer token.
4. Assign users and groups to the Wrenfield app and start provisioning.

SCIM tokens do not expire. Generating a new token revokes the previous one immediately, so update the identity provider right after rotating.

## What gets synced

- Users: the SCIM `userName` maps to the member's email, and `name.givenName` and `name.familyName` map to the profile name.
- Groups: pushed groups become Wrenfield groups, which you can add to spaces to control access.
- Status: setting `active` to false deactivates the member.

## Deprovisioning

When a user is deactivated or unassigned in the identity provider, Wrenfield suspends the member within 60 seconds. Suspension signs the person out of every device and revokes their personal access tokens. Their pages, tasks and comments stay in the workspace, and an admin can transfer page ownership from Settings > Members.

Reactivating the user in the identity provider restores the same account with its previous groups.

## Limits and errors

SCIM requests have their own limit of 100 requests per minute per workspace, separate from the public API limits.

- `WF-4014`: the SCIM token is invalid or has been revoked. Generate a new token and update your identity provider.
- `WF-4001`: a SCIM request failed validation, usually because `userName` is not a valid email address.
