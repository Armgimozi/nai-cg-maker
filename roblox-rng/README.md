# 🌍 랜드마크 RNG (로블록스 RNG + 타이쿤)

지구본을 돌려 세계의 **명소**를 발견하고, 발견한 명소를 **내 관광 공원**에 미니어처로 전시해
관광 수입을 버는 게임입니다. 흔한 홍콩 시계탑은 1/2, 가장 희귀한 세계수는 **1/40,000,000**.

> 이 저장소(nai-cg-maker)의 `roblox-rng/` 폴더에 들어 있지만 나머지 코드와는 **완전히 독립**된 프로젝트입니다.
> 자세한 설계와 모듈 간 약속은 [DESIGN.md](DESIGN.md) 에 있습니다.

## 게임 기능

| 기능 | 내용 |
|---|---|
| 지구본 돌리기 | 버튼 / **R** 키. 지구본이 돌다가 지역에 핀이 꽂히고 명소가 공개됨. 희귀할수록 길고 화려함 |
| 자동 굴리기 | 버튼 / **T** 키 |
| 발견 보너스 · 별 | 처음 발견하면 보너스 코인. 같은 명소를 또 발견하면 별(★1~5)이 올라 수입 증가 |
| 관광 공원 | 광장을 둘러싼 내 부지에 명소 미니어처 전시, 초당 관광 수입. 기본은 희귀한 순서로 자동 배치, **공원 배치** 창(도감 [배치] 버튼 / 내 공원 받침대 클릭 / 공원에 있을 때 메뉴 [배치] 버튼)에서 칸마다 전시할 명소를 직접 고를 수 있음 |
| 업그레이드 | 🌐 지구본(행운) · ✈️ 여행사(굴림 속도) · 🏞️ 공원 확장(전시 칸) · 🎟️ 입장료(수입) — 영구 |
| 여권 도장 | 4대륙(아시아·유럽·아프리카·아메리카)마다 불가사의 등급까지 모두 모으면 도장 + 영구 행운 +25% (전설급은 보너스 수집) |
| 대표 명소 | 고른 명소가 캐릭터 옆에 작게 떠다님 ("더 희귀하면 자동 지정" 설정) |
| 📰 뉴스 속보 | 1/1,000 이상 발견 시 서버 전체 알림, 1/10,000 이상이면 광장 하늘에 거대 홀로그램 |
| 리더보드 | 굴림 횟수, 최고 명소 |
| 저장 | DataStore 자동 저장(2분마다 + 퇴장/서버 종료) · 서버 이동 시 데이터 꼬임 방지 세션 잠금 |
| 보안 | 굴림 판정·코인·업그레이드·대표 지정 전부 **서버에서** 처리/검증 |

## 명소 목록과 확률 (150종 · 5대륙)

| 명소 | 영문 | 지역 | 등급 | 표기 확률 | 실제 확률 (행운 x1) | 발견 보너스 | 기본 수입/초 |
|---|---|---|---|---|---|---|---|
| 홍콩 시계탑 | Clock Tower, Hong Kong | 🏯 아시아 | 일반 명소 | 1 in 2 | 5.56% | 8 | 1 |
| 희망봉 등대 | Cape Point Lighthouse | 🐪 아프리카 | 일반 명소 | 1 in 3 | 2.78% | 9 | 1 |
| 하버 브리지 | Sydney Harbour Bridge | 🏝️ 오세아니아 | 일반 명소 | 1 in 4 | 2.78% | 10 | 1 |
| 풍차 마을 | Kinderdijk Windmills | 🏰 유럽 | 일반 명소 | 1 in 5 | 2.78% | 12 | 1 |
| 돌하르방 | Dol Hareubang, Jeju | 🏯 아시아 | 일반 명소 | 1 in 6 | 2.78% | 13 | 1 |
| 버킹엄 분수 | Buckingham Fountain | 🗽 아메리카 | 일반 명소 | 1 in 7 | 2.78% | 14 | 1 |
| 워싱턴 기념탑 | Washington Monument | 🗽 아메리카 | 일반 명소 | 1 in 8 | 2.78% | 15 | 1 |
| 모에라키 볼더스 | Moeraki Boulders | 🏝️ 오세아니아 | 일반 명소 | 1 in 9 | 2.78% | 15 | 1 |
| 게이트웨이 아치 | Gateway Arch | 🗽 아메리카 | 도시 명소 | 1 in 10 | 2.78% | 16 | 2 |
| 첨성대 | Cheomseongdae Observatory | 🏯 아시아 | 도시 명소 | 1 in 11 | 2.78% | 17 | 2 |
| 개선문 | Arc de Triomphe | 🏰 유럽 | 도시 명소 | 1 in 12 | 2.78% | 18 | 2 |
| 볼더스 비치 펭귄 | Boulders Beach Penguins | 🐪 아프리카 | 도시 명소 | 1 in 13 | 2.78% | 19 | 2 |
| 플린더스 스트리트 역 | Flinders Street Station | 🏝️ 오세아니아 | 도시 명소 | 1 in 14 | 2.78% | 19 | 2 |
| 브란덴부르크 문 | Brandenburg Gate | 🏰 유럽 | 도시 명소 | 1 in 15 | 2.78% | 20 | 2 |
| 다보탑 | Dabotap Pagoda | 🏯 아시아 | 도시 명소 | 1 in 16 | 2.78% | 20 | 2 |
| 브루클린 다리 | Brooklyn Bridge | 🗽 아메리카 | 도시 명소 | 1 in 18 | 2.62% | 22 | 2 |
| 빅벤 | Big Ben | 🏰 유럽 | 도시 명소 | 1 in 20 | 2.48% | 23 | 2 |
| 셰프샤우엔 파란 마을 | Chefchaouen Blue Town | 🐪 아프리카 | 도시 명소 | 1 in 22 | 2.36% | 24 | 2 |
| 팬케이크 바위 | Punakaiki Pancake Rocks | 🏝️ 오세아니아 | 도시 명소 | 1 in 24 | 2.26% | 25 | 2 |
| 스카이타워 | Sky Tower, Auckland | 🏝️ 오세아니아 | 도시 명소 | 1 in 25 | 2.26% | 25 | 2 |
| 트레비 분수 | Trevi Fountain | 🏰 유럽 | 도시 명소 | 1 in 27 | 2.17% | 26 | 2 |
| 숭례문 | Sungnyemun Gate | 🏯 아시아 | 도시 명소 | 1 in 30 | 2.02% | 28 | 2 |
| 테이블 마운틴 | Table Mountain | 🐪 아프리카 | 도시 명소 | 1 in 32 | 1.96% | 29 | 2 |
| 빵산 | Sugarloaf Mountain | 🗽 아메리카 | 도시 명소 | 1 in 35 | 1.84% | 30 | 2 |
| 타워 브리지 | Tower Bridge | 🏰 유럽 | 도시 명소 | 1 in 38 | 1.74% | 31 | 2 |
| 경복궁 | Gyeongbokgung Palace | 🏯 아시아 | 도시 명소 | 1 in 40 | 1.70% | 32 | 2 |
| 캐시드럴 코브 | Cathedral Cove | 🏝️ 오세아니아 | 도시 명소 | 1 in 42 | 1.66% | 33 | 2 |
| 피사의 사탑 | Leaning Tower of Pisa | 🏰 유럽 | 도시 명소 | 1 in 45 | 1.58% | 34 | 2 |
| 바오밥나무 거리 | Avenue of the Baobabs | 🐪 아프리카 | 도시 명소 | 1 in 48 | 1.51% | 35 | 2 |
| 프라하 천문시계 | Prague Astronomical Clock | 🏰 유럽 | 도시 명소 | 1 in 50 | 1.48% | 36 | 2 |
| 성산일출봉 | Seongsan Ilchulbong | 🏯 아시아 | 도시 명소 | 1 in 55 | 1.37% | 38 | 2 |
| 금문교 | Golden Gate Bridge | 🗽 아메리카 | 도시 명소 | 1 in 60 | 1.28% | 39 | 2 |
| 힐리어 핑크 호수 | Lake Hillier (Pink Lake) | 🏝️ 오세아니아 | 도시 명소 | 1 in 65 | 1.20% | 41 | 2 |
| 자유의 여신상 | Statue of Liberty | 🗽 아메리카 | 도시 명소 | 1 in 70 | 1.13% | 42 | 2 |
| 베네치아 리알토 다리 | Rialto Bridge, Venice | 🏰 유럽 | 도시 명소 | 1 in 75 | 1.07% | 44 | 2 |
| 초콜릿 힐 | Chocolate Hills | 🏯 아시아 | 도시 명소 | 1 in 80 | 1.02% | 45 | 2 |
| 아이트벤하두 | Ait Benhaddou | 🐪 아프리카 | 도시 명소 | 1 in 88 | 0.93% | 47 | 2 |
| 피통스 봉우리 | The Pitons | 🗽 아메리카 | 도시 명소 | 1 in 95 | 0.87% | 49 | 2 |
| 산토리니 | Santorini (Oia) | 🏰 유럽 | 국가 명소 | 1 in 100 | 0.84% | 50 | 5 |
| 하와마할 | Hawa Mahal (Palace of the Winds) | 🏯 아시아 | 국가 명소 | 1 in 105 | 0.81% | 52 | 5 |
| 웨이브 록 | Wave Rock | 🏝️ 오세아니아 | 국가 명소 | 1 in 110 | 0.78% | 53 | 5 |
| 백악관 | The White House | 🗽 아메리카 | 국가 명소 | 1 in 115 | 0.75% | 54 | 5 |
| 남산타워 | Namsan Tower, Seoul | 🏯 아시아 | 국가 명소 | 1 in 120 | 0.72% | 55 | 5 |
| 데드블레이 | Deadvlei | 🐪 아프리카 | 국가 명소 | 1 in 130 | 0.67% | 58 | 5 |
| 히메지성 | Himeji Castle | 🏯 아시아 | 국가 명소 | 1 in 140 | 0.63% | 60 | 5 |
| 옐로스톤 간헐천 | Old Faithful Geyser | 🗽 아메리카 | 국가 명소 | 1 in 145 | 0.61% | 61 | 5 |
| 페나 궁전 | Pena Palace | 🏰 유럽 | 국가 명소 | 1 in 155 | 0.58% | 63 | 5 |
| 팔라우 락 아일랜드 | Rock Islands of Palau | 🏝️ 오세아니아 | 국가 명소 | 1 in 165 | 0.55% | 65 | 5 |
| 금각사 | Kinkaku-ji (Golden Pavilion) | 🏯 아시아 | 국가 명소 | 1 in 175 | 0.52% | 67 | 5 |
| 나이아가라 폭포 | Niagara Falls | 🗽 아메리카 | 국가 명소 | 1 in 180 | 0.51% | 68 | 5 |
| 칭기 드 베마라하 | Tsingy de Bemaraha | 🐪 아프리카 | 국가 명소 | 1 in 190 | 0.48% | 69 | 5 |
| 에펠탑 | Eiffel Tower | 🏰 유럽 | 국가 명소 | 1 in 200 | 0.46% | 71 | 5 |
| 드라큘라 성 | Bran Castle (Dracula's Castle) | 🏰 유럽 | 국가 명소 | 1 in 215 | 0.43% | 74 | 5 |
| 파묵칼레 | Pamukkale Travertines | 🏯 아시아 | 국가 명소 | 1 in 225 | 0.41% | 75 | 5 |
| 모레인 호수 | Moraine Lake | 🗽 아메리카 | 국가 명소 | 1 in 240 | 0.39% | 78 | 5 |
| 12사도 바위 | Twelve Apostles | 🏝️ 오세아니아 | 국가 명소 | 1 in 250 | 0.37% | 80 | 5 |
| 헝가리 국회의사당 | Hungarian Parliament Building | 🏰 유럽 | 국가 명소 | 1 in 265 | 0.35% | 82 | 5 |
| 천단 | Temple of Heaven | 🏯 아시아 | 국가 명소 | 1 in 280 | 0.34% | 84 | 5 |
| 무지개산 | Rainbow Mountain (Vinicunca) | 🗽 아메리카 | 국가 명소 | 1 in 300 | 0.32% | 87 | 5 |
| 랄리벨라 암굴 교회 | Church of St. George, Lalibela | 🐪 아프리카 | 국가 명소 | 1 in 315 | 0.30% | 89 | 5 |
| 피렌체 두오모 | Florence Cathedral (Duomo) | 🏰 유럽 | 국가 명소 | 1 in 330 | 0.29% | 91 | 5 |
| 콜로세움 | Colosseum | 🏰 유럽 | 국가 명소 | 1 in 350 | 0.27% | 94 | 5 |
| 후지산 | Mount Fuji | 🏯 아시아 | 국가 명소 | 1 in 370 | 0.26% | 97 | 5 |
| 파나마 운하 | Panama Canal | 🗽 아메리카 | 국가 명소 | 1 in 390 | 0.25% | 99 | 5 |
| 보라보라 섬 | Bora Bora | 🏝️ 오세아니아 | 국가 명소 | 1 in 410 | 0.23% | 102 | 5 |
| 성 바실리 대성당 | Saint Basil's Cathedral | 🏰 유럽 | 국가 명소 | 1 in 435 | 0.22% | 105 | 5 |
| 포탈라궁 | Potala Palace | 🏯 아시아 | 국가 명소 | 1 in 460 | 0.21% | 108 | 5 |
| 카르나크 신전 | Karnak Temple | 🐪 아프리카 | 국가 명소 | 1 in 485 | 0.20% | 111 | 5 |
| 보르군 목조 교회 | Borgund Stave Church | 🏰 유럽 | 국가 명소 | 1 in 515 | 0.19% | 114 | 5 |
| 아레날 화산 | Arenal Volcano | 🗽 아메리카 | 국가 명소 | 1 in 540 | 0.18% | 117 | 5 |
| 석굴암 | Seokguram Grotto | 🏯 아시아 | 국가 명소 | 1 in 570 | 0.17% | 120 | 5 |
| 타지마할 | Taj Mahal | 🏯 아시아 | 국가 명소 | 1 in 600 | 0.16% | 123 | 5 |
| 노트르담 대성당 | Notre-Dame de Paris | 🏰 유럽 | 국가 명소 | 1 in 640 | 0.15% | 127 | 5 |
| 페리토 모레노 빙하 | Perito Moreno Glacier | 🗽 아메리카 | 국가 명소 | 1 in 675 | 0.14% | 130 | 5 |
| 아야 소피아 | Hagia Sophia | 🏯 아시아 | 국가 명소 | 1 in 715 | 0.14% | 134 | 5 |
| 알함브라 궁전 | Alhambra | 🏰 유럽 | 국가 명소 | 1 in 750 | 0.13% | 137 | 5 |
| 메로에 피라미드 | Pyramids of Meroe | 🐪 아프리카 | 국가 명소 | 1 in 800 | 0.12% | 142 | 5 |
| 앙코르와트 | Angkor Wat | 🏯 아시아 | 국가 명소 | 1 in 850 | 0.12% | 146 | 5 |
| 티칼 신전 | Tikal Temple I | 🗽 아메리카 | 국가 명소 | 1 in 900 | 0.11% | 150 | 5 |
| 성 베드로 대성당 | St. Peter's Basilica | 🏰 유럽 | 국가 명소 | 1 in 950 | 0.10% | 155 | 5 |
| 밀퍼드 사운드 | Milford Sound (Mitre Peak) | 🏝️ 오세아니아 | 세계 명소 | 1 in 1,000 | 1/1,014 | 159 | 12 |
| 카파도키아 | Cappadocia | 🏯 아시아 | 세계 명소 | 1 in 1,080 | 1/1,094 | 165 | 12 |
| 우유니 소금사막 | Salar de Uyuni | 🗽 아메리카 | 세계 명소 | 1 in 1,150 | 1/1,164 | 170 | 12 |
| 스핑크스 | Great Sphinx | 🐪 아프리카 | 세계 명소 | 1 in 1,200 | 1/1,214 | 174 | 12 |
| 노이슈반슈타인 성 | Neuschwanstein Castle | 🏰 유럽 | 세계 명소 | 1 in 1,300 | 1/1,314 | 181 | 12 |
| 하롱베이 | Ha Long Bay | 🏯 아시아 | 세계 명소 | 1 in 1,400 | 1/1,414 | 188 | 12 |
| 킬리만자로산 | Mount Kilimanjaro | 🐪 아프리카 | 세계 명소 | 1 in 1,500 | 1/1,514 | 194 | 12 |
| 만리장성 | Great Wall | 🏯 아시아 | 세계 명소 | 1 in 1,600 | 1/1,614 | 200 | 12 |
| 이과수 폭포 | Iguazu Falls | 🗽 아메리카 | 세계 명소 | 1 in 1,700 | 1/1,714 | 207 | 12 |
| 몽생미셸 | Mont-Saint-Michel | 🏰 유럽 | 세계 명소 | 1 in 1,800 | 1/1,814 | 213 | 12 |
| 빅토리아 폭포 | Victoria Falls | 🐪 아프리카 | 세계 명소 | 1 in 1,900 | 1/1,913 | 218 | 12 |
| 킬라우에아 화산 | Kilauea Volcano | 🏝️ 오세아니아 | 세계 명소 | 1 in 2,000 | 1/2,013 | 224 | 12 |
| 기자 피라미드 | Pyramids of Giza | 🐪 아프리카 | 세계 명소 | 1 in 2,200 | 1/2,213 | 235 | 12 |
| 그랜드 캐니언 | Grand Canyon | 🗽 아메리카 | 세계 명소 | 1 in 2,400 | 1/2,413 | 245 | 12 |
| 장가계 | Zhangjiajie Stone Pillars | 🏯 아시아 | 세계 명소 | 1 in 2,500 | 1/2,513 | 250 | 12 |
| 세고비아 수도교 | Aqueduct of Segovia | 🏰 유럽 | 세계 명소 | 1 in 2,650 | 1/2,663 | 258 | 12 |
| 그레이트 배리어 리프 | Great Barrier Reef | 🏝️ 오세아니아 | 세계 명소 | 1 in 2,800 | 1/2,812 | 265 | 12 |
| 치첸이트사 | Chichen Itza | 🗽 아메리카 | 세계 명소 | 1 in 3,000 | 1/3,012 | 274 | 12 |
| 자금성 | Forbidden City | 🏯 아시아 | 세계 명소 | 1 in 3,300 | 1/3,313 | 288 | 12 |
| 세렝게티 초원 | Serengeti | 🐪 아프리카 | 세계 명소 | 1 in 3,500 | 1/3,512 | 296 | 12 |
| 파르테논 신전 | Parthenon | 🏰 유럽 | 세계 명소 | 1 in 3,750 | 1/3,762 | 307 | 12 |
| 마추픽추 | Machu Picchu | 🗽 아메리카 | 세계 명소 | 1 in 4,000 | 1/4,012 | 317 | 12 |
| 아마존 열대우림 | Amazon Rainforest | 🗽 아메리카 | 세계 명소 | 1 in 4,300 | 1/4,312 | 328 | 12 |
| 보로부두르 사원 | Borobudur | 🏯 아시아 | 세계 명소 | 1 in 4,600 | 1/4,612 | 340 | 12 |
| 사하라 사막 | Sahara Desert | 🐪 아프리카 | 세계 명소 | 1 in 4,900 | 1/4,912 | 350 | 12 |
| 메테오라 수도원 | Meteora Monasteries | 🏰 유럽 | 세계 명소 | 1 in 5,200 | 1/5,211 | 361 | 12 |
| 페트라 | Petra | 🏯 아시아 | 세계 명소 | 1 in 5,500 | 1/5,511 | 371 | 12 |
| 갈라파고스 제도 | Galapagos Islands | 🗽 아메리카 | 세계 명소 | 1 in 5,900 | 1/5,911 | 385 | 12 |
| 아부심벨 신전 | Abu Simbel Temples | 🐪 아프리카 | 세계 명소 | 1 in 6,300 | 1/6,310 | 397 | 12 |
| 마터호른 | Matterhorn | 🏰 유럽 | 세계 명소 | 1 in 6,600 | 1/6,610 | 407 | 12 |
| 모아이 석상 | Moai | 🏝️ 오세아니아 | 세계 명소 | 1 in 7,000 | 1/7,010 | 419 | 12 |
| 앙헬 폭포 | Angel Falls | 🗽 아메리카 | 세계 명소 | 1 in 7,500 | 1/7,509 | 434 | 12 |
| 에베레스트산 | Mount Everest | 🏯 아시아 | 세계 명소 | 1 in 8,000 | 1/8,009 | 448 | 12 |
| 테오티우아칸 | Teotihuacan | 🗽 아메리카 | 세계 명소 | 1 in 8,500 | 1/8,508 | 461 | 12 |
| 스톤헨지 | Stonehenge | 🏰 유럽 | 세계 명소 | 1 in 9,000 | 1/9,008 | 475 | 12 |
| 와이토모 반딧불이 동굴 | Waitomo Glowworm Caves | 🏝️ 오세아니아 | 불가사의 | 1 in 10,000 | 1/10,008 | 500 | 30 |
| 자이언츠 코즈웨이 | Giant's Causeway | 🏰 유럽 | 불가사의 | 1 in 11,000 | 1/11,007 | 525 | 30 |
| 진시황 병마용 | Terracotta Army | 🏯 아시아 | 불가사의 | 1 in 12,500 | 1/12,507 | 560 | 30 |
| 그레이트 블루홀 | Great Blue Hole | 🗽 아메리카 | 불가사의 | 1 in 14,000 | 1/14,007 | 592 | 30 |
| 알렉산드리아 등대 | Lighthouse of Alexandria | 🐪 아프리카 | 불가사의 | 1 in 15,000 | 1/15,007 | 613 | 30 |
| 투탕카멘의 무덤 | Tomb of Tutankhamun | 🐪 아프리카 | 불가사의 | 1 in 17,000 | 1/17,007 | 652 | 30 |
| 나스카 라인 | Nazca Lines | 🗽 아메리카 | 불가사의 | 1 in 20,000 | 1/20,007 | 708 | 30 |
| 얍섬 돌 화폐 | Rai Stones of Yap | 🏝️ 오세아니아 | 불가사의 | 1 in 22,000 | 1/22,007 | 742 | 30 |
| 폼페이 | Pompeii & Mount Vesuvius | 🏰 유럽 | 불가사의 | 1 in 25,000 | 1/25,007 | 791 | 30 |
| 바빌론 공중정원 | Hanging Gardens of Babylon | 🏯 아시아 | 불가사의 | 1 in 30,000 | 1/30,007 | 867 | 30 |
| 사하라의 눈 | Richat Structure (Eye of the Sahara) | 🐪 아프리카 | 불가사의 | 1 in 33,000 | 1/33,007 | 909 | 30 |
| 올멕 거대 두상 | Olmec Colossal Head | 🗽 아메리카 | 불가사의 | 1 in 36,000 | 1/36,006 | 949 | 30 |
| 아르테미스 신전 | Temple of Artemis at Ephesus | 🏯 아시아 | 불가사의 | 1 in 40,000 | 1/40,006 | 1,000 | 30 |
| 난마돌 | Nan Madol | 🏝️ 오세아니아 | 불가사의 | 1 in 45,000 | 1/45,006 | 1,061 | 30 |
| 그레이트 짐바브웨 | Great Zimbabwe | 🐪 아프리카 | 불가사의 | 1 in 50,000 | 1/50,005 | 1,119 | 30 |
| 로도스 거상 | Colossus of Rhodes | 🏰 유럽 | 불가사의 | 1 in 60,000 | 1/60,005 | 1,225 | 30 |
| 테노치티틀란 | Tenochtitlan | 🗽 아메리카 | 불가사의 | 1 in 65,000 | 1/65,005 | 1,275 | 30 |
| 올림피아 제우스 상 | Statue of Zeus at Olympia | 🏰 유럽 | 불가사의 | 1 in 72,000 | 1/72,004 | 1,342 | 30 |
| 헤라클레이온 해저 도시 | Sunken City of Heracleion | 🐪 아프리카 | 불가사의 | 1 in 80,000 | 1/80,004 | 1,415 | 30 |
| 마우솔로스 영묘 | Mausoleum at Halicarnassus | 🏯 아시아 | 불가사의 | 1 in 90,000 | 1/90,003 | 1,500 | 30 |
| 네스호의 네시 | Loch Ness & Nessie | 🏰 유럽 | 잃어버린 유산 | 1 in 100,000 | 1/100,003 | 1,582 | 80 |
| 바벨탑 | Tower of Babel | 🏯 아시아 | 잃어버린 유산 | 1 in 150,000 | 1/150,003 | 1,937 | 80 |
| 트로이 목마 | Trojan Horse | 🏯 아시아 | 잃어버린 유산 | 1 in 200,000 | 1/200,003 | 2,237 | 80 |
| 알렉산드리아 도서관 | Library of Alexandria | 🐪 아프리카 | 잃어버린 유산 | 1 in 250,000 | 1/250,003 | 2,500 | 80 |
| 질랜디아 | Zealandia (Sunken Continent) | 🏝️ 오세아니아 | 잃어버린 유산 | 1 in 300,000 | 1/300,003 | 2,739 | 80 |
| 아틀란티스 | Atlantis | 🏰 유럽 | 잃어버린 유산 | 1 in 400,000 | 1/400,003 | 3,163 | 80 |
| 미노타우로스의 미궁 | Labyrinth of the Minotaur | 🏰 유럽 | 잃어버린 유산 | 1 in 500,000 | 1/500,002 | 3,536 | 80 |
| 황룡사 9층 목탑 | Hwangnyongsa Nine-Story Pagoda | 🏯 아시아 | 잃어버린 유산 | 1 in 650,000 | 1/650,002 | 4,032 | 80 |
| 엘도라도 | El Dorado | 🗽 아메리카 | 잃어버린 유산 | 1 in 800,000 | 1/800,002 | 4,473 | 80 |
| 젊음의 샘 | Fountain of Youth | 🗽 아메리카 | 전설 | 1 in 1M | 1/1,000,001 | 5,000 | 250 |
| 용궁 | Dragon King's Palace | 🏯 아시아 | 전설 | 1 in 2M | 1/2,000,001 | 7,072 | 250 |
| 무 대륙 | Lost Continent of Mu | 🏝️ 오세아니아 | 전설 | 1 in 3M | 1/3,000,001 | 8,661 | 250 |
| 사하라 신기루 성 | Mirage Citadel of the Sahara | 🐪 아프리카 | 전설 | 1 in 5M | 1/5,000,001 | 11,181 | 250 |
| 샹그릴라 | Shangri-La | 🏯 아시아 | 전설 | 1 in 10M | 1/10,000,000 | 15,812 | 250 |
| 세계수 | World Tree | 🏰 유럽 | 전설 | 1 in 40M | 1/40,000,000 | 31,623 | 250 |

**판정 방식:** 가장 희귀한 명소부터 차례로 `행운 / N` 확률로 판정해서 처음 성공한 명소를 줍니다
(모두 실패하면 홍콩 시계탑). 행운이 N 이상이 되면 그보다 흔한 명소는 나오지 않습니다.

## 모형을 AI 메쉬로 바꾸기

지금 명소 모형은 **코드로 만든 임시 모형**입니다. 더 예쁜 모형(AI 메쉬 등)으로 바꾸려면:

1. Studio 에서 `ReplicatedStorage` 아래에 **`LandmarkModels`** 폴더를 만듭니다.
2. 명소 Id 와 **같은 이름의 Model** 을 넣습니다 (예: `eiffel`, `tajmahal` — 광장·연출의 장식용 지구본은 `globe`. Id 는 위 표의 영문이 아니라
   [`src/shared/Landmarks.luau`](src/shared/Landmarks.luau) 의 첫 칸).
3. 끝. 공원 미니어처, 굴림 연출, 컬렉션, 대표 명소, 홀로그램 어디서나 자동으로 그 모형이 크기에 맞춰 쓰입니다.

## 실행 / 게시

- **바로 열기**: `LandmarkRNG.rbxlx` 를 Studio 에서 **File → Open from File** → **Play**.
  (Studio 에서는 저장 없이 플레이. 저장까지 테스트하려면 게시 후 Game Settings → Security →
  Enable Studio Access to API Services)
- **Rojo**: `rojo serve` (개발) / `rojo build -o LandmarkRNG.rbxlx` (place 파일 다시 만들기)
- **Open Cloud 업로드**: `apis.roblox.com` 으로
  `POST /universes/v1/{universeId}/places/{placeId}/versions?versionType=Saved|Published`
  (헤더 `x-api-key`, `Content-Type: application/xml`, 본문 = rbxlx 파일)
- 한 서버 최대 인원은 공원 부지 수에 맞춰 **8명**으로 설정하세요 (Game Settings → Places → Max Players, 또는 Open Cloud `PATCH /cloud/v2/universes/{u}/places/{p}?updateMask=serverSize` — 키에 universe-places 쓰기 권한 필요).

## 조정하기

- **밸런스**(쿨타임, 수입, 별 기준, 업그레이드 가격·효과, 알림 기준): [`src/shared/Config.luau`](src/shared/Config.luau)
- **명소 추가/수정**: [`src/shared/Landmarks.luau`](src/shared/Landmarks.luau) 의 `DEFINITIONS` 에 한 줄 추가.
  ⚠️ `Id` 는 저장 키라서 게시한 뒤에는 바꾸지 마세요. 새 명소를 넣으면 공원 최대 칸(`Park.MaxLevel`)도 확인하세요
  (테스트가 알려 줍니다).
- **저장 초기화**: `Config.DATASTORE_NAME` 을 바꾸면 새 저장소를 씁니다.
- **맵 가장자리 풍경**: `Config.SCENERY_EDGE` = `"Ocean"`(바다) / `"Mountains"`(산맥).
  나무 수·정원 주제·산 높이 등은 [`src/server/Scenery/Plan.luau`](src/server/Scenery/Plan.luau) 위쪽 조절 값(`T`).
  고친 뒤 올리기 전에 `tools/world_preview/preview.sh art/map_preview Ocean` 처럼 그림으로 확인하세요
  (시점별 PNG + 부지·길·간판을 막는 장식이 있는지 보고서, Roblox API 호출 없음).

## 테스트

게임 규칙(`src/shared` 의 판정·데이터 로직)은 Roblox 밖에서 테스트합니다(200만 회 확률 검증 포함).

```bash
cargo build --release --manifest-path tools/luaurun/Cargo.toml
./tools/luaurun/target/release/luaurun tests/run.luau
```

서버/클라이언트 코드는 문법 컴파일까지만 자동 확인되므로, 화면·연출은 Studio 나 실제 게임에서 확인해 주세요.

## 이미지 올리기 (Open Cloud)

`art/png/*.png`(아이콘, 버튼·창 스킨)를 Roblox 에 올리고 `src/shared/ImageIds.luau` 에 `rbxassetid://` Id 를 채우는
스크립트가 [`tools/upload_images.py`](tools/upload_images.py) 입니다. Python 3 만 있으면 되고 따로 설치할 것은 없습니다.

### 1. API 키에 권한 넣기 (한 번만)

1. Creator Hub → **Open Cloud → API Keys**
   ([바로 가기](https://create.roblox.com/dashboard/credentials?activeTab=ApiKeysTab)) 에서 지금 쓰는 키를 엽니다
   (새로 만들 때는 **Create API Key**).
2. **Access Permissions** 의 **Select API System** 에서 **Assets** 를 골라 추가합니다.
3. **Select Operations** 에서 **Read** 와 **Write** 를 둘 다 고릅니다.
   Write 는 업로드용이고, Read 는 업로드 결과와 검수 상태를 확인할 때 씁니다.
   Assets 권한은 게임별로 고르지 않고 키 주인 계정 전체에 적용됩니다.
4. 저장합니다. 새 키라면 **Save & Generate Key** 를 누르고 키 문자열을 복사해 둡니다.

- **키 주인이 곧 에셋 주인이어야 합니다.** 스크립트는 기본으로 userId `2038945024` 이름으로 올립니다.
  다른 계정이면 `--user-id 숫자` 를 붙이세요. (OAuth 앱으로 치면 필요한 scope 는 `asset:read`, `asset:write`)
- 키에 IP 제한을 걸어 두었다면 스크립트를 돌리는 컴퓨터의 IP 도 허용 목록에 넣어야 합니다.
- 키를 60일 동안 쓰지 않으면 자동으로 만료됩니다. **Enable Key** 를 껐다가 다시 켜면 풀립니다.

### 2. 실행

```bash
python3 tools/upload_images.py --dry-run            # 무엇을 올릴지만 보기 (네트워크 안 씀, 파일 안 바꿈)
ROBLOX_API_KEY=키 python3 tools/upload_images.py    # 올리고 ImageIds.luau 채우기
python3 tools/upload_images.py --only coin dice     # 일부만
```

- 키는 환경변수 `ROBLOX_API_KEY` 로만 받습니다. 파일에 적거나 커밋하지 마세요.
  Windows PowerShell 에서는 `$env:ROBLOX_API_KEY="키"` 를 먼저 입력합니다.
  원격 개발 환경처럼 프록시가 `apis.roblox.com` 요청에 키를 대신 붙여 주는 곳에서는 환경변수 없이 실행하면 됩니다.
- 끝나면 결과 표가 나옵니다. `CACHED` 는 이미 올린 그림, `UPLOADED` 는 이번에 올린 그림,
  `PENDING` 은 Roblox 쪽에서 아직 처리 중인 그림(다시 실행하면 새로 올리지 않고 이어서 확인),
  `REJECTED` 는 검수에서 거절된 그림, `FAILED` 는 실패한 그림입니다.
- `ImageIds.luau` 에서는 해당 줄의 값만 바꾸고 주석과 묶음은 그대로 둡니다. `art/png` 에만 있는 새 이름은 표 끝에 추가됩니다.
  (`--rewrite` 를 붙이면 표 안을 이름순으로 다시 씁니다.)
- 이미 올린 그림은 다시 올리지 않습니다. `tools/.image_upload_cache.json` 에 파일 내용의 SHA-256 → Id 를 적어 둡니다.
  이 파일을 지우면 모든 그림이 새 Id 로 다시 올라가니 지우지 말고, 다른 컴퓨터에서도 쓰려면 git 에 같이 넣으세요
  (키는 들어 있지 않습니다).
- 다 되면 Rojo 로 동기화하거나 `rojo build -o LandmarkRNG.rbxlx` 로 place 파일을 다시 만듭니다.

**왜 `Image` 로 올리나:** Open Cloud 에서 PNG 는 `Decal` 또는 `Image` 타입으로 올릴 수 있습니다. `Decal` 로 올리면
돌려받는 Id 가 데칼의 Id 입니다(데칼 안에 Image 에셋이 따로 들어 있음). 이 Id 를 `ImageLabel.Image` 에 넣으면 그림이 안 나옵니다.
그래서 스크립트는 `Image` 로 올리고, 받은 Id 를 그대로 씁니다. (`--asset-type Decal` 도 있지만 비추천입니다.
이때는 데칼 안의 Image Id 를 찾아 쓰는데, 이 과정은 공식 문서에 없는 경로라 실패할 수 있습니다.)

### 3. 검수(모더레이션)

- 올린 그림은 모두 Roblox 검수를 거칩니다. 결과 표의 **검수** 칸에 `승인` / `검수 중` / `거절` 로 표시됩니다.
- `검수 중` 이어도 Id 는 `ImageIds.luau` 에 넣습니다. 승인 전에는 게임에서 그림이 안 보일 수 있습니다.
  나중에 스크립트를 다시 실행하면 상태만 확인하고 다시 올리지는 않습니다.
- `거절` 된 그림은 그 줄을 `""` 로 비워 두므로 게임은 코드로 그린 기본 모양을 씁니다. 스크립트는 같은 그림을 자동으로
  다시 올리지 않습니다(거절된 파일을 반복해서 올리면 계정 제재 위험이 있음). 그림을 고치면 내용이 바뀌어 다음 실행 때 새로 올라갑니다.
  꼭 그대로 다시 올려야 하면 `--force` 를 붙입니다.
- 에셋 이름과 설명도 검사되므로 파일 이름은 평범하게 짓습니다(영문 소문자, 숫자, `_`).
- 내 계정 게임에서는 내가 올린 그림이 항상 보입니다. 게임이 **그룹 소유**이고 Asset Privacy 를 켜 두었다면,
  Creator Hub 에서 그 그림을 쓸 수 있게 해당 게임에 권한을 줘야 합니다.

### 4. 그림 바꾸기

1. `art/src/<이름>.svg` 를 고치고 `python3 art/build.py <이름>` 으로 PNG 를 다시 만듭니다.
2. `python3 tools/upload_images.py` 를 실행합니다. 내용이 바뀐 파일만 올라가고, `ImageIds.luau` 의 그 줄이 새 Id 로 바뀝니다.
   이미지 에셋은 내용을 덮어쓸 수 없어서 바꿀 때마다 **새 Id** 가 생깁니다. 예전 에셋은 계정에 그대로 남으니,
   필요 없으면 Creator Hub → Creations → Development Items 에서 보관(Archive)하세요.
- 새 그림은 `art/png/새이름.png` 로 넣으면 됩니다. 이름이 곧 `ImageIds` 의 키입니다.
- Id 를 손으로 넣으려면 `ImageIds.luau` 의 줄을 직접 고칩니다. 단 `art/png` 에 같은 이름의 PNG 가 있으면 다음 실행 때
  스크립트가 그 PNG 의 Id 로 되돌리니, 그 PNG 를 빼거나 `--only` 로 다른 그림만 돌리세요.

**제한:** 파일 하나 20MB 이하, 8000×8000 픽셀 미만, png·jpeg·bmp·tga.
업로드는 분당 120번, 결과 조회는 분당 300번까지입니다(키 주인 기준). 스크립트가 알아서 간격을 두고, 너무 빠르다는 응답(429)을
받으면 `retry-after` 만큼 기다렸다가 다시 시도합니다. 요금이 붙는 업로드라면 올리지 않고 실패하도록 `expectedPrice: 0` 을 보냅니다.

참고: [Assets API 사용 안내](https://create.roblox.com/docs/cloud/guides/usage-assets) ·
[API 키 만들기](https://create.roblox.com/docs/cloud/auth/api-keys) ·
[레이트 리밋](https://create.roblox.com/docs/cloud/reference/rate-limits) ·
[에셋 공개 범위](https://create.roblox.com/docs/projects/assets/privacy)
