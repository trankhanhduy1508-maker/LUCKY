from gradio_client import Client, handle_file
import json, os, shutil, requests

SPACE="tencent/Hunyuan3D-2mv"
OUT="hunyuan3d"
os.makedirs(OUT, exist_ok=True)

urls={
  "front":os.environ["ORBITA_FRONT_URL"],
  "back":os.environ["ORBITA_BACK_URL"],
  "left":os.environ["ORBITA_LEFT_URL"],
  "right":os.environ["ORBITA_RIGHT_URL"],
}

client=Client(SPACE)
print("SPACE_CONNECTED", SPACE)
api=client.view_api(return_format="dict")
print(json.dumps(api, indent=2)[:30000])

def endpoint_candidates(api):
    names=[]
    if isinstance(api,dict):
        named=api.get("named_endpoints",{})
        names.extend(named.keys())
    return names

names=endpoint_candidates(api)
print("ENDPOINTS",names)
target=None
for cand in ["/shape_generation","/shape_generation_1","/generation_all","/generation_all_1"]:
    if cand in names:
        target=cand; break
if target is None:
    for n in names:
        if "shape" in n.lower() or "generation" in n.lower():
            target=n; break
if target is None:
    raise RuntimeError("No shape-generation endpoint found")

front=handle_file(urls["front"]); back=handle_file(urls["back"]); left=handle_file(urls["left"]); right=handle_file(urls["right"])

print("CALLING",target)
# Parameters from the app source: caption,image,mv_front,mv_back,mv_left,mv_right,steps,guidance,seed,octree,rembg,num_chunks,randomize_seed
result=client.predict(
    None,
    None,
    front,
    back,
    left,
    right,
    30,
    5.5,
    1234,
    256,
    True,
    200000,
    False,
    api_name=target,
)
print("RESULT_TYPE",type(result))
print("RESULT",repr(result)[:10000])

def find_mesh(x):
    if isinstance(x,str) and x.lower().endswith((".glb",".obj",".ply")):
        return x
    if isinstance(x,dict):
        for v in x.values():
            g=find_mesh(v)
            if g:return g
    if isinstance(x,(list,tuple)):
        for v in x:
            g=find_mesh(v)
            if g:return g
    for attr in ("path","url","name"):
        try:
            v=getattr(x,attr)
            if isinstance(v,str) and v.lower().endswith((".glb",".obj",".ply")):
                return v
        except Exception:
            pass
    return None

mesh=find_mesh(result)
if not mesh:
    raise RuntimeError(f"No mesh file found in response: {result!r}")
print("MESH_RETURNED",mesh)

ext=os.path.splitext(mesh.split("?")[0])[1].lower() or ".glb"
dst=os.path.join(OUT,"orbita_hunyuan"+ext)
if mesh.startswith("http://") or mesh.startswith("https://"):
    rr=requests.get(mesh,timeout=300);rr.raise_for_status();open(dst,"wb").write(rr.content)
else:
    shutil.copy2(mesh,dst)
assert os.path.getsize(dst)>0
print("HUNYUAN_MULTI_VIEW_PASS",dst,os.path.getsize(dst))
open(os.path.join(OUT,"manifest_source.json"),"w").write(json.dumps({"status":"PASS","space":SPACE,"endpoint":target,"mesh":os.path.basename(dst),"mesh_bytes":os.path.getsize(dst)},indent=2))
