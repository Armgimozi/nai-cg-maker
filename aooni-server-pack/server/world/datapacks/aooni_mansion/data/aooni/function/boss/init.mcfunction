tag @s remove aooni.new
team join aooni_oni @s
effect give @s minecraft:invisibility infinite 0 true
effect give @s minecraft:fire_resistance infinite 0 true
attribute @s minecraft:knockback_resistance base set 1
attribute @s minecraft:follow_range base set 64
attribute @s minecraft:spawn_reinforcements base set 0
attribute @s minecraft:max_health base set 1024
execute store result entity @s Health float 1 run scoreboard players get #bhp aooni.var
execute store result score #bhp_prev aooni.var run data get entity @s Health 10
function aooni:boss/apply_speed
scoreboard players set @s aooni.life 0
scoreboard players set @s aooni.tgt 0
particle minecraft:large_smoke ~ ~1.5 ~ 0.8 1.2 0.8 0.03 120
playsound minecraft:entity.ravager.roar hostile @a[distance=..48] ~ ~ ~ 2 0.5
function aooni:oni/retarget
