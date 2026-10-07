"""Generic companion MCP bindings; native resolution and authority stay in Blender."""
import json
from typing import Any, Literal


def register(mcp, connection):
    def send(command, params=None):
        try:
            return json.dumps({'ok': True, 'result': connection().send_command(command, params,
                read_only=command not in {'operation_execute', 'operation_compensate'})}, allow_nan=False)
        except Exception as exc:
            return json.dumps({'ok': False, 'error': str(exc)})

    @mcp.tool()
    def inspect_blender_workspace(editor_key: str | None = None) -> str:
        """Inspect live modes, selections, native data collections and window/editor keys.

        Supply an editor_key for actual viewport matrices, Properties tab or Node
        Editor selection. Returns permission state and explicit unavailable context.
        Does not infer chat timing or identify every visible widget.
        """
        return send('workspace_inspect', {'editor_key': editor_key})

    @mcp.tool()
    def capture_blender_context(editor_key: str | None = None) -> str:
        """Pin immutable workspace/editor context and selection for a workflow.

        Agent captures are labelled. For 'this', prefer the user's Capture editor
        context for AI button and preserve that exact capture ID. Native operator
        invocation requires an explicit captured editor_key.
        """
        return send('context_capture', {'editor_key': editor_key})

    @mcp.tool()
    def resolve_blender_context(capture_id: str) -> str:
        """Read original captured context and fresh state/staleness; never retarget."""
        return send('context_resolve', {'capture_id': capture_id})

    @mcp.tool()
    def release_blender_context(capture_id: str) -> str:
        """Release a settled capture from bounded session retention."""
        return send('context_release', {'capture_id': capture_id})

    @mcp.tool()
    def inspect_blender_entity(collection: str | None = None, name: str | None = None,
                               path: list[dict[str, Any]] | None = None,
                               reference_id: str | None = None,
                               properties: list[str] | None = None) -> str:
        """Inspect native bpy.data entities or nested RNA structures, without Python eval.

        Use collection/name from discovery or a returned reference_id. path is a
        bounded traversal: {property:'data'}, {property:'nodes'}, {key:'Principled
        BSDF'}, {index:0}. Returns schemas and requested values/digests (up to 32).
        Objects, cameras, materials, scenes, nodes and bones share this route.
        Pointer/collection observations describe relationships; writes require
        native writable scalar/array properties.
        """
        return send('entity_inspect', {'collection': collection, 'name': name, 'path': path,
                    'reference_id': reference_id, 'properties': properties})

    @mcp.tool()
    def discover_blender_capabilities(query: str = '', limit: int = 30,
                                      rna_query: str | None = None,
                                      node_type: str | None = None) -> str:
        """Discover runtime operators/data or exact native RNA/node schemas.

        query filters operator catalog with explicit execution support. rna_query:
        Object.location, Camera.lens or bpy.ops.mesh.primitive_cube_add. node_type
        describes real sockets using a scratch node. Discovery is not authority,
        successful poll or a universal transaction/undo guarantee.
        """
        if rna_query is not None and node_type is not None:
            return json.dumps({'ok': False, 'error': 'CHOOSE_ONE_SCHEMA_QUERY'})
        if rna_query is not None:
            return send('bpy_api_lookup', {'query': rna_query})
        if node_type is not None:
            return send('describe_node_type', {'bl_idname': node_type})
        return send('capability_discover', {'query': query, 'limit': limit})

    @mcp.tool()
    def execute_blender_operation(capture_id: str, request_id: str,
                                   kind: Literal['set_property', 'invoke_operator'],
                                   reference_id: str | None = None,
                                   property: str | None = None, value: Any = None,
                                   expected_digest: str | None = None,
                                   operator: str | None = None,
                                   arguments: dict[str, Any] | None = None,
                                   target_policy: Literal['explicit', 'captured_selection'] = 'explicit') -> str:
        """Execute generic native property edits or supported native operators.

        set_property requires a reference/property/value and inspected digest.
        invoke_operator requires native idname/arguments and captured editor.
        Enable the respective session permission in Blender. Schema, context,
        identity, value and poll checks execute in the add-on. No raw Python
        fallback. Retain request_id on transport uncertainty; observe the original
        before issuing new work. FINISHED alone does not verify an operator's
        domain result. Unsupported operations and compensation remain explicit.
        For 'this selected entity', use target_policy='captured_selection'; other
        explicit references remain valid named targets in the captured document.
        """
        return send('operation_execute', {'capture_id': capture_id, 'request_id': request_id,
                    'kind': kind, 'reference_id': reference_id, 'property': property,
                    'value': value, 'expected_digest': expected_digest,
                    'operator': operator, 'arguments': arguments, 'target_policy': target_policy})

    @mcp.tool()
    def observe_blender_operation(request_id: str) -> str:
        """Read an original retained outcome without re-executing or inventing success."""
        return send('operation_observe', {'request_id': request_id})

    @mcp.tool()
    def compensate_blender_operation(original_request_id: str, capture_id: str, request_id: str) -> str:
        """Guardedly restore a verified property edit with fresh captured context.

        Refuses intervening property changes. Operators have no generic compensation;
        global Blender Undo is not invoked. This is a new retained native action.
        """
        return send('operation_compensate', {'original_request_id': original_request_id,
                    'capture_id': capture_id, 'request_id': request_id})
