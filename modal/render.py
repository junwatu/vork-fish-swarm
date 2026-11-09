"""Render the murmuration stills and clip on one Modal L40S.

The scene directory (scene.json + *.slang + *.bin) is baked into the image at
deploy, so edit/copy the scene BEFORE launching. Shader setup uses the shared
vork cache volume.

Spec is a JSON list of jobs:
  {"out": "hero.png", "shot": "scene.json", "profile": "std/final",
   "resolution": "1920x1080", "at": 9.0}
  {"out": "clip.mp4", "shot": "scene.json", "profile": "std/draft",
   "resolution": "1920x1080", "frame_start": 144, "frame_end": 335}
"""

import base64
import json
import os
import subprocess
from pathlib import Path

import modal

VORK_VERSION = "0.2.0"  # vork release; bump to upgrade the L40S image
app = modal.App("vork-l40s-baitball")
cache = modal.Volume.from_name("vork-l40s-cache", create_if_missing=True)

SCENE = str(Path(__file__).resolve().parent.parent / "scene")

image = (
    modal.Image.from_registry("ubuntu:22.04", add_python="3.13")
    .apt_install(
        "ca-certificates",
        "curl",
        "tar",
        "libvulkan1",
        "libgomp1",
        "libegl1",
        "ffmpeg",
        "vulkan-tools",
    )
    .run_commands(
        f"curl -fL --retry 6 --retry-delay 3 --retry-all-errors https://github.com/voyager-so/vork/releases/download/v{VORK_VERSION}/install.sh -o /tmp/vork-install.sh"
        " && VORK_NO_MODIFY_PATH=1 VORK_SKIP_SETUP=1 sh /tmp/vork-install.sh"
        " && /root/.local/bin/vork --version"
    )
    .add_local_dir(SCENE, remote_path="/scene")
)


def run(cmd: str, env: dict, timeout: int) -> str:
    print(f"\n$ {cmd}", flush=True)
    proc = subprocess.run(
        cmd,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        timeout=timeout,
    )
    text = proc.stdout or ""
    if len(text) > 80_000:
        text = text[:20_000] + "\n...[truncated]...\n" + text[-40_000:]
    print(text, flush=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {cmd}\n{text[-4000:]}")
    return text


def vulkan_env() -> dict:
    icd_dir = Path("/tmp/vulkan/icd.d")
    icd_dir.mkdir(parents=True, exist_ok=True)
    icd = icd_dir / "nvidia_icd.json"
    lib = "/usr/lib/x86_64-linux-gnu/libEGL_nvidia.so.0"
    icd.write_text(
        "{\n"
        '  "file_format_version": "1.0.0",\n'
        '  "ICD": {"library_path": "%s", "api_version": "1.3.290"}\n'
        "}\n" % lib
    )
    env = os.environ.copy()
    env["VK_ICD_FILENAMES"] = str(icd)
    env["VK_DRIVER_FILES"] = str(icd)
    env["VORK_CACHE_DIR"] = "/cache"
    env["VORK_NO_MODIFY_PATH"] = "1"
    env["VORK_SKIP_SETUP"] = "1"
    env["PATH"] = "/root/.local/bin:" + env.get("PATH", "")
    return env


def _vork_args(job: dict) -> str:
    args = (f"vork render /scene/{job['shot']} --profile {job['profile']}"
            f" --set resolution={job['resolution']}")
    if job.get("at") is not None:
        args += f" --at {job['at']}"
    if job.get("frame_start") is not None:
        args += f" --frame-start {job['frame_start']} --frame-end {job['frame_end']}"
    return args


@app.function(
    image=image,
    gpu="L40S",
    timeout=7200,
    cpu=8,
    memory=32768,
    max_containers=10,
    volumes={"/cache": cache},
)
def render_batch(spec: str) -> dict:
    jobs = json.loads(spec)
    env = vulkan_env()
    run("vork --version", env, 60)
    setup = run("vork setup", env, 900)
    logs = []
    errors = []
    files = {}
    try:
        for job in jobs:
            out_name = job["out"]
            try:
                log = run(f"{_vork_args(job)} --out /tmp/{out_name}", env, 5400)
            except Exception as exc:  # keep going: deliver the shots that worked
                errors.append({"out": out_name, "error": str(exc)[-600:]})
                print(f"ERROR {out_name}: {str(exc)[-600:]}", flush=True)
                continue
            data = Path(f"/tmp/{out_name}").read_bytes()
            files[out_name] = base64.b64encode(data).decode()
            logs.append({"out": out_name, "bytes": len(data), "log": log[-400:]})
    finally:
        try:
            cache.commit()
        except Exception as exc:  # concurrent containers may contend on the volume
            print(f"cache commit skipped: {str(exc)[-200:]}", flush=True)
    return {"setup_tail": setup[-300:], "logs": logs, "errors": errors, "files": files}


@app.local_entrypoint()
def main(spec: str, out_dir: str) -> None:
    # Each job in the spec runs in its own container, in parallel, so a long
    # clip can be split into chunks across many GPUs.
    jobs = json.loads(Path(spec).read_text())
    results = list(render_batch.map(json.dumps([job]) for job in jobs))
    dest_dir = Path(out_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        files = result.pop("files")
        for name, encoded in files.items():
            dest = dest_dir / name
            dest.write_bytes(base64.b64decode(encoded))
            print(f"WROTE {dest} {dest.stat().st_size}", flush=True)
        print("REPORT", json.dumps(result)[-4000:], flush=True)
