import glob
import os
import re
from datetime import datetime
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

# 페이지 설정 (라이트 모드 고정)
st.set_page_config(page_title="인하대병원 의료장비 조회 시스템", layout="wide")

# ==========================================
# 📂 설정 파일 및 대기 파일 관리 함수
# ==========================================
CONFIG_FILE = 'config.yaml'
PENDING_FILE = 'pending_users.yaml'

def load_yaml(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.load(f, Loader=SafeLoader)
    return None

def save_yaml(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True)

config = load_yaml(CONFIG_FILE)
if not config:
    st.error("설정 파일(`config.yaml`)을 찾을 수 없습니다.")
    st.stop()

# 인증 객체 생성
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# 세션 상태 초기화
if "page_mode" not in st.session_state:
    st.session_state["page_mode"] = "login"

if "register_success" not in st.session_state:
    st.session_state["register_success"] = False

# ==========================================
# 🔒 로그인 및 가입 화면 라우팅
# ==========================================
if st.session_state.get("authentication_status") != True:
    
    # 1. 회원가입 신청 화면인 경우
    if st.session_state["page_mode"] == "register":
        st.title("📝 사용자 가입 신청")
        st.markdown("의료장비 조회 시스템 사용을 위한 계정 발급을 신청합니다. 관리자 승인 후 로그인할 수 있습니다.")
        
        if st.session_state["register_success"]:
            st.success("🎉 가입 신청이 완료되었습니다! 관리자 승인 후 로그인이 가능합니다.")
            if st.button("로그인 화면으로 돌아가기", use_container_width=True):
                st.session_state["register_success"] = False
                st.session_state["page_mode"] = "login"
                st.rerun()
        else:
            with st.form("register_form"):
                reg_username = st.text_input("아이디 (ID)").strip()
                reg_name = st.text_input("이름").strip()
                reg_email = st.text_input("이메일 주소").strip()
                reg_password = st.text_input("비밀번호", type="password")
                reg_password_check = st.text_input("비밀번호 확인", type="password")
                
                submitted = st.form_submit_button("가입 신청 제출", use_container_width=True)
                
                if submitted:
                    if not reg_username or not reg_name or not reg_password:
                        st.error("모든 필수 항목을 입력해 주세요.")
                    elif reg_password != reg_password_check:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        all_users = list(config['credentials']['usernames'].keys())
                        pending_data = load_yaml(PENDING_FILE) or {'pending_usernames': {}}
                        all_pending = list(pending_data['pending_usernames'].keys())
                        
                        if reg_username in all_users or reg_username in all_pending:
                            st.error("이미 존재하는 아이디이거나 이미 신청된 아이디입니다.")
                        else:
                            try:
                                hashed_pw = stauth.Hasher([reg_password]).generate()[0]
                            except Exception:
                                import bcrypt
                                hashed_pw = bcrypt.hashpw(reg_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

                            pending_data['pending_usernames'][reg_username] = {
                                'email': reg_email,
                                'first_name': reg_name,
                                'last_name': '',
                                'password': hashed_pw
                            }
                            save_yaml(pending_data, PENDING_FILE)
                            st.session_state["register_success"] = True
                            st.rerun()
                            
            if st.button("⬅️ 로그인 화면으로", use_container_width=True):
                st.session_state["page_mode"] = "login"
                st.rerun()
        st.stop()

    # 2. 일반 로그인 화면인 경우
    try:
        authenticator.login()
    except Exception as e:
        st.error(e)

    if st.session_state["authentication_status"] == False:
        st.error("사용자 이름 또는 비밀번호가 올바르지 않습니다.")
    elif st.session_state["authentication_status"] == None:
        st.warning("시스템에 접근하려면 로그인을 진행해 주세요.")
        
    st.markdown("---")
    if st.button("✨ 계정이 없으신가요? [가입 신청하기]", use_container_width=True):
        st.session_state["register_success"] = False
        st.session_state["page_mode"] = "register"
        st.rerun()
    st.stop()

# ==========================================
# 🔓 로그인 성공 후 메인 앱 실행 영역
# ==========================================
username = st.session_state.get("username")
name = st.session_state.get("name")

authenticator.logout('로그아웃', 'sidebar')
st.sidebar.markdown(f"환영합니다, **{name}**님! 👋")
st.sidebar.markdown("---")

# 👑 관리자 계정 ('dhkoh') 전용: 가입 승인 관리 메뉴
if username == "dhkoh":
    st.sidebar.markdown("### 👑 관리자 메뉴")
    if st.sidebar.button("📋 가입 승인 관리", use_container_width=True):
        st.session_state["show_admin_approval"] = True
    else:
        if "show_admin_approval" not in st.session_state:
            st.session_state["show_admin_approval"] = False

# 관리자 승인 화면 구현
if username == "dhkoh" and st.session_state.get("show_admin_approval", False):
    st.title("📋 사용자 가입 신청 승인 관리")
    
    pending_data = load_yaml(PENDING_FILE)
    if not pending_data or not pending_data.get('pending_usernames'):
        st.info("현재 대기 중인 가입 신청이 없습니다.")
    else:
        pending_dict = pending_data['pending_usernames']
        for u_id, u_info in list(pending_dict.items()):
            cols = st.columns([3, 3, 2, 2])
            cols[0].text(f"아이디: {u_id}")
            cols[1].text(f"이름: {u_info['first_name']} (이메일: {u_info['email']})")
            
            if cols[2].button("승인", key=f"approve_{u_id}"):
                config['credentials']['usernames'][u_id] = u_info
                save_yaml(config, CONFIG_FILE)
                
                del pending_dict[u_id]
                save_yaml(pending_data, PENDING_FILE)
                st.success(f"'{u_id}'님의 가입이 승인되었습니다.")
                st.rerun()
                
            if cols[3].button("거절", key=f"reject_{u_id}"):
                del pending_dict[u_id]
                save_yaml(pending_data, PENDING_FILE)
                st.warning(f"'{u_id}'님의 가입이 거절되었습니다.")
                st.rerun()
                
    if st.button("⬅️ 메인 조회 화면으로 돌아가기"):
        st.session_state["show_admin_approval"] = False
        st.rerun()
    st.stop()

# ==========================================
# 🏥 의료장비 데이터 로드 및 조회 시스템 본문
# ==========================================
try:
    import cv2
    import numpy as np
    from pyzbar.pyzbar import decode
    HAS_QR_DECODER = True
except ImportError:
    HAS_QR_DECODER = False

st.title("🏥 인하대병원 의료장비 조회 시스템")
st.markdown("관리번호를 직접 입력하거나, **[📷 카메라/QR 스캔]** 버튼을 눌러 관리번호를 자동으로 입력받으세요.")

def find_latest_status_file(prefix="의료기기 현황조회", extensions=(".xlsx", ".xlsb", ".xls")):
    files = []
    for ext in extensions:
        files.extend(glob.glob(f"{prefix}*{ext}"))
    if not files:
        return None
    def extract_date(filename):
        remainder = filename[len(prefix):]
        matches = re.findall(r'(\d+)', remainder)
        if matches:
            return matches[-1]
        return ""
    files.sort(key=extract_date, reverse=True)
    return files[0]

@st.cache_data
def load_latest_data():
    status_file = find_latest_status_file("의료기기 현황조회")
    repair_files = []
    for ext in (".xlsx", ".xlsb", ".xls"):
        repair_files.extend(glob.glob(f"수리접수 내역*{ext}"))
    if not status_file:
        raise FileNotFoundError("필요한 '의료기기 현황조회' 파일을 찾을 수 없습니다.")
    if not repair_files:
        raise FileNotFoundError("필요한 '수리접수 내역' 파일을 찾을 수 없습니다.")
    
    df_status = pd.read_excel(status_file)
    repair_dfs = []
    for r_file in repair_files:
        try:
            if r_file.endswith('.xlsb'):
                df_r = pd.read_excel(r_file, engine='pyxlsb')
            else:
                df_r = pd.read_excel(r_file)
            repair_dfs.append(df_r)
        except Exception as e:
            st.warning(f"파일을 읽는 중 오류 발생 ({r_file}): {e}")
            
    if repair_dfs:
        df_repair = pd.concat(repair_dfs, ignore_index=True)
        df_repair = df_repair.drop_duplicates()
    else:
        df_repair = pd.DataFrame()
        
    repair_file_names = ", ".join([os.path.basename(f) for f in repair_files])
    return df_status, df_repair, status_file, repair_file_names

try:
    df_status, df_repair, latest_status_path, latest_repair_names = load_latest_data()
except Exception as e:
    st.error(f"데이터 파일을 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

# 세션 상태 초기화
if "search_input_val" not in st.session_state:
    st.session_state["search_input_val"] = ""
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

def trigger_individual_search(query_val):
    clean_q = query_val.strip().upper()
    st.session_state["search_query"] = clean_q
    if clean_q:
        st.session_state["dept_selection"] = "전체보기"
        st.session_state["dept_selectbox_active"] = "전체보기"
        st.session_state["show_repair"] = False
        if clean_q != st.session_state["last_queried_no"]:
            st.session_state["last_queried_no"] = clean_q
            st.session_state["auto_popup_shown"] = False

query_params = st.query_params
if "mgm" in query_params:
    url_mgm = query_params["mgm"]
    if isinstance(url_mgm, list):
        url_mgm = url_mgm[0]
    if url_mgm:
        clean_url_mgm = url_mgm.strip().upper()
        if clean_url_mgm != st.session_state["search_query"]:
            st.session_state["search_input_val"] = clean_url_mgm
            trigger_individual_search(clean_url_mgm)

st.sidebar.markdown("### 📁 현재 참조 중인 파일")
st.sidebar.info(
    f"**[의료기기 현황]**\n`{latest_status_path}`\n\n"
    f"**[수리접수 내역 (통합 참조)]**\n`{latest_repair_names}`"
)

# 검색 입력부
col_search, col_btn = st.columns([4, 1])
with col_search:
    user_input = st.text_input("관리번호 검색", value=st.session_state["search_input_val"], placeholder="예: M12345 또는 장비명 입력", label_visibility="collapsed")
with col_btn:
    search_clicked = st.button("조회", use_container_width=True)

if search_clicked and user_input:
    trigger_individual_search(user_input)

# 간단한 데이터 그리드 또는 전체 목록 표시 예시
if st.session_state["search_query"]:
    st.markdown(f"### 검색 결과: `{st.session_state['search_query']}`")
    # 예시 필터링 로직 (컬럼명에 맞춰 필요시 조정)
    matched_df = df_status[df_status.astype(str).apply(lambda x: x.str.contains(st.session_state["search_query"], case=False)).any(axis=1)]
    if not matched_df.empty:
        st.dataframe(matched_df, use_container_width=True)
    else:
        st.warning("검색 결과가 없습니다.")
else:
    st.info("관리번호를 검색하거나 부서를 선택하여 장비 현황을 확인하세요.")