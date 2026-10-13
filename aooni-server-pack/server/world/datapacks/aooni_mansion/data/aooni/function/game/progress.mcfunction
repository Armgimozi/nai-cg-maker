scoreboard players operation #weap aooni.var = #w1 aooni.var
scoreboard players operation #weap aooni.var += #w2 aooni.var
scoreboard players operation #weap aooni.var += #w3 aooni.var
scoreboard players operation #weap aooni.var += #w4 aooni.var
execute store result bossbar aooni:goal value run scoreboard players get #weap aooni.var
scoreboard players set #goal aooni.var 7
execute if score #store aooni.var matches 0 run scoreboard players set #goal aooni.var 6
execute if score #stairs aooni.var matches 0 run scoreboard players set #goal aooni.var 5
execute if score #din aooni.var matches 0 run scoreboard players set #goal aooni.var 4
execute if score #k_din aooni.var matches 0 run scoreboard players set #goal aooni.var 3
execute if score #lib aooni.var matches 0 run scoreboard players set #goal aooni.var 2
execute if score #k_lib aooni.var matches 0 run scoreboard players set #goal aooni.var 1
execute if score #weap aooni.var matches 4.. run scoreboard players set #goal aooni.var 8
execute if score #final aooni.var matches 1 run scoreboard players set #goal aooni.var 9
execute if score #goal aooni.var matches 1 run bossbar set aooni:goal name {"text":"","extra":[{"text":"봉인 ","color":"gray"},{"score":{"name":"#weap","objective":"aooni.var"},"color":"gold"},{"text":"/4 · ","color":"gray"},{"text":"목표: ","color":"gold"},{"text":"1층을 조사하라 — 거실과 화장실이 수상하다 (검은 버튼 = 조사)","color":"white"}]}
execute if score #goal aooni.var matches 2 run bossbar set aooni:goal name {"text":"","extra":[{"text":"봉인 ","color":"gray"},{"score":{"name":"#weap","objective":"aooni.var"},"color":"gold"},{"text":"/4 · ","color":"gray"},{"text":"목표: ","color":"gold"},{"text":"서재 열쇠로 서재 문을 열어라 (문 옆 버튼)","color":"white"}]}
execute if score #goal aooni.var matches 3 run bossbar set aooni:goal name {"text":"","extra":[{"text":"봉인 ","color":"gray"},{"score":{"name":"#weap","objective":"aooni.var"},"color":"gold"},{"text":"/4 · ","color":"gray"},{"text":"목표: ","color":"gold"},{"text":"서재를 조사하라","color":"white"}]}
execute if score #goal aooni.var matches 4 run bossbar set aooni:goal name {"text":"","extra":[{"text":"봉인 ","color":"gray"},{"score":{"name":"#weap","objective":"aooni.var"},"color":"gold"},{"text":"/4 · ","color":"gray"},{"text":"목표: ","color":"gold"},{"text":"식당 문을 열어라 — 아오오니를 조심하라!","color":"white"}]}
execute if score #goal aooni.var matches 5 run bossbar set aooni:goal name {"text":"","extra":[{"text":"봉인 ","color":"gray"},{"score":{"name":"#weap","objective":"aooni.var"},"color":"gold"},{"text":"/4 · ","color":"gray"},{"text":"목표: ","color":"gold"},{"text":"피아노실에서 악보(서재)대로 연주하라","color":"white"}]}
execute if score #goal aooni.var matches 6 run bossbar set aooni:goal name {"text":"","extra":[{"text":"봉인 ","color":"gray"},{"score":{"name":"#weap","objective":"aooni.var"},"color":"gold"},{"text":"/4 · ","color":"gray"},{"text":"목표: ","color":"gold"},{"text":"2층 네 방의 발판을 동시에 밟아라","color":"white"}]}
execute if score #goal aooni.var matches 7 run bossbar set aooni:goal name {"text":"","extra":[{"text":"봉인 ","color":"gray"},{"score":{"name":"#weap","objective":"aooni.var"},"color":"gold"},{"text":"/4 · ","color":"gray"},{"text":"목표: ","color":"gold"},{"text":"남은 봉인의 비밀번호를 찾아 풀어라","color":"white"}]}
execute if score #goal aooni.var matches 8 run bossbar set aooni:goal name {"text":"","extra":[{"text":"봉인 ","color":"gray"},{"score":{"name":"#weap","objective":"aooni.var"},"color":"gold"},{"text":"/4 · ","color":"gray"},{"text":"목표: ","color":"gold"},{"text":"현관홀 제단에서 전설의 검을 뽑아라!","color":"white"}]}
execute if score #goal aooni.var matches 9 run bossbar set aooni:goal name {"text":"","extra":[{"text":"봉인 ","color":"gray"},{"score":{"name":"#weap","objective":"aooni.var"},"color":"gold"},{"text":"/4 · ","color":"gray"},{"text":"목표: ","color":"gold"},{"text":"결전! 전설의 검으로 거대 아오오니를 족쳐라!","color":"white"}]}
execute if score #oni_on aooni.var matches 1 run bossbar set aooni:goal color red
execute if score #oni_on aooni.var matches 0 run bossbar set aooni:goal color blue
