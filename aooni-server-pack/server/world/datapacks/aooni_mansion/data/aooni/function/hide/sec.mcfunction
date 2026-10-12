execute if entity @e[type=minecraft:zombie,tag=aooni.oni,distance=..3] run scoreboard players add @s aooni.hidet 1
execute unless entity @e[type=minecraft:zombie,tag=aooni.oni,distance=..3] run scoreboard players set @s aooni.hidet 0
execute if score @s aooni.hidet matches 1.. run playsound minecraft:entity.warden.heartbeat master @s ~ ~ ~ 1 1.4
execute if score @s aooni.hidet matches 3.. store result score #r aooni.var run random value 1..3
execute if score @s aooni.hidet matches 3.. if score #r aooni.var matches 1 at @e[type=minecraft:zombie,tag=aooni.oni,sort=nearest,limit=1] run function aooni:player/found
