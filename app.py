import streamlit as st
import pandas as pd
import itertools
from streamlit_gsheets import GSheetsConnection
import datetime

# 티어별 가중치 점수 매핑
TIER_SCORES = {
    "아이언": 1, "브론즈": 2, "실버": 3, "골드": 4, 
    "플래티넘": 5, "에메랄드": 6, "다이아몬드": 7, 
    "마스터": 8, "그랜드마스터": 9, "챌린저": 10
}

st.set_page_config(page_title="LOL 내전 전적 관리 시스템", layout="wide")
st.title("🎮 롤 내전 밸런스 팀짜기 & 자동 전적 시스템")

# --- 구글 시트 데이터베이스 연결 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# 안전하게 데이터를 로드하는 함수
def load_sheet_data(worksheet_name, columns):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df.empty:
            df = pd.DataFrame(columns=columns)
    except Exception:
        df = pd.DataFrame(columns=columns)
    
    # 컬럼 누락 방지 및 결측치 처리
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df.fillna("").astype(str)

# 데이터 불러오기
df_players = load_sheet_data("players", ["lol_id", "tier", "score", "position"])
df_matches = load_sheet_data("match_details", ["lol_id", "champion", "team", "result", "match_date"])

# --- 사이드바: 유저 관리 ---
st.sidebar.header("👤 1. 내전 멤버 등록/수정")
with st.sidebar.form("player_form", clear_on_submit=True):
    lol_id = st.text_input("롤 소환사명 (ID)").strip()
    tier = st.selectbox("현재 티어", list(TIER_SCORES.keys()))
    position = st.selectbox("주 라인", ["탑", "정글", "미드", "원딜", "서폿"])
    submit_btn = st.form_submit_button("멤버 등록/업데이트")
    
    if submit_btn and lol_id:
        score = str(TIER_SCORES[tier])
        
        # 기존 멤버 존재 여부 확인 후 업데이트 또는 추가
        if lol_id in df_players['lol_id'].values:
            df_players.loc[df_players['lol_id'] == lol_id, ['tier', 'score', 'position']] = [tier, score, position]
        else:
            new_player = pd.DataFrame([{"lol_id": lol_id, "tier": tier, "score": score, "position": position}])
            df_players = pd.concat([df_players, new_player], ignore_index=True)
            
        # 구글 시트에 업데이트
        conn.update(worksheet="players", data=df_players)
        st.sidebar.success(f"'{lol_id}'님 등록/수정 완료!")
        st.rerun()

# 메인 화면 탭 구성
tab1, tab2 = st.tabs(["⚖️ 팀 짜기 및 경기 기록", "📊 전적 및 랭킹 대시보드"])

# --- TAB 1: 팀 짜기 및 경기 기록 ---
with tab1:
    st.header("⚖️ 황금 밸런스 팀 매칭")
    
    if len(df_players) < 10:
        st.warning(f"현재 등록된 멤버가 {len(df_players)}명입니다. 팀을 짜려면 최소 10명의 멤버를 사이드바에서 등록해 주세요.")
    else:
        st.write("오늘 내전에 참여할 **10명**을 선택하세요:")
        selected_players = st.multiselect("참가자 선택", df_players['lol_id'].tolist())
        
        if len(selected_players) == 10:
            if st.button("🔥 밸런스 팀 조합 생성", type="primary"):
                match_players = df_players[df_players['lol_id'].isin(selected_players)].to_dict('records')
                
                total_score = sum(int(p['score']) for p in match_players)
                best_diff = float('inf')
                best_team_a = []
                best_team_b = []
                
                for team_a_comb in itertools.combinations(match_players, 5):
                    score_a = sum(int(p['score']) for p in team_a_comb)
                    score_b = total_score - score_a
                    diff = abs(score_a - score_b)
                    
                    if diff < best_diff:
                        best_diff = diff
                        best_team_a = list(team_a_comb)
                        best_team_b = [p for p in match_players if p not in team_a_comb]
                
                st.session_state['team_a'] = best_team_a
                st.session_state['team_b'] = best_team_b
                st.session_state['teams_generated'] = True
                
            if st.session_state.get('teams_generated', False):
                st.divider()
                st.subheader("📝 경기 결과 및 플레이한 챔피언 입력")
                
                winner = st.radio("🏆 승리한 팀을 선택하세요:", ["블루 팀 (Team A) 승리", "레드 팀 (Team B) 승리"])
                st.write("각 유저가 이번 판에 **플레이한 챔피언**을 적어주세요:")
                col1, col2 = st.columns(2)
                
                champs_a = {}
                champs_b = {}
                
                with col1:
                    st.markdown("### 🔵 블루 팀 (Team A)")
                    for p in st.session_state['team_a']:
                        champs_a[p['lol_id']] = st.text_input(f"{p['lol_id']} ({p['position']})의 챔피언", key=f"A_{p['lol_id']}").strip()
                    score_a_sum = sum(int(p['score']) for p in st.session_state['team_a'])
                    st.metric("블루팀 전투력 점수", score_a_sum)
                    
                with col2:
                    st.markdown("### 🔴 레드 팀 (Team B)")
                    for p in st.session_state['team_b']:
                        champs_b[p['lol_id']] = st.text_input(f"{p['lol_id']} ({p['position']})의 챔피언", key=f"B_{p['lol_id']}").strip()
                    score_b_sum = sum(int(p['score']) for p in st.session_state['team_b'])
                    st.metric("레드팀 전투력 점수", score_b_sum)
                
                if st.button("💾 이 경기 결과 저장하기", type="primary"):
                    all_champs = list(champs_a.values()) + list(champs_b.values())
                    if "" in all_champs:
                        st.error("모든 플레이어의 챔피언을 입력해야 저장이 가능합니다!")
                    else:
                        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        new_rows = []
                        
                        res_a = "Win" if winner == "블루 팀 (Team A) 승리" else "Loss"
                        for p in st.session_state['team_a']:
                            new_rows.append({"lol_id": p['lol_id'], "champion": champs_a[p['lol_id']], "team": "Blue", "result": res_a, "match_date": now_str})
                        
                        res_b = "Win" if winner == "레드 팀 (Team B) 승리" else "Loss"
                        for p in st.session_state['team_b']:
                            new_rows.append({"lol_id": p['lol_id'], "champion": champs_b[p['lol_id']], "team": "Red", "result": res_b, "match_date": now_str})
                        
                        df_new_matches = pd.DataFrame(new_rows)
                        df_matches = pd.concat([df_matches, df_new_matches], ignore_index=True)
                        
                        conn.update(worksheet="match_details", data=df_matches)
                        st.success("🏆 경기 결과가 구글 시트에 안전하게 저장되었습니다!")
                        st.session_state['teams_generated'] = False
                        st.rerun()
        else:
            st.info(f"현재 {len(selected_players)}명 선택됨. 정확히 10명을 선택해야 팀 빌더가 활성화됩니다.")

# --- TAB 2: 전적 및 랭킹 대시보드 ---
with tab2:
    st.header("📊 내전 멤버 종합 전적 및 순위")
    
    if df_players.empty:
        st.info("등록된 유저가 없습니다. 사이드바에서 유저를 먼저 등록해 주세요.")
    elif df_matches.empty:
        st.info("아직 기록된 경기 결과가 없습니다. 첫 게임을 진행하고 결과를 기록해 주세요!")
    else:
        stats = []
        for idx, row in df_players.iterrows():
            user_id = row['lol_id']
            user_matches = df_matches[df_matches['lol_id'] == user_id]
            
            wins = len(user_matches[user_matches['result'] == 'Win'])
            losses = len(user_matches[user_matches['result'] == 'Loss'])
            total = wins + losses
            win_rate = round((wins / total) * 100, 1) if total > 0 else 0.0
            
            most_champs_str = "-"
            if total > 0:
                champ_stats = user_matches.groupby('champion').agg(
                    판수=('result', 'count'),
                    승리=('result', lambda x: sum(x == 'Win')),
                    패배=('result', lambda x: sum(x == 'Loss'))
                ).sort_values(by=['판수', '승리'], ascending=False).head(2)
                
                champ_list = []
                for c_name, c_row in champ_stats.iterrows():
                    champ_list.append(f"{c_name}({c_row['판수']}판 {c_row['승리']}승 {c_row['패배']}패)")
                most_champs_str = ", ".join(champ_list)
                
            stats.append({
                '롤 ID': user_id, '티어': row['tier'], '주 라인': row['position'],
                '승리': wins, '패배': losses, '총 판수': total, '승률 (%)': win_rate,
                '🔥 모스트 챔피언 (전적)': most_champs_str
            })
            
        df_dashboard = pd.DataFrame(stats)
        df_dashboard = df_dashboard.sort_values(by=['승률 (%)', '승리'], ascending=False).reset_index(drop=True)
        df_dashboard.index = df_dashboard.index + 1
        df_dashboard.index.name = '순위'
        
        st.dataframe(df_dashboard, use_container_width=True)
