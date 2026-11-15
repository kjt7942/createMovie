"""
prelude.py — helpers for making web-ready 3D assets through Blender MCP.

`blender_mcp.mjs run script.py --prelude` prepends this file to the script sent to
`execute_blender_code`, so scripts can call these directly. Everything here is plain bpy.
Conventions that keep assets friendly to three.js / glTF:
  - 1 Blender unit = 1 metre; model around the origin, facing -Y (glTF exports it as +Z toward camera)
  - materials: Principled BSDF only (base colour, roughness, metallic, emission) — survives glTF export
  - apply transforms before export; name objects clearly (names become node names in three.js)
  - return data by assigning a dict to `result`
"""
import math

import bpy


def reset_scene(fps=30):
    """Empty scene: no objects, orphan data purged, metric units, given frame rate."""
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.curves, bpy.data.actions):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = fps
    return scene


def hex_rgba(hex_color, alpha=1.0):
    h = hex_color.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]  # sRGB → linear
    return (*lin, alpha)


def mat(name, color="#cccccc", roughness=0.6, metallic=0.0, emission=None, emission_strength=1.0):
    """A glTF-safe Principled BSDF material (reused if it already exists)."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = hex_rgba(color)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = hex_rgba(emission)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    return m


def assign(ob, material):
    ob.data.materials.clear()
    ob.data.materials.append(material)
    return ob


def smooth(ob, angle_deg=35):
    """Smooth shading with sharp edges kept above angle_deg (exported as split normals)."""
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle_deg))
    except Exception:  # older/newer operator names
        bpy.ops.object.shade_smooth()
    ob.select_set(False)
    return ob


def apply_transforms(objects=None):
    objs = objects or [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.select_all(action="DESELECT")


def stats():
    """Counts and bounds of the scene's meshes (for `result`)."""
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        for v in me.vertices:
            w = ev.matrix_world @ v.co
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
        ev.to_mesh_clear()
    return {"objects": len(meshes), "triangles": tris,
            "bounds_min": [round(x, 4) for x in lo] if meshes else None,
            "bounds_max": [round(x, 4) for x in hi] if meshes else None,
            "materials": sorted({s.material.name for o in meshes for s in o.material_slots if s.material})}


def export_glb(path, objects=None, animations=True):
    """Export a web-ready GLB (Y-up, transforms applied on export, no Draco so three.js needs no decoder)."""
    bpy.ops.object.select_all(action="DESELECT")
    if objects:
        for o in objects:
            o.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=bool(objects),
        export_yup=True,
        export_apply=True,
        export_animations=animations,
        export_draco_mesh_compression_enable=False,
        export_cameras=False,
        export_lights=False,
    )
    import os
    return {"path": path, "bytes": os.path.getsize(path)}


def save_blend(path):
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    return path
