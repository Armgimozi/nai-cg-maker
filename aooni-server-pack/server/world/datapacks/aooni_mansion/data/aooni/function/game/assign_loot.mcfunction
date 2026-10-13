# 비밀번호 쪽지 4장과 물약 3개를 조사 상자 중 무작위로 골라 넣는다(나머지 상자는 빈 상자)
execute at @e[type=minecraft:marker,tag=aooni.spot] run data modify block ~ ~ ~ Items set value []
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.dig1
tag @e[type=minecraft:marker,tag=aooni.dig1] add aooni.loot
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.dig2
tag @e[type=minecraft:marker,tag=aooni.dig2] add aooni.loot
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.dig3
tag @e[type=minecraft:marker,tag=aooni.dig3] add aooni.loot
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.dig4
tag @e[type=minecraft:marker,tag=aooni.dig4] add aooni.loot
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.buff1
tag @e[type=minecraft:marker,tag=aooni.buff1] add aooni.loot
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.buff2
tag @e[type=minecraft:marker,tag=aooni.buff2] add aooni.loot
execute as @e[type=minecraft:marker,tag=aooni.spot,tag=!aooni.loot,sort=random,limit=1] run tag @s add aooni.buff3
tag @e[type=minecraft:marker,tag=aooni.buff3] add aooni.loot
execute at @e[type=minecraft:marker,tag=aooni.dig1] run function aooni:loot/put_digit1
execute at @e[type=minecraft:marker,tag=aooni.dig2] run function aooni:loot/put_digit2
execute at @e[type=minecraft:marker,tag=aooni.dig3] run function aooni:loot/put_digit3
execute at @e[type=minecraft:marker,tag=aooni.dig4] run function aooni:loot/put_digit4
execute at @e[type=minecraft:marker,tag=aooni.buff1] run item replace block ~ ~ ~ container.13 with minecraft:potion[minecraft:potion_contents={custom_color:8171462,custom_effects:[{id:"minecraft:speed",amplifier:1b,duration:400,show_particles:0b}]},minecraft:custom_name={text:"신속 물약",color:"light_purple",italic:false},minecraft:lore=[{text:"마시면 20초 동안 빨라진다",color:"gray",italic:false}]]
execute at @e[type=minecraft:marker,tag=aooni.buff2] run item replace block ~ ~ ~ container.13 with minecraft:potion[minecraft:potion_contents={custom_color:8356754,custom_effects:[{id:"minecraft:invisibility",amplifier:0b,duration:500,show_particles:0b}]},minecraft:custom_name={text:"투명 물약",color:"light_purple",italic:false},minecraft:lore=[{text:"마시면 25초 동안 투명해진다",color:"gray",italic:false}]]
execute at @e[type=minecraft:marker,tag=aooni.buff3] run item replace block ~ ~ ~ container.13 with minecraft:potion[minecraft:potion_contents={custom_color:2039713,custom_effects:[{id:"minecraft:night_vision",amplifier:0b,duration:2400,show_particles:0b}]},minecraft:custom_name={text:"야간 투시 물약",color:"light_purple",italic:false},minecraft:lore=[{text:"마시면 2분 동안 어둠 속이 잘 보인다",color:"gray",italic:false}]]
