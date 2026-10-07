# Blender companion interface

This fork adds a companion machine surface alongside the live human application.
The human and agent operate on the same Blender datablocks and native operators;
there is no copied scene engine or domain-specific bone API. Upstream MIT attribution
is preserved. This implementation uses independently written general design patterns.

## Machine workflow

1. `inspect_blender_workspace` returns native collections/counts, document epoch,
   scene/view-layer identity, mode, active/selected entities, permission state and
   window/editor keys. Supplying an editor key reads that actual editor under a
   native context override, not a guessed viewport.
2. `capture_blender_context` pins immutable semantic context. For a human's “this”,
   use their **Capture editor context for AI** button and exact returned ID. An
   agent-requested capture is labelled separately. The bridge does not see chat or
   speech and cannot associate an arbitrary earlier gesture with an utterance.
3. `resolve_blender_context` returns original and fresh state plus staleness. It
   never replaces a missing capture with the current pointer or selection.
4. `discover_blender_capabilities` searches runtime native operator schemas and
   execution support. Exact RNA queries and real node-socket descriptions reuse
   existing introspection. Discovery is separate from authority and native poll.
5. `inspect_blender_entity` resolves any exposed bpy.data collection/name or a
   retained reference. Bounded native paths traverse RNA properties and collection
   keys/indices, e.g. Material → node_tree → nodes → key. Requested properties return
   actual values, schemas and digests. No code strings are evaluated.
6. `execute_blender_operation` uses one shared native path for property edits or
   supported native operators. The matching session permission must be enabled in
   Blender. Property edits require a native reference and expected value digest;
   operator calls require a captured editor, valid schema parameters and successful
   native `poll()`. For “this selected entity”, require `target_policy=captured_selection`.
   Explicitly named references use `target_policy=explicit`.
7. `observe_blender_operation` reads a retained original without replay. Property
   edits return verified readback; native operator FINISHED means completion, not
   verified domain correctness. Inspect the affected native state to verify it.
8. `compensate_blender_operation` restores a verified property value only when the
   retained target and current value match its after-digest. It uses fresh captured
   context and a new request ID. There is no universal operator rollback or silent
   global Blender Undo. Release settled captures explicitly.

## Versioned coverage: blender-companion/1, add-on protocol 15

| Surface | Implemented evidence | Explicit boundary |
| --- | --- | --- |
| Data reach | Runtime bpy.data collection discovery; native root/nested RNA refs | Custom Python attributes/callables and arbitrary eval are unavailable |
| Property operations | Writable BOOLEAN/INT/FLOAT/STRING/ENUM scalars and finite arrays/matrices | Pointer/collection assignment, file/script-path settings and driver expressions are refused |
| Objects/cameras/materials/nodes | Same inspect/property/action contract, native IDs and schemas | Each operation still requires valid native type/context/preconditions |
| Editor workspace | Real windows/screens/workspaces/area keys, scene/view layer and mode | No exhaustive widget/control inventory or OS focus claim |
| Viewport | Actual editor matrices, perspective and shading | Image-to-semantic capture atomicity is not implemented |
| Properties | Actual Properties tab and pinned datablock; button context when provided by Blender | Global timer cannot determine arbitrary focused UI property |
| Node Editor | Actual tree identity, active node and selected node names | Not a complete widget/socket-focus capture; nested refs require explicit inspection |
| Mesh editing | Native BMesh selected vertex/edge/face indices, finite/truncated observations | Indices are observation-only, not stable editable entity references |
| Armatures | Selected/active bones and generic native RNA paths | Bones are one domain, not privileged tool endpoints |
| Native operators | Runtime catalog; supported editing/display namespaces; schema and captured-context/poll validation; EXEC_DEFAULT | No generic modal workflow, transaction, domain verifier or compensation |

Property and native-operator permissions are separate, default off, and marked
SKIP_SAVE. Linked datablock property writes are refused. File/process/script/access
operator namespaces are not enabled through the companion. The current supported
operator namespaces and exclusions are returned by discovery/implemented in
`LiveEditorContext`; this is a capability boundary, not a sandbox for plugin code.
Existing arbitrary Python remains a separate legacy facility.

## State, identity and lifetime

Native references retain epoch, root/path and native pointer identity; names are
labels, not enough to substitute a different object. Captures retain selection,
mode, editor state and context digest. Property state uses its own expected digest:
disclosure is not mutation permission or a replacement for native preconditions.

Main-thread timer/request sampling increments source-specific selection serials.
Explicit captures preserve original intent; polling is not a complete event log
and can miss a rapid away/back transition between samples. Node/view/mesh context
is read at capture/guard time. Message bus alone cannot establish complete coverage.

File load, detected file identity change, server stop and add-on unload retire the
epoch. Editor identities are resolved against live windows, never trusted as raw
pointers from the client. Capture/operation observation after reconnect must precede
new work. Reusing an exact request ID returns the retained original; changed payload
reuse refuses. Never rekey a timeout to conceal uncertainty.

Retention is bounded: 32 captures, 512 native references, 64 admitted requests per
epoch. Property reads allow up to 32 requested fields, path depth 8 and finite value
sizes. Some schema/selection/editor observations are truncated explicitly. Results
remain session-only; durable recovery and push event subscriptions are not provided.

A failed property write attempts restoration and reports whether native restoration
was confirmed. An operator exception or incomplete result remains outcome_unknown;
it is never replayed automatically or presented as verified success.

## Verification and remaining gates

Focused stdlib tests exercise native-shaped object/camera/material/node property
operations, editor context, mesh observation, discovery/operator dispatch, deictic
target guards, stale identity/mode/selection/value refusal, retained originals,
compensation conflicts, failure recovery and packaging/inventory regressions.

Cloud testing must use the exact commit and fresh Blender GUI session, loopback,
ephemeral preferences, disabled telemetry/update checks, and deliberately enabled
session permissions. Run full pytest and real MCP tests across objects, cameras,
materials, nodes and editor contexts. Validate native operator completion with
separate domain readback, and report rendered image evidence independently.

Physical human interaction, complete Blender UI parity, safe generic modal/undo
transactions, durable receipts, authentication and atomic screenshot/context capture
remain separate work. No local Blender runtime or persistent access is required by
this change, and no private application source is included.

Official Blender 4.3.2 references: [message-bus limitations](https://github.com/blender/blender/blob/v4.3.2/doc/python_api/examples/bpy.msgbus.1.py),
[main-thread timer queue](https://github.com/blender/blender/blob/v4.3.2/doc/python_api/examples/bpy.app.timers.5.py),
[native editor context](https://github.com/blender/blender/blob/v4.3.2/source/blender/editors/screen/screen_context.cc).
