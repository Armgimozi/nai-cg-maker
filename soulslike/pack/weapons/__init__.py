"""
무기·방패·촉매 모형 (pack/weapons/SPEC.md). gen_pack.py 가 icons 다음, roll_figure 앞에서 set_b.build(out) 와
set_a.build(out) 를 부른다 (어느 한쪽이 없으면 건너뛴다).

  set_a.py  A 몫 열 개 (칼 다섯, 방패 셋, 활, 가마지기의 쇠단지): blades_a, shields_a, bow_a, kiln_pot
  set_b.py  B 몫 열 개 (자루 무기, 판자 방패, 손종)
  공통 부품: _common.py (쥐는 점 격자, 손 자세, 아이템 정의 쓰기), _mats.py (손으로 찍은 재료 칸과 VoxWeapon),
             _views.py / _view.py (게임 밖 미리보기)
"""
