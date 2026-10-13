# 0.5 이상 깎였을 때만(추격용 0.01 피해는 무시) 마지막으로 때린 사람을 기억한다
tag @a remove aooni.lasthit
execute on attacker run tag @s add aooni.lasthit
particle minecraft:crit ~ ~1.8 ~ 0.5 0.8 0.5 0.3 15
playsound minecraft:entity.zombie.hurt hostile @a[distance=..24] ~ ~ ~ 1 0.5
execute unless entity @s[tag=aooni.enraged] if score #bh aooni.var <= #half10 aooni.var run function aooni:boss/enrage
