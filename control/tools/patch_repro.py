import ast
p = 'reproduce.py'
s = open(p).read()
a = '''    env["MISSION"] = "orbit"
    env.setdefault("CONFIG", "config.json")
'''
b = '''    env["MISSION"] = "orbit"
    sel = json.loads((HERE / "mission.json").read_text())       # which configuration / run mode is the final design
    env.setdefault("CONFIG", sel["config"])
'''
assert a in s; s = s.replace(a, b)
a = '''           "--experiment", args.experiment]
'''
b = '''           "--experiment", args.experiment]
    if sel.get("prestart", False):
        # the controller must hold the fuel-free thrusters from the very first physics frame
        cmd += ["--controller-prestart", "--pre-controller-hold", "0"]
'''
assert a in s; s = s.replace(a, b)
s = s.replace("import argparse\nimport os\n", "import argparse\nimport json\nimport os\n")
open(p, 'w').write(s); ast.parse(s)

p = 'controller.py'
s = open(p).read()
a = '''    cfg = json.loads((HERE / os.environ.get("CONFIG", "config.json")).read_text())'''
b = '''    default_cfg = json.loads((HERE / "mission.json").read_text())["config"]
    cfg = json.loads((HERE / os.environ.get("CONFIG", default_cfg)).read_text())'''
assert a in s; s = s.replace(a, b)
open(p, 'w').write(s); ast.parse(s)
open('mission.json', 'w').write('{\n "config": "config_v3.json",\n "prestart": true\n}\n')
print("ok")
