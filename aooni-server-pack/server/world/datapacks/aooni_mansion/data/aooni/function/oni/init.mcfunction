tag @s remove aooni.new
team join aooni_oni @s
effect give @s minecraft:invisibility infinite 0 true
effect give @s minecraft:fire_resistance infinite 0 true
attribute @s minecraft:knockback_resistance base set 1
attribute @s minecraft:follow_range base set 48
attribute @s minecraft:spawn_reinforcements base set 0
attribute @s minecraft:max_health base set 40
data merge entity @s {Health:40f}
function aooni:oni/apply_speed
scoreboard players set @s aooni.life 0
scoreboard players set @s aooni.lost 0
scoreboard players set @s aooni.tgt 0
particle minecraft:large_smoke ~ ~1 ~ 0.4 0.8 0.4 0.02 40
playsound minecraft:block.wooden_door.open hostile @a[distance=..40] ~ ~ ~ 1.5 0.6
playsound minecraft:entity.iron_golem.step hostile @a[distance=..30] ~ ~ ~ 1.5 0.5
tellraw @a[tag=aooni.alive] {"text":"어디선가 문이 열리는 소리가 났다…","color":"dark_red","italic":true}
function aooni:oni/retarget
