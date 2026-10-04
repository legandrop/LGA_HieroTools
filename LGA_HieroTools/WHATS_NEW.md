# What's new in LGA HieroTools

## v3.97 (2026-10-04)

- **New:** TL | Solo EditRef in the Viewer | TL panel (Alt+Shift+D) turns off every video track except EditRef and BurnIn to watch the edit on its own; press it again to turn them all back on.
- **New:** The Import Shots transcode queue has a Skip Current button: a plate that hangs can be skipped, its originals go back in place and the queue moves on to the next one; failed plates show the reason when you hover over Error.
- **New:** Review Pic and the Shift+Click of Viewer | Snapshot now work on macOS too, opening the picture in FrameRev to annotate it. (macOS only)
- **New:** Ctrl+Alt+Click on Rev Dir in the Flow Review panel opens the delivery slate's Submission Note with Submitting For and Media Color; it never overwrites a newer note and asks before saving an empty one. (Studio only)
- **New:** The Slate Frame button in the Flow | S3 panel saves the viewer image as the shot's slate frame for the delivery slate. (Studio only)
- **New:** The Flow Review panel has Rev Netflix and SL Approved status buttons. (Client only)
- **New:** The Flow Pull results window can show only the shots in review (Only in review).
- **New:** Reviewers: the Flow Pull results window can also show only your own reviews (Only for me). (Studio only)
- **New:** HieroTools now answers PipeSync's Show shot in NukeStudio: it opens the project if needed, switches to the sequence, marks the shot and brings NukeStudio to the front.
- **Improved:** Review Pic and Viewer | Snapshot trim only the black around the image, so zoomed or panned shots are no longer cut.
- **Improved:** Review Pic and the Shift+Click of Viewer | Snapshot open the picture in FrameRev to annotate it, replacing the ShareX image editor that came inside HieroTools, which is no longer included. FrameRev 0.265 or later has to be installed and opened once; otherwise a message says so.
- **Improved:** Every status button in the Flow Review panel now has a tooltip listing its click gestures.
- **Improved:** Create Shot now creates the task folders in lowercase, the same as PipeSync, so a task no longer ends up with two folders that differ only in capitalization.
- **Fixed:** Shot Info, Push, Assign and Clear Assignees now find the shot when the clip's path has the project name in lowercase.
