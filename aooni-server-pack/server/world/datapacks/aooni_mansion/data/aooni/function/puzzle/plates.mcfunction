scoreboard players set #pl aooni.var 0
execute if entity @a[tag=aooni.alive,x=2,y=-55,z=10,dx=0,dy=0,dz=0] run scoreboard players add #pl aooni.var 1
execute if entity @a[tag=aooni.alive,x=24,y=-55,z=10,dx=0,dy=0,dz=0] run scoreboard players add #pl aooni.var 1
execute if entity @a[tag=aooni.alive,x=3,y=-55,z=32,dx=0,dy=0,dz=0] run scoreboard players add #pl aooni.var 1
execute if entity @a[tag=aooni.alive,x=27,y=-55,z=20,dx=0,dy=0,dz=0] run scoreboard players add #pl aooni.var 1
execute if score #pl aooni.var matches 0 run return 0
scoreboard players operation #need aooni.var = #alive aooni.var
execute if score #need aooni.var matches 5.. run scoreboard players set #need aooni.var 4
execute if score #need aooni.var matches ..0 run scoreboard players set #need aooni.var 1
execute as @a[tag=aooni.alive,x=2,y=-55,z=10,dx=0,dy=0,dz=0] run title @s actionbar {"text":"","extra":[{"text":"발판 ","color":"aqua"},{"score":{"name":"#pl","objective":"aooni.var"},"color":"white"},{"text":" / ","color":"gray"},{"score":{"name":"#need","objective":"aooni.var"},"color":"white"},{"text":"  — 다른 방의 발판도 동시에!","color":"gray"}]}
execute as @a[tag=aooni.alive,x=24,y=-55,z=10,dx=0,dy=0,dz=0] run title @s actionbar {"text":"","extra":[{"text":"발판 ","color":"aqua"},{"score":{"name":"#pl","objective":"aooni.var"},"color":"white"},{"text":" / ","color":"gray"},{"score":{"name":"#need","objective":"aooni.var"},"color":"white"},{"text":"  — 다른 방의 발판도 동시에!","color":"gray"}]}
execute as @a[tag=aooni.alive,x=3,y=-55,z=32,dx=0,dy=0,dz=0] run title @s actionbar {"text":"","extra":[{"text":"발판 ","color":"aqua"},{"score":{"name":"#pl","objective":"aooni.var"},"color":"white"},{"text":" / ","color":"gray"},{"score":{"name":"#need","objective":"aooni.var"},"color":"white"},{"text":"  — 다른 방의 발판도 동시에!","color":"gray"}]}
execute as @a[tag=aooni.alive,x=27,y=-55,z=20,dx=0,dy=0,dz=0] run title @s actionbar {"text":"","extra":[{"text":"발판 ","color":"aqua"},{"score":{"name":"#pl","objective":"aooni.var"},"color":"white"},{"text":" / ","color":"gray"},{"score":{"name":"#need","objective":"aooni.var"},"color":"white"},{"text":"  — 다른 방의 발판도 동시에!","color":"gray"}]}
execute if score #pl aooni.var >= #need aooni.var run function aooni:puzzle/plates_solved
