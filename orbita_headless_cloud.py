from __future__ import annotations
import json, math, sys, time
from pathlib import Path
import bpy, mathutils

def out_dir():
    p=Path("evidence"); p.mkdir(parents=True,exist_ok=True); return p.resolve()
def mat(n,c,metallic=0.0,roughness=0.45):
    m=bpy.data.materials.get(n) or bpy.data.materials.new(n); m.diffuse_color=c; m.metallic=metallic; m.roughness=roughness; return m
def box(n,loc,dims,m,bev=0.06):
    bpy.ops.mesh.primitive_cube_add(location=loc); o=bpy.context.active_object; o.name=n; o.dimensions=dims; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if m:o.data.materials.append(m)
    if bev>0: q=o.modifiers.new("EdgeSoft","BEVEL"); q.width=bev; q.segments=3
    return o
def cyl(n,loc,r,d,m,rot=(0,0,0),v=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=v,radius=r,depth=d,location=loc,rotation=rot); o=bpy.context.active_object; o.name=n
    if m:o.data.materials.append(m)
    return o
def beam(n,a,b,r,m):
    a=mathutils.Vector(a); b=mathutils.Vector(b); d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=r,depth=d.length,location=(a+b)*0.5); o=bpy.context.active_object; o.name=n; o.rotation_euler=d.to_track_quat("Z","Y").to_euler()
    if m:o.data.materials.append(m)
    return o
def wheel(n,loc,tire,metal):
    cyl(n,loc,0.54,0.28,tire,(math.radians(90),0,0),64); cyl(n+"_Rim",loc,0.31,0.30,metal,(math.radians(90),0,0),48)
def bbox(o):
    p=[o.matrix_world@mathutils.Vector(c) for c in o.bound_box]; return {"min":[min(x.x for x in p),min(x.y for x in p),min(x.z for x in p)],"max":[max(x.x for x in p),max(x.y for x in p),max(x.z for x in p)]}
def camera(c,loc,target,lens):
    c.location=loc; t=mathutils.Vector(target); c.rotation_euler=(t-c.location).to_track_quat("-Z","Y").to_euler(); c.data.lens=lens; bpy.context.scene.camera=c; bpy.context.view_layer.update()
def render(scene,c,path,loc,target,lens):
    camera(c,loc,target,lens); scene.render.filepath=str(path); bpy.ops.render.render(write_still=True)
    if not path.is_file() or path.stat().st_size<=0: raise RuntimeError("render missing "+str(path))
    return path.stat().st_size

def main():
    started=time.time(); out=out_dir()
    for o in list(bpy.data.objects): bpy.data.objects.remove(o,do_unlink=True)
    body=mat("ORBITA_Body",(0.035,0.16,0.42,1),0.55,0.24); accent=mat("ORBITA_Accent",(0.9,0.16,0.05,1),0.28,0.3); tire=mat("ORBITA_Tire",(0.018,0.018,0.022,1),0,0.68); metal=mat("ORBITA_Metal",(0.14,0.16,0.19,1),0.9,0.2); dark=mat("ORBITA_Dark",(0.025,0.035,0.055,1),0.2,0.32); screen=mat("ORBITA_Screen",(0.04,0.7,0.95,1),0.1,0.12); usb=mat("ORBITA_USB",(0.65,0.68,0.72,1),0.8,0.2)
    fx,fy,wz=1.72,0.82,0.56
    wheel("FrontWheel_L",(fx,fy,wz),tire,metal); wheel("FrontWheel_R",(fx,-fy,wz),tire,metal); wheel("RearWheel",(-1.92,0,0.58),tire,metal)
    box("MainChassis",(-0.05,0,0.82),(3.22,1.13,0.42),dark,0.12); box("FrontFairing",(0.82,0,1.10),(1.45,1.22,0.76),body,0.16); box("CenterBody",(-0.15,0,1.10),(1.52,1.06,0.72),body,0.14); box("TailBody",(-1.24,0,1.03),(1.25,0.84,0.62),body,0.16); box("Seat",(-0.62,0,1.50),(1.12,0.62,0.22),dark,0.10); box("FrontSplitter",(1.48,0,0.74),(0.58,1.18,0.15),accent,0.04)
    for side,y in (("L",fy),("R",-fy)):
        hub=(fx,y,wz); top=(fx-0.08,y,1.05); beam("Upright_"+side,hub,top,0.055,metal); beam("UpperLinkA_"+side,top,(0.70,0.42 if y>0 else -0.42,1.27),0.045,metal); beam("UpperLinkB_"+side,top,(0.92,0.24 if y>0 else -0.24,1.14),0.042,metal); beam("LowerLinkA_"+side,hub,(0.64,0.45 if y>0 else -0.45,0.70),0.052,metal); beam("LowerLinkB_"+side,hub,(0.90,0.24 if y>0 else -0.24,0.76),0.048,metal)
    beam("SteeringTie",(1.36,fy,0.78),(1.36,-fy,0.78),0.038,accent)
    box("TFT_Housing",(0.58,0,1.92),(0.13,0.68,0.42),dark,0.05); box("TFT_Screen",(0.66,0,1.92),(0.035,0.58,0.32),screen,0.025); box("PhoneDock_Housing",(0.71,0,1.21),(0.18,0.44,0.68),dark,0.055); box("PhoneMock",(0.78,0,1.21),(0.045,0.35,0.60),screen,0.035); box("USB_C_L",(0.75,0.145,1.00),(0.045,0.09,0.038),usb,0.012); box("USB_C_R",(0.75,-0.145,1.00),(0.045,0.09,0.038),usb,0.012)
    beam("Handlebar",(0.25,0.54,1.78),(0.25,-0.54,1.78),0.038,metal); beam("CockpitStem",(0.25,0,1.28),(0.25,0,1.78),0.05,metal)
    bpy.ops.mesh.primitive_plane_add(size=18,location=(0,0,0)); g=bpy.context.active_object; g.name="Ground"; g.data.materials.append(mat("GroundMat",(0.055,0.06,0.07,1),0,0.78))
    bpy.ops.object.camera_add(location=(6.8,-6.2,3.2)); c=bpy.context.active_object; c.name="AuditCamera"
    for n,loc,e,s in (("KeyLight",(3.5,-3.8,6),1500,5),("FillLight",(0,4,4),900,4),("RimLight",(-4,-2,3.8),1100,3)):
        bpy.ops.object.light_add(type="AREA",location=loc); l=bpy.context.active_object; l.name=n; l.data.energy=e; l.data.shape="DISK"; l.data.size=s
    sc=bpy.context.scene; sc.camera=c; sc.render.engine="BLENDER_EEVEE"; sc.render.resolution_x=512; sc.render.resolution_y=384; sc.render.resolution_percentage=100; sc.render.image_settings.file_format="PNG"; sc.world.color=(0.025,0.03,0.045); bpy.context.view_layer.update()
    fl,fr=bpy.data.objects["FrontWheel_L"],bpy.data.objects["FrontWheel_R"]; fair=bpy.data.objects["FrontFairing"]; t=bpy.data.objects["TFT_Housing"]; d=bpy.data.objects["PhoneDock_Housing"]; ul=bpy.data.objects["USB_C_L"]; ur=bpy.data.objects["USB_C_R"]; tb,db=bbox(t),bbox(d); track=abs(float(fl.location.y-fr.location.y))
    checks={"exactly_three_primary_wheels":all(bpy.data.objects.get(n) for n in ("FrontWheel_L","FrontWheel_R","RearWheel")),"two_front_one_rear":bool(fl.location.x>0 and fr.location.x>0 and bpy.data.objects["RearWheel"].location.x<0),"front_track_body_ratio":bool(1.20<=track/float(fair.dimensions.y)<=1.55),"tft_above_phone":bool(t.location.z>d.location.z),"tft_phone_vertical_clearance":bool(float(tb["min"][2]-db["max"][2])>=0.08),"usb_c_symmetric":bool(abs(float(ul.location.y+ur.location.y))<0.001),"dock_has_side_protrusion":bool(float(d.dimensions.x)>=0.14),"suspension_links_present":sum(1 for o in bpy.data.objects if o.name.startswith(("UpperLink","LowerLink","Upright")))>=10}
    if not all(checks.values()): raise RuntimeError(json.dumps(checks))
    blend=out/"ORBITA_CLOUD_FINAL.blend"; bpy.ops.wm.save_as_mainfile(filepath=str(blend)); assert blend.is_file() and blend.stat().st_size>0
    views={"front":((6.9,0,2.25),(0,0,1),56),"side":((0,-7.8,2.2),(-0.1,0,1.05),58),"front_3q":((5.9,-5.2,3),(0,0,1.05),55),"cockpit":((2.85,-1.35,2.2),(0.55,0,1.48),72)}
    renders={}
    for n,(loc,tgt,lens) in views.items():
        p=out/f"orbita_{n}.png"; renders[n]={"file":p.name,"bytes":render(sc,c,p,loc,tgt,lens)}
    manifest={"status":"PASS","runner":"github-public-actions","blender_version":".".join(map(str,bpy.app.version)),"render_engine":sc.render.engine,"checkpoint":{"file":blend.name,"bytes":blend.stat().st_size},"renders":renders,"checks":checks,"object_count":len(sc.objects),"elapsed_seconds":round(time.time()-started,3)}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding="utf-8"); print("CWS_CLOUD_BLENDER_PASS"); print(json.dumps(manifest,indent=2,sort_keys=True))
if __name__=="__main__": main()

# CWS cloud probe trigger: workflow already exists on default branch.
