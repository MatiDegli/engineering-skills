# Delivery criteria

Apply these criteria when artifacts reach anyone beyond the machines that build them: published,
distributed, released, or deployed; see the [areas table](criteria.md#areas) and the
[project's shape](criteria.md#project-shape). Otherwise close the area in Coverage with
`DEL-* (nothing reaches anyone beyond the machines that build it)`.

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| DEL-01 | Builds identify the validated revision and use locked dependencies | Artifacts reach anyone beyond the machines that build them | [standard](standard.md#delivery-and-operations) |
| DEL-02 | Artifact contents are reviewed and installed outside the development tree, without secrets, private fixtures, caches, or local configuration | Artifacts are distributed | [standard](standard.md#delivery-and-operations) |
| DEL-03 | Releases are authorized, versioned, and record their changes | Releases exist | [standard](standard.md#delivery-and-operations) |
| DEL-04 | Distributed artifacts come with build provenance and a software bill of materials that consumers can verify | Artifacts are distributed at security level 2 or higher | [standard](standard.md#delivery-and-operations) |
