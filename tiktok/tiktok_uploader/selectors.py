"""TikTok Studio 셀렉터 모음.

**페이지가 바뀌면 고칠 곳은 여기 한 곳뿐이다.**

각 항목은 후보 리스트다. 위에서부터 순서대로 시도해서 처음 보이는 것을 쓴다.
`data-e2e` 속성이 가장 오래 버티므로 맨 위에 두고, 구조 셀렉터, 텍스트 셀렉터
순으로 내려간다. 텍스트는 계정 언어 설정에 따라 한국어/영어가 섞이므로
둘 다 적어 둔다.

깨졌을 때는 `tiktok-upload doctor --channel <채널>` 을 돌리면 어떤 항목이
빗나갔는지와 그 시점의 HTML 덤프를 받을 수 있다.
"""

from __future__ import annotations

# 업로드 페이지. from=upload 를 붙여야 바로 업로드 화면으로 들어간다.
UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?from=upload"
LOGIN_URL = "https://www.tiktok.com/login"
CONTENT_URL = "https://www.tiktok.com/tiktokstudio/content"

# 업로드 UI가 iframe 안에 들어있던 시기가 있었다. 이 중 하나가 잡히면
# 이후 모든 셀렉터를 그 프레임 안에서 찾는다.
UPLOAD_IFRAME = [
    'iframe[src*="creator-center/upload"]',
    'iframe[src*="tiktokstudio/upload"]',
    "iframe.tiktok-upload-iframe",
]

# 로그인 여부 판정. 로그인 상태에서만 보이는 것들.
LOGGED_IN_MARKER = [
    '[data-e2e="profile-icon"]',
    '[data-e2e="nav-profile"]',
    'div[class*="StudioLayout"]',
    'aside[class*="Sidebar"]',
]

# 로그인 화면으로 튕겼을 때 보이는 것들.
LOGGED_OUT_MARKER = [
    '[data-e2e="channel-item"]',
    'div[class*="login-modal"]',
    'a[href*="/login"][data-e2e]',
]

# 영상 파일을 넣을 input. 보통 화면에 숨겨져 있어 set_input_files 로 직접 넣는다.
FILE_INPUT = [
    'input[type="file"][accept*="video"]',
    'input[type="file"]',
]

# 캡션 편집기. DraftJS 기반 contenteditable 이라 일반 input 이 아니다.
CAPTION_EDITOR = [
    'div[contenteditable="true"][role="combobox"]',
    "div.public-DraftEditor-content",
    '[data-e2e="caption_container"] div[contenteditable="true"]',
    'div[contenteditable="true"]',
]

# 업로드가 끝났는지. 아래 중 하나라도 보이면 전송이 완료된 것으로 본다.
UPLOAD_COMPLETE_MARKER = [
    '[data-e2e="video_cover"]',
    'div[class*="VideoPreview"] video',
    'text=/업로드됨|Uploaded|업로드 완료/i',
]

# 업로드 진행 중 표시. 이게 사라질 때까지 기다린다.
UPLOAD_PROGRESS_MARKER = [
    'div[class*="UploadProgress"]',
    'text=/업로드 중|Uploading/i',
]

# 공개 범위 드롭다운.
PRIVACY_DROPDOWN = [
    '[data-e2e="privacy_dropdown"]',
    '[data-e2e="visibility_selector"]',
    'div[class*="PrivacySelect"]',
]

# 드롭다운을 연 뒤 고를 항목. 값별로 텍스트 후보를 둔다.
PRIVACY_OPTION = {
    "public": ["전체 공개", "공개", "Everyone", "Public"],
    "friends": ["친구", "팔로워", "Friends", "Followers"],
    "private": ["나만 보기", "비공개", "Only you", "Private"],
}

# 댓글·듀엣·이어찍기 허용 체크박스.
INTERACTION_TOGGLES = {
    "comment": [
        '[data-e2e="allow_comment"]',
        'input[type="checkbox"][name="comment"]',
    ],
    "duet": [
        '[data-e2e="allow_duet"]',
        'input[type="checkbox"][name="duet"]',
    ],
    "stitch": [
        '[data-e2e="allow_stitch"]',
        'input[type="checkbox"][name="stitch"]',
    ],
}

# 예약 게시 스위치. 켜면 날짜/시간 입력이 나타난다.
SCHEDULE_SWITCH = [
    '[data-e2e="schedule_switch"]',
    '[data-e2e="schedule_toggle"]',
    'div[class*="ScheduleSwitch"] input[type="checkbox"]',
    'div[class*="Switch"]:near(:text("예약"))',
    'div[class*="Switch"]:near(:text("Schedule"))',
]

SCHEDULE_DATE_INPUT = [
    '[data-e2e="schedule_date"] input',
    '[data-e2e="schedule_date"]',
    'input[placeholder*="YYYY"]',
    'div[class*="DatePicker"] input',
]

SCHEDULE_TIME_INPUT = [
    '[data-e2e="schedule_time"] input',
    '[data-e2e="schedule_time"]',
    'input[placeholder*="HH"]',
    'div[class*="TimePicker"] input',
]

# 날짜 피커가 읽기 전용일 때 날짜 칸을 직접 클릭해야 한다.
# {day} 는 1~31 의 일(日) 숫자로 치환된다.
SCHEDULE_DAY_CELL = [
    'div[class*="calendar"] span:text-is("{day}")',
    'div[class*="Calendar"] div:text-is("{day}")',
    'td[title*="{day}"]',
]

# 시간 피커가 읽기 전용일 때. {value} 는 두 자리 숫자.
SCHEDULE_HOUR_CELL = [
    'div[class*="hour"] span:text-is("{value}")',
    'div[class*="TimePicker"] div[class*="hour"] >> text="{value}"',
]
SCHEDULE_MINUTE_CELL = [
    'div[class*="minute"] span:text-is("{value}")',
    'div[class*="TimePicker"] div[class*="minute"] >> text="{value}"',
]

# 최종 게시 버튼.
POST_BUTTON = [
    '[data-e2e="post_video_button"]',
    'button[data-e2e="post_button"]',
    'button:has-text("게시")',
    'button:has-text("예약")',
    'button:has-text("Post")',
    'button:has-text("Schedule")',
]

# 게시 성공 신호.
POST_SUCCESS_MARKER = [
    'text=/게시되었|예약되었|업로드되었/i',
    'text=/Your video is being uploaded|Posted|Scheduled/i',
    '[data-e2e="upload_success"]',
]

# 게시 직후 뜨는 "콘텐츠 관리로 이동" 류의 확인 모달 버튼.
POST_CONFIRM_BUTTON = [
    'button:has-text("콘텐츠 관리")',
    'button:has-text("Manage posts")',
    'button:has-text("확인")',
    'button:has-text("OK")',
]
