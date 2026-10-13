execute if score #f2 aooni.var matches 1 run return 0
scoreboard players set #f2 aooni.var 1
scoreboard players add #found aooni.var 1
function aooni:loot/read2 with storage aooni:v
tellraw @a[tag=aooni.player,tag=!aooni.oni_p] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) ","color":"white"},{"text":"비밀번호 쪽지 ②","color":"gold","bold":true},{"text":" 을(를) 찾았다! (","color":"white"},{"score":{"name":"#found","objective":"aooni.var"},"color":"gold"},{"text":"/4)","color":"white"}]}
execute as @a[tag=aooni.player,tag=!aooni.oni_p] at @s run playsound minecraft:entity.experience_orb.pickup master @s ~ ~ ~ 1 1.3
function aooni:game/progress
