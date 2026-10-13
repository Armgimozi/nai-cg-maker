# 깨어나기 전까지는 NoAI 로 다락방에 묶어 둔다(game/oni_wake 에서 풀림)
kill @e[type=minecraft:zombie,tag=aooni.dummy]
summon minecraft:zombie 38.5 -55 27.5 {Tags:["aooni.dummy"],NoAI:1b,Silent:1b,PersistenceRequired:1b,CanPickUpLoot:0b,CanBreakDoors:0b,IsBaby:0b,active_effects:[{id:"minecraft:invisibility",amplifier:0b,duration:-1,show_particles:0b},{id:"minecraft:fire_resistance",amplifier:0b,duration:-1,show_particles:0b}],attributes:[{id:"minecraft:follow_range",base:256.0d},{id:"minecraft:knockback_resistance",base:1.0d},{id:"minecraft:spawn_reinforcements",base:0.0d}]}
# 갇힌/탈락한 사람과 같은 팀 → 그 사람들은 즉시 목표에서 빠진다
team join aooni_out @e[type=minecraft:zombie,tag=aooni.dummy]
execute if score #diff aooni.var matches 1 as @e[type=minecraft:zombie,tag=aooni.dummy] run attribute @s minecraft:movement_speed base set 0.27
execute if score #diff aooni.var matches 2 as @e[type=minecraft:zombie,tag=aooni.dummy] run attribute @s minecraft:movement_speed base set 0.3
execute if score #diff aooni.var matches 3 as @e[type=minecraft:zombie,tag=aooni.dummy] run attribute @s minecraft:movement_speed base set 0.33
execute at @e[type=minecraft:zombie,tag=aooni.dummy,limit=1] run function aooni:oni/model
