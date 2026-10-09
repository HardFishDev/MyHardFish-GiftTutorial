import bpy
import bmesh
import json
import math
from pathlib import Path
from mathutils import Vector

output = Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.wm.stl_import(filepath=str(output / 'nanyu-raw-150mm.stl'))
character = bpy.context.object
character.name = 'Nanyu_Print_150mm'
mesh = bmesh.new()
mesh.from_mesh(character.data)
bmesh.ops.remove_doubles(mesh, verts=list(mesh.verts), dist=0.0001)
boundary = [edge for edge in mesh.edges if edge.is_boundary]
filled = bmesh.ops.holes_fill(mesh, edges=boundary, sides=0)
bmesh.ops.recalc_face_normals(mesh, faces=list(mesh.faces))
mesh.to_mesh(character.data)
mesh.free()
character.location.z = 3.5
bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=1, depth=4, location=(0, 0, 2))
base = bpy.context.object
base.name = 'Oval_Base_100x58x4mm'
base.scale = (50, 29, 1)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bevel = base.modifiers.new('Rounded base edge', 'BEVEL')
bevel.width = 0.7
bevel.segments = 3
bpy.ops.object.modifier_apply(modifier=bevel.name)
character.select_set(True)
bpy.context.view_layer.objects.active = character
bpy.ops.object.join()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
character.data.remesh_voxel_size = 0.2
character.data.remesh_voxel_adaptivity = 0
bpy.ops.object.voxel_remesh()
mesh = bmesh.new()
mesh.from_mesh(character.data)
components = []
remaining = set(mesh.verts)
while remaining:
    pending = [remaining.pop()]
    component = set(pending)
    while pending:
        current = pending.pop()
        for edge in current.link_edges:
            neighbor = edge.other_vert(current)
            if neighbor in remaining:
                remaining.remove(neighbor)
                component.add(neighbor)
                pending.append(neighbor)
    components.append(component)
components.sort(key=len, reverse=True)
component_sizes = [len(component) for component in components]
removed = []
for component in components[1:]:
    if len(component) < 100:
        removed.append(len(component))
        bmesh.ops.delete(mesh, geom=list(component), context='VERTS')
bmesh.ops.recalc_face_normals(mesh, faces=list(mesh.faces))
report = {
    'source': 'nanyu-raw-150mm.stl',
    'voxel_mm': 0.2,
    'filled_faces_before_remesh': len(filled['faces']),
    'components_before_speck_removal': component_sizes,
    'removed_small_components': removed,
    'remaining_components': len(components) - len(removed),
    'boundary_edges': sum(edge.is_boundary for edge in mesh.edges),
    'non_manifold_edges': sum(not edge.is_manifold for edge in mesh.edges),
    'signed_volume_mm3': mesh.calc_volume(signed=True),
    'vertices': len(mesh.verts),
    'faces': len(mesh.faces),
    'base_mm': [100, 58, 4],
    'checks_not_performed': ['minimum wall thickness', 'slicer validation', 'physical print'],
}
mesh.to_mesh(character.data)
mesh.free()
bpy.context.view_layer.update()
report['overall_size_mm'] = list(character.dimensions)
print('REPAIR_REPORT', json.dumps(report), flush=True)
(output / 'nanyu-repair-report.json').write_text(json.dumps(report, indent=2))
bpy.ops.wm.stl_export(filepath=str(output / 'nanyu-repaired-with-base.stl'), export_selected_objects=True)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 0.001
material = bpy.data.materials.new('Ivory')
material.diffuse_color = (0.72, 0.68, 0.59, 1)
character.data.materials.clear()
character.data.materials.append(material)
for polygon in character.data.polygons:
    polygon.use_smooth = True
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 16
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.world.color = (0.25, 0.25, 0.25)
for location, energy, size in [((100, -140, 230), 400000, 120), ((-120, -40, 140), 250000, 100), ((40, 100, 180), 350000, 100)]:
    bpy.ops.object.light_add(type='AREA', location=location)
    light = bpy.context.object
    light.data.energy = energy
    light.data.shape = 'DISK'
    light.data.size = size
    light.rotation_euler = (Vector((0, 0, 80)) - light.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.camera_add(location=(180, -290, 165))
camera = bpy.context.object
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 185
camera.rotation_euler = (Vector((0, 0, 77)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera
bpy.ops.object.select_all(action='DESELECT')
character.select_set(True)
bpy.context.view_layer.objects.active = character
bpy.ops.wm.save_as_mainfile(filepath=str(output / 'nanyu-repaired.blend'))
scene.render.filepath = str(output / 'nanyu-repaired-preview.png')
bpy.ops.render.render(write_still=True)
