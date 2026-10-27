# Security and compliance

This article summarizes how Wrenfield protects workspace data and which certifications and agreements are available. Security documents can be requested from the Trust Center at trust.wrenfield.app.

## Certifications and agreements

- SOC 2 Type II: Wrenfield is audited every year by an independent firm. The current report covers the 12 months ending June 30, 2026, and is available under NDA from the Trust Center.
- ISO/IEC 27001:2022: the Wrenfield information security management system is certified, and the certificate can be downloaded from the Trust Center without an NDA.
- GDPR: a data processing agreement (DPA) is part of the Terms of Service on every plan. A countersigned copy can be downloaded from Settings > Legal.
- HIPAA: Wrenfield signs a business associate agreement (BAA) on the Enterprise plan only. Workspaces without a BAA must not store protected health information.

## Encryption

Data is encrypted at rest with AES-256 and in transit with TLS 1.2 or higher. Enterprise customers can add Enterprise Key Management, which encrypts workspace content with a key that you control in AWS KMS. Revoking the key makes the content unreadable to Wrenfield within 15 minutes.

## Account security

Members can protect their accounts with two-factor authentication using an authenticator app or a WebAuthn security key. On Business and Enterprise, owners can require two-factor authentication for every member.

Sessions on the web and desktop apps last 30 days by default. Admins on Business and Enterprise can set a shorter session length, anywhere from 1 hour to 30 days, in Settings > Security > Sessions.

## Network controls

Enterprise workspaces can restrict access to an IP allowlist of up to 50 CIDR ranges. Requests from other addresses, including API calls, are rejected. Owners can always sign in from any address to update the list.

## Testing and reporting

An independent firm runs a penetration test every year, and a summary of the results is published in the Trust Center. Wrenfield also runs a public bug bounty program. Report vulnerabilities to security@wrenfield.app and expect an acknowledgment within 2 business days.
