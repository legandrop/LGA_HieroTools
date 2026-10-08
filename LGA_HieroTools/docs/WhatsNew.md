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

## v3.99
- [improved] Apply AMF now applies the shot's .cube LUT, together with the .cdl grade when there is one.
- [fixed] Apply AMF no longer deletes effects you had added to the clip: the look goes on top of them.
- [fixed] Apply AMF works with the OCIO v2 configs that ship with Nuke 17, and warns when a look file is missing or corrupt instead of leaving the clip black.
- [fixed] Compare Versions now loads the previous version in the same color space as the comp in color-managed projects, so the difference compares like with like.
- [improved] Fix Colorspaces, and the automatic fix after a Flow Pull, now also fix the other loaded versions of each clip, so switching versions keeps the right color space.
- [fixed] Fix Colorspaces no longer skips plates and comps it used to report as having no color transform available.
- [fixed] Contact Sheet connects the clips in timeline order again: the first clip on the left is input 0, even when the selection includes effects.
- [fixed] Create NK v000 now trims the review range (without handles) on every movie output of the template, whatever the Write node is named.
- [improved] Create NK v000 points LUT look nodes that use a .cube file to the shot's .cube in Look_Files.

## v3.98
- [fixed] Create NK v000 no longer rejects shots whose name has no vendor code at the end.
- [improved] Create NK v000 works with a template that only has the plates the project uses: aPlate is the only one it needs, and the plate Reads can be empty with just their label.
- [improved] The Flow Pull results window remembers its Only in review and Only for me checkboxes, the same way it already remembers Keep this window on top.
- [fixed] Nuke Studio no longer prints a "Can't restore panel" message for every HieroTools panel at startup: the installer now sets this up on its own.

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
