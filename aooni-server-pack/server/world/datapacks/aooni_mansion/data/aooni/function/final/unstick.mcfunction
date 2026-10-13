# 1.3배가 되면 키가 2칸을 넘는다 → 옷장(2칸)이나 낮은 곳에 있으면 질식하므로 먼저 꺼낸다
execute if entity @s[x=12,y=-60,z=10,dx=1,dy=1,dz=0] run return run tp @s 11.5 -60 10.5
execute if entity @s[x=34,y=-60,z=10,dx=1,dy=1,dz=0] run return run tp @s 33.5 -60 10.5
execute if entity @s[x=44,y=-60,z=10,dx=1,dy=1,dz=0] run return run tp @s 43.5 -60 10.5
execute if entity @s[x=11,y=-60,z=24,dx=1,dy=1,dz=0] run return run tp @s 13.5 -60 24.5
execute if entity @s[x=19,y=-60,z=20,dx=1,dy=1,dz=0] run return run tp @s 21.5 -60 20.5
execute if entity @s[x=38,y=-60,z=34,dx=1,dy=1,dz=0] run return run tp @s 40.5 -60 34.5
execute if entity @s[x=12,y=-55,z=8,dx=1,dy=1,dz=0] run return run tp @s 11.5 -55 8.5
execute if entity @s[x=34,y=-55,z=2,dx=1,dy=1,dz=0] run return run tp @s 33.5 -55 2.5
execute if entity @s[x=37,y=-55,z=10,dx=1,dy=1,dz=0] run return run tp @s 39.5 -55 10.5
execute if entity @s[x=12,y=-55,z=33,dx=1,dy=1,dz=0] run return run tp @s 11.5 -55 33.5
execute if entity @s[x=15,y=-55,z=21,dx=1,dy=1,dz=0] run return run tp @s 17.5 -55 21.5
execute if entity @s[x=44,y=-55,z=27,dx=1,dy=1,dz=0] run return run tp @s 43.5 -55 27.5
execute at @s unless block ~ ~2 ~ minecraft:air run tp @s 38.5 -55 27.5
