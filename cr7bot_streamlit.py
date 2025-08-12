import streamlit as st
st.set_page_config(page_title="CR7 BOT — Treinador ChatGPT", layout="centered")

# ---- imports essenciais
import pandas as pd
from io import BytesIO
import re
import streamlit.components.v1 as components
import streamlit_authenticator as stauth

# ================== DEBUG HELPERS ==================
DEBUG = True

def show_debug_header(stage="start"):
    if not DEBUG:
        return
    import sys, importlib
    with st.sidebar.expander("🛠 Debug (ambiente)", expanded=True):
        st.write({"stage": stage})
        st.write({"python": sys.version})
        st.write({"streamlit": st.__version__})
        st.write({"pandas": pd.__version__})
        st.write({"stauth_version": getattr(stauth, "__version__", "unknown")})
        # confirma main file carregado
        st.write({"__name__": __name__})

show_debug_header("imports_ok")

# ================== AUTENTICAÇÃO (>=0.3.x, sem bcrypt) ==================
USERS = [
    {"username": "paulo", "name": "Paulo Silva", "password": "1234"},
    {"username": "joao",  "name": "João Ribeiro", "password": "abcd"},
]

passwords_plain = [u["password"] for u in USERS]
hashed_list = stauth.Hasher(passwords_plain).generate()

credentials = {"usernames": {}}
for u, hashed in zip(USERS, hashed_list):
    credentials["usernames"][u["username"]] = {"name": u["name"], "password": hashed}

try:
    authenticator = stauth.Authenticate(
        credentials=credentials,
        cookie_name="cr7bot_app",
        key="abcdef",
        cookie_expiry_days=30,
        preauthorized=[]
    )
    name, authentication_status, username = authenticator.login("Login", "main")
except Exception as e:
    st.error("Falha ao inicializar autenticação. Verifica a versão do streamlit-authenticator.")
    if DEBUG:
        st.exception(e)
    st.stop()

show_debug_header("auth_ok")

# ================== LISTAS / FUNÇÕES ==================
formacoes_lista = [
    "4-4-2","4-3-3","4-2-3-1","3-5-2","3-4-3","5-3-2","4-1-4-1","4-5-1",
    "3-4-2-1","3-4-1-2","3-6-1","4-4-1-1","4-3-1-2","4-2-2-2","4-3-2-1",
    "5-4-1","5-2-3","5-2-1-2","4-1-2-1-2","3-5-1-1","4-1-2-3","3-3-3-1",
    "3-2-3-2","3-3-1-3","4-2-4","4-3-2","3-2-5","2-3-5","4-2-1-3","Outro"
]
tipos_formacao = ["Atacante","Equilibrado","Defensivo"]
tipos_troca = [
    "Avançado por Avançado","Avançado por Médio","Avançado por Defesa",
    "Médio por Avançado","Médio por Médio","Médio por Defesa",
    "Defesa por Avançado","Defesa por Médio","Defesa por Defesa","Outro"
]
posicoes_lista = ["GR","Defesa","Médio","Avançado"]
importancias_lista = ["Peça chave","Importante","Normal"]
meteos_lista = ["Sol","Chuva","Nublado","Vento","Frio","Outro"]

def kelly_criterion(prob, odd, banca, fracao=1):
    b = odd - 1
    q = 1 - prob
    f = ((b * prob - q) / b) * fracao
    return max(0, banca * f)

def calc_ev(p, o): return round(o * p - 1, 2)

def to_excel(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Resultados')
    return output.getvalue()

def sugestao_formacao(eventos):
    if not eventos: return ""
    u = eventos[-1]
    if u["tipo"] == "Substituição":
        if u.get("tipo_troca") in ["Avançado por Médio","Avançado por Defesa"]:
            return "⚠️ Sugerido: 4-5-1 / 5-4-1 / 4-2-3-1."
        if u.get("tipo_troca") in ["Defesa por Avançado","Médio por Avançado"]:
            return "⚡ Sugerido: 4-3-3 atacante / 4-2-4 / 3-4-3."
    return ""

def interpretar_tatica(eventos, live_base, resultado_actual):
    if not eventos: return "Sem eventos recentes. O treinador mantém o plano inicial."
    ultimo = eventos[-1]; equipa = ultimo.get("equipa","")
    tipo = ultimo["tipo"]
    if tipo == "Substituição":
        t = ultimo.get("tipo_troca","")
        if t in ["Avançado por Médio","Avançado por Defesa"]:
            c = f"O treinador ({equipa}) abdica de ataque; pode proteger vantagem."
        elif t in ["Defesa por Avançado","Médio por Avançado"]:
            c = f"O treinador ({equipa}) arrisca mais no ataque."
        elif t == "Médio por Médio":
            c = f"O treinador ({equipa}) mantém equilíbrio no meio."
        else:
            c = f"Substituição sem alteração táctica evidente ({t})."
    elif tipo == "Mudança de formação":
        nova = ultimo.get("nova_formacao",""); tf = ultimo.get("tipo_formacao","")
        if tf == "Atacante": c = f"Formação ofensiva ({nova})."
        elif tf == "Defensivo": c = f"Formação defensiva ({nova})."
        else: c = f"Formação ajustada ({nova})."
    elif tipo == "Expulsão":
        c = f"Expulsão em {ultimo.get('posicao','?')} ({equipa}). Ajuste obrigatório."
    elif tipo == "Amarelo":
        c = f"Amarelo para {ultimo.get('posicao','?')} ({equipa})."
    elif tipo == "Penalty": c = f"Penalty para {equipa}!"
    elif tipo == "Golo": c = f"Golo {equipa}!"
    else: c = "Sem alteração táctica identificada."
    return "🤖 Treinador ChatGPT: " + c + "\n" + sugestao_formacao(eventos)

def calc_xg_live(dados, eventos):
    xg_total_1p = dados["xg_casa"] + dados["xg_fora"]
    xgot_total_1p = dados["xgot_casa"] + dados["xgot_fora"]
    xg_ponderado = 0.7*xg_total_1p + 0.3*xgot_total_1p
    remates_baliza_total = dados["remates_baliza_casa"] + dados["remates_baliza_fora"]
    grandes_ocasioes_total = dados["grandes_ocasioes_casa"] + dados["grandes_ocasioes_fora"]
    remates_ferro_total = dados["remates_ferro_casa"] + dados["remates_ferro_fora"]
    ajuste = 1.0 + (dados["rating_casa"] - dados["rating_fora"])*0.10
    if grandes_ocasioes_total >= 3: ajuste += 0.10
    if remates_baliza_total >= 6: ajuste += 0.05
    if xg_ponderado >= 1.0: ajuste += 0.10
    if remates_ferro_total: ajuste += remates_ferro_total * 0.07
    if dados["amarelos_casa"] >= 3: ajuste -= 0.05
    if dados["amarelos_fora"] >= 3: ajuste -= 0.05
    if dados["vermelhos_casa"]: ajuste -= 0.20 * dados["vermelhos_casa"]
    if dados["vermelhos_fora"]: ajuste += 0.20 * dados["vermelhos_fora"]
    for ev in eventos:
        t, eq = ev["tipo"], ev["equipa"]
        if t == "Golo": ajuste += 0.2 if eq=="Casa" else -0.2
        elif t == "Expulsão": ajuste -= 0.15 if eq=="Casa" else 0.15
        elif t == "Penalty": ajuste += 0.25 if eq=="Casa" else -0.25
        elif t == "Substituição":
            peso = {"Avançado por Médio":-0.08,"Avançado por Defesa":-0.12,
                    "Médio por Avançado":+0.07,"Defesa por Avançado":+0.10}.get(ev.get("tipo_troca",""),0)
            ajuste += peso if eq=="Casa" else -peso
        elif t == "Mudança de formação":
            imp = 0.08 if ev.get("tipo_formacao")=="Atacante" else -0.08 if ev.get("tipo_formacao")=="Defensivo" else 0
            ajuste += imp if eq=="Casa" else -imp
        elif t == "Amarelo":
            pos = ev.get("posicao","Desconhecida")
            peso = {"Defesa":-0.05,"Médio":-0.03,"Avançado":-0.01}.get(pos,0)
            ajuste += peso if eq=="Casa" else -peso
    return xg_ponderado*ajuste, ajuste, xg_ponderado

def parse_m3u(m3u_text: str):
    channels, current = [], {}
    for line in m3u_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#EXTM3U"): continue
        if line.startswith("#EXTINF"):
            name = line.split(",",1)[1].strip() if "," in line else "Sem nome"
            logo = re.search(r'tvg-logo="([^"]*)"', line)
            group = re.search(r'group-title="([^"]*)"', line)
            current = {"name": name, "logo": logo.group(1) if logo else "", "group": group.group(1) if group else ""}
        elif not line.startswith("#") and current:
            current["url"] = line
            channels.append(current); current = {}
    return channels

# ================== UI / FLUXO ==================
if authentication_status is False:
    st.error("Username ou password incorretos!")
elif authentication_status is None:
    st.warning("Por favor faz login.")
else:
    authenticator.logout('Logout', 'sidebar')
    st.sidebar.success(f"Bem-vindo, {name}!")

    st.title("⚽️ CR7 BOT — Treinador ChatGPT (Pré-Jogo + Live + Inteligência)")
    tab1, tab2, tab3 = st.tabs(["⚽ Pré-Jogo","🔥 Live / 2ª Parte + Treinador ChatGPT","📺 Player IPTV"])

    # ---------- TAB 1 ----------
    with tab1:
        st.header("Análise Pré-Jogo")
        st.subheader("Formações e Estratégias")
        colf1, colf2 = st.columns(2)
        with colf1:
            form_casa = st.selectbox("Formação inicial CASA", formacoes_lista, key="form_casa_pre")
            tipo_form_casa = st.selectbox("Abordagem (CASA)", tipos_formacao, key="tipo_form_casa_pre")
        with colf2:
            form_fora = st.selectbox("Formação inicial FORA", formacoes_lista, key="form_fora_pre")
            tipo_form_fora = st.selectbox("Abordagem (FORA)", tipos_formacao, key="tipo_form_fora_pre")

        st.subheader("Titulares disponíveis")
        titulares_casa = st.number_input("Quantos titulares disponíveis na CASA? (0-11)", 0, 11, 11, key="titulares_casa")
        if titulares_casa < 11:
            st.warning(f"⚠️ Atenção: {11 - titulares_casa} titular(es) ausente(s) na CASA!")
        titulares_fora = st.number_input("Quantos titulares disponíveis na FORA? (0-11)", 0, 11, 11, key="titulares_fora")
        if titulares_fora < 11:
            st.warning(f"⚠️ Atenção: {11 - titulares_fora} titular(es) ausente(s) na FORA!")

        st.subheader("Condições Especiais")
        meteo = st.selectbox("Tempo esperado", meteos_lista, key="meteo_pre")
        arbitro_nota = st.slider("Nota do Árbitro (0=caseiro, 10=deixa jogar)", 0.0, 10.0, 5.0, step=0.1, key="arbitro_pre")
        motivacao = st.selectbox("Motivação principal do jogo", ["Normal","Alta (decisão)","Baixa"], key="motivacao_pre")

        with st.form("totais_golos_form"):
            st.subheader("Equipa da CASA")
            total_golos_casa = st.number_input("Total de golos marcados (CASA)", min_value=0, value=0, key="golos_casa")
            total_sofridos_casa = st.number_input("Total de golos sofridos (CASA)", min_value=0, value=0, key="sofridos_casa")
            jogos_casa = st.number_input("Nº de jogos (CASA)", min_value=1, value=5, key="jogos_casa")
            st.info(f"Média marcados: {total_golos_casa/jogos_casa:.2f} | Média sofridos: {total_sofridos_casa/jogos_casa:.2f}")

            st.subheader("Equipa de FORA")
            total_golos_fora = st.number_input("Total de golos marcados (FORA)", min_value=0, value=0, key="golos_fora")
            total_sofridos_fora = st.number_input("Total de golos sofridos (FORA)", min_value=0, value=0, key="sofridos_fora")
            jogos_fora = st.number_input("Nº de jogos (FORA)", min_value=1, value=5, key="jogos_fora")
            st.info(f"Média marcados: {total_golos_fora/jogos_fora:.2f} | Média sofridos: {total_sofridos_fora/jogos_fora:.2f}")

            st.subheader("Confrontos Diretos (H2H)")
            total_golos_h2h_casa = st.number_input("Total golos marcados H2H (CASA)", min_value=0, value=0, key="golos_h2h_casa")
            total_golos_h2h_fora = st.number_input("Total golos marcados H2H (FORA)", min_value=0, value=0, key="golos_h2h_fora")
            jogos_h2h = st.number_input("Nº de jogos (H2H)", min_value=1, value=5, key="jogos_h2h")
            st.info(f"Média H2H CASA: {total_golos_h2h_casa/jogos_h2h:.2f} | Média H2H FORA: {total_golos_h2h_fora/jogos_h2h:.2f}")

            confirm1 = st.form_submit_button("✅ Confirmar Totais")
        if confirm1:
            st.session_state['medias'] = {
                'marc_casa': total_golos_casa/jogos_casa,
                'sofr_casa': total_sofridos_casa/jogos_casa,
                'marc_fora': total_golos_fora/jogos_fora,
                'sofr_fora': total_sofridos_fora/jogos_fora,
                'marc_h2h_casa': total_golos_h2h_casa/jogos_h2h,
                'marc_h2h_fora': total_golos_h2h_fora/jogos_h2h,
            }
            st.success("Totais confirmados!")

        st.subheader("Odds de Mercado (Casa de Apostas)")
        colod1, colod2, colod3 = st.columns(3)
        odd_casa = colod1.number_input("Odd CASA", min_value=1.01, value=1.80, key="odd_casa")
        odd_empate = colod2.number_input("Odd EMPATE", min_value=1.01, value=3.40, key="odd_empate")
        odd_fora = colod3.number_input("Odd FORA", min_value=1.01, value=4.20, key="odd_fora")
        odd_btts_sim = st.number_input("Odd Ambas Marcam SIM", min_value=1.01, value=1.90, key="odd_btts_sim")
        odd_btts_nao = st.number_input("Odd Ambas Marcam NÃO", min_value=1.01, value=1.80, key="odd_btts_nao")
        st.caption(f"Soma odds 1X2: {odd_casa + odd_empate + odd_fora:.2f} | Soma BTTS: {odd_btts_sim + odd_btts_nao:.2f}")

        if st.button("Exportar para Excel (Pré-Jogo)"):
            df = pd.DataFrame({"Odd":["Casa","Empate","Fora","BTTS Sim","BTTS Não"],
                               "Valor":[odd_casa,odd_empate,odd_fora,odd_btts_sim,odd_btts_nao]})
            st.download_button("📥 Download Excel", data=to_excel(df), file_name="odds_pre_jogo.xlsx",
                               mime="application/vnd.ms-excel")

    # ---------- TAB 2 ----------
    with tab2:
        st.header("Live/2ª Parte — Previsão de Golos (Modo Escuta + Treinador ChatGPT)")
        col_livef1, col_livef2 = st.columns(2)
        with col_livef1:
            form_casa_live = st.selectbox("Formação CASA (Live)", formacoes_lista, key="form_casa_live")
            tipo_form_casa_live = st.selectbox("Abordagem CASA", tipos_formacao, key="tipo_form_casa_live")
        with col_livef2:
            form_fora_live = st.selectbox("Formação FORA (Live)", formacoes_lista, key="form_fora_live")
            tipo_form_fora_live = st.selectbox("Abordagem FORA", tipos_formacao, key="tipo_form_fora_live")

        with st.form("form_live_base"):
            resultado_intervalo = st.text_input("Resultado ao intervalo", value="0-0")
            xg_casa = st.number_input("xG CASA (1ª parte)", min_value=0.0, value=0.0, step=0.01)
            xg_fora = st.number_input("xG FORA (1ª parte)", min_value=0.0, value=0.0, step=0.01)
            xgot_casa = st.number_input("xGOT CASA (1ª parte)", min_value=0.0, value=0.0, step=0.01)
            xgot_fora = st.number_input("xGOT FORA (1ª parte)", min_value=0.0, value=0.0, step=0.01)
            remates_baliza_casa = st.number_input("Remates à baliza (CASA)", min_value=0, value=0)
            remates_baliza_fora = st.number_input("Remates à baliza (FORA)", min_value=0, value=0)
            grandes_ocasioes_casa = st.number_input("Grandes oportunidades (CASA)", min_value=0, value=0)
            grandes_ocasioes_fora = st.number_input("Grandes oportunidades (FORA)", min_value=0, value=0)
            remates_ferro_casa = st.number_input("Remates ao ferro (CASA)", min_value=0, value=0)
            remates_ferro_fora = st.number_input("Remates ao ferro (FORA)", min_value=0, value=0)
            amarelos_casa = st.number_input("Cartões amarelos (CASA)", min_value=0, value=0)
            amarelos_fora = st.number_input("Cartões amarelos (FORA)", min_value=0, value=0)
            vermelhos_casa = st.number_input("Cartões vermelhos (CASA)", min_value=0, value=0)
            vermelhos_fora = st.number_input("Cartões vermelhos (FORA)", min_value=0, value=0)
            rating_casa = st.number_input("Rating CASA (0-10)", min_value=0.0, max_value=10.0, value=7.0, step=0.01)
            rating_fora = st.number_input("Rating FORA (0-10)", min_value=0.0, max_value=10.0, value=6.9, step=0.01)
            confirmar_base = st.form_submit_button("✅ Confirmar Dados 1ª Parte")
        if confirmar_base:
            st.session_state['live_base'] = {
                "xg_casa": xg_casa, "xg_fora": xg_fora, "xgot_casa": xgot_casa, "xgot_fora": xgot_fora,
                "remates_baliza_casa": remates_baliza_casa, "remates_baliza_fora": remates_baliza_fora,
                "grandes_ocasioes_casa": grandes_ocasioes_casa, "grandes_ocasioes_fora": grandes_ocasioes_fora,
                "remates_ferro_casa": remates_ferro_casa, "remates_ferro_fora": remates_ferro_fora,
                "amarelos_casa": amarelos_casa, "amarelos_fora": amarelos_fora,
                "vermelhos_casa": vermelhos_casa, "vermelhos_fora": vermelhos_fora,
                "rating_casa": rating_casa, "rating_fora": rating_fora,
                "form_casa": form_casa_live, "form_fora": form_fora_live,
                "tipo_form_casa": tipo_form_casa_live, "tipo_form_fora": tipo_form_fora_live
            }
            st.success("Estatísticas e formações registadas! Agora adiciona eventos live.")

        if "eventos_live" not in st.session_state:
            st.session_state["eventos_live"] = []

        st.subheader("➕ Adicionar Evento LIVE")
        tipo_evento = st.selectbox("Tipo de evento", ["Golo","Expulsão","Penalty","Substituição","Mudança de formação","Amarelo"])
        equipa_evento = st.selectbox("Equipa", ["Casa","Fora"])
        detalhes_evento = st.text_input("Detalhes (opcional)", key="detalhes_ev")
        posicao_ev = tipo_troca_ev = nova_form_ev = tipo_form_ev = imp_ev = None
        if tipo_evento in ["Expulsão","Amarelo"]:
            posicao_ev = st.selectbox("Posição do jogador", posicoes_lista, key="pos_ev")
            imp_ev = st.selectbox("Importância do jogador", importancias_lista, key="imp_ev")
        if tipo_evento == "Substituição":
            tipo_troca_ev = st.selectbox("Tipo de substituição", tipos_troca, key="troca_ev")
        if tipo_evento == "Mudança de formação":
            nova_form_ev = st.selectbox("Nova formação", formacoes_lista, key="nova_form_ev")
            tipo_form_ev = st.selectbox("Nova abordagem", tipos_formacao, key="tipo_form_ev")

        if st.button("Adicionar evento LIVE"):
            ev = {"tipo": tipo_evento, "equipa": equipa_evento, "detalhes": detalhes_evento}
            if posicao_ev: ev["posicao"] = posicao_ev
            if tipo_troca_ev: ev["tipo_troca"] = tipo_troca_ev
            if nova_form_ev: ev["nova_formacao"] = nova_form_ev
            if tipo_form_ev: ev["tipo_formacao"] = tipo_form_ev
            if imp_ev: ev["importancia"] = imp_ev
            st.session_state["eventos_live"].append(ev)
            st.success("Evento adicionado! Atualiza previsão em baixo.")

        st.markdown("#### Eventos registados:")
        if st.session_state["eventos_live"]:
            for i, ev in enumerate(st.session_state["eventos_live"], 1):
                parts = [f"{i}. {ev['tipo']} | {ev['equipa']}"]
                for k in ["posicao","tipo_troca","nova_formacao","importancia","detalhes"]:
                    if ev.get(k): parts.append(str(ev[k]))
                st.write(" | ".join(parts))
        else:
            st.write("Nenhum evento registado ainda.")

        st.markdown("### 🤖 Treinador ChatGPT — Interpretação Tática Live")
        comentario = interpretar_tatica(st.session_state["eventos_live"], st.session_state.get('live_base', {}), 0)
        st.info(comentario)

        if st.button("🔁 Atualizar Previsão com Eventos Live"):
            if 'live_base' not in st.session_state:
                st.error("Preenche e confirma primeiro as estatísticas da 1ª parte!")
            else:
                xg_2p, ajuste, xg_ponderado = calc_xg_live(st.session_state['live_base'], st.session_state["eventos_live"])
                st.markdown(f"### 🟢 Golos Esperados para a 2ª parte: `{xg_2p:.2f}`")
                st.caption(f"xG ponderado: {xg_ponderado:.2f} | Ajuste total: {ajuste:.2f} | Eventos: {len(st.session_state['eventos_live'])}")

        if st.button("🗑️ Limpar eventos LIVE"):
            st.session_state["eventos_live"] = []
            st.success("Lista de eventos live limpa!")

        if st.button("Exportar para Excel (Live)"):
            base = st.session_state.get('live_base', {})
            df_base = pd.DataFrame([base]) if base else pd.DataFrame()
            df_eventos = pd.DataFrame(st.session_state["eventos_live"])
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                if not df_base.empty: df_base.to_excel(writer, sheet_name='Base', index=False)
                df_eventos.to_excel(writer, sheet_name='Eventos', index=False)
            st.download_button("📥 Download Excel (Live)", data=output.getvalue(),
                               file_name="live_analysis.xlsx", mime="application/vnd.ms-excel")

    # ---------- TAB 3 ----------
    with tab3:
        st.header("📺 Player IPTV (M3U/M3U8)")
        st.caption("Suporta HLS (.m3u8). Outros formatos: o browser tenta abrir direto.")
        origem = st.radio("Origem da playlist", ["Ficheiro .m3u","URL da playlist","URL direto da stream"], horizontal=True)

        canais = []; selected_url = None
        if origem == "Ficheiro .m3u":
            up = st.file_uploader("Carrega o ficheiro .m3u", type=["m3u","m3u8"])
            if up is not None:
                txt = up.read().decode("utf-8", errors="ignore"); canais = parse_m3u(txt)
        elif origem == "URL da playlist":
            m3u_url = st.text_input("URL da playlist .m3u/.m3u8")
            if m3u_url and st.button("Tentar carregar (pode falhar por CORS)"):
                st.warning("Se falhar por CORS, cola o conteúdo M3U abaixo.")
            playlist_raw = st.text_area("Ou cola aqui o conteúdo M3U")
            if playlist_raw: canais = parse_m3u(playlist_raw)
        else:
            selected_url = st.text_input("URL direto (.m3u8, .mp4, etc.)")

        if canais:
            nomes = [f"{c.get('group','') + ' | ' if c.get('group') else ''}{c['name']}" for c in canais]
            idx = st.selectbox("Escolhe o canal", list(range(len(nomes))), format_func=lambda i: nomes[i])
            canal = canais[idx]; selected_url = canal["url"]
            c1, c2 = st.columns([3,1])
            with c2:
                if canal.get("logo"): st.image(canal["logo"])
            with c1:
                st.write(f"**Canal:** {canal['name']}  {'(' + canal.get('group','') + ')' if canal.get('group') else ''}")
                st.code(selected_url, language="text")

        if selected_url:
            player_html = f"""
            <div style="width:100%;max-width:980px;margin:0 auto;">
              <video id="video" controls playsinline style="width:100%;height:auto;background:#000;" poster="">
                Seu navegador não suporta vídeo.
              </video>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
            <script>
            (function() {{
              var url = {selected_url!r};
              var video = document.getElementById('video');
              function playDirect(src) {{ video.src = src; video.play().catch(()=>{{}}); }}
              if (url.endsWith('.m3u8')) {{
                if (window.Hls && window.Hls.isSupported()) {{
                  var hls = new Hls({{lowLatencyMode:true}});
                  hls.loadSource(url); hls.attachMedia(video);
                  hls.on(Hls.Events.MANIFEST_PARSED, function() {{ video.play().catch(()=>{{}}); }});
                  hls.on(Hls.Events.ERROR, function(e, data) {{
                    if (data && data.fatal) {{ hls.destroy(); playDirect(url); }}
                  }});
                }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                  playDirect(url);
                }} else {{ playDirect(url); }}
              }} else {{ playDirect(url); }}
            }})();
            </script>
            """
            components.html(player_html, height=520, scrolling=False)
