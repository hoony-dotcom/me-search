import streamlit as st
import pandas as pd
import glob
import os
import re
import streamlit.components.v1 as components

# 페이지 설정
st.set_page_config(page_title="의료장비 통합 조회 시스템", layout="wide")

st.title("🏥 의료장비 관리번호 통합 조회 시스템")
st.markdown("관리번호를 직접 입력하거나 스마트폰 카메라(바코드/QR)로 스캔하여 최신 장비 상세 내역 및 수리 이력을 조회하세요.")

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
    # 현황조회 파일 및 수리접수 내역 파일 자동 탐색
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

# ==========================================
# 📂 좌측 사이드바 구성 (참조 파일, 부서별 조회, 장비 검색)
# ==========================================
st.sidebar.title("🛠️ 제어판 및 설정")

# 초기화 버튼 영역 (상단 배치)
if st.sidebar.button("🔄 검색 및 부서 초기화", use_container_width=True):
    st.session_state["search_query"] = ""
    st.session_state["dept_selection"] = "전체보기"
    st.rerun()

st.sidebar.markdown("---")

# 1. 참조 파일 확인 영역
st.sidebar.markdown("### 📁 현재 참조 중인 파일")
st.sidebar.info(
    f"**[의료기기 현황]**\n`{latest_status_path}`\n\n"
    f"**[수리접수 내역 (.xlsb)]**\n`{latest_repair_path}`"
)

st.sidebar.markdown("---")

# 2. 장비 검색 영역 (관리번호 입력 / 카메라 스캔 연동)
st.sidebar.markdown("### 🔍 관리번호 개별 장비 검색")

# 모바일 카메라 바코드 스캐너 토글 및 컴포넌트 추가
use_camera = st.sidebar.checkbox("📷 모바일 카메라 스캐너 사용", value=False)

if use_camera:
    st.sidebar.markdown("👇 **카메라를 바코드/QR에 비추세요**")
    scanner_html = """
    <div style="width: 100%; max-width: 400px; margin: auto;">
        <div id="reader" style="width: 100%;"></div>
    </div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        function onScanSuccess(decodedText, decodedResult) {
            const inputField = parent.document.querySelector('input[aria-label="관리번호 입력 (직접 입력 또는 스캔)"]');
            if (inputField) {
                inputField.value = decodedText;
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

mgm_no_input = st.sidebar.text_input("관리번호 입력 (직접 입력 또는 스캔)", value=st.session_state["search_query"], placeholder="예: 50A1100001 또는 50M1100162")

if mgm_no_input != st.session_state["search_query"]:
    st.session_state["search_query"] = mgm_no_input.strip()

query = st.session_state["search_query"]

st.sidebar.markdown("---")

# 3. 사용부서별 장비 리스트 조회 영역
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
# 메인 화면 콘텐츠 영역
# ==========================================

# 만약 관리번호가 검색된 경우 (우선 표시)
if query:
    matched_status = df_status[df_status['관리번호'].astype(str).str.strip().str.lower() == query.lower()]
    
    if matched_status.empty:
        st.warning(f"입력하신 관리번호 (**{query}**)에 해당하는 장비를 최신 [의료기기 현황조회] 파일에서 찾을 수 없습니다.")
    else:
        st.success(f"장비 조회 성공! 관리번호: **{query}**")
        
        # 3개의 단추 생성
        col1, col2, col3 = st.columns(3)
        
        with col1:
            btn_detail = st.button("1. 의료장비 상세내역 조회", use_container_width=True)
        with col2:
            btn_repair = st.button("2. 수리접수 이력 조회", use_container_width=True)
        with col3:
            btn_prevent = st.button("3. 예방점검 현황", use_container_width=True)
            
        st.markdown("---")
        
        # 버튼 1: 의료장비 상세내역 조회
        if btn_detail or "active_tab" not in st.session_state:
            st.session_state["active_tab"] = "detail"
            
        if st.session_state.get("active_tab") == "detail":
            st.subheader("📋 [버튼 1] 의료장비 상세내역")
            record = matched_status.iloc[0]
            item_list = list(record.items())
            
            st.markdown(f"#### 🔹 전체 항목 상세 Information (총 {len(item_list)}개 항목 중 상위 10개 표시)")
            
            preview_items = item_list[:10]
            cols = st.columns(2)
            half_len = (len(preview_items) + 1) // 2
            
            with cols[0]:
                for k, v in preview_items[:half_len]:
                    clean_key = str(k).replace('\n', ' ')
                    val_str = "-" if pd.isna(v) else str(v)
                    st.text(f"• [{clean_key}]: {val_str}")
                    
            with cols[1]:
                for k, v in preview_items[half_len:]:
                    clean_key = str(k).replace('\n', ' ')
                    val_str = "-" if pd.isna(v) else str(v)
                    st.text(f"• [{clean_key}]: {val_str}")
            
            @st.dialog("📋 의료장비 상세내역 전체 보기", width="large")
            def show_all_details_dialog(rec_items):
                st.write(f"관리번호 **{query}** 장비의 전체 상세 항목입니다.")
                d_cols = st.columns(2)
                d_half = (len(rec_items) + 1) // 2
                with d_cols[0]:
                    for k, v in rec_items[:d_half]:
                        clean_key = str(k).replace('\n', ' ')
                        val_str = "-" if pd.isna(v) else str(v)
                        st.text(f"• [{clean_key}]: {val_str}")
                with d_cols[1]:
                    for k, v in rec_items[d_half:]:
                        clean_key = str(k).replace('\n', ' ')
                        val_str = "-" if pd.isna(v) else str(v)
                        st.text(f"• [{clean_key}]: {val_str}")
                
                st.markdown("---")
                if st.button("닫기", use_container_width=True):
                    st.rerun()

            col_expand, _ = st.columns([2, 8])
            with col_expand:
                if st.button("🔍 전체 내용 확장해서 보기 (새 창)", use_container_width=True):
                    show_all_details_dialog(item_list)
            
            st.markdown("---")
            with st.expander("데이터프레임 형태로 전체 항목 보기"):
                st.dataframe(matched_status, use_container_width=True)

        # 버튼 2: 수리접수 이력 조회
        if btn_repair:
            st.session_state["active_tab"] = "repair"
            
        if st.session_state.get("active_tab") == "repair":
            st.subheader("🔧 [버튼 2] 수리접수 이력 조회 (모든 필드 / 최신순 정렬)")
            
            matched_repair = df_repair[df_repair['관리번호'].astype(str).str.strip().str.lower() == query.lower()].copy()
            
            if matched_repair.empty:
                st.info("해당 장비의 수리접수 이력이 존재하지 않습니다.")
            else:
                st.write(f"총 **{len(matched_repair)}건**의 수리 이력이 확인되었습니다.")
                
                if '접수일자' in matched_repair.columns:
                    matched_repair['접수일자_dt'] = pd.to_datetime(matched_repair['접수일자'], errors='coerce')
                    matched_repair = matched_repair.sort_values(by='접수일자_dt', ascending=False)
                    matched_repair = matched_repair.drop(columns=['접수일자_dt'])
                
                st.dataframe(matched_repair, use_container_width=True)

        # 버튼 3: 예방점검 현황
        if btn_prevent:
            st.session_state["active_tab"] = "prevent"
            
        if st.session_state.get("active_tab") == "prevent":
            st.subheader("🛡️ [버튼 3] 예방점검 현황")
            
            status_record = matched_status.iloc[0]
            equipment_name = status_record.get('장비명/구성품명', '-')
            dept_name = status_record.get('사용\n부서', status_record.get('사용부서', '-'))
            inspection_cycle = status_record.get('사용부서\n점검주기', status_record.get('사용부서점검주기', '-'))
            
            risk_col = [c for c in status_record.index if '위험' in str(c) or '등급' in str(c)]
            risk_grade = status_record.get(risk_col[0], '-') if risk_col else '-'
            if pd.isna(risk_grade) or str(risk_grade).strip() == '':
                risk_grade = "정보 없음"
            
            prevent_col = [c for c in df_repair.columns if '예방' in c and '점검' in c]
            if prevent_col:
                p_col = prevent_col[0]
                repair_matched = df_repair[
                    (df_repair['관리번호'].astype(str).str.strip().str.lower() == query.lower()) &
                    (df_repair[p_col].astype(str).str.strip().str.upper() == 'Y')
                ].copy()
            else:
                repair_matched = pd.DataFrame()
                
            last_inspection_date = "-"
            next_inspection_date = "-"
            
            if not repair_matched.empty and '완료일자' in repair_matched.columns:
                repair_matched['완료일자_dt'] = pd.to_datetime(repair_matched['완료일자'], errors='coerce')
                valid_dates = repair_matched['완료일자_dt'].dropna()
                if not valid_dates.empty:
                    latest_dt = valid_dates.max()
                    last_inspection_date = latest_dt.strftime('%Y-%m-%d')
                    
                    cycle_str = str(inspection_cycle).strip()
                    
                    if '일일' in cycle_str or ('일' in cycle_str and '회' not in cycle_str):
                        next_dt = latest_dt + pd.Timedelta(days=1)
                        next_inspection_date = next_dt.strftime('%Y-%m-%d')
                    elif '주간' in cycle_str or '주' in cycle_str:
                        next_dt = latest_dt + pd.Timedelta(weeks=1)
                        next_inspection_date = next_dt.strftime('%Y-%m-%d')
                    elif '반기' in cycle_str or '6개월' in cycle_str:
                        next_dt = latest_dt + pd.DateOffset(months=6)
                        next_inspection_date = next_dt.strftime('%Y-%m-%d')
                    elif '년' in cycle_str or '12개월' in cycle_str or '연간' in cycle_str or '1년' in cycle_str:
                        next_dt = latest_dt + pd.DateOffset(months=12)
                        next_inspection_date = next_dt.strftime('%Y-%m-%d')
                    elif '월간' in cycle_str or '월' in cycle_str:
                        match_month = re.search(r'(\d+)\s*개월', cycle_str)
                        if match_month:
                            m_val = int(match_month.group(1))
                            next_dt = latest_dt + pd.DateOffset(months=m_val)
                        else:
                            next_dt = latest_dt + pd.DateOffset(months=1)
                        next_inspection_date = next_dt.strftime('%Y-%m-%d')
                    else:
                        if '년' in cycle_str:
                            next_dt = latest_dt + pd.DateOffset(months=12)
                        else:
                            next_dt = latest_dt + pd.DateOffset(months=12)
                        next_inspection_date = next_dt.strftime('%Y-%m-%d')

            @st.dialog("🛡️ 예방점검 요약 및 위험등급 정보", width="small")
            def show_prevent_dialog():
                st.markdown(f"**• 관리번호:** `{query}`")
                st.markdown(f"**• 장비명:** {equipment_name}")
                st.markdown(f"**• 사용부서:** {str(dept_name).replace(chr(10), ' ')}")
                st.markdown(f"**• 점검주기:** {str(inspection_cycle).replace(chr(10), ' ')}")
                st.markdown(f"**• 최종점검일:** `{last_inspection_date}`")
                st.markdown(f"**• 차기점검일:** `{next_inspection_date}`")
                
                st.markdown("---")
                st.markdown(f"### ⚠️ 위험등급: **{risk_grade}**")
                
                if last_inspection_date == "-":
                    st.info("해당 장비의 수리내역 중 예방점검('Y') 이력이 존재하지 않습니다.")

            if st.button("🔍 예방점검 현황 및 위험등급 팝업 열기", use_container_width=True):
                show_prevent_dialog()
            
            show_prevent_dialog()

# 관리번호 검색어가 없고 부서별 조회를 선택한 경우
elif selected_dept != '전체보기':
    st.header(f"🏢 사용부서: [{selected_dept}] 장비 현황 리스트")
    dept_filtered_df = df_status[df_status[dept_col].astype(str).str.strip().str.lower() == selected_dept.lower()]
    st.write(f"총 **{len(dept_filtered_df)}대**의 장비가 등록되어 있습니다.")
    
    summary_display_cols = [c for c in ['관리번호', '장비명/구성품명', '설치장소', '모델', '제조업체', '일련번호', '자산\n상태', '취득일자'] if c in dept_filtered_df.columns]
    if summary_display_cols:
        st.dataframe(dept_filtered_df[summary_display_cols], use_container_width=True)
    
    st.markdown("#### ⚡ 빠른 장비 선택 및 조회")
    st.markdown("아래 목록에서 조회하고자 하는 장비의 **관리번호 버튼**을 클릭하시면 즉시 해당 장비의 상세 정보가 조회됩니다.")
    
    mgmt_numbers = dept_filtered_df['관리번호'].dropna().astype(str).tolist()
    if mgmt_numbers:
        cols_per_row = 5
        for i in range(0, len(mgmt_numbers), cols_per_row):
            row_items = mgmt_numbers[i:i+cols_per_row]
            btn_cols = st.columns(cols_per_row)
            for idx, m_no in enumerate(row_items):
                with btn_cols[idx]:
                    if st.button(f"📌 {m_no}", key=f"quick_btn_{i}_{idx}", use_container_width=True):
                        st.session_state["search_query"] = m_no
                        st.rerun()

    with st.expander("해당 부서 장비 전체 컬럼 원본 데이터 보기"):
        st.dataframe(dept_filtered_df, use_container_width=True)

else:
    st.info("👈 좌측 사이드바의 [모바일 카메라 스캐너 사용]을 체크하거나 관리번호를 직접 입력해주세요.")