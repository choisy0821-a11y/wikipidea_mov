import re
import platform
import requests
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup


# 0. 운영체제별 한글 폰트 설정 함수 (그래프 한글 깨짐 방지)
def set_korean_font():
    system_name = platform.system()
    if system_name == "Windows":
        plt.rcParams["font.family"] = "Malgun Gothic"
    elif system_name == "Darwin":
        plt.rcParams["font.family"] = "AppleGothic"
    else:
        plt.rcParams["font.family"] = "NanumGothic"

    plt.rcParams["axes.unicode_minus"] = False


# 1. 웹 페이지 HTML을 가져오는 함수
def fetch_html(url):
    headers = {
        "User-Agent": "UniversityPythonClassPractice/1.0 (Educational Purpose)"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.Timeout:
        st.error("오류: 서버 응답 시간이 초과되었습니다.")
    except requests.exceptions.ConnectionError:
        st.error("오류: 인터넷 연결에 실패했거나 서버에 접속할 수 없습니다.")
    except requests.exceptions.HTTPError as e:
        st.error(f"오류: HTTP 상태 코드 문제가 발생했습니다. ({e})")
    except requests.exceptions.RequestException as e:
        st.error(f"오류: 알 수 없는 요청 오류가 발생했습니다. ({e})")
    return None


# 2. HTML에서 원하는 표를 찾아 DataFrame으로 변환하는 함수
def parse_movie_table(html):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", {"class": "wikitable"})

    target_table = None
    for table in tables:
        first_row = table.find("tr")
        if first_row:
            header_text = first_row.get_text()
            if "관객수" in header_text and "감독" in header_text:
                target_table = table
                break

    if target_table is None:
        st.error("오류: 조건에 맞는 영화 흥행 기록 표를 찾지 못했습니다.")
        return None

    # 각주 번호(sup 태그) 제거
    for sup in target_table.find_all("sup"):
        sup.decompose()

    rows = target_table.find_all("tr")
    headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]

    data = []
    for row in rows[1:]:
        cols = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cols) == len(headers):
            data.append(cols)

    df = pd.DataFrame(data, columns=headers)
    return df


# 3. 수집한 데이터를 분석하기 좋게 정제하는 함수
def clean_movie_data(df):
    df_clean = df.copy()

    # 제목 열 이름 찾기 및 《 》 제거
    title_col = [c for c in df_clean.columns if "제목" in c][0]
    df_clean[title_col] = (
        df_clean[title_col]
        .str.replace("《", "", regex=False)
        .str.replace("》", "", regex=False)
        .str.strip()
    )

    # 관객수 열 이름 찾기 및 숫자 변환
    aud_col = [c for c in df_clean.columns if "관객수" in c][0]
    df_clean["관객수_숫자"] = df_clean[aud_col].apply(
        lambda x: int(re.sub(r"[^0-9]", "", str(x))) if re.sub(r"[^0-9]", "", str(x)) else 0
    )

    # 개봉일 열 찾기 ('개봉' 또는 '연도'가 포함된 열 검색)
    date_cols = [c for c in df_clean.columns if "개봉" in c or "연도" in c]
    if date_cols:
        date_col = date_cols[0]
        # '2014년 7월 30일' 또는 '2014-07-30' 형태 모두 대응하도록 4자리 숫자(연도) 추출
        df_clean["개봉연도"] = df_clean[date_col].astype(str).str.extract(r"((?:19|20)\d{2})")
        # 연도 뒤에 오는 월(1~12) 추출
        df_clean["개봉월"] = df_clean[date_col].astype(str).str.extract(r"(?:19|20)\d{2}[^0-9]+(\d{1,2})")
    else:
        df_clean["개봉연도"] = None
        df_clean["개봉월"] = None

    # 배급사 열 이름 찾기
    dist_cols = [c for c in df_clean.columns if "배급사" in c]
    dist_col = dist_cols[0] if dist_cols else None

    if dist_col:
        df_clean[dist_col] = df_clean[dist_col].str.strip()

    return df_clean, title_col, dist_col


# 4. 배급사별 편수를 집계해 원그래프(파이 차트)를 그리는 함수
def plot_distributor_pie(df, dist_col, top_n=4):
    if dist_col is None:
        st.warning("배급사 정보를 찾을 수 없어 원그래프를 그릴 수 없습니다.")
        return

    counts = df[dist_col].value_counts()

    # 상위 top_n개 주요 배급사만 남기고 나머지는 '기타'로 합치기
    if len(counts) > top_n:
        major_counts = counts.iloc[:top_n].copy()
        others_sum = counts.iloc[top_n:].sum()
        major_counts["기타"] = others_sum
    else:
        major_counts = counts

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(
        major_counts.values,
        labels=major_counts.index,
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
    )
    ax.set_title("한국내 주요 배급사별 천만 영화 비율")

    st.pyplot(fig)


# 5. 지표, 표, 차트를 화면에 출력하는 함수
def display_dashboard(df, title_col, dist_col):
    df_sorted = df.sort_values(by="관객수_숫자", ascending=False).reset_index(drop=True)

    # 주요 지표 계산
    total_movies = len(df_sorted)
    top_movie = df_sorted.loc[0, title_col]
    top_audience = df_sorted.loc[0, "관객수_숫자"]

    col1, col2, col3 = st.columns(3)
    col1.metric("천만 영화 수", f"{total_movies}편")
    col2.metric("역대 1위 영화", top_movie)
    col3.metric("1위 관객수", f"{top_audience:,}명")

    st.divider()

    # 정제된 데이터 표 출력 (인덱스 숨김)
    st.subheader("천만 관객 한국 영화 목록")
    st.dataframe(df_sorted, hide_index=True, use_container_width=True)

    st.divider()

    # 관객수 상위 10편 가로 막대 차트
    st.subheader("관객수 상위 10편")
    top10 = df_sorted.head(10).set_index(title_col)["관객수_숫자"]
    st.bar_chart(top10, horizontal=True)

    st.divider()

    # 개봉 연도별 편수 막대 차트
    st.subheader("개봉 연도별 편수")
    year_series = df_sorted["개봉연도"].dropna()
    if not year_series.empty:
        year_counts = year_series.value_counts().sort_index()
        st.bar_chart(year_counts)
    else:
        st.warning("개봉연도 데이터를 추출할 수 없습니다. 표의 날짜 열 형식을 확인해 주세요.")

    st.divider()

    # 한국내 배급사별 원그래프
    st.subheader("한국내 배급사별 점유율 (상위 4개사 및 기타)")
    plot_distributor_pie(df_sorted, dist_col, top_n=4)


# 6. 전체 앱 실행 흐름을 제어하는 메인 함수
def main():
    st.set_page_config(page_title="천만 관객 한국 영화 분석", layout="wide")
    set_korean_font()

    st.title("대한민국 천만 관객 영화 흥행 분석")
    st.write("위키백과 '대한민국의 영화 흥행 기록' 문서에서 데이터를 수집해 분석합니다.")

    url = "https://ko.wikipedia.org/wiki/대한민국의_영화_흥행_기록"

    if st.button("데이터 수집 및 분석 시작"):
        with st.spinner("위키백과에서 데이터를 불러오는 중입니다..."):
            html = fetch_html(url)

            if html is not None:
                raw_df = parse_movie_table(html)

                if raw_df is not None and not raw_df.empty:
                    clean_df, title_col, dist_col = clean_movie_data(raw_df)
                    display_dashboard(clean_df, title_col, dist_col)


if __name__ == "__main__":
    main()