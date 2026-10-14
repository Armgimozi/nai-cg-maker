clear @s minecraft:paper[minecraft:custom_data={aooni_fake:1b}]
give @s minecraft:paper[minecraft:custom_name={text:"번진 쪽지",color:"gray",italic:false},minecraft:lore=[{text:"글씨가 번져서 아무것도 읽을 수 없다",color:"gray",italic:false}]]
playsound minecraft:item.book.page_turn player @s ~ ~ ~ 1 0.8
tellraw @s {"text":"","extra":[{"text":"쪽지를 펼쳐 보니… 글씨가 번져서 아무것도 읽을 수 없다. ","color":"gray"},{"text":"가짜였다!","color":"red"}]}
