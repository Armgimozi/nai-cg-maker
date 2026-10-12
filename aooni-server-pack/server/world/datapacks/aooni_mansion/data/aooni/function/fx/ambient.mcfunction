execute store result score #r aooni.var run random value 1..4
execute if score #r aooni.var matches 1 as @a[tag=aooni.alive] at @s run playsound minecraft:ambient.cave ambient @s ~ ~ ~ 1 0.8
execute if score #r aooni.var matches 2 as @a[tag=aooni.alive] at @s run playsound minecraft:block.wooden_door.close ambient @s ~4 ~ ~-3 0.6 0.5
execute if score #r aooni.var matches 3 as @a[tag=aooni.alive] at @s run playsound minecraft:entity.zombie.ambient ambient @s ~-5 ~ ~5 0.4 0.4
execute if score #r aooni.var matches 4 as @a[tag=aooni.alive] at @s run playsound minecraft:block.note_block.chime ambient @s ~ ~2 ~ 0.4 0.5
execute store result score #amb aooni.var run random value 30..60
