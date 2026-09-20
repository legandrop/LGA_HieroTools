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

- **Broadly reusable:** several tools in `Viewer | TL`, parts of `Edit`, parts of `Review`, and `ClipColor`
- **Reusable with adaptation:** `Projects`, some `Flow Review` utilities, and some comparison / reconnect tools
- **Strongly pipeline-specific:** most of `Flow Review`, `Flow | S3`, and `Assignee`, plus anything tied to Flow Production Tracking, Wasabi, PipeSync, or studio naming rules

## Panels Overview

### Flow Review Panel

Tools for the Flow review cycle: pull current data, inspect shots, create review
snapshots, and push context-valid review/delivery states. The runtime module and
dock id remain `LGA_NKS_Flow_Panel` / `com.lega.FPTPanel`; only the visible title
and private folder changed.

Internal reference: [Flow Review Panel](LGA_HieroTools/docs/LGA_NKS_Flow_Rev_Panel_README.md).

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

### Flow | S3 Panel

Production-facing tools split into two visual blocks. The first six actions
belong to Flow; the final five belong to FileManagerS3/Wasabi S3. The runtime
module and dock id remain `LGA_NKS_Coordination_Panel` /
`com.lega.FlowProdPanel` for layout compatibility.

Internal reference: [Flow | S3 Panel](LGA_HieroTools/docs/LGA_NKS_Flow_S3_Panel_README.md).

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
- **FileManagerS3**  
  Opens the shot folder in FileManagerS3.
- **Download Shot**  
  Downloads the shot from Wasabi S3.
- **Upload Shot**  
  Uploads the shot to Wasabi S3.
- **Download Clip** — Click downloads the latest available version;
  Shift+Click: downloads the selected version.
- **Download AMF** — Downloads the selected shot's `_input/Look_Files` folder.

The former **.Psync** button is intentionally hidden because that handoff is no
longer used. Its script remains in the repository as a documented legacy tool.

### Viewer | TL Panel

Viewer and timeline utilities. Every label declares its scope with `Viewer |`
or `TL |`, so similarly colored controls do not imply an unrelated function.

- **Viewer | Rec.709**
  Changes the viewer LUT to ACES / Rec.709.  
  Shortcut: `Shift+V`.
- **Viewer | Mask 3:2**
  Sets the viewer overlay to 3:2 and cycles mask styles `(None, Half, Full)`, insetting the BurnIn track burn-ins so the side bars do not cover them.
- **Viewer | Frame Number**
  Toggles the frame-number burn-in and positions it in the visible bottom-left
  area of the viewer, creating the frame-only burn-in when needed.
  Shortcut: `Shift+F`.
- **Viewer | Snapshot**
  Click: creates a snapshot from the current viewer image, crops it to the
  sequence aspect ratio, and copies it to the clipboard. Shift+Click opens the
  same temporary capture in ShareX ImageEditor LGA without saving it.
- **TL | Refresh**
  Rebuilds the active timeline view when it becomes unstable: it preserves the
  view state, cleans temporary `NukeVFX` tracks, refreshes the sequence and
  restores zoom, scroll and track position.
- **TL | Top Track**
  Scrolls to the top track in the timeline.  
  Shortcut: `Ctrl+Shift+T`.
- **TL | In/Out EditRef**
  Sets sequence In and Out from the closest clip on the `EditRef` or
  `EditRefClean` track.
  Shortcut: `Ctrl+Shift+U`.
- **TL | Prev Rev [User]**
  Searches for the previous clip with that user's review status and adjusts the view by setting In / Out from EditRef, selecting the clip, and fitting the zoom.
- **TL | Next Rev [User]**
  Searches for the next clip with that user's review status and adjusts the view by setting In / Out from EditRef, selecting the clip, and fitting the zoom.
- **TL | ON Clips / OFF v00**
  Click: enables all timeline clips and disables `v00`/`v000` task clips.
  Shift+Click: applies only to selected clips.
- **TL | ON/OFF _comp_**
  Enables or disables the clip on the `_comp_` track.
  Shortcut: `Shift+D`.
- **TL | ON/OFF _roto_ / _cg_**
  Enables or disables the second task track: `_roto_` in Studio and `_cg_` in
  Client. Shortcut: `Ctrl+Shift+D`.

### Edit Panel

Timeline editing, shot setup, reconnect, media repair, colorspace, and validation
utilities. Button colors identify those functional groups; they are not status
indicators.

- **Rec709 | Clip**  
  Sets the selected clips' color transform to Rec.709.
- **Default | Clip**  
  Sets the selected clips' color transform to default.
- **Compositing Log | Clip**  
  Sets the selected clips' color transform to `compositing_log`.
- **Fix Colorspaces**  
  Uses the project's PipeSync color-management settings when enabled; otherwise
  detects and fixes clips using `rec709` or `gamma2.2`.
- **Apply AMF**
  Adds or removes the shot's CDL/CLF effects on selected EXRs, or on EXRs under
  the playhead when fewer than two clips are selected. Shortcut: `Shift+L`.
- **Import shot**  
  Imports shots into the project: plates and references into the shot bin and onto their tracks.
- **Set Shot Name**
  Sets the shot name based on the file path.
- **Create EXR v000**
  Opens the validator that prepares black EXR `v000` sequences for one or more shots/tasks.
- **Create NK v000**  
  Builds the shot's Nuke comp script from the project template. See [Docu_CreateNKScript.md](LGA_HieroTools/docs/Docu_CreateNKScript.md).
- **New Video Track**
  Creates a new video track above the selected track.
- **Extend &Edit**  
  Extends the clip out point to the playhead by retiming the clip.  
  Shortcut: `Alt+E`.
- **Trim &In**  
  Trims the clip In point to the playhead.  
  Shortcut: `Alt+[`.
- **Trim &Out**  
  Trims the clip Out point to the playhead.  
  Shortcut: `Alt+]`.
- **Reconnect ▸**
  Opens the compact reconnect menu: `T > N`, `N > T`, and `Win > Mac`.
  The first two swap their corresponding path roots. `Win > Mac` reconnects
  the whole timeline on click and only selected clips on Shift+Click, then
  performs a self-replace to rebuild their media/bin relationships.
- **Reconnect Media**  
  Opens a dialog for manual media reconnection.  
  Shortcut: `Alt+M`.
- **Replace Clip**  
  Replaces the media of the selected clip with a file you choose, even if it has a different name or folder. Pick any frame of a sequence. Frame range and resolution are checked before replacing, and trims, color and bin are kept. See [Docu_Clips_Zombie.md](LGA_HieroTools/docs/Docu_Clips_Zombie.md).
- **Self ReplaceClip**  
  Replaces the selected clip with its own media while preserving trims and
  color, rebuilding a damaged relationship with its bin item.
- **Fix Zombies**  
  Scans every clip in the timeline and repairs the broken ones (no Properties, no metadata, Reconnect Media does nothing) with a self replace. Offline ones are listed so you can fix them with Replace Clip.
- **Check Frames**  
  Checks selected clips for missing or corrupted frames.
- **Clear Tag**
  Removes all tags from the selected clips.

### Review Panel

Review and inspection tools for compare workflows, reveals, annotations, and
opening related Nuke scripts.

- **Difference Mode**  
  Toggles Difference mode on the `_comp_` track.
- **Compare Versions**  
  Creates a new `COMPARE` track with a previous version of the selected clip and puts the track into Difference mode.
- **Compare OFF**  
  Removes the `COMPARE` track and disables Difference mode.
- **Contact Sheet**
  Sends the selected timeline clips to the script currently open in NukeX,
  creates an `LGA_ContactSheet` from their Reads, and connects the Viewer. The
  network request and the NukeX operation run without blocking Nuke Studio.
- **Previous Annotation**
  Jumps to the previous annotation on the selected clip and wraps to the last.
- **Next Annotation**
  Jumps to the next annotation on the selected clip and wraps to the first.
- **Reveal in Explorer**  
  Opens the selected clips' folders in the default file manager; without a
  selection it opens the first open project's folder.
  Shortcut: `Shift+E`.
- **Reveal NKS Project**  
  Opens the folder of the project that owns the active sequence in the default
  file manager. With no active sequence, it only falls back when one project is open.
- **Reveal NK Script**  
  Opens the selected shot's `Comp/1_projects` folder in the default file manager.
  Shortcut: `Shift+R`.
- **OpenInNukeX**  
  Finds and opens a Comp script for the selected shot in NukeX.
  Shortcut: `Shift+X`.
- **Match Rev Ver**
  Click: matches the version of clips on the `_compRev_` track `(mov or mxf)` to the corresponding EXR version.
  Shift+Click: processes the whole timeline.
- **Compare Rev EdRef**
  Click: compares frame ranges between clips on the `_compRev_` track `(mov or mxf)` and the `EditRef` track.
  Shift+Click: compares the whole timeline.
- **Compare EXR aPlate**
  Click: compares frame ranges between clips on the `_comp_` track `(exr)` and the `aPlate` track.
  Shift+Click: compares the whole timeline.

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
