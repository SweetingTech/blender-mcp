"""MCP bindings for native editor context; authority stays in the add-on."""
import json


def register(mcp, connection):
    def send(command, params=None):
        try:
            return json.dumps({'ok': True, 'result': connection().send_command(command, params, read_only=command not in {
                'apply_bone_transform', 'undo_bone_transform'})}, allow_nan=False)
        except Exception as exc:
            return json.dumps({'ok': False, 'error': str(exc)})

    @mcp.tool()
    def get_editor_context(capture_id: str | None = None) -> str:
        """Read actual active object, selected bones, mode and supported live context.

        With a capture ID, read the immutable original and fresh state/staleness.
        Without it, discover latest explicit human capture. Does not know chat
        timing: bind 'this bone' to an explicit capture, never silently retarget.
        Unsupported UI/subelement fields are explicitly listed. Requires add-on 14.
        """
        return send('get_editor_context', {'capture_id': capture_id})

    @mcp.tool()
    def capture_editor_context() -> str:
        """Pin the current single active bone, mode, identity and native properties.

        This is an agent-requested capture, not evidence of a human gesture.
        Prefer the user's Capture selected bone for AI button for 'this bone'.
        Preserve capture_id and bone_digest for guarded actions. Capacity is finite.
        """
        return send('capture_editor_context')

    @mcp.tool()
    def release_editor_context(capture_id: str) -> str:
        """Release an immutable context capture when its workflow is settled."""
        return send('release_editor_context', {'capture_id': capture_id})

    @mcp.tool()
    def discover_blender_controls(query: str, node_type: bool = False) -> str:
        """Discover native RNA types/properties/operator parameters on this Blender.

        Examples: PoseBone.location, EditBone, bpy.ops.pose.transforms_clear.
        node_type=True describes sockets via the existing scratch-node routine.
        Discovery is not permission or proof that an operator polls successfully;
        only the captured bone action contract below is executable through this
        scoped path. Other operations still require the legacy Python facility.
        """
        return send('describe_node_type' if node_type else 'bpy_api_lookup',
                    {'bl_idname': query} if node_type else {'query': query})

    @mcp.tool()
    def apply_bone_transform(capture_id: str, expected_digest: str, request_id: str,
                             location: list[float] | None = None,
                             head: list[float] | None = None,
                             tail: list[float] | None = None,
                             roll: float | None = None) -> str:
        """Guarded native edit of the exact captured selected bone, with readback.

        User must enable Allow captured bone edits in Blender for this session.
        POSE accepts location only (bone local channels, scene length units).
        EDIT_ARMATURE accepts head/tail (armature-local coordinates) and roll
        (radians). Connected/shared/linked/animated or constrained cases may be
        refused. No mode switch, keyframes, rotation or arbitrary Python.
        Selection/mode/document/property changes invalidate the write. Reuse the
        exact request ID on uncertain transport outcomes; never retry with a new
        ID. A result verifies native properties, not visual rig correctness.
        """
        transform = {key: value for key, value in {'location': location, 'head': head,
                     'tail': tail, 'roll': roll}.items() if value is not None}
        return send('apply_bone_transform', {'capture_id': capture_id,
                    'expected_digest': expected_digest, 'request_id': request_id,
                    'transform': transform})

    @mcp.tool()
    def undo_bone_transform(receipt_id: str, request_id: str) -> str:
        """Compensate a verified edit only if its target/context/after-state still match.

        This is a new guarded edit with native readback, not global Blender Undo.
        Other human edits are never blindly reverted. Retain its returned receipt.
        """
        return send('undo_bone_transform', {'receipt_id': receipt_id, 'request_id': request_id})
