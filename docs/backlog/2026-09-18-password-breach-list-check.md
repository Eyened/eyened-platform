# New passwords are not checked against a breached or common password list

**Status:** open

## Source

RBAC admin P3b brainstorm (password policy), 2026-09-18. P3b adopts NIST SP 800-63B-4
§3.1.1.2 for every path that sets a password: minimum 15 characters, maximum 128, no
composition rules, and a context blocklist (the username, `eyened`). The breach-corpus part
of that section's blocklist was deferred.

## What

Reject a new password that appears in a list of passwords from breaches or of common
passwords, in the same `check_new_password` function that enforces the rest of the policy.
Two ways to do it:

- **A bundled list:** a public common-password list (e.g. SecLists, MIT), filtered to
  entries of at least 15 characters, since shorter ones fail the length rule anyway. It is
  small, offline and deterministic.
- **The HIBP range API** (k-anonymity: only a 5-character SHA-1 prefix leaves the host).
  It covers far more, but adds an outbound call and a failure mode to every password
  change, from a platform that holds medical data. Some deployments (SURF Research Cloud)
  may block outbound calls.

## Why

NIST SP 800-63B-4 §3.1.1.2: verifiers "SHALL compare the prospective secret against a
blocklist that contains known commonly used, expected, or compromised passwords."
Until this lands, the platform does not meet that SHALL. The 15-character minimum removes most
of what such lists contain, which is why this was deferred rather than done in P3b, but
long leaked passphrases still get through.
