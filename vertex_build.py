#!/usr/bin/env python3
"""vertex_build.py - Build Vertex programs; JSON result for the IDE."""
import sys, json, subprocess, os, re, argparse

def run_cmd(cmd, cwd=None, env=None):
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=cwd, env=env
        )
        return proc.returncode, proc.stdout or ""
    except FileNotFoundError as e:
        return 127, str(e)
    except Exception as e:
        return 1, str(e)

def parse_vertexc_errors(text):
    errors = []
    for line in text.splitlines():
        m = re.search(r'Error at line (\d+):\s*(.+?)(?:\s+\(found (.+)\))?$', line, re.I)
        if m:
            msg = m.group(2).strip()
            if m.group(3):
                msg += f" (found '{m.group(3)}')"
            errors.append({"stage": "vertexc", "line": int(m.group(1)), "file": None,
                           "message": msg, "raw_line": line.strip()})
    return errors

def parse_gpp_errors(text):
    errors = []
    for line in text.splitlines():
        m = re.search(r'^([^:]+):(\d+)(?::\d+)?:\s*error:\s*(.+)$', line)
        if m:
            errors.append({"stage": "gpp", "line": int(m.group(2)), "file": m.group(1),
                           "message": m.group(3), "raw_line": line.strip()})
    return errors

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--mode", default="auto", choices=["gui", "console", "auto"])
    ap.add_argument("--output-dir", default=".")
    ap.add_argument("--vertexc", default="vertexc")
    ap.add_argument("--gpp", default="g++")
    ap.add_argument("--static", action="store_true", default=True)
    ap.add_argument("--no-static", dest="static", action="store_false")
    args = ap.parse_args()

    src = os.path.abspath(args.source)
    src_dir = os.path.dirname(src) or os.getcwd()
    out_dir = os.path.abspath(args.output_dir or src_dir)
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0]
    exe = os.path.join(out_dir, base + (".exe" if os.name == "nt" else ""))

    mode = args.mode
    if mode == "auto":
        try:
            text = open(src, encoding="utf-8", errors="replace").read()
            gui_pat = re.compile(r'Import\s*"vcl\.vtx"|RunApp\s*\(|\bWindow\s*\(|\bHWND\b', re.I)
            mode = "gui" if gui_pat.search(text) else "console"
        except Exception:
            mode = "console"

    env = os.environ.copy()
    gpp_dir = os.path.dirname(os.path.abspath(args.gpp)) if args.gpp else ""
    if gpp_dir and os.path.isdir(gpp_dir):
        env["PATH"] = gpp_dir + os.pathsep + env.get("PATH", "")

    # 1) vertexc
    rc, out = run_cmd([args.vertexc, src], cwd=src_dir, env=env)
    if rc != 0:
        errs = parse_vertexc_errors(out)
        if not errs:
            errs = [{"stage": "vertexc", "line": None, "file": None,
                     "message": out.strip() or f"vertexc exited {rc}", "raw_line": out.strip()}]
        print(json.dumps({"success": False, "stage": "vertexc", "errors": errs,
                          "raw_output": out, "mode": mode, "executable": None}))
        return 1

    cpp = None
    for c in (os.path.join(src_dir, "output.cpp"), os.path.join(out_dir, "output.cpp"),
              os.path.abspath("output.cpp")):
        if os.path.isfile(c):
            cpp = c
            break
    if not cpp:
        print(json.dumps({"success": False, "stage": "vertexc",
                          "errors": [{"stage": "vertexc", "line": None, "file": None,
                                      "message": "output.cpp not generated", "raw_line": ""}],
                          "raw_output": out, "mode": mode, "executable": None}))
        return 1

    dest = os.path.join(out_dir, "output.cpp")
    if os.path.abspath(cpp) != os.path.abspath(dest):
        try:
            open(dest, "wb").write(open(cpp, "rb").read())
            cpp = dest
        except Exception:
            pass

    # 2) g++
    cmd = [args.gpp, "-O2", "-std=c++17", cpp, "-o", exe]
    if mode == "gui":
        cmd += ["-mwindows"]
        if args.static:
            cmd += ["-static", "-static-libgcc", "-static-libstdc++"]
        cmd += ["-luser32", "-lgdi32", "-lcomdlg32", "-lwinmm", "-ladvapi32"]
    else:
        if args.static:
            cmd += ["-static", "-static-libgcc", "-static-libstdc++"]

    rc, gout = run_cmd(cmd, cwd=out_dir, env=env)
    combined = (out + "\n" + gout).strip()
    if rc != 0:
        errs = parse_gpp_errors(gout)
        if not errs:
            # show first non-empty lines so IDE is not blank
            lines = [ln for ln in gout.splitlines() if ln.strip()]
            msg = lines[0] if lines else f"g++ exited {rc} (no error text captured)"
            errs = [{"stage": "gpp", "line": None, "file": None,
                     "message": msg, "raw_line": msg}]
            # attach more context
            if len(lines) > 1:
                errs[0]["message"] = " | ".join(lines[:5])
        print(json.dumps({"success": False, "stage": "gpp", "errors": errs,
                          "raw_output": combined, "mode": mode, "executable": None,
                          "gpp_cmd": cmd}))
        return 1

    print(json.dumps({"success": True, "stage": "done", "errors": [],
                      "raw_output": combined, "mode": mode, "executable": exe,
                      "gpp_cmd": cmd}))
    return 0

if __name__ == "__main__":
    sys.exit(main())