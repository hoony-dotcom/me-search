import streamlit as st
import pandas as pd
import glob
import os
import re
from datetime import datetime
import streamlit.components.v1 as components

# 페이지 설정
st.set_page_config(page_title="의료장비 통합 조회 시스템", layout="wide")

st.title("🏥 의료장비 관리번호 통합 조회 시스템")
st.markdown("관리번호를 직접 입력하거나 모바일 카메라로 바코드/QR을 스캔하여 상세 내역과 예방점검 라벨 현황을 확인하세요.")

# 최신 파일 자동 탐색 함수 (정확한 접두사 및 확장자 매칭)
def find_latest_file(prefix, extensions=(".xlsx", ".xlsb", ".xls")):
    files = []
    for ext in extensions:
        files.extend(glob.glob(f"{prefix}*{ext}"))
        
    if not files:
        return None
    
    def extract_date(filename):
        remainder = filename[len(prefix):]
        match = re.search(r'(\d+)', remainder)
        if match:
            return match.group(1)
        return ""
    
    files.sort(key=extract_date, reverse=True)
    return files[0]

# 1. 최신 데이터 파일 로드 (캐싱 활용)
@st.cache_data
def load_latest_data():
    status_file = find_latest_file("의료기기 현황조회")
    repair_file = find_latest_file("수리접수 내역")
    
    if not status_file or not repair_file:
        raise FileNotFoundError(f"필요한 데이터 파일을 찾을 수 없습니다. (검색된 현황파일: {status_file}, 수리파일: {repair_file})")
        
    df_status = pd.read_excel(status_file)
    
    # 수리접수 내역 파일이 .xlsb 바이너리 형식인 경우 pyxlsb 엔진 지정
    if repair_file.endswith('.xlsb'):
        df_repair = pd.read_excel(repair_file, engine='pyxlsb')
    else:
        df_repair = pd.read_excel(repair_file)
        
    return df_status, df_repair, status_file, repair_file

try:
    df_status, df_repair, latest_status_path, latest_repair_path = load_latest_data()
except Exception as e:
    st.error(f"데이터 파일을 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

# ==========================================
# 세션 상태 초기화
# ==========================================
if "search_query" not in st.session_state:
    st.session_state["search_query"] = ""

if "dept_selection" not in st.session_state:
    st.session_state["dept_selection"] = "전체보기"

if "show_repair" not in st.session_state:
    st.session_state["show_repair"] = False

if "last_queried_no" not in st.session_state:
    st.session_state["last_queried_no"] = ""

if "auto_popup_shown" not in st.session_state:
    st.session_state["auto_popup_shown"] = False

# ==========================================
# 📂 좌측 사이드바 구성
# ==========================================
st.sidebar.title("🛠️ 제어판 및 설정")

# 초기화 버튼 영역 (상단 배치)
if st.sidebar.button("🔄 검색 및 부서 초기화", use_container_width=True):
    st.session_state["search_query"] = ""
    st.session_state["dept_selection"] = "전체보기"
    st.session_state["show_repair"] = False
    st.session_state["last_queried_no"] = ""
    st.session_state["auto_popup_shown"] = False
    st.rerun()

st.sidebar.markdown("---")

# 1. 참조 파일 확인 영역
st.sidebar.markdown("### 📁 현재 참조 중인 파일")
st.sidebar.info(
    f"**[의료기기 현황]**\n`{latest_status_path}`\n\n"
    f"**[수리접수 내역 (.xlsb)]**\n`{latest_repair_path}`"
)

st.sidebar.markdown("---")

# 2. 장비 검색 영역 (관리번호 입력)
st.sidebar.markdown("### 🔍 관리번호 개별 장비 검색")
mgm_no_input = st.sidebar.text_input("관리번호 입력", value=st.session_state["search_query"], placeholder="예: 50A1100001 또는 50M1100162")

if mgm_no_input != st.session_state["search_query"]:
    new_q = mgm_no_input.strip().upper()
    st.session_state["search_query"] = new_q
    st.session_state["show_repair"] = False
    
    if new_q != st.session_state["last_queried_no"]:
        st.session_state["last_queried_no"] = new_q
        st.session_state["auto_popup_shown"] = False

query = st.session_state["search_query"]

st.sidebar.markdown("---")

# 3. 모바일 카메라 바코드/QR 스캐너 영역
st.sidebar.markdown("### 📷 모바일 카메라 스캐너")
use_camera = st.sidebar.checkbox("모바일 카메라 스캐너 사용", value=False)

if use_camera:
    st.sidebar.markdown("👇 **카메라를 바코드/QR에 비추세요**")
    scanner_html = """
    <div style="width: 100%; max-width: 400px; margin: auto;">
        <div id="reader" style="width: 100%;"></div>
    </div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        function onScanSuccess(decodedText, decodedResult) {
            const inputField = parent.document.querySelector('input[aria-label="관리번호 입력"]');
            if (inputField) {
                inputField.value = decodedText.trim().toUpperCase();
                inputField.dispatchEvent(new Event('input', { bubbles: true }));
                inputField.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        let html5QrcodeScanner = new Html5QrcodeScanner(
            "reader", { fps: 10, qrbox: { width: 250, height: 150 } }, false);
        html5QrcodeScanner.render(onScanSuccess, (error) => {});
    </script>
    """
    components.html(scanner_html, height=350)

st.sidebar.markdown("---")

# 4. 사용부서별 장비 리스트 조회 영역
st.sidebar.markdown("### 🏢 부서별 장비 리스트 조회")
dept_col = '사용\n부서' if '사용\n부서' in df_status.columns else '사용부서'

if dept_col in df_status.columns:
    raw_depts = df_status[dept_col].dropna().astype(str).str.strip()
    unique_depts = sorted(list(set(raw_depts)), key=lambda x: x.lower())
    dept_list = ['전체보기'] + unique_depts
    
    current_dept = st.session_state["dept_selection"]
    if current_dept not in dept_list:
        current_dept = '전체보기'
    dept_idx = dept_list.index(current_dept)
    
    selected_dept = st.sidebar.selectbox("사용부서 선택", dept_list, index=dept_idx, key="dept_selectbox_active")
    
    if selected_dept != st.session_state["dept_selection"]:
        st.session_state["dept_selection"] = selected_dept
        st.rerun()
else:
    selected_dept = '전체보기'
    st.sidebar.warning("사용부서 컬럼을 찾을 수 없습니다.")

# ==========================================
# 공통 버튼 스타일 적용
# ==========================================
st.markdown("""
<style>
div.stButton > button:first-child {
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    padding: 0.6rem 1.2rem !important;
    white-space: nowrap !important;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 메인 화면 콘텐츠 영역
# ==========================================

if query:
    matched_status = df_status[df_status['관리번호'].astype(str).str.strip().str.upper() == query.upper()]
    
    if matched_status.empty:
        st.warning(f"입력하신 관리번호 (**{query}**)에 해당하는 장비를 최신 [의료기기 현황조회] 파일에서 찾을 수 없습니다.")
    else:
        st.success(f"장비 조회 성공! 관리번호: **{query}**")
        
        # 예방점검 라벨 현황 데이터 연산
        status_record = matched_status.iloc[0]
        equipment_name = status_record.get('장비명/구성품명', '-')
        raw_dept_val = status_record.get(dept_col, '-')
        dept_name = str(raw_dept_val).replace('\n', ' ')
        inspection_cycle = str(status_record.get('사용부서\n점검주기', status_record.get('사용부서점검주기', '-'))).replace('\n', ' ')
        
        count_col = [c for c in status_record.index if '정도관리' in str(c) or '회/년' in str(c) or '점검횟수' in str(c)]
        inspection_count_val = status_record.get(count_col[0], 1) if count_col else 1
        
        risk_col = [c for c in status_record.index if '위험' in str(c) or '등급' in str(c)]
        risk_grade = status_record.get(risk_col[0], '-') if risk_col else '-'
        if pd.isna(risk_grade) or str(risk_grade).strip() == '':
            risk_grade = "정보 없음"
        
        prevent_col = [c for c in df_repair.columns if '예방' in c and '점검' in c]
        if prevent_col:
            p_col = prevent_col[0]
            repair_matched = df_repair[
                (df_repair['관리번호'].astype(str).str.strip().str.upper() == query.upper()) &
                (df_repair[p_col].astype(str).str.strip().str.upper() == 'Y')
            ].copy()
        else:
            repair_matched = pd.DataFrame()
            
        last_inspection_date = "-"
        next_inspection_date = "-"
        repairer_name = status_record.get('의공담당', status_record.get('담당자', '-'))
        
        if not repair_matched.empty and '완료일자' in repair_matched.columns:
            repair_matched['완료일자_dt'] = pd.to_datetime(repair_matched['완료일자'], errors='coerce')
            valid_df = repair_matched.dropna(subset=['완료일자_dt'])
            if not valid_df.empty:
                latest_row = valid_df.loc[valid_df['완료일자_dt'].idxmax()]
                latest_dt = latest_row['완료일자_dt']
                last_inspection_date = latest_dt.strftime('%Y-%m-%d')
                
                if '담당자' in latest_row and pd.notna(latest_row['담당자']):
                    repairer_name = latest_row['담당자']
                    
                match_cnt = re.search(r'(\d+)', str(inspection_count_val))
                cnt = int(match_cnt.group(1)) if match_cnt else 1
                    
                if cnt > 0:
                    add_months = max(1, int(round(12 / cnt)))
                    next_dt = latest_dt + pd.DateOffset(months=add_months)
                    next_inspection_date = next_dt.strftime('%Y-%m-%d')
                else:
                    next_dt = latest_dt + pd.DateOffset(months=12)
                    next_inspection_date = next_dt.strftime('%Y-%m-%d')

        if pd.isna(repairer_name) or str(repairer_name).strip() == '':
            repairer_name = "-"

        date_color = "#111"
        alert_html = ""
        
        # 사용부서가 '88' 또는 '77'인 경우 예외 처리
        is_disposed_dept = str(raw_dept_val).strip() in ['88', '77']
        is_dept_88 = str(raw_dept_val).strip() == '88'

        if is_disposed_dept:
            next_inspection_display = '<span style="color: #d9534f; font-weight: bold; animation: blink 1s infinite;">폐기장비로 해당없음</span>'
        else:
            if next_inspection_date != "-":
                try:
                    today = datetime.now().date()
                    next_dt_obj = datetime.strptime(next_inspection_date, "%Y-%m-%d").date()
                    diff_days = (next_dt_obj - today).days
                    
                    if diff_days < 0:
                        date_color = "#d9534f"
                        alert_html = '<span style="color: #d9534f; font-weight: bold; animation: blink 1s infinite; margin-left: 10px;">(예방점검 INHIS 의뢰해주세요)</span>'
                    elif 0 <= diff_days <= 14:
                        date_color = "#0275d8"
                        alert_html = '<span style="color: #0275d8; font-weight: bold; animation: blink 1s infinite; margin-left: 10px;">(예방점검 INHIS 의뢰해주세요)</span>'
                except Exception:
                    pass
            next_inspection_display = f'<span style="color: {date_color}; font-weight: bold;">{next_inspection_date}</span> {alert_html}'

        @st.dialog("🏷️ 예방점검 라벨 현황", width="small")
        def show_prevent_dialog():
            st.markdown(
                f"""
                <style>
                @keyframes blink {{
                    0% {{ opacity: 1; }}
                    50% {{ opacity: 0.2; }}
                    100% {{ opacity: 1; }}
                }}
                </style>
                <div style="border: 2px solid #333; padding: 15px; border-radius: 8px; background-color: #fafafa; font-family: sans-serif; color: #111;">
                    <div style="display: flex; justify-content: space-between; font-weight: bold; font-size: 1.1em; margin-bottom: 5px;">
                        <span>{dept_name}</span>
                        <span>{query.upper()}</span>
                    </div>
                    <div style="font-size: 1.05em; font-weight: bold; margin-bottom: 12px; color: #333;">
                        {equipment_name}
                    </div>
                    <hr style="border: 0.5px solid #ccc; margin: 8px 0;">
                    <div style="font-size: 1em; margin: 6px 0;">
                        <b>점 검 일 자 :</b> {last_inspection_date}
                    </div>
                    <div style="font-size: 1em; margin: 6px 0;">
                        <b>차 기 점 검 :</b> {next_inspection_display}
                    </div>
                    <div style="font-size: 0.95em; margin-top: 10px; color: #555;">
                        <b>점검주기/등급 :</b> 년 {inspection_count_val}회 / {risk_grade}
                    </div>
                    <div style="text-align: center; font-weight: bold; font-size: 1.08em; margin-top: 15px; color: #222;">
                        인하대병원 의용공학팀 &nbsp;|&nbsp; 정비자: {repairer_name}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            if last_inspection_date == "-":
                st.info("해당 장비의 수리내역 중 예방점검('Y') 이력이 존재하지 않습니다.")

        if not st.session_state["auto_popup_shown"]:
            st.session_state["auto_popup_shown"] = True
            show_prevent_dialog()

        col_btn1, col_btn2 = st.columns([3, 7])
        with col_btn1:
            if st.button("🔍 예방점검 라벨 팝업 열기", use_container_width=True):
                show_prevent_dialog()

        st.markdown("---")

        # 메인 화면: 의료장비 상세내역 기본 노출 (st.markdown을 사용하여 HTML 렌더링 허용)
        if is_dept_88:
            st.markdown("### 📋 의료장비 상세내역 <span style='color: red;'>-폐기완료장비-</span>", unsafe_allow_html=True)
        else:
            st.markdown("### 📋 의료장비 상세내역")

        item_list = list(status_record.items())
        preview_items = item_list[:10]
        cols = st.columns(2)
        half_len = (len(preview_items) + 1) // 2
        
        # 상세내역 폰트 색상 제어 (부서가 88인 경우 빨간색)
        font_color_style = "color: red;" if is_dept_88 else ""

        with cols[0]:
            for k, v in preview_items[:half_len]:
                clean_key = str(k).replace('\n', ' ')
                val_str = "-" if pd.isna(v) else str(v).upper() if clean_key == "관리번호" else str(v)
                if font_color_style:
                    st.markdown(f"<span style='{font_color_style}'>• [{clean_key}]: {val_str}</span>", unsafe_allow_html=True)
                else:
                    st.text(f"• [{clean_key}]: {val_str}")
                
        with cols[1]:
            for k, v in preview_items[half_len:]:
                clean_key = str(k).replace('\n', ' ')
                val_str = "-" if pd.isna(v) else str(v).upper() if clean_key == "관리번호" else str(v)
                if font_color_style:
                    st.markdown(f"<span style='{font_color_style}'>• [{clean_key}]: {val_str}</span>", unsafe_allow_html=True)
                else:
                    st.text(f"• [{clean_key}]: {val_str}")
        
        @st.dialog("📋 의료장비 상세내역 전체 보기", width="large")
        def show_all_details_dialog(rec_items):
            if is_dept_88:
                st.markdown(f"관리번호 **{query.upper()}** 장비의 전체 상세 항목입니다. <span style='color: red; font-weight: bold;'>-폐기완료장비-</span>", unsafe_allow_html=True)
            else:
                st.write(f"관리번호 **{query.upper()}** 장비의 전체 상세 항목입니다.")
                
            d_cols = st.columns(2)
            d_half = (len(rec_items) + 1) // 2
            with d_cols[0]:
                for k, v in rec_items[:d_half]:
                    clean_key = str(k).replace('\n', ' ')
                    val_str = "-" if pd.isna(v) else str(v).upper() if clean_key == "관리번호" else str(v)
                    if font_color_style:
                        st.markdown(f"<span style='{font_color_style}'>• [{clean_key}]: {val_str}</span>", unsafe_allow_html=True)
                    else:
                        st.text(f"• [{clean_key}]: {val_str}")
            with d_cols[1]:
                for k, v in rec_items[d_half:]:
                    clean_key = str(k).replace('\n', ' ')
                    val_str = "-" if pd.isna(v) else str(v).upper() if clean_key == "관리번호" else str(v)
                    if font_color_style:
                        st.markdown(f"<span style='{font_color_style}'>• [{clean_key}]: {val_str}</span>", unsafe_allow_html=True)
                    else:
                        st.text(f"• [{clean_key}]: {val_str}")
            
            st.markdown("---")
            if st.button("닫기", use_container_width=True):
                st.rerun()

        col_expand, _ = st.columns([3, 7])
        with col_expand:
            if st.button("🔍 전체 내용 확장해서 보기 (새 창)", use_container_width=True):
                show_all_details_dialog(item_list)
        
        st.markdown("---")

        # 수리내역 확인용 별도 버튼
        if st.button("🔧 수리접수 이력 확인하기", use_container_width=True):
            st.session_state["show_repair"] = not st.session_state["show_repair"]

        if st.session_state["show_repair"]:
            st.subheader("🔧 수리접수 이력 조회 결과 (최신순 정렬)")
            
            matched_repair = df_repair[df_repair['관리번호'].astype(str).str.strip().str.upper() == query.upper()].copy()
            
            if matched_repair.empty:
                st.info("해당 장비의 수리접수 이력이 존재하지 않습니다.")
            else:
                st.write(f"총 **{len(matched_repair)}건**의 수리 이력이 확인되었습니다.")
                
                if '관리번호' in matched_repair.columns:
                    matched_repair['관리번호'] = matched_repair['관리번호'].astype(str).str.upper()
                
                if '접수일자' in matched_repair.columns:
                    matched_repair['접수일자_dt'] = pd.to_datetime(matched_repair['접수일자'], errors='coerce')
                    matched_repair = matched_repair.sort_values(by='접수일자_dt', ascending=False)
                    matched_repair = matched_repair.drop(columns=['접수일자_dt'])
                
                st.dataframe(matched_repair, use_container_width=True)

# 관리번호 검색어가 없고 부서별 조회를 선택한 경우
elif selected_dept != '전체보기':
    st.header(f"🏢 사용부서: [{selected_dept}] 장비 현황 리스트")
    dept_filtered_df = df_status[df_status[dept_col].astype(str).str.strip().str.lower() == selected_dept.lower()].copy()
    
    if '관리번호' in dept_filtered_df.columns:
        dept_filtered_df['관리번호'] = dept_filtered_df['관리번호'].astype(str).str.upper()
        
    st.write(f"총 **{len(dept_filtered_df)}대**의 장비가 등록되어 있습니다.")
    
    summary_display_cols = [c for c in ['관리번호', '장비명/구성품명', '설치장소', '모델', '제조업체', '일련번호', '자산\n상태', '취득일자'] if c in dept_filtered_df.columns]
    if summary_display_cols:
        st.dataframe(dept_filtered_df[summary_display_cols], use_container_width=True)

    with st.expander("해당 부서 장비 전체 컬럼 원본 데이터 보기"):
        st.dataframe(dept_filtered_df, use_container_width=True)

else:
    st.info("👈 좌측 사이드바의 모바일 카메라 스캐너를 켜거나 관리번호를 직접 입력해주세요.")