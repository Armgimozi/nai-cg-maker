$tellraw @s {"text":"♪ 악보:  $(n1) → $(n2) → $(n3) → $(n4) → $(n5)","color":"light_purple","bold":true}
$data modify entity @e[type=minecraft:text_display,tag=aooni.sheet,limit=1] text set value {"text":"♪ $(n1) $(n2) $(n3) $(n4) $(n5)","color":"light_purple"}
