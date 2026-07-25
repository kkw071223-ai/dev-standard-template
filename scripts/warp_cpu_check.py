import warp as wp
wp.init()
print("devices:", [str(d) for d in wp.get_devices()])

@wp.kernel
def integrate(pos: wp.array(dtype=wp.vec3), vel: wp.array(dtype=wp.vec3), dt: float):
    i = wp.tid()
    v = vel[i] + wp.vec3(0.0, 0.0, -9.81) * dt
    vel[i] = v
    pos[i] = pos[i] + v * dt

d = "cpu"
pos = wp.array([wp.vec3(0.0, 0.0, 10.0)], dtype=wp.vec3, device=d)
vel = wp.array([wp.vec3(1.0, 0.0, 0.0)], dtype=wp.vec3, device=d)
for step in range(100):
    wp.launch(integrate, dim=1, inputs=[pos, vel, 0.01], device=d)
print("after 100 steps (1.0s) ballistic on CPU:")
print("  pos =", pos.numpy()[0], " vel =", vel.numpy()[0])
