"""Native-property contract tests using RNA-shaped stubs; no Blender startup."""
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

ROOT = Path(__file__).resolve().parents[1]


class RNA(types.SimpleNamespace):
    def as_pointer(self):
        return id(self)


class Bones(dict):
    def __iter__(self):
        return iter(self.values())


class LiveContextTests(unittest.TestCase):
    def setUp(self):
        self.bone = RNA(name='Bone', select=True, location=[0., 0., 0.],
                        constraints=[], lock_location=[False]*3,
                        head=[0., 0., 0.], tail=[0., 1., 0.], roll=0.,
                        use_connect=False, children=[], parent=None, length=1.)
        bones = Bones(Bone=self.bone)
        bones.active = self.bone
        data = RNA(bones=bones, edit_bones=bones, users=1, library=None, animation_data=None)
        self.obj = RNA(name='Rig', type='ARMATURE', data=data, pose=RNA(bones=bones),
                       library=None, animation_data=None)
        self.ctx = RNA(scene=RNA(name='Scene', blendermcp_allow_bone_edits=True,
                                unit_settings=RNA(scale_length=1.)),
                       view_layer=RNA(name='ViewLayer', objects=RNA(active=self.obj), update=lambda: None),
                       selected_objects=[self.obj], mode='POSE', area=RNA(type='VIEW_3D'))
        self.bpy = RNA(data=RNA(filepath='', objects={'Rig': self.obj}))
        tree = ast.parse((ROOT / 'addon.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LiveEditorContext')
        ns = dict(bpy=self.bpy, json=json, uuid=uuid, hashlib=hashlib, math=math, time=time)
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<live-context>', 'exec'), ns)
        self.live = ns['LiveEditorContext']()

    def capture(self):
        return self.live.capture(self.ctx, source='human_button')

    def apply(self, capture, request='edit-1', transform=None):
        return self.live.apply(self.ctx, capture['capture_id'], capture['bone_digest'],
                               transform or {'location': [1., 2., 3.]}, request)

    def test_repeat_sample_does_not_change_selection_serial(self):
        capture = self.capture()
        self.assertEqual(capture['selection_serial'], self.live.sample(self.ctx)['selection_serial'])

    def test_capture_edit_readback_and_guarded_compensation(self):
        capture = self.capture()
        receipt = self.apply(capture)
        self.assertTrue(receipt['verified'])
        self.assertEqual([1., 2., 3.], self.bone.location)
        self.assertEqual([0., 0., 0.], self.live.observe(self.ctx, capture['capture_id'])['capture']['bone_state']['location'])
        undo = self.live.undo(self.ctx, receipt['receipt_id'], 'undo-1')
        self.assertEqual([0., 0., 0.], self.bone.location)
        self.assertEqual(receipt['receipt_id'], undo['compensates'])
        self.assertEqual(undo, self.live.undo(self.ctx, receipt['receipt_id'], 'undo-1'))

    def test_duplicate_request_never_reapplies_after_human_change(self):
        capture = self.capture()
        first = self.apply(capture)
        self.bone.location = [9., 9., 9.]
        self.assertEqual(first, self.apply(capture))
        self.assertEqual([9., 9., 9.], self.bone.location)
        with self.assertRaisesRegex(ValueError, 'REQUEST_ID_REUSED'):
            self.apply(capture, transform={'location': [4., 5., 6.]})

    def test_selection_away_and_back_is_stale(self):
        capture = self.capture()
        self.bone.select = False
        self.live.sample(self.ctx)
        self.bone.select = True
        with self.assertRaisesRegex(ValueError, 'SELECTION_CHANGED'):
            self.apply(capture)

    def test_mode_change_and_property_change_are_refused(self):
        capture = self.capture()
        self.ctx.mode = 'EDIT_ARMATURE'
        with self.assertRaisesRegex(ValueError, 'MODE_CHANGED'):
            self.apply(capture)
        capture = self.capture()
        self.bone.head = [2., 0., 0.]
        with self.assertRaisesRegex(ValueError, 'BONE_STATE_CHANGED'):
            self.apply(capture, transform={'roll': 0.3})

    def test_permission_disabled_and_unsupported_fields(self):
        capture = self.capture()
        self.ctx.scene.blendermcp_allow_bone_edits = False
        with self.assertRaisesRegex(ValueError, 'SCOPED_BONE_EDITS_DISABLED'):
            self.apply(capture)
        self.ctx.scene.blendermcp_allow_bone_edits = True
        for transform in ({'rotation': [0, 0, 0]}, {'location': [float('nan'), 0, 0]}, {'location': [True, 0, 0]}):
            with self.assertRaises(ValueError):
                self.apply(capture, transform=transform)
        self.assertEqual([0., 0., 0.], self.bone.location)

    def test_document_and_identity_changes_do_not_retarget(self):
        capture = self.capture()
        self.bpy.data.filepath = '/another.blend'
        with self.assertRaisesRegex(ValueError, 'CAPTURE_NOT_FOUND'):
            self.apply(capture)
        capture = self.capture()
        replacement = RNA(**vars(self.obj))
        self.bpy.data.objects['Rig'] = replacement
        with self.assertRaisesRegex(ValueError, 'TARGET_IDENTITY_CHANGED'):
            self.apply(capture)

    def test_undo_does_not_clobber_human_edits(self):
        receipt = self.apply(self.capture())
        self.bone.location = [8., 0., 0.]
        with self.assertRaisesRegex(ValueError, 'UNDO_STATE_CHANGED'):
            self.live.undo(self.ctx, receipt['receipt_id'], 'undo')
        self.assertEqual([8., 0., 0.], self.bone.location)

    def test_edit_bone_transform_and_compensation(self):
        self.ctx.mode = 'EDIT_ARMATURE'
        receipt = self.apply(self.capture(), transform={'tail': [0., 2., 0.], 'roll': 0.25})
        self.assertEqual([0., 2., 0.], self.bone.tail)
        self.live.undo(self.ctx, receipt['receipt_id'], 'undo')
        self.assertEqual([0., 1., 0.], self.bone.tail)
        self.assertEqual(0., self.bone.roll)

    def test_shared_constrained_and_connected_rigs_fail_closed(self):
        capture = self.capture()
        self.obj.data.users = 2
        with self.assertRaisesRegex(ValueError, 'LINKED_OR_SHARED'):
            self.apply(capture)
        self.obj.data.users = 1
        self.bone.constraints = [RNA(type='COPY_LOCATION')]
        with self.assertRaisesRegex(ValueError, 'CONSTRAINED_OR_LOCKED'):
            self.apply(capture)
        self.bone.constraints = []
        self.ctx.mode = 'EDIT_ARMATURE'
        capture = self.capture()
        self.bone.use_connect = True
        with self.assertRaisesRegex(ValueError, 'CONNECTED_EDIT_BONE'):
            self.apply(capture, transform={'tail': [0, 2, 0]})

    def test_capture_release_and_finite_retention(self):
        capture = self.capture()
        self.live.release(capture['capture_id'])
        with self.assertRaisesRegex(ValueError, 'CAPTURE_NOT_FOUND'):
            self.live.observe(self.ctx, capture['capture_id'])
        for _ in range(self.live.LIMIT):
            self.capture()
        with self.assertRaisesRegex(ValueError, 'CAPTURE_CAPACITY'):
            self.capture()

    def test_failed_readback_rolls_back_and_retains_original(self):
        capture = self.capture()
        calls = []
        def update():
            calls.append(True)
            if len(calls) == 1:
                raise RuntimeError('native update failed')
        self.ctx.view_layer.update = update
        with self.assertRaisesRegex(RuntimeError, 'native update failed'):
            self.apply(capture)
        self.assertEqual([0., 0., 0.], self.bone.location)
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_OUTCOME_UNKNOWN'):
            self.apply(capture)

    def test_failed_compensation_retains_undo_request_identity(self):
        receipt = self.apply(self.capture())
        calls = []
        def update():
            calls.append(True)
            if len(calls) == 1:
                raise RuntimeError('native update failed')
        self.ctx.view_layer.update = update
        with self.assertRaisesRegex(RuntimeError, 'native update failed'):
            self.live.undo(self.ctx, receipt['receipt_id'], 'undo')
        self.assertEqual([1., 2., 3.], self.bone.location)
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_OUTCOME_UNKNOWN'):
            self.live.undo(self.ctx, receipt['receipt_id'], 'undo')

    def test_bundled_addon_matches_and_mcp_routes_are_explicit(self):
        self.assertEqual((ROOT/'addon.py').read_bytes(), (ROOT/'src/blender_mcp/bundled/addon.py').read_bytes())
        path = ROOT/'src/blender_mcp/live_context_tools.py'
        spec = importlib.util.spec_from_file_location('bindings', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tools, calls = {}, []
        class MCP:
            def tool(self):
                def attach(fn):
                    tools[fn.__name__] = fn
                    return fn
                return attach
        class Connection:
            def send_command(self, command, params=None, read_only=False):
                calls.append((command, params, read_only))
                return {'test': True}
        module.register(MCP(), Connection)
        tools['apply_bone_transform']('capture', 'digest', 'request', location=[1, 2, 3])
        self.assertEqual(('apply_bone_transform', {'capture_id': 'capture', 'expected_digest': 'digest',
                          'request_id': 'request', 'transform': {'location': [1, 2, 3]}}, False), calls[-1])
        tools['discover_blender_controls']('PoseBone.location')
        self.assertEqual('bpy_api_lookup', calls[-1][0])
        self.assertTrue(calls[-1][2])


if __name__ == '__main__':
    unittest.main()
