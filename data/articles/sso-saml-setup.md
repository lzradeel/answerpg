# Set up SAML single sign-on

SAML single sign-on (SSO) lets members sign in to Wrenfield through your identity provider. SSO is available on the Business and Enterprise plans, and only workspace owners and admins can configure it.

## Supported identity providers

Wrenfield works with any SAML 2.0 identity provider. Okta, Microsoft Entra ID, Google Workspace, OneLogin and JumpCloud have step-by-step guides in Settings > Security > SSO.

## Before you start

Verify your email domain first. In Settings > Security > Domains, add the domain and publish the TXT record `wrenfield-verification=<code>` in your DNS. Wrenfield checks the record every 10 minutes for up to 48 hours.

## Configure the connection

1. In your identity provider, create a SAML application.
2. Set the ACS URL to `https://auth.wrenfield.app/saml/acs`.
3. Set the Entity ID to `https://auth.wrenfield.app/saml/<workspace-id>`, using the ID shown in Settings > Workspace.
4. Send the user's email address as the NameID. The optional attributes `firstName` and `lastName` fill in profile names.
5. Paste the IdP metadata URL into Wrenfield, or upload the X.509 signing certificate. A metadata URL is refreshed every 24 hours, so certificate rotations are picked up automatically.
6. Click Test connection, then Enable.

## Enforcing SSO

After SSO is enabled, you can turn on Require SSO. Members with a verified email domain must then sign in through the identity provider, and password and Google sign-in stop working for them. At least one owner keeps password sign-in as a fallback in case the identity provider is unavailable.

People who sign in through SSO for the first time are added to the workspace automatically with the Member role. Admins can change this default to Guest.

## Sign-in errors

- `WF-4032`: the SAML response signature could not be verified. This usually happens after the identity provider rotates its certificate while Wrenfield still has the old one. Upload the new certificate or switch to a metadata URL.
- `WF-4033`: the SAML assertion is outside its validity window. Check that the identity provider's clock is accurate, because Wrenfield accepts a clock skew of up to 3 minutes.
- `WF-4036`: password sign-in was blocked because the workspace requires SSO. Use the Sign in with SSO button instead.
