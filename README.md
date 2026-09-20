<p>
  <span style="font-size:1.6em;font-weight:700;line-height:1;">LGA HIERO TOOLS</span><br>
  <span style="font-style:italic;line-height:1;">Lega | v3.94</span><br>
</p>
<br clear="left">

These tools were developed for my own post-production pipeline in Hiero / Nuke Studio.
Some of them can be useful right away in other environments; others require adapting naming conventions, track structure, production integration, or internal services.
I am sharing this repository both for the reusable tools and as a reference implementation for panel-driven workflows inside Hiero / Nuke Studio.

## Installation

- Copy the contents of this folder into your `.nuke/Python/Startup` directory.
- Restart Hiero / Nuke Studio.
- If you are adapting the tools to your own environment, review any pipeline-specific integrations first, especially:
  - Flow Production Tracking / ShotGrid
  - Wasabi / S3 access
  - PipeSync-related paths and data
  - Studio-specific clip naming conventions
  - Track names such as `_comp_`, `_roto_`, `_cleanup_`, `_compRev_`, `EditRef`, `aPlate`, and `BurnIn`
  - Track naming logic documented in [docs/Docu_Logica_Nombres_Tracks.md](LGA_HieroTools/docs/Docu_Logica_Nombres_Tracks.md)

## User Settings

Some Hiero Tools settings are stored outside the repository so user preferences survive updates.

- **Windows:** `%APPDATA%\LGA\HieroTools\`
- **macOS:** `~/Library/Application Support/LGA/HieroTools/`
- **Fallback:** `~/.config/LGA/HieroTools/`

Current persisted settings:

- `CreateV000.ini`: stores the `Create v000` handle value.

## Reusability

- **Broadly reusable:** several tools in `ViewerTL`, parts of `Edit`, parts of `Review`, and `ClipColor`
- **Reusable with adaptation:** `Projects`, some `Flow Rev` utilities, and some comparison / reconnect tools
- **Strongly pipeline-specific:** most of `Flow Rev`, `Flow S3`, and `Assignee`, plus anything tied to Flow Production Tracking, Wasabi, PipeSync, or studio naming rules

## Panels Overview

### Flow Rev Panel

Tools for the Flow review cycle: pull current data, inspect shots, create review
snapshots, and push context-valid review/delivery states. The runtime module and
dock id remain `LGA_NKS_Flow_Panel` / `com.lega.FPTPanel`; only the visible title
and private folder changed.

Internal reference: [Flow Rev Panel](LGA_HieroTools/docs/LGA_NKS_Flow_Rev_Panel_README.md).

- **Flow Pull**  
  Click: pull all shots from the timeline.  
  Shift+Click: pull only the selected shot.
- **Shot Info**  
  Shows shot information and version comments for the task resolved from the
  active context (Comp, Roto, Cleanup, or another enabled task scope).
- **Review Pic**  
  Creates a viewer snapshot and saves it with its frame number so it can be sent together with review notes.
- **Review / delivery state buttons**

  Generated from Flow's context policy rather than a duplicated list. Studio
  and Client expose only their valid review/delivery states, in Flow order.

### Assignee Panel

Tools for assigning artists to Flow tasks and managing related Wasabi access policies.

- **Get Assignees**  
  Gets the users assigned in Flow for the selected tasks, with comp used by default. If multiple clips are selected, it processes all of them; if only one clip is selected, it uses the playhead.
- **Clear Assignees**  
  Click: removes assignees in Flow for the selected tasks, with comp used by default. If multiple clips are selected, it processes all of them; if only one clip is selected, it uses the playhead.  
  Shift+Click: scans approved / delivery_checked shots in `pipesync.db` and lets you clean their lines from Wasabi policies.
- **Dynamic user buttons**  
  User buttons are generated from PipeSync's `pipesync_stats.db`; there is no local JSON fallback.
  Click: assigns the user in Flow, mirrors the local databases, then grants Wasabi access in Studio after the stats mirror succeeds.
  Shift+Click: runs the same canonical PipeSync grant engine for that user. In Client, the Wasabi step is always skipped.
  Ctrl+Shift+Click: opens a window to manage the shots currently assigned to that user's Wasabi policy.

### Flow S3 Panel

Production-facing tools split into two visual blocks. The first six actions
belong to Flow; the final six belong to PipeSync/FileManagerS3. The runtime
module and dock id remain `LGA_NKS_Coordination_Panel` /
`com.lega.FlowProdPanel` for layout compatibility.

Internal reference: [Flow S3 Panel](LGA_HieroTools/docs/LGA_NKS_Flow_S3_Panel_README.md).

- **Create Shot**  
  Creates a shot in Flow based on the selected clip. In Client, external vendor
  suffixes are validated before any write and create the Shot/Task access links;
  `SUP` remains an internal naming suffix without vendor access and is omitted
  from the Flow Shot code; external vendor suffixes remain part of the code.
  Comp is the only task enabled by default, CG remains available but disabled,
  and Lega is the only reviewer offered in Client.
- **Modify Shot**  
  Modifies an existing shot in Flow. One clip at a time.
- **Check Shots Exist**  
  Checks whether shots from the context task tracks exist in Flow: Comp in
  Studio, and Comp plus every CG track in Client.
- **Thumbnail**

  Click: replaces the shot's thumbnail in Flow with a viewer snapshot, after a
  confirmation window comparing the current and proposed images. The upload
  runs on a background thread.

  Shift+Click: saves the same zoom-to-fill snapshot, cropped to the sequence
  aspect, to `N:/<project>/Thumbs`.
- **Shot Priority**  
  Toggles shot priority between high and normal. Its green/red gradient keeps
  it in the Flow block while signalling priority.
- **Reveal in Flow** — Click opens the preferred context task in Flow (Comp;
  CG fallback in Client); Shift+Click opens the full shot. Shortcut:
  `Ctrl+Shift+F`. Its green/gray gradient closes the Flow block.
- **.Psync**  
  Generates a `.psync` file for sharing.
- **FileManagerS3**  
  Opens the shot folder in FileManagerS3.
- **Download Shot**  
  Downloads the shot from Wasabi S3.
- **Upload Shot**  
  Uploads the shot to Wasabi S3.
- **Download Clip** — Click downloads the latest available version;
  Shift+Click: downloads the selected version.
- **Download AMF** — Downloads the selected shot's `_input/Look_Files` folder.

### ViewerTL Panel

Viewer and timeline utilities focused on framing, navigation, review navigation, and quick snapshots.

- **Viewer | Rec709**  
  Changes the viewer LUT to ACES / Rec.709.  
  Shortcut: `Shift+V`.
- **Viewer | 3:2**  
  Sets the viewer overlay to 3:2 and cycles mask styles `(None, Half, Full)`, insetting the BurnIn track burn-ins so the side bars do not cover them.
- **Refresh Timeline**  
  Refreshes the timeline while preserving the current zoom level. Useful when the timeline starts behaving incorrectly.
- **Top Track**  
  Scrolls to the top track in the timeline.  
  Shortcut: `Ctrl+Shift+T`.
- **In Out Editref**  
  Sets sequence In and Out based on the closest clip on the `EditRef` or `EditRefClean` track.  
  Shortcut: `Ctrl+Shift+U`.
- **Prev Rev [User]**  
  Searches for the previous clip with that user's review status and adjusts the view by setting In / Out from EditRef, selecting the clip, and fitting the zoom.
- **Next Rev [User]**  
  Searches for the next clip with that user's review status and adjusts the view by setting In / Out from EditRef, selecting the clip, and fitting the zoom.
- **Frame Number**  
  Moves the frame-number burn-in into the visible bottom-left area of the viewer.  
  Shortcut: `Shift+F`.
- **SnapShot**  
  Creates a snapshot from the current viewer image, crops it to the sequence aspect ratio, and copies it to the clipboard. Intended for quick notes or messaging.

### Edit Panel

Timeline editing, reconnect, colorspace, and validation utilities.
- **Rec709 | Clip**  
  Sets the selected clips' color transform to Rec.709.
- **Default | Clip**  
  Sets the selected clips' color transform to default.
- **Compositing Log | Clip**  
  Sets the selected clips' color transform to `compositing_log`.
- **Fix Colorspaces**  
  Detects and fixes clips using `rec709` or `gamma2.2`.
- **New Video Track**  
  Creates a new video track above the selected track.
- **Set Shot Name**  
  Sets the shot name based on the file path.
- **Import shot**  
  Imports shots into the project: plates and references into the shot bin and onto their tracks.
- **Create NK v000**  
  Builds the shot's Nuke comp script from the project template. See [Docu_CreateNKScript.md](LGA_HieroTools/docs/Docu_CreateNKScript.md).
- **Apply AMF**  
  Builds the shot's color chain (CDL + CLF) on the selected clips, driven by the shot's `.amf`. Click again to remove it. Shortcut: `Shift+L`.
- **Extend &Edit**  
  Extends the clip out point to the playhead by retiming the clip.  
  Shortcut: `Alt+E`.
- **Trim &In**  
  Trims the clip In point to the playhead.  
  Shortcut: `Alt+[`.
- **Trim &Out**  
  Trims the clip Out point to the playhead.  
  Shortcut: `Alt+]`.
- **Reconnect T > N**  
  Reconnects clips by changing paths from `t:` to `n:`.
- **Reconnect N > T**  
  Reconnects clips by changing paths from `n:` to `t:`.
- **Reconnect Win > Mac**  
  Click: reconnects all timeline clips.  
  Shift+Click: reconnects only the selected clips.
- **Reconnect Media**  
  Opens a dialog for manual media reconnection.  
  Shortcut: `Alt+M`.
- **Replace Clip**  
  Replaces the media of the selected clip with a file you choose, even if it has a different name or folder. Pick any frame of a sequence. Frame range and resolution are checked before replacing, and trims, color and bin are kept. See [Docu_Clips_Zombie.md](LGA_HieroTools/docs/Docu_Clips_Zombie.md).
- **Self ReplaceClip**  
  Replaces the selected clip with its own media, which rebuilds its bin entry. Fixes clips that stopped showing Properties or metadata.
- **Fix Zombies**  
  Scans every clip in the timeline and repairs the broken ones (no Properties, no metadata, Reconnect Media does nothing) with a self replace. Offline ones are listed so you can fix them with Replace Clip.
- **Clear Tag**  
  Removes all tags from the selected clips.
- **Match Rev Ver**  
  Click: matches the version of clips on the `_compRev_` track `(mov or mxf)` to the corresponding EXR version.  
  Shift+Click: processes the whole timeline.
- **Compare Rev EdRef**  
  Click: compares frame ranges between clips on the `_compRev_` track `(mov or mxf)` and the `EditRef` track.  
  Shift+Click: compares the whole timeline.
- **Compare EXR aPlate**  
  Click: compares frame ranges between clips on the `_comp_` track `(exr)` and the `aPlate` track.  
  Shift+Click: compares the whole timeline.
- **Check Frames**  
  Checks selected clips for missing or corrupted frames.

### Review Panel

Review and inspection tools for compare workflows, reveals, clip toggling, and opening related Nuke scripts.

- **ON Clips | OFF v00**  
  Click: enables all clips in the timeline and disables `v00` clips.  
  Shift+Click: applies only to selected clips.
- **ON OFF _comp_**  
  Enables or disables the clip on the `_comp_` track.  
  Shortcut: `Shift+D`.
- **ON OFF _roto_**  
  Enables or disables the clip on the `_roto_` track.  
  Shortcut: `Ctrl+Shift+D`.
- **Difference Mode**  
  Toggles Difference mode on the `_comp_` track.
- **Compare Versions**  
  Creates a new `COMPARE` track with a previous version of the selected clip and puts the track into Difference mode.
- **Compare OFF**  
  Removes the `COMPARE` track and disables Difference mode.
- **Reveal in Explorer**  
  Reveals the selected clips' files in Windows Explorer.  
  Shortcut: `Shift+E`.
- **Reveal NKS Project**  
  Reveals the active NKS project in Windows Explorer.
- **Reveal NK Script**  
  Opens the folder that contains the Nuke script associated with the selected clip.  
  Shortcut: `Shift+R`.
- **OpenInNukeX**  
  Opens the Nuke script associated with the selected clip in NukeX.  
  Shortcut: `Shift+X`.

### Projects Panel

Project browser and sequence switcher built around the studio's project structure and PipeSync storage.

- **Project list**  
  Scans projects on disk, shows open projects, and lets you switch sequences without losing viewer state. Each timeline remembers its zoom, horizontal scroll and playhead across sessions and project versions, and opening a project goes back to its last timeline.
- **Collapse / expand**  
  Clicking the name or the triangle of an open project collapses or expands its sequences without closing it.
- **Close project (×)**  
  Appears when hovering an open project. Asks before discarding unsaved changes, and jumps to another open project if the closed one was active.
- **Refresh** — Bold circular-arrow icon. Re-scans projects.
- **Reload Panel** — Solid two-arrow icon. Reloads and re-docks the panel using the external smart-reload script.
- **Settings** — Gear icon. Opens the panel configuration.
- **Organize Project** — Folder-with-arrow icon in the right rail. Organizes clips into bins based on their file path; its original Spanish tooltip is preserved.
- **Clean Project** — Trash icon in the right rail. Removes unused clips from the project; its original Spanish tooltip is preserved.
- **Auto-refresh settings**  
  Includes configurable refresh intervals for keeping the project list current.

### ClipColor Panel

Simple clip-color utility panel for quickly tagging selected clips.

- **v_00**  
  Sets the clip color to the `v_00` color.
- **Plate**  
  Sets the clip color to the Plate color.
- **EditRef**  
  Sets the clip color to the EditRef color.
- **Reference**  
  Sets the clip color to the Reference color.
- **Error**  
  Sets the clip color to the Error color.
- **Violet**  
  Sets the clip color to the Violet color.
- **Magenta**  
  Sets the clip color to the Magenta color.
- **Cyan**  
  Sets the clip color to the Cyan color.

## Pipeline-Specific Notes

This repository is not a generic plug-and-play product. Many tools assume:

- a specific shot naming scheme
- specific timeline track names
- Flow Production Tracking / ShotGrid connectivity
- Wasabi / S3 policy workflows
- PipeSync-based local database and path conventions
- internal project layouts used in my studio

If you are adapting this pack to your own pipeline, the most reusable approach is usually:

- keep the panel structure
- keep the UI / tooltip organization
- replace the external scripts behind each button
- adapt naming utilities and track filters to your own conventions

## Why Share It

Even when a panel is tightly tied to a studio workflow, it can still be useful as:

- a reference for building custom Qt panels inside Hiero / Nuke Studio
- an example of button-driven production tools
- a template for connecting timeline actions to external scripts
- a starting point for designing a studio-specific review or production toolkit
