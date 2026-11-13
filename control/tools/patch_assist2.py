import ast, json
p='fsw/core.py'; s=open(p).read()
a='''            if self.cfg.get("att_assist", False) and not rcs and s.alt > self.cfg.get("assist_alt_min", 300.0):'''
b='''            if (self.cfg.get("att_assist", False) and not rcs and s.alt > self.cfg.get("assist_alt_min", 300.0)
                    and (self.payload_attached or not self.cfg.get("assist_loaded_only", True))):
                # (only with the payload on board: the light empty vehicle turns well enough on its wheels, and the
                #  bang-bang couples over-stress very long arms when it is empty)'''
assert a in s; s=s.replace(a,b,1); open(p,'w').write(s); ast.parse(s)
for f in ("config_v3j.json", "config_v3k.json"):
    c = json.load(open(f)); c.update({"assist_loaded_only": True}); json.dump(c, open(f, "w"), indent=1)
c = json.load(open("config_v3j.json")); c["att_rate_max_empty"] = 0.17; json.dump(c, open("config_v3j.json", "w"), indent=1)
print("ok")
