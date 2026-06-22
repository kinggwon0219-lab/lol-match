import streamlit as st
import sqlite3
import itertools
import pandas as pd

# --- 데이터베이스 설정 ---
conn = sqlite3.connect('lol_inner_match.db', check_same_thread=False)
c = conn.cursor()

# 1. 플레이어 기본 정보 테이블
c.execute('''
    CREATE TABLE IF NOT EXISTS players (
        lol_id TEXT PRIMARY KEY,
        tier TEXT,
        score INTEGER,
        position TEXT
    )
''')

# 2. 경기별 세부 기록 테이블 (챔피언 및 승패 자동 집계용)
c.execute('''
    CREATE TABLE IF NOT EXISTS match_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lol_id TEXT,
        champion TEXT,
        team TEXT,
        result TEXT,
        match_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# 티어별 가중치 점수 매핑
TIER_SCORES = {
    "아이언": 1, "브론즈": 2, "실버": 3, "골드": 4, 
    "플래티넘": 5, "에메랄드": 6, "다이아몬드": 7, 
    "마스터": 8, "그랜드마스터": 9, "챌린저": 10
}

st.set_page_config(page_title="LOL 내전 전적 관리 시스템", layout="wide")
st.title("🎮 롤 내전 밸런스 팀짜기 & 자동 전적 시스템")

# --- 사이드바: 유저 관리 ---
st.sidebar.header("👤 1. 내전 멤버 등록/수정")
with st.sidebar.form("player_form", clear_on_submit=True):
    lol_id = st.text_input("롤 소환사명 (ID)").strip()
    tier = st.selectbox("현재 티어", list(TIER_SCORES.keys()))
    position = st.selectbox("주 라인", ["탑", "정글", "미드", "원딜", "서폿"])
    submit_btn = st.form_submit_button("멤버 등록/업데이트")
    
    if submit_btn and lol_id:
        score = TIER_SCORES[tier]
        c.execute('''
            INSERT INTO players (lol_id, tier, score, position)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(lol_id) DO UPDATE SET tier=excluded.tier, score=excluded.score, position=excluded.position
        ''', (lol_id, tier, score, position))
        conn.commit()
        st.sidebar.success(f"'{lol_id}'님 등록/수정 완료!")

# 메인 화면 탭 구성
tab1, tab2 = st.tabs(["⚖️ 팀 짜기 및 경기 기록", "📊 전적 및 랭킹 대시보드"])

# --- TAB 1: 팀 짜기 및 경기 기록 ---
with tab1:
    st.header("⚖️ 황금 밸런스 팀 매칭")
    df_players = pd.read_sql_query("SELECT * FROM players", conn)
    
    if len(df_players) < 10:
        st.warning(f"현재 등록된 멤버가 {len(df_players)}명입니다. 팀을 짜려면 최소 10명의 멤버를 사이드바에서 등록해 주세요.")
    else:
        st.write("오늘 내전에 참여할 **10명**을 선택하세요:")
        selected_players = st.multiselect("참가자 선택", df_players['lol_id'].tolist())
        
        if len(selected_players) == 10:
            if st.button("🔥 밸런스 팀 조합 생성", type="primary"):
                match_players = df_players[df_players['lol_id'].isin(selected_players)].to_dict('records')
                
                # 10명 중 5명을 뽑는 최적의 조합 탐색
                total_score = sum(p['score'] for p in match_players)
                best_diff = float('inf')
                best_team_a = []
                best_team_b = []
                
                for team_a_comb in itertools.combinations(match_players, 5):
                    score_a = sum(p['score'] for p in team_a_comb)
                    score_b = total_score - score_a
                    diff = abs(score_a - score_b)
                    
                    if diff < best_diff:
                        best_diff = diff
                        best_team_a = list(team_a_comb)
                        best_team_b = [p for p in match_players if p not in team_a_comb]
                
                st.session_state['team_a'] = best_team_a
                st.session_state['team_b'] = best_team_b
                st.session_state['teams_generated'] = True
                
            # 팀 생성 결과 출력 및 챔피언 입력 폼
            if st.session_state.get('teams_generated', False):
                st.divider()
                st.subheader("📝 경기 결과 및 플레이한 챔피언 입력")
                
                # 라디오 버튼을 상단에 배치
                winner = st.radio("🏆 승리한 팀을 선택하세요:", ["블루 팀 (Team A) 승리", "레드 팀 (Team B) 승리"])
                
                st.write("각 유저가 이번 판에 **플레이한 챔피언**을 적어주세요:")
                col1, col2 = st.columns(2)
                
                champs_a = {}
                champs_b = {}
                
                with col1:
                    st.markdown("### 🔵 블루 팀 (Team A)")
                    for p in st.session_state['team_a']:
                        champs_a[p['lol_id']] = st.text_input(f"{p['lol_id']} ({p['position']})의 챔피언", key=f"A_{p['lol_id']}").strip()
                    score_a_sum = sum(p['score'] for p in st.session_state['team_a'])
                    st.metric("블루팀 전투력 점수", score_a_sum)
                    
                with col2:
                    st.markdown("### 🔴 레드 팀 (Team B)")
                    for p in st.session_state['team_b']:
                        champs_b[p['lol_id']] = st.text_input(f"{p['lol_id']} ({p['position']})의 챔피언", key=f"B_{p['lol_id']}").strip()
                    score_b_sum = sum(p['score'] for p in st.session_state['team_b'])
                    st.metric("레드팀 전투력 점수", score_b_sum)
                
                if st.button("💾 이 경기 결과 저장하기", type="primary"):
                    # 챔피언 빈칸 검사
                    all_champs = list(champs_a.values()) + list(champs_b.values())
                    if "" in all_champs:
                        st.error("모든 플레이어의 챔피언을 입력해야 저장이 가능합니다!")
                    else:
                        # 블루팀 데이터 저장
                        res_a = "Win" if winner == "블루 팀 (Team A) 승리" else "Loss"
                        for p in st.session_state['team_a']:
                            c.execute("INSERT INTO match_details (lol_id, champion, team, result) VALUES (?, ?, 'Blue', ?)",
                                      (p['lol_id'], champs_a[p['lol_id']], res_a))
                        
                        # 레드팀 데이터 저장
                        res_b = "Win" if winner == "레드 팀 (Team B) 승리" else "Loss"
                        for p in st.session_state['team_b']:
                            c.execute("INSERT INTO match_details (lol_id, champion, team, result) VALUES (?, ?, 'Red', ?)",
                                      (p['lol_id'], champs_b[p['lol_id']], res_b))
                        
                        conn.commit()
                        st.success("🏆 경기 결과와 챔피언 기록이 안전하게 저장되었습니다! 대시보드를 확인하세요.")
                        st.session_state['teams_generated'] = False
        else:
            st.info(f"현재 {len(selected_players)}명 선택됨. 정확히 10명을 선택해야 팀 빌더가 활성화됩니다.")

# --- TAB 2: 전적 및 랭킹 대시보드 ---
with tab2:
    st.header("📊 내전 멤버 종합 전적 및 순위")
    
    df_p = pd.read_sql_query("SELECT * FROM players", conn)
    df_m = pd.read_sql_query("SELECT * FROM match_details", conn)
    
    if df_p.empty:
        st.info("등록된 유저가 없습니다. 사이드바에서 유저를 먼저 등록해 주세요.")
    elif df_m.empty:
        st.info("아직 기록된 경기 결과가 없습니다. 첫 게임을 진행하고 결과를 기록해 주세요!")
    else:
        # 유저별 승/패/판수 집계
        stats = []
        for idx, row in df_p.iterrows():
            user_id = row['lol_id']
            user_matches = df_m[df_m['lol_id'] == user_id]
            
            wins = len(user_matches[user_matches['result'] == 'Win'])
            losses = len(user_matches[user_matches['result'] == 'Loss'])
            total = wins + losses
            win_rate = round((wins / total) * 100, 1) if total > 0 else 0.0
            
            # 모스트 챔피언 및 챔피언별 승률 계산
            most_champs_str = "-"
            if total > 0:
                champ_stats = user_matches.groupby('champion').agg(
                    판수=('result', 'count'),
                    승리=('result', lambda x: sum(x == 'Win')),
                    패배=('result', lambda x: sum(x == 'Loss'))
                ).sort_values(by=['판수', '승리'], ascending=False).head(2) # 상위 2개 추출
                
                champ_list = []
                for c_name, c_row in champ_stats.iterrows():
                    champ_list.append(f"{c_name}({c_row['판수']}판 {c_row['승리']}승 {c_row['패배']}패)")
                most_champs_str = ", ".join(champ_list)
                
            stats.append({
                '롤 ID': user_id,
                '티어': row['tier'],
                '주 라인': row['position'],
                '승리': wins,
                '패배': losses,
                '총 판수': total,
                '승률 (%)': win_rate,
                '🔥 모스트 챔피언 (전적)': most_champs_str
            })
            
        df_dashboard = pd.DataFrame(stats)
        df_dashboard = df_dashboard.sort_values(by=['승률 (%)', '승리'], ascending=False).reset_index(drop=True)
        df_dashboard.index = df_dashboard.index + 1
        df_dashboard.index.name = '순위'
        
        st.dataframe(df_dashboard, use_container_width=True)
        
        # 꿀잼 통계 트리비아 
        st.markdown("### 👑 현재 내전 최강자")
        if len(df_dashboard) > 0 and df_dashboard.iloc[0]['총 판수'] > 0:
            st.success(f"현재 1위는 승률 **{df_dashboard.iloc[0]['승률 (%)']}%**을 달리고 있는 **{df_dashboard.iloc[0]['롤 ID']}** 님입니다!")