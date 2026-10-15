import yaml
R="/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/"
mobs=yaml.safe_load(open(R+"mobs.yml"))["mobs"]
bos=yaml.safe_load(open(R+"bosses.yml"))["bosses"]
fl=yaml.safe_load(open(R+"floors.yml"))["floors"]
for f,v in sorted(fl.items()):
    ms=v.get("mobs",[])
    hp=[mobs[m]["hp"] for m in ms]; dm=[mobs[m]["damage"] for m in ms]; de=[mobs[m].get("defense",0) for m in ms]
    print(f, v.get("level_range"), "dens",v.get("mob_density"), "rooms",v.get("rooms"), "elite",v.get("elite"), mobs[v["elite"]]["hp"] if v.get("elite") in mobs else None, "boss",v.get("boss"))
    print("   mob hp avg %.0f [%d..%d] dmg avg %.1f def avg %.1f"%(sum(hp)/len(hp),min(hp),max(hp),sum(dm)/len(dm),sum(de)/len(de)), [ (m, mobs[m]["hp"], mobs[m]["damage"], mobs[m].get("defense",0), mobs[m].get("ai"), mobs[m].get("attack_interval")) for m in ms])
for b,v in bos.items():
    print(b, "floor",v.get("floor"), "hp",v.get("hp"),"dmg",v.get("damage"),"def",v.get("defense"), "phases", v.get("phases") and len(v.get("phases")))
