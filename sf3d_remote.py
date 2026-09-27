from gradio_client import Client, handle_file
import json, os, shutil, sys, traceback

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

img = handle_file(IMAGE_URL)

# The Space exposes functions bound to input_img.change and run_btn.click.
# First ask it to remove/prepare background, then feed the returned processed image to run_button.
prep=None
prep_errors=[]
for api_name in ["/requires_bg_remove", "/requires_bg_remove_1", "/lambda"]:
    try:
        print("TRY_PREP", api_name)
        prep=client.predict(img, 0.85, api_name=api_name)
        print("PREP_OK", api_name, type(prep), prep)
        break
    except Exception as e:
        prep_errors.append((api_name, repr(e)))
        print("PREP_FAIL", api_name, repr(e))

if prep is None:
    raise RuntimeError("Could not call background preparation endpoints: "+json.dumps(prep_errors))

# Gradio response expected: run_btn update, img_proc_state, background_remove_state, preview, output3d update, hdr update
if not isinstance(prep, (tuple,list)) or len(prep) < 3:
    raise RuntimeError(f"Unexpected prep response: {prep!r}")
background_state=prep[2]
img_proc_state=prep[1]
print("BACKGROUND_STATE", background_state)

run_errors=[]
result=None
for api_name in ["/run_button", "/run_button_1"]:
    try:
        print("TRY_RUN", api_name)
        result=client.predict(
            "Run",
            img,
            background_state,
            0.85,
            "None",
            -1,
            1024,
            api_name=api_name,
        )
        print("RUN_OK", api_name, type(result), result)
        break
    except Exception as e:
        run_errors.append((api_name, repr(e)))
        print("RUN_FAIL", api_name, repr(e))

if result is None:
    raise RuntimeError("SF3D run failed: "+json.dumps(run_errors))

# Find returned GLB path / file object recursively.
def find_glb(x):
    if isinstance(x, str) and x.lower().endswith(".glb"):
        return x
    if isinstance(x, dict):
        for k,v in x.items():
            if isinstance(v,str) and v.lower().endswith(".glb"):
                return v
            g=find_glb(v)
            if g:return g
    if isinstance(x,(list,tuple)):
        for v in x:
            g=find_glb(v)
            if g:return g
    # gradio FileData-like objects
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

# Gradio client generally downloads returned files locally. Copy it to stable output path.
dst=os.path.join(OUT,"orbita_sf3d.glb")
if glb.startswith("http://") or glb.startswith("https://"):
    import requests
    rr=requests.get(glb, timeout=180)
    rr.raise_for_status()
    open(dst,"wb").write(rr.content)
else:
    shutil.copy2(glb,dst)
assert os.path.getsize(dst)>0
print("SF3D_GLTF_PASS", dst, os.path.getsize(dst))
open(os.path.join(OUT,"sf3d_manifest.json"),"w").write(json.dumps({"status":"PASS","space":SPACE,"glb_bytes":os.path.getsize(dst)},indent=2))
