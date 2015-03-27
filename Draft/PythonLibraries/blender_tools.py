import os
from math import *
import numpy as np

try:
    import bpy    # tested in Blender v2.69
    from mathutils import Quaternion
except ImportError:
    print ("Warning: can't load Blender modules required for most functions of \"blender_tools\" module.")

import dataset_tools



""" Helper functions """

def get_objects(by_selection=False, name_starts_with="", name_ends_with=""):
    """
    Return a list of tuples, each containing the name of the object, and the object itself.
    The entries are sorted by object-name.
    
    "by_selection" :
        (optional) if True, only the selected objects are considered,
        otherwise the objects of the current scene are considered
    "name_starts_with" : (optional) prefix of object name
    "name_ends_with" : (optional) suffix of object name
    """
    
    if by_selection:
        objects = bpy.context.selected_objects
    else:
        objects = bpy.context.scene.objects
    
    return sorted([
            (ob.name, ob) for ob in objects
            if ob.name.startswith(name_starts_with) and ob.name.endswith(name_ends_with) and ob.type == "MESH" ])

def object_name_from_filename(filename, name_prefix="", strip_file_extension=True):
    """
    Create an object-name corresponding with the filename "filename" of the file containing
    the data to represent the object.
    
    "name_prefix" : (optional) prefix
    "strip_file_extension" : (optional) if True, omit the file-extension in the object-name
    """
    name = bpy.path.basename(filename)
    
    if strip_file_extension:
        name = os.path.splitext(name)[0]
    
    return name_prefix + name


""" Functions related to cameras """

def print_pose(rvec, tvec):
    """
    Some debug printing of the camera pose projection matrix,
    the printed output can be used in Blender to visualize this camera pose,
    using the "create_pose_camera()" function.
    
    "rvec", "tvec" : defining the camera pose, compatible with OpenCV's output
    """
    import cv2
    import transforms as trfm
    
    ax, an = trfm.axis_and_angle_from_rvec(-rvec)
    
    print ("axis, angle = \\")
    print (list(ax.reshape(-1)), an)    # R^(-1)
    
    print ("pos = \\")
    print (list(-cv2.Rodrigues(-rvec)[0].dot(tvec).reshape(-1)))    # -R^(-1) * t

def create_camera_pose(name, axis, angle, pos):
    """
    Create a camera named "name" by providing information of the pose.
    Unit pose corresponds with a camera at the origin,
    with view-direction lying along the +Z-axis,
    and with the +Y-axis facing downwards in the camera frustrum.
    
    "pos" : the camera center with respect to the world origin
    "axis", "angle" : axis-angle representation of the orientation of the camera with respect to the world origin
    
    The "print_pose()" function can be used to print the input for this function,
    useful to visualize OpenCV's "rvec" and "tvec".
    """
    #name = name_camera + "_" + suffix
    
    if name in bpy.data.objects and bpy.data.objects[name].type == "CAMERA":
        ob = bpy.data.objects[name]
    else:
        bpy.ops.object.camera_add()
        ob = bpy.context.object
        ob.name = name
    
    ob.rotation_mode = "AXIS_ANGLE"
    ob.rotation_axis_angle[0] = angle[0]
    ob.rotation_axis_angle[1] = axis[0]
    ob.rotation_axis_angle[2] = axis[1]
    ob.rotation_axis_angle[3] = axis[2]
    
    ob.location[0] = pos[0]
    ob.location[1] = pos[1]
    ob.location[2] = pos[2]
    
    ob.rotation_mode = "QUATERNION"    # rotate 180 deg around local X because a blender camera has Y and Z axes opposite to OpenCV's
    ob.rotation_quaternion *= Quaternion((1.0, 0.0, 0.0), radians(180.0))

def extract_current_pose():
    """
    Convert current object's pose to OpenCV's "rvec" and "tvec".
    """
    
    ob = bpy.context.object
    if ob.rotation_mode == "QUATERNION":
        q = ob.rotation_quaternion
    elif ob.rotation_mode == "AXIS_ANGLE":
        q = Quaternion(ob.rotation_axis_angle[1:4], ob.rotation_axis_angle[0])
    else:
        assert ob.rotation_mode in ("XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX")
        q = ob.rotation_euler.to_quaternion()
    
    # Rotate 180 deg around local X because a blender camera has Y and Z axes opposite to OpenCV's
    q *= Quaternion((1.0, 0.0, 0.0), radians(180.0))
    
    aa = q.to_axis_angle()
    rvec = [c * -aa[1] for c in aa[0]]
    tvec = list(q.inverted() * (-ob.location))
    
    return rvec, tvec

def create_cam_trajectory(name,
                          locations, quaternions,
                          start_frame=1, framenrs=None):
    """
    "name" : name of Camera to be created
    "locations" : list of cam center positions for each trajectory node
    "quaternions" : list of cam orientation (quaternion (qx, qy, qz, qw)) for each trajectory node
    "start_frame" : (optional) number of the start frame
    "framenrs" : (optional) list of frame numbers for each trajectory node (should be in increasing order)
    """
    frame_current_backup = bpy.context.scene.frame_current    # backup the current framenr
    
    # Create the camera
    if name in bpy.data.objects and bpy.data.objects[name].type == "CAMERA":
        ob = bpy.data.objects[name]
        bpy.ops.object.select_all(action="DESELECT")
        ob.select = True
        bpy.context.scene.objects.active = ob
    else:
        bpy.ops.object.camera_add()
        ob = bpy.context.object
        ob.name = name
    
    ob.rotation_mode = "QUATERNION"
    
    # Create path of the camera
    for i, (location, quaternion) in enumerate(zip(locations, quaternions)):
        bpy.context.scene.frame_current = framenrs[i] if framenrs else i + 1
        
        ob.location = list(location)
        
        qx, qy, qz, qw = quaternion
        ob.rotation_quaternion = [qw, qx, qy, qz]
        # We assume the TUM format uses the OpenCV cam convention (Z-axis in direction of view, Y-axis down)
        # so we'll have to convert, since Blender follows OpenGL convention
        ob.rotation_quaternion *= Quaternion((1.0, 0.0, 0.0), radians(180.0))
        
        bpy.ops.anim.keyframe_insert_menu(type="BUILTIN_KSI_LocRot")
    
    # Visualize path
    ob.animation_visualization.motion_path.show_keyframe_highlight = bool(framenrs)
    if framenrs:
        bpy.ops.object.paths_calculate(start_frame=framenrs[0], end_frame=framenrs[-1])
    else:
        bpy.ops.object.paths_calculate(start_frame=start_frame, end_frame=start_frame + len(locations))
    
    bpy.context.scene.frame_current = frame_current_backup    # restore the original framenr

def load_and_create_cam_trajectory(filename, name_prefix="", strip_file_extension=False):
    """
    Load a camera trajectory (in the TUM format, see "dataset_tools" module for more info)
    with filename "filename", and create it in Blender.
    
    "name_prefix", "strip_file_extension" : see documentation of "object_name_from_filename()"
    """
    
    timestps, locations, quaternions = dataset_tools.load_cam_trajectory_TUM(filename)
    create_cam_trajectory(
            object_name_from_filename(filename, name_prefix, strip_file_extension), locations, quaternions )


""" Functions related to 3D geometry """

def create_mesh(name, coords, connect=False, edges=None):
    """
    Create a mesh with name "name" from a list of vertices "coords".
    Return the generated object.
    
    If "connect" is True, two successive (in order) vertices
    will be linked together by an edge.
    Otherwise, if "edges" list is specified, each element is a tuple of 2 vertex indices,
    to be linked together with an edge.
    """
    
    # Define the coordinates of the vertices. Each vertex is defined by a tuple of 3 floats.
    mesh_name = name + "Mesh"
    
    me = bpy.data.meshes.new(mesh_name)    # create a new mesh
    if name in bpy.data.objects and bpy.data.objects[name].type == "MESH":
        ob = bpy.data.objects[name]
        me_old = ob.data
        ob.data = me
        bpy.data.meshes.remove(me_old)
    else:
        ob = bpy.data.objects.new(name, me)    # create an object with that mesh
        bpy.context.scene.objects.link(ob)    # link object to scene
    
    ob.location = [0, 0, 0]    # position object at origin
    
    # Define the edge by index numbers of its vertices. Each edge is defined by a tuple of 2 integers.
    if connect:
        edges = list(zip(range(len(coords) - 1), range(1, len(coords))))
    elif not edges:
        edges = []
    
    # Define the faces by index numbers of its vertices. Each face is defined by a tuple of 3 or more integers.
    # N-gons would require a tuple of size N.
    faces = []
    
    # Fill the mesh with verts, edges, faces
    me.from_pydata(coords, edges, faces)    # edges or faces should be [], or you ask for problems
    me.update(calc_edges=True)    # update mesh with new data
    
    return ob


""" File- import/export functions """

def extract_points_to_MATLAB(filename,
                             by_selection=False, name_starts_with="", name_ends_with="",
                             var_name="scene_3D_points"):
    """
    Extract 3D coordinates of vertices of meshes to a MATLAB/Octave compatible file.
    The resulting vertices are sorted by object-name.
    
    "filename" : .mat-file to save to
    "by_selection", "name_starts_with", "name_ends_with" : see documentation of "get_objects()"
    "var_name" : MATLAB variable name in which the data will be stored
    """
    import scipy.io as sio
    
    verts = []
    for ob_name, ob in get_objects(by_selection, name_starts_with, name_ends_with):
        verts += [tuple(ob.matrix_world * vertex.co) for vertex in ob.data.vertices]
    verts = np.array(verts)
    
    sio.savemat(filename, {var_name: verts})

def extract_points_to_ply_file(filename, by_selection=False, name_starts_with="", name_ends_with=""):
    """
    Extract 3D coordinates of vertices of meshes to a PointCloud (.ply) file.
    
    "filename" : .ply-file to save to
    "by_selection", "name_starts_with", "name_ends_with" : see documentation of "get_objects()"
    
    Note: at least 3 vertices should be extracted (in total).
    """
    
    # Save current selection
    selected_objects_backup = bpy.context.selected_objects
    active_object_backup = bpy.context.active_object
    
    # Select to-be-exported objects
    bpy.ops.object.select_all(action="DESELECT")
    for ob_name, ob in get_objects(by_selection, name_starts_with, name_ends_with):
        ob.select = True
        bpy.context.scene.objects.active = ob
    
    # Join to-be-exported objects into one temporary mesh
    bpy.ops.object.duplicate()
    if len(bpy.context.selected_objects) > 1:
        bpy.ops.object.join()
    
    # Remove all edges and faces, and add dummy faces (required for ply-exporter)
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.delete(type='EDGE_FACE')
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.edge_face_add()
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.editmode_toggle()
    
    bpy.ops.export_mesh.ply(filepath=filename, use_normals=False, use_uv_coords=False)    # export to ply-file
    bpy.ops.object.delete(use_global=True)    # remove temporary mesh
    
    # Restore original selection
    bpy.ops.object.select_all(action="DESELECT")
    for ob in selected_objects_backup:
        ob.select = True
    bpy.context.scene.objects.active = active_object_backup

def extract_points_to_pcd_file(filename, by_selection=False, name_starts_with="", name_ends_with=""):
    """
    Extract 3D coordinates of vertices of meshes to a PointCloud (.pcd) file.
    The resulting vertices are sorted by object-name.
    
    "filename" : .pcd-file to save to
    "by_selection", "name_starts_with", "name_ends_with" : see documentation of "get_objects()"
    """
    
    verts = []
    for ob_name, ob in get_objects(by_selection, name_starts_with, name_ends_with):
        verts += [tuple(ob.matrix_world * vertex.co) for vertex in ob.data.vertices]
    verts = np.array(verts)
    
    dataset_tools.save_3D_points_to_pcd_file(filename, verts)

def import_points_from_pcd_file(filename, name_prefix=""):
    """
    Import 3D coordinates of vertices from a PointCloud (.pcd) file.
    
    "name_prefix" : see documentation of "object_name_from_filename()"
    
    Note: currently, colors are not yet supported.
    """
    
    # Import point cloud
    verts, colors = dataset_tools.load_3D_points_from_pcd_file(filename)
    ob = create_mesh(object_name_from_filename(filename, name_prefix), verts)
    
    # Select the generated object
    bpy.ops.object.select_all(action="DESELECT")
    ob.select = True
    bpy.context.scene.objects.active = ob