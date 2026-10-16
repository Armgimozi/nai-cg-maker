리소스팩 공개 받기 주소용 사본 (터널·포트 문제로 서버가 직접 못 보낼 때 config.yml pack.url 에 씀).
파일 이름 뒤 8글자 = SHA-1 앞 8글자. 판이 바뀌어 팩이 바뀌면 새 파일을 더 올린다.
0.3.6.1 부터 플러그인이 이 사본을 스스로 쓴다 (config pack.public_copy). 판을 낼 때 python3 tools/check_pack_host.py --write 로 새 사본을 만들어 같이 올린다.
