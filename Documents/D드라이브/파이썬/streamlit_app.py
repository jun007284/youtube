import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
import datetime
import requests  # 썸네일 다운로드용
from pytrends.request import TrendReq
import matplotlib.pyplot as plt
import time  # 시간 측정용

API_KEY = "AIzaSyCTlkqFVtkZFSuOlvBbQ9XsCsWXmYlqCGA"

# --- 유튜브 검색 함수 및 상세 조회 함수 ---
def search_youtube(query, max_results=10, video_duration="any"):
    youtube = build("youtube", "v3", developerKey=API_KEY)
    all_items = []
    next_page_token = None
    fetched = 0
    max_per_page = 50

    while True:
        results_to_fetch = min(max_per_page, max_results - fetched)
        if results_to_fetch <= 0:
            break
        request = youtube.search().list(
            q=query,
            type="video",
            part="id,snippet",
            maxResults=results_to_fetch,
            order="relevance",
            videoDuration=video_duration,
            pageToken=next_page_token
        )
        response = request.execute()
        all_items.extend(response.get("items", []))
        fetched += len(response.get("items", []))
        next_page_token = response.get("nextPageToken")
        if not next_page_token or fetched >= max_results:
            break
    return all_items

def get_video_details(video_id):
    youtube = build("youtube", "v3", developerKey=API_KEY)
    video_response = youtube.videos().list(
        id=video_id, part="snippet,statistics,contentDetails"
    ).execute()
    item = video_response["items"][0]
    stats = item["statistics"]
    snippet = item["snippet"]
    content_details = item["contentDetails"]
    duration = content_details.get("duration", "PT0S")

    def iso8601_to_seconds(duration):
        import re
        pattern = re.compile(
            'PT'
            '(?:(\d+)H)?'
            '(?:(\d+)M)?'
            '(?:(\d+)S)?'
        )
        matches = pattern.match(duration)
        if not matches:
            return 0
        hours = int(matches.group(1)) if matches.group(1) else 0
        minutes = int(matches.group(2)) if matches.group(2) else 0
        seconds = int(matches.group(3)) if matches.group(3) else 0
        return hours * 3600 + minutes * 60 + seconds

    duration_seconds = iso8601_to_seconds(duration)

    return {
        "title": snippet["title"],
        "description": snippet.get("description", ""),
        "channel": snippet["channelTitle"],
        "publishedAt": snippet["publishedAt"][:10],
        "thumbnail": snippet["thumbnails"]["medium"]["url"],
        "viewCount": int(stats.get("viewCount", 0)),
        "videoId": video_id,
        "channelId": snippet["channelId"],
        "duration": duration_seconds
    }

def get_channel_subscribers(channel_id):
    youtube = build("youtube", "v3", developerKey=API_KEY)
    channel_response = youtube.channels().list(
        id=channel_id, part="statistics"
    ).execute()
    try:
        return int(channel_response["items"][0]["statistics"]["subscriberCount"])
    except:
        return 0

# pytrends 초기화
pytrends = TrendReq(hl='en-US', tz=360)

st.title("🔍 YouTube 키워드 필터 검색기")

with st.sidebar:
    st.header("검색 필터")
    query = st.text_input("검색어", "뉴질랜드")
    min_views = st.number_input("최소 조회수", value=1000, step=100)
    max_views = st.number_input("최대 조회수", value=2000000, step=100)
    min_subs = st.number_input("최소 구독자수", value=0, step=10)
    max_subs = st.number_input("최대 구독자수", value=20000000, step=100)
    result_limit = st.selectbox("검색 결과 개수", [10, 25, 50, 100, 200, 300, 400, 500], index=3)

    sort_col = st.selectbox("정렬 기준", ("조회수", "구독자수"))

    # 실시간 유튜브 검색 트렌드 UI
    st.markdown("---")
    st.subheader("실시간 유튜브 검색 트렌드 조회 (Google Trends 기반)")
    trend_kw = st.text_input("트렌드 키워드 입력", "뉴질랜드", key="trend_kw")
    country_code = st.selectbox(
        "국가 선택 (ISO 코드)",
        ("US", "KR", "JP", "CN", "GB", "FR", "DE", "IN", "BR", "RU"),
        index=1,
        key="trend_country"
    )
    trend_button = st.button("트렌드 조회 시작", key="trend_button")

# 키워드 포함 / 채널 포함/제외 입력 UI (정렬 UI 바로 아래에 배치)
keyword_filter = st.text_input("키워드 포함 필터 (제목 및 설명)", "")
channel_include = st.text_input("포함할 채널명 (쉼표로 구분)", "")
channel_exclude = st.text_input("제외할 채널명 (쉼표로 구분)", "")

sort_order = st.radio("정렬 순서", ("내림차순", "오름차순"), horizontal=True)

# 업로드 날짜 필터 UI
start_date = st.date_input("업로드 시작일", datetime.date(2005, 1, 1))
end_date = st.date_input("업로드 종료일", datetime.date.today())

# 동영상 길이 필터 UI
duration_option = st.selectbox(
    "동영상 길이 구분",
    ("전체", "쇼츠 60초 이내", "쇼츠 4분 이내", "미드폼 30분 이내", "롱폼 30분 이상"),
    index=0
)

video_duration_map = {
    "전체": "any",
    "쇼츠 60초 이내": "short",
    "쇼츠 4분 이내": "short",
    "미드폼 30분 이내": "any",
    "롱폼 30분 이상": "long"
}
video_duration_param = video_duration_map.get(duration_option, "any")

# --- 유튜브 검색 실행 ---
if st.button("🔍 검색 시작"):
    st.info("검색을 시작합니다...")
    start_time = time.time()
    results = []
    status_placeholder = st.empty()

    search_items = search_youtube(query, max_results=result_limit, video_duration=video_duration_param)

    for idx, item in enumerate(search_items):
        elapsed = time.time() - start_time
        total_items = len(search_items)
        completed = idx + 1
        avg_time = elapsed / completed if completed > 0 else 0
        remaining = avg_time * (total_items - completed)
        status_placeholder.info(f"진행 중: {completed}/{total_items} ({remaining:.1f}초 남음)")

        video_id = item["id"]["videoId"]
        video_detail = get_video_details(video_id)

        video_date = datetime.datetime.strptime(video_detail["publishedAt"], "%Y-%m-%d").date()
        if video_date < start_date or video_date > end_date:
            continue

        dur = video_detail["duration"]
        if duration_option == "쇼츠 60초 이내" and dur > 60:
            continue
        elif duration_option == "미드폼 30분 이내" and dur > 1800:
            continue
        elif duration_option == "롱폼 30분 이상" and dur < 1800:
            continue

        keyword = keyword_filter.lower().strip()
        title_lower = video_detail["title"].lower()
        description_lower = video_detail.get("description", "").lower()
        if keyword and (keyword not in title_lower and keyword not in description_lower):
            continue

        if channel_include:
            includes = [x.strip().lower() for x in channel_include.split(",")]
            if not any(ch in video_detail["channel"].lower() for ch in includes):
                continue

        if channel_exclude:
            excludes = [x.strip().lower() for x in channel_exclude.split(",")]
            if any(ch in video_detail["channel"].lower() for ch in excludes):
                continue

        thumb_url = video_detail["thumbnail"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        channel_id = video_detail["channelId"]
        sub_count = get_channel_subscribers(channel_id)

        if not (min_views <= video_detail["viewCount"] <= max_views):
            continue
        if not (min_subs <= sub_count <= max_subs):
            continue

        results.append({
            "썸네일": thumb_url,
            "제목": video_detail["title"],
            "영상링크": video_url,
            "조회수": video_detail["viewCount"],
            "구독자수": sub_count,
            "채널명": video_detail["channel"],
            "업로드일": video_detail["publishedAt"]
        })

    status_placeholder.success("검색이 완료되었습니다.")

    if not results:
        st.error("조건에 맞는 영상이 없습니다!")
    else:
        df = pd.DataFrame(results)
        df = df.sort_values(by=sort_col, ascending=(sort_order == "오름차순")).reset_index(drop=True)

        html = '''
<style>
.yt-table th, .yt-table td {
    border:1px solid #222;
    padding:8px;
    text-align:center;
    vertical-align:middle;
    font-size: 0.9rem;
}
.yt-table {border-collapse:collapse; width:100%;}
.yt-table img { 
    width:120px !important;
    height:80px !important;
    object-fit:cover;
    border-radius:8px;
}
</style>
<table class="yt-table">
  <tr>
    <th>썸네일</th>
    <th>제목<br>(클릭시 유튜브)</th>
    <th>조회수</th>
    <th>구독자수</th>
    <th>채널명</th>
    <th>업로드일</th>
  </tr>
'''
        for idx, row in df.iterrows():
            # 조회수에 다운로드 버튼 링크 연결 (썸네일 이미지 다운로드 기능)
            download_btn = f"""
                <a href="{row['썸네일']}" download="{row['제목'][:20].replace(' ', '_')}.jpg" title="썸네일 다운로드" style="color:#1E90FF; cursor:pointer; text-decoration:underline;">
                    {row['조회수']:,}
                </a>
            """
            html += f'''
  <tr>
    <td><img src="{row['썸네일']}" alt="thumb" /></td>
    <td style="text-align:left"><a href="{row['영상링크']}" target="_blank">{row['제목']}</a></td>
    <td>{download_btn}</td>
    <td>{row['구독자수']:,}</td>
    <td>{row['채널명']}</td>
    <td>{row['업로드일']}</td>
  </tr>
'''
        html += "</table>"
        st.markdown(html, unsafe_allow_html=True)

# --- 실시간 유튜브 검색 트렌드 조회 ---
if trend_button:
    st.info(f"{trend_kw} 키워드에 대한 {country_code} 유튜브 검색 트렌드를 조회중...")
    try:
        pytrends.build_payload([trend_kw], cat=0, timeframe='now 1-H', geo=country_code, gprop='youtube')
        trend_data = pytrends.interest_over_time()
        if trend_data.empty:
            st.warning("트렌드 데이터가 없습니다.")
        else:
            st.line_chart(trend_data[trend_kw])
            st.success("트렌드 조회 완료!")
    except Exception as e:
        st.error(f"트렌드 조회 중 오류 발생: {e}")
