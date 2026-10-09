import bpy
import bmesh
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
original = root.parent / 'model-extraction/nanyu-repaired.blend'
editable = root / 'project/nanyu-editable.blend'
bpy.ops.wm.open_mainfile(filepath=str(original if original.exists() else editable))
character = bpy.data.objects['Nanyu_Print_150mm']
bpy.ops.object.select_all(action='DESELECT')
character.select_set(True)
bpy.context.view_layer.objects.active = character
if original.exists() and not editable.exists():
    bpy.ops.wm.save_as_mainfile(filepath=str(editable), compress=True)
modifier = character.modifiers.new('Print file simplification', 'DECIMATE')
modifier.ratio = 0.15
bpy.ops.object.modifier_apply(modifier=modifier.name)
mesh = bmesh.new()
mesh.from_mesh(character.data)
remaining = set(mesh.verts)
components = 0
while remaining:
    components += 1
    pending = [remaining.pop()]
    while pending:
        current = pending.pop()
        for edge in current.link_edges:
            neighbor = edge.other_vert(current)
            if neighbor in remaining:
                remaining.remove(neighbor)
                pending.append(neighbor)
report = {
    'file': 'models/nanyu-print.stl',
    'units': 'mm',
    'components': components,
    'boundary_edges': sum(edge.is_boundary for edge in mesh.edges),
    'non_manifold_edges': sum(not edge.is_manifold for edge in mesh.edges),
    'signed_volume_mm3': mesh.calc_volume(signed=True),
    'faces': len(mesh.faces),
    'dimensions_mm': list(character.dimensions),
    'operation': 'decimate repaired mesh to 15% for distribution; original preserved in original-models.zip',
}
mesh.free()
if report['components'] != 1 or report['non_manifold_edges'] != 0 or report['signed_volume_mm3'] <= 0:
    raise RuntimeError(report)
bpy.ops.wm.stl_export(filepath=str(root / 'models/nanyu-print.stl'), export_selected_objects=True)
(root / 'project/reports/print-model-check.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report), flush=True)
bpy.context.scene.render.filepath = str(root / 'assets/model-preview.png')
bpy.ops.render.render(write_still=True)
