effect give @s minecraft:saturation infinite 0 true
execute unless entity @s[tag=aooni.armed] run effect give @s minecraft:weakness infinite 9 true
execute if entity @s[tag=aooni.armed] run effect give @s minecraft:strength infinite 4 true
execute if entity @s[tag=aooni.jailed] run effect give @s minecraft:resistance infinite 4 true
