# What's new in LGA HieroTools

## v4.022 (2026-10-28)

- **New:** Shot Marks, en el panel Review, lee la planilla de breakdown y marca cada shot en el timeline en su timecode; con Shift+Click en Previous Annotation y Next Annotation saltás de un shot al otro y se abre una ventanita con la descripción, el brief y los datos de ese shot en la planilla, con el vendor en su color; mientras está abierta, cambia sola cuando el playhead entra en otro shot.
- **New:** Shot Marks también funciona con planillas sin timecode que solo traen una foto por shot: `Locate from Thumbnails...` encuentra cada foto en el video del timeline, marca el plano entero y te deja revisar los dudosos paso a paso sobre el visor, al lado de la foto; al navegar las marcas, la ventanita muestra la foto de la planilla y resalta los shots omitidos o posiblemente omitidos. (Windows only)
- **New:** Si además le das el EDL del armado, Shot Marks marca cada shot exactamente de corte a corte y la ventanita muestra el clip de cámara y el SRC TC de cada uno. (Windows only)
- **Fixed:** En los proyectos con color management, Fix Colorspaces deja en Rec.709 los mp4 y mov de los tracks de plates y de EditRef, en vez de pasarlos a ACEScg o dejarlos como venían.

## v4.021 (2026-10-20)

- **Improved:** La descarga de LGA HieroTools pasa de 435 MB a unos 35 MB: el pack ya no trae programas de terceros que ninguna herramienta usa.
- **Fixed:** Create V000, Import Shots y el transcode de EXR ya no fallan en una máquina que no tiene instalado el runtime de Visual C++ de Microsoft. (Windows only)

## v4.020 (2026-10-20)

- **New:** Hover an open project in the Projects panel to save it as the next version with one click; if a newer version already exists on disk, it asks before using the next free number.
- **New:** Hover an open project in the Projects panel to upload it to Wasabi through FileManager S3; the icon shows when the upload is running, finished or failed.
- **Improved:** Apply AMF uses the shot's .csp LUT before any other look file: when there is one, it applies only that LUT, with linear interpolation in ACEScg.
- **Improved:** Create NK v000 loads the shot's .csp LUT into the template's look nodes (linear, ACEScg) and turns off the CDL nodes when there is one.
- **Fixed:** LGA BurnIn's background panels stay lined up with their text when the sequence format differs from the clip's.
- **Fixed:** Adding the LGA BurnIn soft effect no longer freezes the timeline viewer; moving the playhead updates the image right away.

## v4.01 (2026-10-14)

- **Improved:** When Flow Pull finds none of the timeline shots, the warning tells you whether the project is missing from PipeSync or the shot names don't match Flow, and lists the names it searched for.
- **Fixed:** Flow Pull, Push, Shot Info and the other Flow tools find shots whose name has a single description block or a description that starts with a number, instead of reporting that they aren't in PipeSync.

## v4.00 (2026-10-13)

- **New:** Drop a Nuke Studio or Hiero 17 project onto the Projects panel to save a separate Nuke 16.0 copy, with an editable next-version name, a folder chooser and an explicit choice to discard incompatible annotations.
- **New:** In projects framed for 3:2, the Projects panel now turns the 3:2 viewer mask on at half opacity every time you switch to one of their timelines.
- **Improved:** Flow Shot Info separates the responsible artists from Viewers who retain task access, while preserving version and assignment history.
- **Improved:** TL | Refresh and timeline switches apply the preferred Media Spreadsheet column order, widths and visibility, with rows sorted by Clip.
- **Improved:** Download AMF downloads the look files of every selected shot at once when two or more clips are selected, instead of one shot at a time.
- **Improved:** Shot Info opens as tall as its content instead of at a fixed size, so a shot with little to show no longer opens a mostly empty window.
- **Fixed:** Switching timelines in the Projects panel keeps one Media Spreadsheet tab instead of accumulating duplicates.
- **Fixed:** Apply AMF applies the shot's .cdl and .clf again instead of reporting that valid look files could not be loaded.

## v3.99 (2026-10-08)

- **Improved:** Apply AMF now applies the shot's .cube LUT, together with the .cdl grade when there is one.
- **Improved:** Fix Colorspaces, and the automatic fix after a Flow Pull, now also fix the other loaded versions of each clip, so switching versions keeps the right color space.
- **Improved:** Create NK v000 points LUT look nodes that use a .cube file to the shot's .cube in Look_Files.
- **Fixed:** Apply AMF no longer deletes effects you had added to the clip: the look goes on top of them.
- **Fixed:** Apply AMF works with the OCIO v2 configs that ship with Nuke 17, and warns when a look file is missing or corrupt instead of leaving the clip black.
- **Fixed:** Compare Versions now loads the previous version in the same color space as the comp in color-managed projects, so the difference compares like with like.
- **Fixed:** Fix Colorspaces no longer skips plates and comps it used to report as having no color transform available.
- **Fixed:** Contact Sheet connects the clips in timeline order: the first clip on the left is input 0, even when the selection includes effects.
- **Fixed:** Create NK v000 now trims the review range (without handles) on every movie output of the template, whatever the Write node is named.

## v3.98 (2026-10-06)

- **Improved:** Create NK v000 works with a template that only has the plates the project uses: aPlate is the only one it needs, and the plate Reads can be empty with just their label.
- **Improved:** The Flow Pull results window remembers its Only in review and Only for me checkboxes, the same way it already remembers Keep this window on top.
- **Fixed:** Create NK v000 no longer rejects shots whose name has no vendor code at the end.
- **Fixed:** Nuke Studio no longer prints a "Can't restore panel" message for every HieroTools panel at startup: the installer now sets this up on its own.

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
