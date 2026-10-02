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
- [new] TL | Solo EditRef in the Viewer | TL panel (Alt+Shift+D) turns off every video track except EditRef and BurnIn to watch the edit on its own; press it again to turn them all back on.
- [new] The Import Shots transcode queue has a Skip Current button: a plate that hangs can be skipped, its originals go back in place and the queue moves on to the next one; failed plates show the reason when you hover over Error.
- [improved] Review Pic and Viewer | Snapshot trim only the black around the image, so zoomed or panned shots are no longer cut.
- [improved] Review Pic and the Shift+Click of Viewer | Snapshot open the picture in FrameRev to annotate it, replacing the ShareX image editor that came inside HieroTools, which is no longer included. FrameRev 0.265 or later has to be installed and opened once; otherwise a message says so.
- [new][mac] Review Pic and the Shift+Click of Viewer | Snapshot now work on macOS too, opening the picture in FrameRev to annotate it.
- [new][studio] Ctrl+Alt+Click on Rev Dir in the Flow Review panel opens the delivery slate's Submission Note with Submitting For and Media Color; it never overwrites a newer note and asks before saving an empty one.
- [new][studio] The Slate Frame button in the Flow | S3 panel saves the viewer image as the shot's slate frame for the delivery slate.
- [improved] Every status button in the Flow Review panel now has a tooltip listing its click gestures.
- [new][client] The Flow Review panel has Rev Netflix and SL Approved status buttons.
- [new] The Flow Pull results window can show only the shots in review (Only in review).
- [new][for: Reviewers][studio] the Flow Pull results window can also show only your own reviews (Only for me).
- [new] HieroTools now answers PipeSync's Show shot in NukeStudio: it opens the project if needed, switches to the sequence, marks the shot and brings NukeStudio to the front.
- [improved] Create Shot now creates the task folders in lowercase, the same as PipeSync, so a task no longer ends up with two folders that differ only in capitalization.
- [fixed] Shot Info, Push, Assign and Clear Assignees now find the shot when the clip's path has the project name in lowercase.
