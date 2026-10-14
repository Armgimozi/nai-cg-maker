# 쓰러진 자리(LastDeathLocation)에 마검을 떨어뜨린다. 반짝여서 멀리서도 보인다
execute store result score #c aooni.var run clear @s minecraft:netherite_sword 0
execute if score #c aooni.var matches 0 run return 0
clear @s minecraft:netherite_sword
execute store result storage aooni:v dx int 1 run data get entity @s LastDeathLocation.pos[0]
execute store result storage aooni:v dy int 1 run data get entity @s LastDeathLocation.pos[1]
execute store result storage aooni:v dz int 1 run data get entity @s LastDeathLocation.pos[2]
function aooni:player/drop_sword_at with storage aooni:v
tellraw @a[tag=aooni.player] {"text":"","extra":[{"text":"마검이 쓰러진 자리에 떨어졌다! ","color":"gold","bold":true},{"text":"누군가 주워서 싸워야 한다!","color":"yellow"}]}
function aooni:player/arm_check
