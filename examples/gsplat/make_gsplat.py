"""Synthesize a 3DGS PLY the way a NuRec/gsplat reconstruction of a real scene would emit it."""
import numpy as np, struct, sys
n = 2000
rng = np.random.default_rng(7)
# a "reconstructed room": floor plane + a box-ish object
floor = np.column_stack([rng.uniform(-3,3,n//2), rng.uniform(-3,3,n//2), np.zeros(n//2)])
obj   = np.column_stack([rng.uniform(-0.4,0.4,n//2), rng.uniform(-0.4,0.4,n//2), rng.uniform(0,0.8,n//2)])
xyz = np.vstack([floor,obj]).astype(np.float32)
f_dc = np.vstack([np.tile([0.3,0.35,0.3],(n//2,1)), np.tile([0.8,0.2,0.2],(n//2,1))]).astype(np.float32)
opacity = rng.uniform(2.0,5.0,n).astype(np.float32)          # logit space
scale   = np.log(rng.uniform(0.01,0.05,(n,3))).astype(np.float32)  # log space
rot     = np.tile([1.0,0.0,0.0,0.0],(n,1)).astype(np.float32)

props = ["x","y","z","f_dc_0","f_dc_1","f_dc_2","opacity",
         "scale_0","scale_1","scale_2","rot_0","rot_1","rot_2","rot_3"]
hdr = "ply\nformat binary_little_endian 1.0\nelement vertex %d\n" % n
hdr += "".join("property float %s\n" % p for p in props) + "end_header\n"
data = np.hstack([xyz, f_dc, opacity[:,None], scale, rot]).astype(np.float32)
with open(sys.argv[1],"wb") as f:
    f.write(hdr.encode()); f.write(data.tobytes())
print("wrote %s: %d splats, %d properties" % (sys.argv[1], n, len(props)))
