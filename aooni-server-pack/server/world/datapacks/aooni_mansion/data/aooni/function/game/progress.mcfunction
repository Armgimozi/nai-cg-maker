scoreboard players set #prog aooni.var 0
execute if score #k_lib aooni.var matches 1 run scoreboard players add #prog aooni.var 1
execute if score #lib aooni.var matches 1 run scoreboard players add #prog aooni.var 1
execute if score #k_din aooni.var matches 1 run scoreboard players add #prog aooni.var 1
execute if score #din aooni.var matches 1 run scoreboard players add #prog aooni.var 1
execute if score #stairs aooni.var matches 1 run scoreboard players add #prog aooni.var 1
execute if score #store aooni.var matches 1 run scoreboard players add #prog aooni.var 1
execute if score #k_front aooni.var matches 1 run scoreboard players add #prog aooni.var 1
execute if score #front aooni.var matches 1 run scoreboard players add #prog aooni.var 1
execute store result bossbar aooni:goal value run scoreboard players get #prog aooni.var
execute if score #prog aooni.var matches 0 run bossbar set aooni:goal name {"text":"","extra":[{"text":"목표: ","color":"gold"},{"text":"1층을 조사해 단서를 찾아라 (검은 버튼 = 조사)","color":"white"}]}
execute if score #prog aooni.var matches 1 run bossbar set aooni:goal name {"text":"","extra":[{"text":"목표: ","color":"gold"},{"text":"서재 열쇠로 서재 문을 열어라 (문 옆 버튼)","color":"white"}]}
execute if score #prog aooni.var matches 2 run bossbar set aooni:goal name {"text":"","extra":[{"text":"목표: ","color":"gold"},{"text":"서재를 조사하라","color":"white"}]}
execute if score #prog aooni.var matches 3 run bossbar set aooni:goal name {"text":"","extra":[{"text":"목표: ","color":"gold"},{"text":"식당 문을 열어라 — 아오오니를 조심하라!","color":"white"}]}
execute if score #prog aooni.var matches 4 run bossbar set aooni:goal name {"text":"","extra":[{"text":"목표: ","color":"gold"},{"text":"피아노실에서 악보(서재)대로 연주하라","color":"white"}]}
execute if score #prog aooni.var matches 5 run bossbar set aooni:goal name {"text":"","extra":[{"text":"목표: ","color":"gold"},{"text":"2층의 네 발판을 동시에 밟아라 (안방·손님방·아이방·작업실)","color":"white"}]}
execute if score #prog aooni.var matches 6 run bossbar set aooni:goal name {"text":"","extra":[{"text":"목표: ","color":"gold"},{"text":"창고 금고를 열어라 — 숫자 단서 ①②③④","color":"white"}]}
execute if score #prog aooni.var matches 7 run bossbar set aooni:goal name {"text":"","extra":[{"text":"목표: ","color":"gold"},{"text":"현관 열쇠로 현관문을 열어라!","color":"white"}]}
execute if score #prog aooni.var matches 8 run bossbar set aooni:goal name {"text":"","extra":[{"text":"목표: ","color":"gold"},{"text":"정원 대문으로 탈출하라!","color":"white"}]}
execute if score #prog aooni.var matches 3.. run bossbar set aooni:goal color red
execute if score #prog aooni.var matches ..2 run bossbar set aooni:goal color blue
