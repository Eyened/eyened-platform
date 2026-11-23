# Triage Labels

The skills speak in terms of canonical triage roles. This file maps those roles to the label strings used in `Eyened/eyened-platform`.

| Label in mattpocock/skills | Label in our tracker     | Meaning                                                    |
| -------------------------- | ------------------------ | ---------------------------------------------------------- |
| `needs-triage`             | `status/needs-triage`    | Maintainer needs to evaluate this issue                    |
| `needs-info`               | `status/needs-info`      | Waiting on answers to the questions in the triage notes    |
| `ready-for-agent`          | `status/ready-for-agent` | Fully specified, ready for an AFK agent                    |
| `ready-for-human`          | `status/ready-for-human` | Requires human implementation                              |
| `wontfix`                  | `status/wontfix`         | Will not be actioned                                       |
| `bug`                      | `type/bug`               | Something is broken                                        |
| `enhancement`              | `type/feature`           | New feature or improvement                                 |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Labels outside this table keep their own meaning: `area/*` says where the work is, `type/maintenance` is refactoring and upkeep, and `status/blocked` can sit alongside a state label. Triage applies to this repo only, not to the security issues in `Eyened/designdocuments`.
