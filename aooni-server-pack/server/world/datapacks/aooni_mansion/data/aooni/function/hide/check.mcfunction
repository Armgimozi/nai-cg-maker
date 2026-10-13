tag @a remove aooni.hid_new
execute as @a[tag=aooni.alive,x=12,y=-60,z=10,dx=1,dy=1,dz=0] if block 12 -60 10 minecraft:spruce_door[open=false] run tag @s add aooni.hid_new
execute as @a[tag=aooni.oni_p,x=12,y=-60,z=10,dx=1,dy=1,dz=0] if block 12 -60 10 minecraft:spruce_door[open=false] run tp @s 11.5 -60 10.5
execute as @a[tag=aooni.alive,x=34,y=-60,z=10,dx=1,dy=1,dz=0] if block 34 -60 10 minecraft:spruce_door[open=false] run tag @s add aooni.hid_new
execute as @a[tag=aooni.oni_p,x=34,y=-60,z=10,dx=1,dy=1,dz=0] if block 34 -60 10 minecraft:spruce_door[open=false] run tp @s 33.5 -60 10.5
execute as @a[tag=aooni.alive,x=44,y=-60,z=10,dx=1,dy=1,dz=0] if block 44 -60 10 minecraft:spruce_door[open=false] run tag @s add aooni.hid_new
execute as @a[tag=aooni.oni_p,x=44,y=-60,z=10,dx=1,dy=1,dz=0] if block 44 -60 10 minecraft:spruce_door[open=false] run tp @s 43.5 -60 10.5
execute as @a[tag=aooni.alive,x=11,y=-60,z=24,dx=1,dy=1,dz=0] if block 12 -60 24 minecraft:spruce_door[open=false] run tag @s add aooni.hid_new
execute as @a[tag=aooni.oni_p,x=11,y=-60,z=24,dx=1,dy=1,dz=0] if block 12 -60 24 minecraft:spruce_door[open=false] run tp @s 13.5 -60 24.5
execute as @a[tag=aooni.alive,x=19,y=-60,z=20,dx=1,dy=1,dz=0] if block 20 -60 20 minecraft:spruce_door[open=false] run tag @s add aooni.hid_new
execute as @a[tag=aooni.oni_p,x=19,y=-60,z=20,dx=1,dy=1,dz=0] if block 20 -60 20 minecraft:spruce_door[open=false] run tp @s 21.5 -60 20.5
execute as @a[tag=aooni.alive,x=38,y=-60,z=34,dx=1,dy=1,dz=0] if block 39 -60 34 minecraft:spruce_door[open=false] run tag @s add aooni.hid_new
execute as @a[tag=aooni.oni_p,x=38,y=-60,z=34,dx=1,dy=1,dz=0] if block 39 -60 34 minecraft:spruce_door[open=false] run tp @s 40.5 -60 34.5
execute as @a[tag=aooni.alive,x=12,y=-55,z=8,dx=1,dy=1,dz=0] if block 12 -55 8 minecraft:spruce_door[open=false] run tag @s add aooni.hid_new
execute as @a[tag=aooni.oni_p,x=12,y=-55,z=8,dx=1,dy=1,dz=0] if block 12 -55 8 minecraft:spruce_door[open=false] run tp @s 11.5 -55 8.5
execute as @a[tag=aooni.alive,x=34,y=-55,z=2,dx=1,dy=1,dz=0] if block 34 -55 2 minecraft:spruce_door[open=false] run tag @s add aooni.hid_new
execute as @a[tag=aooni.oni_p,x=34,y=-55,z=2,dx=1,dy=1,dz=0] if block 34 -55 2 minecraft:spruce_door[open=false] run tp @s 33.5 -55 2.5
execute as @a[tag=aooni.alive,x=37,y=-55,z=10,dx=1,dy=1,dz=0] if block 38 -55 10 minecraft:spruce_door[open=false] run tag @s add aooni.hid_new
execute as @a[tag=aooni.oni_p,x=37,y=-55,z=10,dx=1,dy=1,dz=0] if block 38 -55 10 minecraft:spruce_door[open=false] run tp @s 39.5 -55 10.5
execute as @a[tag=aooni.alive,x=12,y=-55,z=33,dx=1,dy=1,dz=0] if block 12 -55 33 minecraft:spruce_door[open=false] run tag @s add aooni.hid_new
execute as @a[tag=aooni.oni_p,x=12,y=-55,z=33,dx=1,dy=1,dz=0] if block 12 -55 33 minecraft:spruce_door[open=false] run tp @s 11.5 -55 33.5
execute as @a[tag=aooni.alive,x=15,y=-55,z=21,dx=1,dy=1,dz=0] if block 16 -55 21 minecraft:spruce_door[open=false] run tag @s add aooni.hid_new
execute as @a[tag=aooni.oni_p,x=15,y=-55,z=21,dx=1,dy=1,dz=0] if block 16 -55 21 minecraft:spruce_door[open=false] run tp @s 17.5 -55 21.5
execute as @a[tag=aooni.alive,x=44,y=-55,z=27,dx=1,dy=1,dz=0] if block 44 -55 27 minecraft:spruce_door[open=false] run tag @s add aooni.hid_new
execute as @a[tag=aooni.oni_p,x=44,y=-55,z=27,dx=1,dy=1,dz=0] if block 44 -55 27 minecraft:spruce_door[open=false] run tp @s 43.5 -55 27.5
execute as @a[tag=aooni.hid_new,tag=!aooni.hidden] run function aooni:hide/enter
execute as @a[tag=aooni.hidden,tag=!aooni.hid_new] run function aooni:hide/leave
