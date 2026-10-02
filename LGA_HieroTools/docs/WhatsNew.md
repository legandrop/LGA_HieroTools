---
product: LGA HieroTools
release_repo: legandrop/LGA_HieroTools
tech_changelog: ChangeLog.md
version_heading: "v{v}:"
roles: [Coordinators, Reviewers]
editions: [studio, client]
platforms: [win, mac]
---
# What's new in LGA HieroTools
<!-- Editable while a version is unpublished. NOT append-only. Published versions are frozen. -->

## Unreleased

## v3.97
- [new] The Help menu has a new LGA HieroTools: What's new entry that shows what changed in each version.
- [new][studio] Ctrl+Alt+Click on Rev Dir in the Flow Review panel opens the delivery slate's Submission Note with Submitting For and Media Color; it never overwrites a newer note and asks before saving an empty one.
- [new][studio] The Slate Frame button in the Flow | S3 panel saves the viewer image as the shot's slate frame for the delivery slate.
- [improved] Every status button in the Flow Review panel now has a tooltip listing its click gestures.
- [new][client] The Flow Review panel has Rev Netflix and SL Approved status buttons.
- [new] The Flow Pull results window can show only the shots in review (Only in review).
- [new][for: Reviewers][studio] the Flow Pull results window can also show only your own reviews (Only for me).
- [new] HieroTools now answers PipeSync's Show shot in NukeStudio: it opens the project if needed, switches to the sequence, marks the shot and brings NukeStudio to the front.
- [improved] Create Shot now creates the task folders in lowercase, the same as PipeSync, so a task no longer ends up with two folders that differ only in capitalization.
- [fixed] Shot Info, Push, Assign and Clear Assignees now find the shot when the clip's path has the project name in lowercase.
