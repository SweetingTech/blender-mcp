# Captured Blender editor context (first slice)

This fork adds native, session-only bone context and guarded edits to the existing
MCP/add-on bridge. It does not provide complete Blender UI parity. The source and
MIT attribution are retained; this feature is independently implemented.

## Human and agent workflow

1. In Blender, select a bone in Pose Mode or armature Edit Mode.
2. Open the MCP sidebar and press **Capture selected bone for AI**. The displayed
   capture ID is an immutable referent. Tell the agent to use that capture ID, or
   explicitly identify the latest human-button capture. The bridge does not see
   chat and cannot infer which click preceded an utterance.
3. Agent calls `get_editor_context` with the capture ID. It returns original
   context, current context and a staleness indication. A missing/stale capture is
   not replaced by the current selection. An agent-requested capture is labelled
   `agent_request`, not a human interaction.
4. `discover_blender_controls` queries this runtime's RNA type/property/operator
   schemas; node descriptions use the existing scratch-node introspection path.
   Discovery does not grant permission or certify operator `poll()` success.
5. Enable **Allow captured bone edits** in the sidebar only for the intended
   session. This scoped switch defaults off and is not saved with the document.
6. `apply_bone_transform` takes the exact capture ID, captured `bone_digest`, a
   caller request ID and typed transform fields. Pose Mode supports only local
   `location` channels. Edit Mode supports armature-local `head`, `tail` and
   `roll` in radians. Coordinates use Blender scene length units.
7. Inspect the returned before/after receipt and native property verification;
   view the model through the existing `look` tool. Property readback alone does
   not establish a visually correct rig, evaluated motion or deformation.
8. `undo_bone_transform` compensates the receipt with a new request ID only while
   the same selection/mode/document and recorded after-state still match. It
   does not invoke global Blender Undo or revert unrelated human work.
9. Release settled captures with `release_editor_context`.

## Contract and lifetime

Add-on protocol 14 advertises the five context/action wire commands alongside
existing `bpy_api_lookup` and `describe_node_type`. The MCP binding adds six tools.
Older add-ons return unsupported-command errors; no raw-code fallback is used.

Captures contain a random session/document epoch, capture ID, selection serial,
object/armature/bone identities plus labels, mode, scene/view layer, selected
objects/bones, local bone state/digest, parent/length/constraints and unit scale.
Human captures also include the actual invocation area/window and view matrices
when available. Unavailable view data stays null; another viewport is not guessed.

Selection sampling runs in the existing main-thread command-drain timer and on
each request. The serial changes for sampled object/bone selection, active bone,
mode or document changes. Polling is not a complete input event log: a rapid
away-and-back transition entirely between samples can be missed. The explicit
button anchors the supported human workflow; arbitrary viewport clicks are not
claimed as captured events. Message bus alone would not fix coverage: Blender's
official message-bus example excludes viewport movement and animation changes.

Snapshots are not subscriptions. After socket reconnection, ask for current
context before any new action. Known duplicate request IDs return the original
receipt and never reapply the edit; changed payload reuse fails. An admitted edit
whose outcome remains unknown blocks replay of that request. File load, detected
document/view-layer replacement, server stop and add-on unload invalidate retained
captures/receipts/requests. Do not generate a new request ID to hide uncertainty.

Retention is bounded to 32 captures and 64 admitted action requests per epoch.
Captures may be released explicitly; results are retained until epoch retirement.
Restart only after settling outstanding work, not as an automatic retry strategy.

The bridge validates scope and preconditions on its main thread, refuses changed
selection/mode/identity/native values, and rejects malformed/nonfinite/oversized
transforms. Linked/shared/animated armatures, pose constraints/location locks and
connected edit bones or connected children are refused. A failed native write
attempts compensation to the observed before-values; a failure remains explicit,
and its request is never automatically re-executed.

## Coverage and remaining evidence

Implemented: active object/armature bone, selected object/bone names, native mode,
explicit human-button capture, scope/digest checks, pose location and disconnected
edit-bone endpoints/roll, readback and guarded compensation, native RNA lookup.

Unavailable: mesh vertex/edge/face selections, multi-object armature editing,
partial bone endpoint selections, node/asset/timeline selection, focused property,
complete UI/control inventory, rotation/scale actions, full event subscription,
chat/voice timing, automatic screenshot-to-context identity and native Ctrl-Z
integration. The existing screenshot picker targets objects, not bone selection.
These require additional typed observation/action slices and acceptance evidence.

The legacy `execute_blender_code` and direct socket `execute_code` remain separate
arbitrary-code facilities. The scoped switch is not a sandbox for those routes.
This change adds no socket authentication, remote bind or persistent access. Use
an isolated loopback process for cloud evaluation; no personal rig is needed.

## Validation

`python -m unittest discover -s tests -p test_live_editor_context.py -v` exercises
selection/mode/state/identity refusal, immutable originals, deduplication,
compensation conflicts, finite retention and failed-write recovery with RNA-shaped
stubs. It does not substitute for a live Blender test.

Cloud acceptance should use the exact feature commit, a fresh Blender GUI session
and synthetic rig. Disable telemetry and update checks, use loopback and ephemeral
preferences, and permit scoped edits only inside that session. Through the real
MCP client, inspect/capture/lookup/apply/readback/compensate in Pose and Edit modes;
verify stale selection and mode refusals. Record a rendered image and native
assertions separately. A programmatic capture operator test does not prove a
physical human click. A desktop human click remains a separate acceptance gate.

Official Blender 4.3.2 references:

- https://github.com/blender/blender/blob/v4.3.2/doc/python_api/examples/bpy.msgbus.1.py
- https://github.com/blender/blender/blob/v4.3.2/doc/python_api/examples/bpy.app.timers.5.py
- https://github.com/blender/blender/blob/v4.3.2/source/blender/editors/screen/screen_context.cc
