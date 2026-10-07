"""Generic companion contract tests with native-shaped stubs, without Blender."""
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time
import types
import unittest
import uuid
from contextlib import contextmanager
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]


class Props(dict):
    def __iter__(self):
        return iter(self.values())


class Collection(dict):
    def __iter__(self):
        return iter(self.values())


class RNA(types.SimpleNamespace):
    def as_pointer(self):
        return id(self)


def prop(name, type='STRING', readonly=False, length=0, enum=()):
    return RNA(identifier=name, type=type, is_readonly=readonly, is_array=length > 0,
               array_length=length, hard_min=-1e6, hard_max=1e6, is_enum_flag=False,
               enum_items=[RNA(identifier=v) for v in enum])


def native(rna_type, properties, **values):
    return RNA(bl_rna=RNA(identifier=rna_type, properties=Props((p.identifier, p) for p in properties)), **values)


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.obj = native('Object', [prop('location', 'FLOAT', length=3), prop('name'), prop('data', 'POINTER')],
                          name='Cube', type='MESH', location=[0., 0., 0.], library=None)
        self.camera = native('Camera', [prop('lens', 'FLOAT')], name='Camera', lens=50., library=None)
        self.node = native('ShaderNodeValue', [prop('label')], name='Value', label='', select=True)
        self.nodes = Collection(Value=self.node)
        self.nodes.active = self.node
        self.tree = native('ShaderNodeTree', [prop('nodes', 'COLLECTION')], name='Tree', nodes=self.nodes)
        self.material = native('Material', [prop('diffuse_color', 'FLOAT', length=4), prop('node_tree', 'POINTER')],
                               name='Material', diffuse_color=[1., 1., 1., 1.], node_tree=self.tree, library=None)
        self.obj.active_material = self.material
        region = RNA(type='WINDOW')
        region3d = RNA(view_matrix=[[1, 0], [0, 1]], perspective_matrix=[[1, 0], [0, 1]], view_perspective='PERSP')
        self.area = RNA(type='VIEW_3D', width=800, height=600, regions=[region],
                        spaces=RNA(active=RNA(region_3d=region3d, shading=RNA(type='SOLID'))))
        self.window = RNA(screen=RNA(name='Screen', areas=[self.area]), workspace=RNA(name='Layout'))
        self.ctx = RNA(scene=RNA(name='Scene', blendermcp_allow_property_edits=True,
                                blendermcp_allow_native_operators=True),
                       view_layer=RNA(name='ViewLayer', objects=RNA(active=self.obj), update=lambda: None),
                       selected_objects=[self.obj], mode='OBJECT', area=self.area, window=self.window,
                       window_manager=RNA(windows=[self.window]))
        self.overrides = []
        @contextmanager
        def override(**kwargs):
            self.overrides.append(kwargs)
            yield self.ctx
        self.ctx.temp_override = override
        collections = {'objects': Collection(Cube=self.obj), 'cameras': Collection(Camera=self.camera),
                       'materials': Collection(Material=self.material)}
        data = native('BlendData', [prop(key, 'COLLECTION') for key in collections], filepath='', **collections)
        self.op_calls = []
        owner = self
        class Operator:
            def get_rna_type(self):
                return RNA(name='Primitive cube', description='Create a cube',
                           properties=Props(size=prop('size', 'FLOAT')))
            def poll(self):
                return True
            def __call__(self, mode, **args):
                owner.op_calls.append((mode, args))
                return {'FINISHED'}
        self.bpy = RNA(data=data, context=self.ctx, ops=RNA(mesh=RNA(primitive_cube_add=Operator())))
        tree = ast.parse((ROOT/'addon.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LiveEditorContext')
        ns = dict(bpy=self.bpy, json=json, uuid=uuid, hashlib=hashlib, math=math, time=time)
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<companion>', 'exec'), ns)
        self.live = ns['LiveEditorContext']()

    def capture(self):
        return self.live.capture(self.ctx, source='human_button')

    def inspect(self, collection='objects', name='Cube', properties=None, path=None):
        return self.live.inspect(self.ctx, collection=collection, name=name, properties=properties or ['location'], path=path)

    def write(self, observed, captured, value, property='location', request_id='edit'):
        return self.live.execute(self.ctx, captured['capture_id'], request_id, 'set_property',
                                 observed['reference_id'], property, value, observed['properties'][property]['digest'])

    def test_workspace_publishes_native_collections_editors_and_selection(self):
        state = self.live.workspace(self.ctx)
        self.assertEqual(['Cube'], state['selected_objects'])
        self.assertEqual({'objects', 'materials', 'cameras'}, {c['name'] for c in state['data_collections']})
        self.assertEqual('VIEW_3D', state['editors'][0]['type'])
        detailed = self.live.workspace(self.ctx, state['editors'][0]['editor_key'])
        self.assertEqual('SOLID', detailed['editor_context']['view']['shading'])

    def test_generic_property_read_edit_verify_and_compensation(self):
        captured, observed = self.capture(), self.inspect()
        result = self.write(observed, captured, [1., 2., 3.])
        self.assertEqual('applied', result['status'])
        self.assertTrue(result['verified'])
        self.assertEqual([1., 2., 3.], self.obj.location)
        compensation = self.live.compensate(self.ctx, 'edit', self.capture()['capture_id'], 'undo')
        self.assertTrue(compensation['verified'])
        self.assertEqual([0., 0., 0.], self.obj.location)

    def test_camera_material_and_node_share_same_property_route(self):
        camera = self.inspect('cameras', 'Camera', ['lens'])
        self.write(camera, self.capture(), 35., 'lens', 'camera')
        material = self.inspect('materials', 'Material', ['diffuse_color'])
        self.write(material, self.capture(), [0.1, 0.2, 0.3, 1.], 'diffuse_color', 'material')
        node = self.inspect('materials', 'Material', ['label'],
                            [{'property': 'node_tree'}, {'property': 'nodes'}, {'key': 'Value'}])
        self.write(node, self.capture(), 'Agent value', 'label', 'node')
        self.assertEqual(35., self.camera.lens)
        self.assertEqual('Agent value', self.node.label)

    def test_discovery_and_native_operator_use_captured_editor_and_poll(self):
        discovery = self.live.discover('mesh.primitive', 10)
        self.assertEqual('mesh.primitive_cube_add', discovery['operations'][0]['idname'])
        self.assertTrue(discovery['operations'][0]['execution_supported'])
        captured = self.capture()
        result = self.live.execute(self.ctx, captured['capture_id'], 'operator', 'invoke_operator',
                                   operator='mesh.primitive_cube_add', arguments={'size': 2.})
        self.assertEqual('applied', result['status'])
        self.assertFalse(result['verified'])
        self.assertEqual('unavailable', result['compensation'])
        self.assertEqual([('EXEC_DEFAULT', {'size': 2.})], self.op_calls)
        self.assertIs(self.area, self.overrides[0]['area'])
        self.assertEqual(result, self.live.observe_operation('operator'))

    def test_stale_selection_mode_and_property_refuse_before_edit(self):
        captured, observed = self.capture(), self.inspect()
        self.ctx.mode = 'SCULPT'
        with self.assertRaisesRegex(ValueError, 'CONTEXT_CHANGED'):
            self.write(observed, captured, [1, 2, 3])
        captured = self.capture()
        self.ctx.selected_objects = []
        with self.assertRaisesRegex(ValueError, 'CONTEXT_CHANGED'):
            self.write(observed, captured, [1, 2, 3])
        captured = self.capture()
        self.obj.location = [8., 0., 0.]
        with self.assertRaisesRegex(ValueError, 'PROPERTY_STATE_CHANGED'):
            self.write(observed, captured, [1, 2, 3])

    def test_permission_and_schema_refusal_are_bridge_enforced(self):
        captured, observed = self.capture(), self.inspect()
        self.ctx.scene.blendermcp_allow_property_edits = False
        with self.assertRaisesRegex(ValueError, 'PROPERTY_EDITS_DISABLED'):
            self.write(observed, captured, [1, 2, 3])
        self.ctx.scene.blendermcp_allow_property_edits = True
        for value in ([True, 0, 0], [float('nan'), 0, 0], [1, 2]):
            with self.assertRaises(ValueError):
                self.write(observed, captured, value)
        self.assertFalse(self.live.operator_supported('wm.open_mainfile'))
        self.assertFalse(self.live.operator_supported('screen.screenshot'))

    def test_identity_document_and_native_path_checks(self):
        captured, observed = self.capture(), self.inspect()
        self.bpy.data.objects['Cube'] = native('Object', [], name='Cube')
        with self.assertRaisesRegex(ValueError, 'TARGET_IDENTITY_CHANGED'):
            self.live.resolve(observed['reference_id'])
        with self.assertRaisesRegex(ValueError, 'CONTEXT_CHANGED'):
            self.write(observed, captured, [1, 2, 3])
        self.bpy.data.objects['Cube'] = self.obj
        self.bpy.data.filepath = '/new.blend'
        with self.assertRaisesRegex(ValueError, 'CONTEXT_CHANGED'):
            self.write(observed, captured, [1, 2, 3])
        with self.assertRaisesRegex(ValueError, 'RNA_PROPERTY_NOT_FOUND'):
            self.inspect(path=[{'property': '__class__'}])

    def test_original_capture_never_follows_later_state(self):
        captured = self.capture()
        self.ctx.selected_objects = []
        resolved = self.live.observe_context(self.ctx, captured['capture_id'])
        self.assertTrue(resolved['stale'])
        self.assertEqual(['Cube'], resolved['capture']['selected_objects'])

    def test_duplicate_requests_return_original_and_payload_conflicts_fail(self):
        captured, observed = self.capture(), self.inspect()
        result = self.write(observed, captured, [1, 2, 3])
        self.obj.location = [9, 9, 9]
        self.assertEqual(result, self.write(observed, captured, [1, 2, 3]))
        self.assertEqual([9, 9, 9], self.obj.location)
        with self.assertRaisesRegex(ValueError, 'REQUEST_ID_REUSED'):
            self.write(observed, captured, [4, 5, 6])

    def test_compensation_refuses_intervening_human_value(self):
        self.write(self.inspect(), self.capture(), [1, 2, 3])
        self.obj.location = [9, 0, 0]
        with self.assertRaisesRegex(ValueError, 'PROPERTY_STATE_CHANGED'):
            self.live.compensate(self.ctx, 'edit', self.capture()['capture_id'], 'undo')

    def test_failed_write_restores_and_never_replays(self):
        captured, observed = self.capture(), self.inspect()
        calls = []
        def update():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError('native failure')
        self.ctx.view_layer.update = update
        result = self.write(observed, captured, [1, 2, 3])
        self.assertEqual('failed', result['status'])
        self.assertTrue(result['restored'])
        self.assertEqual([0., 0., 0.], self.obj.location)
        self.assertEqual(result, self.write(observed, captured, [1, 2, 3]))
        self.assertEqual(2, len(calls))

    def test_editor_node_selection_is_part_of_context_guard(self):
        self.area.type = 'NODE_EDITOR'
        self.area.spaces.active = RNA(edit_tree=self.tree)
        captured = self.capture()
        self.assertEqual(['Value'], captured['editor_context']['selected_nodes'])
        self.node.select = False
        with self.assertRaisesRegex(ValueError, 'CONTEXT_CHANGED'):
            self.write(self.inspect(), captured, [1, 2, 3])

    def test_capture_and_request_retention_are_bounded(self):
        capture = self.capture()
        self.live.release(capture['capture_id'])
        with self.assertRaisesRegex(ValueError, 'CAPTURE_EXPIRED'):
            self.live.observe_context(self.ctx, capture['capture_id'])
        for _ in range(self.live.CAPTURE_LIMIT):
            self.capture()
        with self.assertRaisesRegex(ValueError, 'CAPTURE_CAPACITY'):
            self.capture()

    def test_mcp_routes_and_bundled_source_match(self):
        self.assertEqual((ROOT/'addon.py').read_bytes(), (ROOT/'src/blender_mcp/bundled/addon.py').read_bytes())
        spec = importlib.util.spec_from_file_location('bindings', ROOT/'src/blender_mcp/live_context_tools.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tools, calls = {}, []
        class MCP:
            def tool(self):
                def add(fn):
                    tools[fn.__name__] = fn
                    return fn
                return add
        class Connection:
            def send_command(self, command, params=None, read_only=False):
                calls.append((command, params, read_only))
                return {}
        module.register(MCP(), Connection)
        tools['execute_blender_operation']('capture', 'request', 'set_property', 'ref', 'lens', 35., 'digest')
        self.assertEqual('operation_execute', calls[-1][0])
        self.assertEqual('lens', calls[-1][1]['property'])
        tools['discover_blender_capabilities'](rna_query='Camera.lens')
        self.assertEqual('bpy_api_lookup', calls[-1][0])
        self.assertTrue(calls[-1][2])

    def test_deictic_target_must_be_disclosed_in_capture_selection(self):
        camera = self.inspect('cameras', 'Camera', ['lens'])
        with self.assertRaisesRegex(ValueError, 'CAPTURED_TARGET_MISMATCH'):
            self.live.execute(self.ctx, self.capture()['capture_id'], 'camera', 'set_property',
                              camera['reference_id'], 'lens', 35., camera['properties']['lens']['digest'],
                              target_policy='captured_selection')

    def test_matrix_properties_use_native_dimensions_and_recursive_readback(self):
        p = prop('matrix', 'FLOAT', length=4)
        p.array_dimensions = [2, 2, 0]
        self.obj.bl_rna.properties['matrix'] = p
        self.obj.matrix = [[1., 0.], [0., 1.]]
        result = self.write(self.inspect(properties=['matrix']), self.capture(), [[0.5, 0.], [0., 0.5]], 'matrix')
        self.assertTrue(result['verified'])
        self.assertEqual([[0.5, 0.], [0., 0.5]], self.obj.matrix)

    def test_mesh_selection_is_native_observation_and_guarded(self):
        mesh = RNA(verts=Collection(Zero=RNA(index=0, select=True)), edges=Collection(), faces=Collection())
        for collection in (mesh.verts, mesh.edges, mesh.faces):
            collection.index_update = lambda: None
        self.obj.data = object()
        self.ctx.mode = 'EDIT_MESH'
        fake = types.ModuleType('bmesh')
        fake.from_edit_mesh = lambda data: mesh
        with patch.dict(sys.modules, bmesh=fake):
            captured = self.capture()
            self.assertEqual([0], captured['mesh_selection']['vertices'])
            mesh.verts['Zero'].select = False
            with self.assertRaisesRegex(ValueError, 'CONTEXT_CHANGED'):
                self.write(self.inspect(), captured, [1, 2, 3])

    def test_command_inventory_recognizes_all_companion_dispatches(self):
        ns = dict(ast=ast)
        tree = ast.parse((ROOT/'tests/test_compat_matrix.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_commands')
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<inventory>', 'exec'), ns)
        commands = ns['_commands']((ROOT/'addon.py').read_text(encoding='utf-8'))
        self.assertTrue({'workspace_inspect', 'context_capture', 'context_resolve', 'context_release',
                         'entity_inspect', 'capability_discover', 'operation_execute', 'operation_observe',
                         'operation_compensate'} <= commands)

    def test_missing_deployment_config_disables_telemetry_without_endpoint_or_key(self):
        tree = ast.parse((ROOT/'src/blender_mcp/telemetry.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_load_deployment_config')
        package = types.ModuleType('companion_test_package')
        package.__path__ = []
        ns = {'__package__': package.__name__, 'logger': RNA(info=lambda text: None)}
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<config>', 'exec'), ns)
        with patch.dict(sys.modules, {package.__name__: package}):
            config = ns['_load_deployment_config']()
        self.assertFalse(config.enabled)
        self.assertFalse(hasattr(config, 'supabase_url'))
        self.assertFalse(hasattr(config, 'supabase_anon_key'))


if __name__ == '__main__':
    unittest.main()
