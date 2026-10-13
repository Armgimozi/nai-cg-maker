# 사용법: /execute as <닉네임> run function aooni:admin/oni_pick  → 다음 판 아오오니로 지정
tag @a remove aooni.want_oni
tag @s add aooni.want_oni
tellraw @a {"text":"","extra":[{"text":"[아오오니 저택] 다음 판 아오오니: ","color":"gray"},{"selector":"@s","color":"aqua"}]}
