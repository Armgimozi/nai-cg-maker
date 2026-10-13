$tellraw @s {"text":"쪽지를 찾았다: 『비밀번호 넷째 자리 = $(k4)』","color":"dark_red","bold":true}
execute if entity @e[type=minecraft:marker,tag=aooni.spot,tag=aooni.found,distance=..0.5] run return 0
tag @e[type=minecraft:marker,tag=aooni.spot,distance=..0.5,limit=1] add aooni.found
scoreboard players add #found aooni.var 1
$summon minecraft:text_display ~ ~0.7 ~ {Tags:["aooni.fx","aooni.digit"],text:{"text":"④ $(k4)","color":"dark_red","bold":true},billboard:"vertical",background:0,shadow:1b,transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[0.8f,0.8f,0.8f]}}
tellraw @a[tag=aooni.player,tag=!aooni.oni_p] {"text":"","extra":[{"selector":"@s","color":"aqua"},{"text":" 이(가) 비밀번호 ","color":"white"},{"text":"넷째 자리","color":"gold","bold":true},{"text":"를 찾았다! (","color":"white"},{"score":{"name":"#found","objective":"aooni.var"},"color":"gold"},{"text":"/4)","color":"white"}]}
execute as @a[tag=aooni.player,tag=!aooni.oni_p] at @s run playsound minecraft:entity.experience_orb.pickup master @s ~ ~ ~ 1 1.3
function aooni:game/progress
