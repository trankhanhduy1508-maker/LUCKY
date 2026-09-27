from gradio_client import Client, handle_file
import json, os, shutil, requests

SPACE="stabilityai/stable-fast-3d"
IMAGE_URL=os.environ["ORBITA_IMAGE_URL"]
OUT="ai3d"
os.makedirs(OUT, exist_ok=True)

client=Client(SPACE)
print("SPACE_CONNECTED")
try:
    print(client.view_api(return_format="dict"))
except Exception as e:
    print("VIEW_API_ERROR", repr(e))

img=handle_file(IMAGE_URL)

# Current public API exposes run_button directly with 5 visible arguments.
# Hidden Gradio states are managed server-side and must not be passed.
result=client.predict(
    img,
    0.85,
    "None",
    -1,
    1024,
    api_name="/run_button",
)
print("RUN_OK", type(result), result)

def find_glb(x):
    if isinstance(x,str) and x.lower().endswith(".glb"):
        return x
    if isinstance(x,dict):
        for v in x.values():
            g=find_glb(v)
            if g:return g
    if isinstance(x,(list,tuple)):
        for v in x:
            g=find_glb(v)
            if g:return g
    for attr in ("path","url","name"):
        try:
            v=getattr(x,attr)
            if isinstance(v,str) and v.lower().endswith(".glb"):
                return v
        except Exception:
            pass
    return None

glb=find_glb(result)
if not glb:
    raise RuntimeError(f"No GLB in response: {result!r}")
print("GLB_RETURNED", glb)
dst=os.path.join(OUT,"orbita_sf3d.glb")
if glb.startswith("http://") or glb.startswith("https://"):
    rr=requests.get(glb,timeout=180);rr.raise_for_status();open(dst,"wb").write(rr.content)
else:
    shutil.copy2(glb,dst)
assert os.path.getsize(dst)>0
print("SF3D_GLTF_PASS",dst,os.path.getsize(dst))
open(os.path.join(OUT,"sf3d_manifest.json"),"w").write(json.dumps({"status":"PASS","space":SPACE,"glb_bytes":os.path.getsize(dst)},indent=2))
