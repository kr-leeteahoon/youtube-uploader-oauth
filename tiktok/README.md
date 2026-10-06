# 채널별 TikTok 업로더

TikTok Studio 웹을 브라우저로 자동화해서 영상을 올리는 CLI입니다.
기존 YouTube 업로더와는 독립적으로 동작합니다.

## 왜 API가 아니라 웹 자동화인가

TikTok Content Posting API는 이 용도에 맞지 않습니다.

- **예약 게시 기능이 없습니다.** 공개 시각에 맥이 깨어 있다가 직접 게시 API를 호출해야 합니다.
- **심사를 통과하기 전까지 올린 영상이 전부 비공개로만 게시됩니다.**
- 개발자 앱 등록, 스코프 승인, 도메인 검증이 전부 선행되어야 합니다.

반면 TikTok Studio 웹에는 **예약 게시가 있고(최대 10일)**, 심사도 앱 등록도 필요 없습니다.

대신 감수할 것이 있습니다. 브라우저 자동화는 TikTok 약관이 권장하는 접근 방식이
아니고, 페이지 구조가 바뀌면 깨집니다. 캡차나 로그인 챌린지가 뜨면 사람이
개입해야 합니다. 그래서 셀렉터를 한 파일에 모아두고(`selectors.py`), 깨진 곳을
짚어주는 `doctor` 명령을 같이 두었습니다.

## 설치

Python 3.11 이상이 필요합니다.

```sh
cd tiktok
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
playwright install chromium
```

맥에 Chrome이 설치되어 있으면 번들 Chromium 대신 그쪽을 씁니다. 자동화 탐지에
덜 걸립니다.

## 설정

```sh
cp channels.toml.example channels.toml
```

`channels.toml`에 채널을 적습니다. **계정 정보는 여기 적지 않습니다.**
채널명에 한글이나 공백이 들어가면 TOML 규칙상 따옴표로 감싸야 합니다.

```toml
[channels."보수시민"]
default_privacy = "public"   # public | friends | private
allow_comment = true
allow_duet = true
allow_stitch = true
```

## 계정 관리

채널마다 **별도의 브라우저 프로필**을 씁니다.

```
~/Library/Application Support/tiktok-uploader/profiles/보수시민/
~/Library/Application Support/tiktok-uploader/profiles/진보시민/
```

쿠키를 주입하는 대신 실제 브라우저 프로필을 그대로 재사용합니다. 로그인 상태가
오래 유지되고, 계정끼리 세션이 섞일 수 없습니다. 디렉터리는 `0700`으로 만듭니다.

비밀번호는 어디에도 저장하지 않습니다. 최초 1회 브라우저가 열리면 직접
로그인하면 되고(2단계 인증·캡차 포함), 그 결과가 프로필에 남습니다.

```sh
tiktok-upload login --channel 보수시민
tiktok-upload login --channel 진보시민
```

## 업로드

```sh
# 즉시 게시
tiktok-upload post \
  --channel 보수시민 \
  --video ~/Movies/clip.mp4 \
  --caption "오늘의 정리 #시사 #뉴스"

# 예약 게시 (최대 10일 뒤까지)
tiktok-upload post \
  --channel 진보시민 \
  --video ~/Movies/clip.mp4 \
  --caption-file caption.txt \
  --schedule "2026-10-10 19:00"

# 게시 버튼만 누르지 않고 전부 진행해 보기
tiktok-upload post --channel 보수시민 --video clip.mp4 --caption "테스트" --dry-run --keep-open
```

| 옵션 | 설명 |
|---|---|
| `--privacy public\|friends\|private` | 채널 기본값을 덮어씀 |
| `--no-comment` / `--no-duet` / `--no-stitch` | 상호작용 비허용 |
| `--schedule "YYYY-MM-DD HH:MM"` | 지금부터 20분~10일 사이 |
| `--headless` | 창 없이 실행. TikTok이 막는 경우가 있어 기본은 창 있는 모드 |
| `--slow-mo 300` | 동작 사이에 지연을 넣어 느린 UI에 맞춤 |
| `--dry-run` | 게시하지 않고 중단, 확인용 덤프를 남김 |

영상은 세로 1080×1920을 전제로 합니다. 가로 영상도 올라가지만 추천 노출이
제대로 되지 않습니다.

## 깨졌을 때

TikTok이 페이지를 바꾸면 셀렉터가 빗나갑니다. 어디가 깨졌는지 먼저 확인하세요.

```sh
tiktok-upload doctor --channel 보수시민 --video ~/Movies/clip.mp4
```

영상을 붙인 뒤 각 요소를 하나씩 찾아보고, 빗나간 항목과 그 시점의
스크린샷·HTML을 `~/Library/Application Support/tiktok-uploader/debug/` 에 남깁니다.
게시 버튼은 누르지 않습니다.

그 HTML에서 실제 속성을 확인하고 **`tiktok_uploader/selectors.py` 의 해당 항목에
후보를 추가**하면 됩니다. 고칠 곳은 그 파일 하나입니다.

## 안전장치

잘못 게시되는 것보다 멈추는 쪽을 택합니다.

- **공개 범위 UI를 못 찾으면 중단합니다.** 의도하지 않은 범위로 올라가는 것을 막습니다.
- **예약 시각을 입력한 뒤 화면에서 되읽어 확인합니다.** 값이 반영되지 않았으면 중단합니다.
- **예약 범위를 미리 검사합니다.** 20분 미만이거나 10일을 넘으면 브라우저를 띄우기 전에 거릅니다.
- 듀엣·이어찍기는 영상 길이나 계정 설정에 따라 UI가 아예 안 뜰 수 있어, 이 둘만 경고 후 건너뜁니다.

## 아직 검증되지 않은 부분

이 코드는 실제 TikTok 페이지에 대고 돌려본 적이 없습니다. 특히 **예약 날짜·시간
피커**는 커스텀 위젯이라 셀렉터가 빗나갈 가능성이 가장 높습니다. 처음 쓸 때는
`doctor` 와 `--dry-run` 으로 확인하고 시작하세요.
