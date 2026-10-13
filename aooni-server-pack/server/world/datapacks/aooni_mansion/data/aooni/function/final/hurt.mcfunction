tag @a remove aooni.lasthit
execute on attacker run tag @s add aooni.lasthit
particle minecraft:crit ~ ~1.8 ~ 0.5 0.8 0.5 0.3 15
execute unless entity @s[tag=aooni.enraged] if score #bh aooni.var <= #half10 aooni.var run function aooni:final/enrage
