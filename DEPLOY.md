# 배포 가이드 (PC 안 켜도 됨 · 각자 키 입력 BYO-key)

배포본은 **완전 BYO-key**입니다: 서버에 키를 두지 않고, 접속자가 웹의 **🔑 설정**에서
자기 Anthropic·NovelAI 키를 입력합니다(키는 브라우저에만 저장되고 요청 헤더로만 전달).
그래서 사이트가 공개돼도 **당신의 토큰은 쓰이지 않습니다.**

## ⚠️ 보안 (가장 중요)
- **`config.json` 을 절대 깃에 올리지 마세요** — 당신의 실제 키가 들어있습니다. (`.gitignore`/`.dockerignore` 에 이미 제외돼 있음)
- 호스트 환경변수에 `ANTHROPIC_API_KEY`/`NAI_API_TOKEN` 을 **설정하지 마세요** (설정하면 그게 기본키로 쓰여 토큰이 낭비됩니다). 비워두면 순수 BYO-key.

## 옵션 A — Render (무료, 추천)
1. 이 폴더를 GitHub 저장소로 올립니다 (`config.json` 은 제외됨).
2. [render.com](https://render.com) → New → **Web Service** → 저장소 연결.
3. 런타임 **Docker** 선택 (Dockerfile 자동 인식). 끝.
   - Docker 안 쓰려면: Environment=Python, Build=`pip install -r requirements.txt && python fetch_tags.py`, Start=`gunicorn wsgi:app --timeout 300`.
4. 발급된 `https://<이름>.onrender.com` 주소를 PC·폰 어디서나 접속 → 🔑 설정에 키 입력 → 사용.
   - 무료 플랜은 15분 미사용 시 잠들고 다음 접속 때 깨어나는 데 30초쯤 걸립니다.

## 옵션 B — Hugging Face Spaces (무료, Docker)
1. huggingface.co → New Space → SDK **Docker** → 빈 템플릿.
2. 이 폴더 파일을 업로드(또는 git push). `config.json` 제외.
3. 빌드되면 Space URL 로 접속 → 🔑 설정에 키 입력.

## 옵션 C — 내 PC에서 임시 공유 (배포 X)
- `start-phone.bat` 더블클릭 → cloudflared 임시 https 주소. PC가 켜져 있어야 함.

## 로컬 개인용 (기존 그대로)
- `start.bat` 또는 `python run.py` — 이땐 `config.json` 의 키를 서버 기본값으로 씁니다.
