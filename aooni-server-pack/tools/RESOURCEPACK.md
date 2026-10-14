# 아오오니 저택 리소스팩

`dist/aooni-resourcepack.zip` 은 아오오니 저택 서버팩용 **선택 리소스팩**입니다.

- **아오오니 모형**: 파란 몸, 커다란 머리, 큰 흰 눈과 작은 눈동자, 두툼한 보라색 입술.
  머리·몸통·양팔·양다리 6조각으로 나뉘어 있어서 데이터팩이 팔다리를 움직일 수 있습니다.
- **마검**: 검붉은 칼날에 붉게 빛나는 날과 룬 무늬, 금색 날밑, 감은 손잡이 (네더라이트 검과 다르게 보입니다).
- 지원 버전: **Java 에디션 1.21.5 ~ 26.3** (리소스팩 포맷 55 ~ 97.1)

리소스팩이 없는 사람에게는 아오오니 모형이 **보라·검정 체크무늬 상자**(빠진 모델 표시)로 보입니다.
게임 진행에는 지장이 없지만, 모두 리소스팩을 켜고 하는 것을 권장합니다.

## 플레이어: 직접 설치하기

1. `aooni-resourcepack.zip` 을 받습니다. **압축을 풀지 마세요.** zip 그대로 씁니다.
2. 마인크래프트의 `resourcepacks` 폴더에 넣습니다.
   - Windows: `%APPDATA%\.minecraft\resourcepacks` (Win+R 에 붙여 넣고 엔터)
   - macOS: `~/Library/Application Support/minecraft/resourcepacks`
   - Linux: `~/.minecraft/resourcepacks`
   - 런처에서 설치(프로필)마다 다른 게임 폴더를 지정했다면 그 폴더 안의 `resourcepacks` 입니다.
   - 게임 안에서 **옵션 → 리소스 팩 → 팩 폴더 열기** 를 누르면 바로 그 폴더가 열립니다.
3. 게임에서 **옵션 → 리소스 팩** 으로 들어가 왼쪽 "사용 가능" 목록의 **아오오니 저택** 을
   오른쪽 "선택됨" 으로 옮기고 **완료** 를 누릅니다.
4. "호환되지 않음" 표시가 뜨면 1.21.5 미만이나 26.3 보다 새 버전입니다. 1.21.5 ~ 26.3 을 쓰세요.

## 서버 주인: 접속할 때 자동으로 받게 하기 (선택)

`server.properties` 에 다음 줄을 넣으면, 접속하는 사람에게 리소스팩을 받을지 묻고 자동으로 적용합니다.

```properties
resource-pack=https://example.com/aooni-resourcepack.zip
resource-pack-sha1=빌드할 때 출력된 40자리 sha1
require-resource-pack=false
```

- `resource-pack` 은 **브라우저에서 열면 곧바로 zip 이 내려받아지는 직접 링크**여야 합니다.
  - GitHub 릴리스 첨부 파일: `https://github.com/<계정>/<저장소>/releases/download/<태그>/aooni-resourcepack.zip`
  - Dropbox: 공유 링크 끝의 `?dl=0` 을 `?dl=1` 로 바꿉니다.
  - Google Drive 공유 링크는 확인 화면이 끼어서 대개 동작하지 않습니다.
- `resource-pack-sha1` 은 zip 파일의 SHA-1 입니다. `python3 tools/build_rp.py` 를 실행하면
  `resource-pack-sha1=...` 줄이 출력되니 그대로 복사하세요. 직접 구하려면
  - Windows: `certutil -hashfile aooni-resourcepack.zip SHA1`
  - macOS: `shasum aooni-resourcepack.zip` / Linux: `sha1sum aooni-resourcepack.zip`
- zip 을 다시 만들거나 내용을 바꾸면 sha1 도 바뀝니다. **새 파일을 올릴 때마다 sha1 도 같이 고치세요.**
  sha1 이 틀리면 클라이언트가 팩을 거부하거나 예전 파일을 계속 씁니다.
- `require-resource-pack=true` 로 하면 리소스팩을 거절한 사람은 접속할 수 없습니다.
  `resource-pack-prompt` 에 안내 문구(JSON 텍스트)를 넣을 수도 있습니다.
- 서버를 다시 켜야 적용됩니다. 마인크래프트가 저장하면서 `https\://` 처럼 `:` 앞에 `\` 를 붙일 수 있는데 정상입니다.

## 개발자용

```bash
python3 tools/build_rp.py                       # dist/aooni-resourcepack.zip + tools/rp_parts.json, sha1 출력, 검사
python3 tools/build_rp.py --preview <폴더>       # 미리보기 PNG + 1인칭 검사 (Pillow, numpy 필요)
python3 tools/rp_preview.py --out <폴더>         # 미리보기만 다시 그리기
```

- `build_rp.py` 는 표준 라이브러리만 씁니다. 텍스처(아오오니 256x256, 마검 32x32, pack.png 128x128)도 코드로 그립니다.
  타임스탬프를 고정하고 항목을 정렬하므로, 내용이 같으면 zip 과 sha1 도 항상 같습니다.
- 검사 항목: 모든 JSON 파싱, 참조한 텍스처·모델 존재, 요소 좌표 -16..32, 요소 회전(1.21.5 허용 각도),
  UV 범위, `pack.mcmeta` 가 1.21.5 ~ 26.3 의 옛/새 파서 모두에서 통과하는지, 아오오니 눈 높이(1.62, 웅크리면 1.27)가 머리 안인지.
  `--preview` 를 주면 눈 위치에서 672 방향으로 실제로 그려 보아 머리가 한 번도 보이지 않는지도 확인합니다.
- `pack.mcmeta` 는 `pack_format: 55`, `supported_formats: [55, 97]`, `min_format: 55`, `max_format: 97` 을 함께 적습니다.
  1.21.5 ~ 1.21.8 은 앞의 두 값을, 1.21.9 이후는 뒤의 두 값을 읽습니다(`max_format` 정수 97 은 97.x 전체, 26.3 = 97.1 포함).

### 데이터팩에서 쓰기

- 모형은 `item_display` 6개로 조립합니다. 각 아이템에 `minecraft:item_model` 컴포넌트를 붙입니다.
  예: `{id:"minecraft:paper",count:1,components:{"minecraft:item_model":"aooni:oni_head"}}`
- 모델마다 관절(회전축)이 모델 좌표 (8,8,8) = 엔티티 원점입니다. 6개 모두 아오오니 플레이어 발 위치에
  플레이어 yaw 로 두고, `transformation.translation` 에 `tools/rp_parts.json` 의 관절 좌표를 넣습니다.
  팔다리를 흔들 때는 `left_rotation` 을 X 축 회전으로 바꿉니다(음수 = 앞으로). 자세한 약속은 `rp_parts.json` 의 설명을 보세요.
- 마검: 검 아이템에 `minecraft:item_model="aooni:magum"` 을 붙입니다.

---
아오오니(青鬼)는 noprops 의 프리 호러 게임 캐릭터입니다. 이 리소스팩은 비공식 팬메이드입니다.
