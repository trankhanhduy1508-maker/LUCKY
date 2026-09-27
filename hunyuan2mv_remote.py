from gradio_client import Client, handle_file
import json, os, shutil, requests

SPACE="tencent/Hunyuan3D-2mv"
OUT="hunyuan"
os.makedirs(OUT, exist_ok=True)

urls = {
    "front": os.environ["ORBITA_FRONT_URL"],
    "back": os.environ["ORBITA_BACK_URL"],
    "left": os.environ["ORBITA_LEFT_URL"],
    "right": os.environ["ORBITA_RIGHT_URL"],
}

client = Client(SPACE)
api = client.view_api(return_format="dict")
print("API", json.dumps(api, indent=2, default=str))

api_name = None
fn_index = None
for name, spec in (api.get("named_endpoints") or {}).items():
    params = [p.get("parameter_name") for p in spec.get("parameters", [])]
    if "mv_image_front" in params and "mv_image_right" in params:
        api_name = name
        print("USING_NAMED_ENDPOINT", api_name, params)
        break

if api_name is None:
    for key, spec in (api.get("unnamed_endpoints") or {}).items():
        params = [p.get("parameter_name") for p in spec.get("parameters", [])]
        if "mv_image_front" in params and "mv_image_right" in params:
            try:
                fn_index = int(key)
            except Exception:
                fn_index = spec.get("fn_index")
            print("USING_FN_INDEX", fn_index, params)
            break

front = handle_file(urls["front"])
back = handle_file(urls["back"])
left = handle_file(urls["left"])
right = handle_file(urls["right"])

args = [
    None,  # caption
    None,  # single image
    front,
    back,
    left,
    right,
    30,    # steps, quality mode
    7.5,   # guidance
    1234,  # seed
    256,   # octree resolution
    True,  # remove background
    200000,
    False, # randomize seed
]

if api_name is not None:
    result = client.predict(*args, api_name=api_name)
elif fn_index is not None:
    result = client.predict(*args, fn_index=fn_index)
else:
    raise RuntimeError("Could not discover Hunyuan multiview generation endpoint")

print("RESULT", repr(result))

def find_mesh(x):
    if isinstance(x, str):
        low=x.lower()
        if low.endswith((".glb",".obj",".ply",".stl")):
            return x
    if isinstance(x, dict):
        for k in ("path","value","url","name"):
            v=x.get(k)
            if isinstance(v,str) and v.lower().endswith((".glb",".obj",".ply",".stl")):
                return v
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
            if isinstance(v,str) and v.lower().endswith((".glb",".obj",".ply",".stl")):
                return v
        except Exception:
            pass
    return None

mesh=find_mesh(result)
if not mesh:
    raise RuntimeError("No mesh file found in Hunyuan response")

dst=os.path.join(OUT,"orbita_hunyuan.glb")
if mesh.startswith(("http://","https://")):
    rr=requests.get(mesh,timeout=300); rr.raise_for_status(); open(dst,"wb").write(rr.content)
else:
    if not os.path.exists(mesh):
        raise RuntimeError(f"Returned mesh path does not exist locally: {mesh}")
    ext=os.path.splitext(mesh)[1].lower()
    if ext==".glb":
        shutil.copy2(mesh,dst)
    else:
        # Keep original extension too; Blender script can import it if needed.
        original=os.path.join(OUT,"orbita_hunyuan"+ext)
        shutil.copy2(mesh,original)
        raise RuntimeError(f"Hunyuan returned {ext}; GLB conversion not implemented yet: {original}")

assert os.path.getsize(dst)>0
manifest={"status":"PASS","space":SPACE,"mesh_bytes":os.path.getsize(dst),"endpoint":api_name,"fn_index":fn_index}
open(os.path.join(OUT,"hunyuan_manifest.json"),"w").write(json.dumps(manifest,indent=2))
print("HUNYUAN_2MV_PASS", json.dumps(manifest))
