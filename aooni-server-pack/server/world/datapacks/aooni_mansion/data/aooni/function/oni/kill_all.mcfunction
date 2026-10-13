execute as @e[type=minecraft:zombie,tag=aooni.oni] run tp @s ~ -120 ~
kill @e[tag=aooni.part]
kill @e[type=minecraft:zombie,tag=aooni.oni]
bossbar set aooni:boss visible false
