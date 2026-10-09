# Inspected ASVS dataset

Inspected the official repository tree at tag `v5.0.0`, resolving to commit
`61a544f0fdbb7cc1578e0c3a3037a8a2874a944e`. This release publishes standard
hierarchical, flat, legacy, and CycloneDX JSON. The importer deliberately supports
only the standard hierarchical format. See data/README.md for the pinned source.

Actual field structure:

- Root: `Name`, `ShortName`, `Version`, `Description`, `Requirements`.
- Chapter: `Shortcode`, `Ordinal`, `ShortName`, `Name`, `Items` (sections).
- Section: `Shortcode`, `Ordinal`, `Name`, `Items` (requirements).
- Requirement: `Shortcode`, `Ordinal`, `Description`, `L`.

`Shortcode` includes the leading `V` (for example `V1.1.1`). `Ordinal` is a positive
integer matching the final identifier component. `L` is exactly a string `"1"`,
`"2"`, or `"3"`, indicating minimum verification level. `Version` is `"5.0.0"`.
Do not convert IDs to another notation or synthesize version-prefixed IDs. The
version belongs to the dataset snapshot.

There are 17 chapters and 345 requirements. Minimum-level counts are 70 at L1,
183 at L2, and 92 at L3. Cumulative counts are 70, 253, and 345. Tests assert these
counts only for the bundled complete release; custom imports may be valid subsets.

Pydantic rejects unexpected fields rather than silently discarding information.
Importer errors identify the failing field and error type but omit input values.
Duplicate identifiers and JSON keys are rejected, as are inconsistent parent IDs.
Unknown versions need inspection and an explicit adapter; no fallback guessing is
performed. UTF-8 BOM is accepted, and source strings are not stripped or rewritten.
