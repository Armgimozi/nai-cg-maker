# NAI 도트 가챠 (Godot 4.3)

NovelAI 로 만든 **일러스트**와 직접 그린 **도트 스프라이트**로 캐릭터를 모으는
수집형 가챠 게임. Google Play 출시를 목표로 한 Android 세로 화면(720×1280) 프로젝트.

역할 분담:

| 에셋 | 만드는 방법 | 쓰이는 곳 |
|---|---|---|
| 도트 스프라이트 `assets/characters/<id>.png` | 직접 제작(Aseprite 등). 임시로 `tools/make_placeholders.py` 가 절차적 생성 | 도감 카드, 뽑기 결과, 상세 화면 좌하단 |
| NAI 일러스트 `assets/illust/<id>.png` | `tools/gen_characters.py` 가 NAI 로 생성 | 상세 화면 큰 그림(CG 감상) |

NAI 는 일러스트만 만듭니다. 도트는 NAI 로 만들지 않습니다.

## 구성

```
game/
├─ project.godot              # 720x1280 세로, canvas_items 스트레치, 텍스처 필터 Nearest(도트)
├─ data/characters.json       # 캐릭터 24명: id·이름·칭호·등급·설명·NAI 프롬프트·색
├─ scenes/                    # main_menu · gacha · collection · character_detail · ui/character_card
├─ scripts/autoload/          # CharacterDB(데이터·텍스처) · GameState(재화·저장) · Gacha(확률·천장)
├─ scripts/                   # 각 씬 스크립트
├─ assets/characters/*.png    # 도트 스프라이트(32x48)
├─ assets/illust/*.png        # NAI 일러스트(생성 전엔 비어 있음)
├─ assets/fonts/Galmuri11.ttf # 한글 픽셀 폰트(OFL)
├─ theme/default_theme.tres   # 버튼·패널·폰트 테마
├─ tests/smoke.tscn           # 헤드리스 스모크 테스트
└─ export_presets.cfg         # Android AAB 프리셋
```

## 게임 규칙

- 재화 **젬**: 시작 1500, 일일 보상 300, 앱을 켜 두거나 꺼 둔 동안 분당 10(오프라인 상한 600).
- **뽑기**: 1회 100젬 / 10회 900젬. 확률 UR 1% · SSR 5% · SR 14% · R 30% · N 50%.
  50회 안에 SSR 이상이 없으면 50회째 확정, 10연차는 SR 이상 1장 보장.
  확률은 뽑기 화면 하단에 그대로 표시됩니다(확률형 아이템 고지).
- **중복**은 등급별 조각(5/10/30/100/300)으로 바뀌고, 조각은 메인 메뉴에서 젬과 1:1 교환.
- 저장은 `user://save.json` 에 자동(뽑기·1분마다·앱 종료/백그라운드 시).

## 실행

1. [Godot 4.3](https://godotengine.org/download) 설치 → **Import** 로 `game/project.godot` 선택 → ▶.
2. 스모크 테스트(선택): `godot --headless --path game tests/smoke.tscn` → `SMOKE OK`.

## 캐릭터 추가·교체

1. `data/characters.json` 의 `characters` 배열에 항목 추가. `id` 는 파일명이 됩니다.
2. 도트 스프라이트를 `assets/characters/<id>.png` 로 저장(권장 32×48, 투명 배경).
   없으면 `python tools/make_placeholders.py` 가 임시 스프라이트를 만듭니다(있는 건 건드리지 않음).
3. NAI 일러스트 생성(저장소 루트에서):

   ```bash
   set NAI_API_TOKEN=pst-...                       # 또는 config.json 의 nai_token
   python tools/gen_characters.py --dry-run        # 프롬프트 확인(무료)
   python tools/gen_characters.py                  # 없는 일러스트만 생성
   python tools/gen_characters.py --only draconia --force --seed 42
   python tools/gen_characters.py --webp           # 용량 절감(Godot 이 webp 도 읽음)
   ```

   - 프롬프트 = `style.prefix` + 캐릭터 `prompt`, 네거티브 = `style.negative`.
   - `style.reference` 에 그림체 기준 이미지 경로를 넣으면 Precise Reference(style) 로
     전 캐릭터 그림체를 통일합니다(생성당 +5 Anlas).
   - 모델·해상도·스텝은 `config.json` 의 `nai_*` 값. 원본 렌더는 `cache/nai_illust_raw/` 보관.
   - 상업 출시용이면 `artist:` 태그(작가 이름)는 넣지 않는 편이 안전합니다.

## Android 빌드 (AAB)

1. Godot **Editor → Manage Export Templates** 에서 4.3 템플릿 설치.
2. Android Studio(또는 SDK 커맨드라인 툴)와 JDK 17 설치 후
   **Editor → Editor Settings → Export → Android** 에 SDK 경로·JDK 경로 지정.
3. 서명 키 생성(한 번만, **절대 커밋 금지** — `.gitignore` 에 `*.keystore` 포함):

   ```bash
   keytool -genkey -v -keystore release.keystore -alias upload -keyalg RSA -keysize 2048 -validity 10000
   ```

4. **Project → Export → Android** 프리셋에서
   - `package/unique_name` 을 본인 도메인으로(예 `com.yourname.dotgacha`)
   - Release Keystore 경로·alias·비밀번호 입력
   - `gradle_build/export_format` = AAB(프리셋에 이미 설정)
   - 아이콘: `launcher_icons` 에 512 아이콘(`icon.png`)을 넣고 adaptive icon 도 준비
5. **Export Project** → `build/nai-dot-gacha.aab`.

## Google Play 출시 체크리스트

- **Play Console** 개발자 계정(1회 등록비) → 앱 만들기 → 내부 테스트 트랙에 AAB 업로드.
  Play App Signing 사용(업로드 키는 위 keystore).
- **타겟 API 레벨**: 신규 앱은 최신 요구 수준(현재 Android 15 / API 35)을 맞춰야 합니다.
  Godot 4.3 의 기본 target SDK 로 부족하면 `gradle_build/target_sdk` 를 올리세요.
- **스토어 등록정보**: 아이콘 512, 그래픽 이미지 1024×500, 스크린샷(세로 2장 이상), 설명.
- **콘텐츠 등급** 설문, **데이터 보안** 양식(이 게임은 네트워크 통신·수집 데이터 없음),
  **개인정보처리방침 URL**(광고/분석 SDK 를 넣으면 필수).
- **확률형 아이템**: 유료 결제로 뽑기를 팔면 확률 고지 의무. 현재는 무료 재화만 쓰지만
  화면에 확률을 이미 표시합니다. 국내 출시 시 게임산업법의 확률형 아이템 표시 의무도 확인.
- **AI 생성 이미지**: 앱 안에서 생성하지 않고 내장만 하므로 Play 의 AI 생성 콘텐츠
  정책(앱 내 생성 기능 대상)은 적용되지 않습니다. NovelAI 약관상 생성물 권리는
  이용자에게 있으나 출시 전 최신 약관을 다시 확인하세요.
- **폰트 라이선스**: Galmuri(OFL 1.1) — `assets/fonts/LICENSE-Galmuri.txt` 를 함께 배포.
- 출시 전 `tests/` 폴더는 export 에서 제외되도록 프리셋에 `exclude_filter="tests/*"` 설정됨.

## 다음 단계 아이디어

- 캐릭터 강화/레벨·전투 등 진행 콘텐츠, 이벤트 배너(픽업 확률), 튜토리얼
- 효과음·BGM, 뽑기 연출 강화(등급별 이펙트), 진동
- 광고 보상(AdMob 플러그인) 또는 인앱 결제(확률 고지·환불 정책 필요)
