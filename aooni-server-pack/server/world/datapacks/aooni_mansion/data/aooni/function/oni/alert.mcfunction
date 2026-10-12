# 소리를 낸 플레이어(태그 aooni.me) 쪽으로 아오오니가 반응한다
execute as @e[type=minecraft:zombie,tag=aooni.oni] run damage @s 0.01 minecraft:generic by @a[tag=aooni.me,limit=1]
execute unless entity @e[type=minecraft:zombie,tag=aooni.oni] if score #oni_on aooni.var matches 1 if score #oni_cd aooni.var matches 9.. run scoreboard players set #oni_cd aooni.var 8
