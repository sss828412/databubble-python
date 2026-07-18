# Security Policy

> This file belongs in the root of each DataBubble repository (databubble, databubble-knowledge, databubble-python). Adjust the "Supported versions" table per repo.

## Reporting a vulnerability

If you believe you've found a security vulnerability in DataBubble, please report it **privately**. Do **not** open a public GitHub issue, pull request, or discussion for security matters.

- **Contact:** _<add a dedicated security contact — e.g. security@yourdomain>_
- Please include: a description of the issue, the affected repository and version, steps to reproduce, and the potential impact.
- Please do **not** include live secrets (API keys, admin secret, warehouse credentials) in your report. Redact them.

We aim to acknowledge reports within _<X business days>_ and to provide a remediation timeline after triage.

## Coordinated disclosure

We ask that you give us a reasonable window to investigate and release a fix before any public disclosure. We're happy to credit reporters who follow coordinated disclosure, if they wish.

## Supported versions

| Version | Supported |
|---|---|
| latest `main` | ✅ |
| older releases | ❌ (please upgrade) |

_(For `databubble-python`: track supported SDK versions here once it is published and versioned.)_

## Scope

In scope: authentication/authorization, API key handling and metering, BYOK credential handling, data-source connector isolation, and any path that could expose client data.

Out of scope: issues that require a compromised host or physical access, and best-practice suggestions without a demonstrable vulnerability (please file those as normal issues).

## What we do to protect data

- API keys are stored as **SHA-256 hashes only**; raw keys are shown once and never persisted.
- Admin operations require a separate secret, compared in **constant time**.
- Auth is **deny-by-default** on all non-public routes; a production boot guard prevents shipping with auth disabled.
- BYOK credentials are **encrypted at rest** and the credential path **fails closed**.
- All data-source access is **read-only**, with row ceilings and timeouts, and **per-tenant isolation**.

_Please verify the security contact and response-time commitments above before publishing this file._
