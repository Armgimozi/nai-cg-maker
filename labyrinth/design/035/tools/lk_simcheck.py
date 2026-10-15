import sys, time
sys.path.insert(0, '/tmp/claude-0/-home-user-nai-cg-maker/f3f3d909-a465-5457-ae4c-97c24013e339/scratchpad/design')
import sim, random
random.seed(1)
t=time.time()
scn=sim.proposal()
for c in ["guardian","shadow"]:
    print(c, sim.floor_stats(c,"average","normal",scn,40))
print(time.time()-t)
