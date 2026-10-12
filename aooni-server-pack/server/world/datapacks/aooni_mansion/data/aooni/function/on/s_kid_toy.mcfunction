playsound minecraft:item.book.page_turn block @s ~ ~ ~ 1 1
tellraw @s {"text":"오르골이 저절로 울리기 시작했다…","color":"gray","italic":true}
playsound minecraft:block.note_block.chime block @a[distance=..16] ~ ~ ~ 1 0.6
schedule function aooni:fx/musicbox 10t
