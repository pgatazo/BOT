import streamlit as st
st.set_page_config(page_title="CR7 BOT — Treinador ChatGPT", layout="centered")  # tem de ser o 1º st.*

import pandas as pd
from io import BytesIO
import re
import streamlit.components.v1 as components

import bcrypt
import streamlit_authenticator as stauth

# --- Utilizadores e palavras-passe (texto plano -> serão hashed em runtime)
USERS = [
    {"username": "paulo", "name": "Paulo Silva", "password": "1234"},
    {"username": "joao",  "name": "João Ribeiro", "password": "abcd"},
]

# Gera credenciais no formato da API nova
credentials = {"usernames": {}}
for u in USERS:
    # hash seguro; em produção, grava estes hashes e NÃO guardes as passwords em claro
    pwd_hash = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt()).decode()
    credentials["usernames"][u["username"]] = {
        "name": u["name"],
        "password": pwd_hash,
    }

# Instancia o autenticador (API ≥ 0.3.x)
authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="cr7bot_app",
    key="abcdef",
    cookie_expiry_days=30,
    preauthorized=[]
)

name, authentication_status, username = authenticator.login("Login", "main")

# --- Listas para dropdowns (SEM indentação extra)
formacoes_lista = [
    "4-4-2", "4-3-3", "4-2-3-1", "3-5-2", "3-4-3", "5-3-2", "4-1-4-1", "4-5-1",
    "3-4-2-1", "3-4-1-2", "3-6-1", "4-4-1-1", "4-3-1-2", "4-2-2-2", "4-3-2-1",
    "5-4-1", "5-2-3", "5-2-1-2", "4-1-2-1-2", "3-5-1-1", "4-1-2-3", "3-3-3-1",
    "3-2-3-2", "3-3-1-3", "4-2-4", "4-3-2", "3-2-5", "2-3-5", "4-2-1-3", "Outro"
]
tipos_formacao = ["Atacante", "Equilibrado", "Defensivo"]
tipos_troca = [
    "Avançado por Avançado", "Avançado por Médio", "Avançado por Defesa",
    "Médio por Avançado", "Médio por Médio", "Médio por Defesa",
    "Defesa por Avançado", "Defesa por Médio", "Defesa por Defesa", "Outro"
]
posicoes_lista = ["GR", "Defesa", "Médio", "Avançado"]
importancias_lista = ["Peça chave", "Importante", "Normal"]
meteos_lista = ["Sol", "Chuva", "Nublado", "Vento", "Frio", "Outro"]


    # ========= INTELIGÊNCIA TÁTICA / SUGESTÃO DE FORMAÇÃO =========
    def sugestao_formacao(eventos):
        if not eventos:
            return ""
        ultimo = eventos[-1]
        if ultimo["tipo"] == "Substituição":
            if ultimo.get("tipo_troca") in ["Avançado por Médio", "Avançado por Defesa"]:
                return "⚠️ Sugerido: equipa pode alterar para sistema mais defensivo (ex: 4-5-1, 5-4-1, 4-2-3-1)."
            if ultimo.get("tipo_troca") in ["Defesa por Avançado", "Médio por Avançado"]:
                return "⚡ Sugerido: treinador procura mais ataque (ex: 4-3-3 atacante, 4-2-4, 3-4-3)."
        return ""

    def interpretar_tatica(eventos, live_base, resultado_actual):
        comentario = ""
        ultimo = eventos[-1] if eventos else {}
        equipa = ultimo.get("equipa", "")
        if not eventos:
            return "Sem eventos recentes. O treinador mantém o plano inicial."
        if ultimo["tipo"] == "Substituição":
            tipo_troca = ultimo.get("tipo_troca", "")
            if tipo_troca in ["Avançado por Médio", "Avançado por Defesa"]:
                comentario = f"O treinador ({equipa}) abdica de ataque por meio-campo/defesa. Pode estar a proteger vantagem ou fechar jogo."
            elif tipo_troca in ["Defesa por Avançado", "Médio por Avançado"]:
                comentario = f"O treinador ({equipa}) lança mais ataque, quer marcar ou virar o resultado."
            elif tipo_troca == "Médio por Médio":
                comentario = f"O treinador ({equipa}) mantém equilíbrio no meio-campo."
            else:
                comentario = f"Substituição sem alteração táctica evidente ({tipo_troca})."
        elif ultimo["tipo"] == "Mudança de formação":
            nova_form = ultimo.get("nova_formacao", "")
            tipo_nova = ultimo.get("tipo_formacao", "")
            if tipo_nova == "Atacante":
                comentario = f"O treinador ({equipa}) muda para formação ofensiva ({nova_form}). Procura marcar."
            elif tipo_nova == "Defensivo":
                comentario = f"O treinador ({equipa}) muda para formação defensiva ({nova_form}). Procura segurar resultado."
            else:
                comentario = f"Mudança de formação para ({nova_form}), mantendo equilíbrio."
        elif ultimo["tipo"] == "Expulsão":
            pos = ultimo.get("posicao", "Desconhecida")
            imp = ultimo.get("importancia", "Normal")
            comentario = f"Expulsão ({imp}) na posição {pos} ({equipa}). Vai obrigar a ajustar bloco."
        elif ultimo["tipo"] == "Amarelo":
            pos = ultimo.get("posicao", "Desconhecida")
            imp = ultimo.get("importancia", "Normal")
            comentario = f"Cartão amarelo para {pos} ({equipa}) — jogador condicionado."
        elif ultimo["tipo"] == "Penalty":
            comentario = f"Penalty para {equipa}! Expectável reação tática dependendo do resultado."
        elif ultimo["tipo"] == "Golo":
            comentario = f"Golo para {equipa}! Expectável ajuste do adversário."
        else:
            comentario = "Sem alteração táctica identificada."
        comentario += "\n" + sugestao_formacao(eventos)
        return "🤖 Treinador ChatGPT: " + comentario

    # ======= Cálculo de xG Live =======
    def calc_xg_live(dados, eventos):
        xg_total_1p = dados["xg_casa"] + dados["xg_fora"]
        xgot_total_1p = dados["xgot_casa"] + dados["xgot_fora"]
        xg_ponderado = 0.7 * xg_total_1p + 0.3 * xgot_total_1p
        remates_baliza_total = dados["remates_baliza_casa"] + dados["remates_baliza_fora"]
        grandes_ocasioes_total = dados["grandes_ocasioes_casa"] + dados["grandes_ocasioes_fora"]
        remates_ferro_total = dados["remates_ferro_casa"] + dados["remates_ferro_fora"]
        ajuste = 1.0
        diff_rating = dados["rating_casa"] - dados["rating_fora"]
        ajuste += diff_rating * 0.10
        if grandes_ocasioes_total >= 3: ajuste += 0.10
        if remates_baliza_total >= 6: ajuste += 0.05
        if xg_ponderado >= 1.0: ajuste += 0.10
        if remates_ferro_total: ajuste += remates_ferro_total * 0.07
        if dados["amarelos_casa"] >= 3: ajuste -= 0.05
        if dados["amarelos_fora"] >= 3: ajuste -= 0.05
        if dados["vermelhos_casa"]: ajuste -= 0.20 * dados["vermelhos_casa"]
        if dados["vermelhos_fora"]: ajuste += 0.20 * dados["vermelhos_fora"]
        for ev in eventos:
            tipo = ev["tipo"]
            eq = ev["equipa"]
            if tipo == "Golo":
                ajuste += 0.2 if eq == "Casa" else -0.2
            elif tipo == "Expulsão":
                ajuste -= 0.15 if eq == "Casa" else 0.15
            elif tipo == "Penalty":
                ajuste += 0.25 if eq == "Casa" else -0.25
            elif tipo == "Substituição":
                peso = 0
                if ev.get("tipo_troca") == "Avançado por Médio":
                    peso = -0.08
                elif ev.get("tipo_troca") == "Avançado por Defesa":
                    peso = -0.12
                elif ev.get("tipo_troca") == "Médio por Avançado":
                    peso = +0.07
                elif ev.get("tipo_troca") == "Defesa por Avançado":
                    peso = +0.10
                elif ev.get("tipo_troca") == "Médio por Médio":
                    peso = 0
                ajuste += peso if eq == "Casa" else -peso
            elif tipo == "Mudança de formação":
                impacto = 0.08 if ev.get("tipo_formacao") == "Atacante" else -0.08 if ev.get("tipo_formacao") == "Defensivo" else 0
                ajuste += impacto if eq == "Casa" else -impacto
            elif tipo == "Amarelo":
                pos = ev.get("posicao", "Desconhecida")
                if pos == "Defesa":
                    ajuste -= 0.05 if eq == "Casa" else -0.05
                elif pos == "Médio":
                    ajuste -= 0.03 if eq == "Casa" else -0.03
                elif pos == "Avançado":
                    ajuste -= 0.01 if eq == "Casa" else -0.01
        xg_2p = xg_ponderado * ajuste
        return xg_2p, ajuste, xg_ponderado

    # ======= Parser M3U =======
    def parse_m3u(m3u_text: str):
        """
        Devolve lista de canais: [{"name":..., "url":..., "logo":..., "group":...}]
        Suporta #EXTM3U / #EXTINF.
        """
        channels = []
        current = {}
        for line in m3u_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#EXTM3U"):
                continue
            if line.startswith("#EXTINF"):
                name_match = line.split(",", 1)
                name = name_match[1].strip() if len(name_match) > 1 else "Sem nome"
                logo = ""
                group = ""
                m_logo = re.search(r'tvg-logo="([^"]*)"', line)
                m_group = re.search(r'group-title="([^"]*)"', line)
                if m_logo: logo = m_logo.group(1)
                if m_group: group = m_group.group(1)
                current = {"name": name, "logo": logo, "group": group}
            elif not line.startswith("#") and current:
                current["url"] = line
                channels.append(current)
                current = {}
        return channels

    # ================== INÍCIO APP (conteúdo autenticado) ===================
    st.title("⚽️ CR7 BOT — Treinador ChatGPT (Pré-Jogo + Live + Inteligência)")
    tab1, tab2, tab3 = st.tabs([
        "⚽ Pré-Jogo",
        "🔥 Live / 2ª Parte + Treinador ChatGPT",
        "📺 Player IPTV"
    ])

    # ========= TAB PRÉ-JOGO =========
    with tab1:
        st.header("Análise Pré-Jogo")

        # ----- 1. Formação inicial e abordagem -----
        st.subheader("Formações e Estratégias")
        colf1, colf2 = st.columns(2)
        with colf1:
            form_casa = st.selectbox("Formação inicial CASA", formacoes_lista, key="form_casa_pre")
            tipo_form_casa = st.selectbox("Abordagem (CASA)", tipos_formacao, key="tipo_form_casa_pre")
        with colf2:
            form_fora = st.selectbox("Formação inicial FORA", formacoes_lista, key="form_fora_pre")
            tipo_form_fora = st.selectbox("Abordagem (FORA)", tipos_formacao, key="tipo_form_fora_pre")

        # ----- 2. Titulares -----
        st.subheader("Titulares disponíveis")
        titulares_casa = st.number_input("Quantos titulares disponíveis na CASA? (0-11)", 0, 11, 11, key="titulares_casa")
        ausentes_casa = []
        if titulares_casa < 11:
            n_ausentes_casa = 11 - titulares_casa
            st.warning(f"⚠️ Atenção: {n_ausentes_casa} titular(es) ausente(s) na CASA!")
            for i in range(n_ausentes_casa):
                st.markdown(f"**Ausente #{i+1} (CASA):**")
                pos = st.selectbox(f"Posição", posicoes_lista, key=f"pos_casa_{i}")
                imp = st.selectbox("Importância", importancias_lista, key=f"imp_casa_{i}")
                ausentes_casa.append({"posição": pos, "importancia": imp})
        titulares_fora = st.number_input("Quantos titulares disponíveis na FORA? (0-11)", 0, 11, 11, key="titulares_fora")
        ausentes_fora = []
        if titulares_fora < 11:
            n_ausentes_fora = 11 - titulares_fora
            st.warning(f"⚠️ Atenção: {n_ausentes_fora} titular(es) ausente(s) na FORA!")
            for i in range(n_ausentes_fora):
                st.markdown(f"**Ausente #{i+1} (FORA):**")
                pos = st.selectbox(f"Posição", posicoes_lista, key=f"pos_fora_{i}")
                imp = st.selectbox("Importância", importancias_lista, key=f"imp_fora_{i}")
                ausentes_fora.append({"posição": pos, "importancia": imp})

        # ----- 3. Meteorologia, Árbitro, Motivação -----
        st.subheader("Condições Especiais")
        meteo = st.selectbox("Tempo esperado", meteos_lista, key="meteo_pre")
        arbitro_nota = st.slider("Nota do Árbitro (0=caseiro, 10=deixa jogar)", 0.0, 10.0, 5.0, step=0.1, key="arbitro_pre")
        motivacao = st.selectbox("Motivação principal do jogo", ["Normal", "Alta (decisão)", "Baixa"], key="motivacao_pre")

        # ----- 4. Totais de Golos & Jogos (médias automáticas) -----
        with st.form("totais_golos_form"):
            st.subheader("Equipa da CASA")
            total_golos_casa = st.number_input("Total de golos marcados (CASA)", min_value=0, value=0, key="golos_casa")
            total_sofridos_casa = st.number_input("Total de golos sofridos (CASA)", min_value=0, value=0, key="sofridos_casa")
            jogos_casa = st.number_input("Nº de jogos (CASA)", min_value=1, value=5, key="jogos_casa")
            media_marcados_casa = total_golos_casa / jogos_casa
            media_sofridos_casa = total_sofridos_casa / jogos_casa
            st.info(f"Média marcados: **{media_marcados_casa:.2f}** | Média sofridos: **{media_sofridos_casa:.2f}**")

            st.subheader("Equipa de FORA")
            total_golos_fora = st.number_input("Total de golos marcados (FORA)", min_value=0, value=0, key="golos_fora")
            total_sofridos_fora = st.number_input("Total de golos sofridos (FORA)", min_value=0, value=0, key="sofridos_fora")
            jogos_fora = st.number_input("Nº de jogos (FORA)", min_value=1, value=5, key="jogos_fora")
            media_marcados_fora = total_golos_fora / jogos_fora
            media_sofridos_fora = total_sofridos_fora / jogos_fora
            st.info(f"Média marcados: **{media_marcados_fora:.2f}** | Média sofridos: **{media_sofridos_fora:.2f}**")

            st.subheader("Confrontos Diretos (H2H)")
            total_golos_h2h_casa = st.number_input("Total golos marcados H2H (CASA)", min_value=0, value=0, key="golos_h2h_casa")
            total_golos_h2h_fora = st.number_input("Total golos marcados H2H (FORA)", min_value=0, value=0, key="golos_h2h_fora")
            jogos_h2h = st.number_input("Nº de jogos (H2H)", min_value=1, value=5, key="jogos_h2h")
            media_h2h_casa = total_golos_h2h_casa / jogos_h2h
            media_h2h_fora = total_golos_h2h_fora / jogos_h2h
            st.info(f"Média H2H CASA: **{media_h2h_casa:.2f}** | Média H2H FORA: **{media_h2h_fora:.2f}**")

            confirm1 = st.form_submit_button("✅ Confirmar Totais")
        if confirm1:
            st.session_state['medias'] = {
                'marc_casa': media_marcados_casa,
                'sofr_casa': media_sofridos_casa,
                'marc_fora': media_marcados_fora,
                'sofr_fora': media_sofridos_fora,
                'marc_h2h_casa': media_h2h_casa,
                'marc_h2h_fora': media_h2h_fora,
            }
            st.success("Totais confirmados!")

        # --- 5. ODDS DE MERCADO e NORMALIZAÇÃO ---
        st.subheader("Odds de Mercado (Casa de Apostas)")
        colod1, colod2, colod3 = st.columns(3)
        with colod1:
            odd_casa = st.number_input("Odd CASA", min_value=1.01, value=1.80, key="odd_casa")
        with colod2:
            odd_empate = st.number_input("Odd EMPATE", min_value=1.01, value=3.40, key="odd_empate")
        with colod3:
            odd_fora = st.number_input("Odd FORA", min_value=1.01, value=4.20, key="odd_fora")
        odd_btts_sim = st.number_input("Odd Ambas Marcam SIM", min_value=1.01, value=1.90, key="odd_btts_sim")
        odd_btts_nao = st.number_input("Odd Ambas Marcam NÃO", min_value=1.01, value=1.80, key="odd_btts_nao")
        soma_1x2 = odd_casa + odd_empate + odd_fora
        soma_btts = odd_btts_sim + odd_btts_nao
        st.info(f"Soma odds 1X2: **{soma_1x2:.2f}** (máximo normal: 8.55) | Soma BTTS: **{soma_btts:.2f}**")

        # --- EXPORTAÇÃO DADOS ---
        if st.button("Exportar para Excel (Pré-Jogo)"):
            dados = {
                "Odd": ["Casa", "Empate", "Fora", "BTTS Sim", "BTTS Não"],
                "Valor": [odd_casa, odd_empate, odd_fora, odd_btts_sim, odd_btts_nao]
            }
            df = pd.DataFrame(dados)
            st.download_button(
                label="📥 Download Excel",
                data=to_excel(df),
                file_name="odds_pre_jogo.xlsx",
                mime="application/vnd.ms-excel"
            )

    # ========= TAB LIVE / 2ª PARTE COM ESCUTA =========
    with tab2:
        st.header("Live/2ª Parte — Previsão de Golos (Modo Escuta + Treinador ChatGPT)")

        # --- Formação inicial live + abordagem ---
        st.subheader("Formações e Estratégias (início da 2ª parte)")
        col_livef1, col_livef2 = st.columns(2)
        with col_livef1:
            form_casa_live = st.selectbox("Formação CASA (Live)", formacoes_lista, key="form_casa_live")
            tipo_form_casa_live = st.selectbox("Abordagem CASA", tipos_formacao, key="tipo_form_casa_live")
        with col_livef2:
            form_fora_live = st.selectbox("Formação FORA (Live)", formacoes_lista, key="form_fora_live")
            tipo_form_fora_live = st.selectbox("Abordagem FORA", tipos_formacao, key="tipo_form_fora_live")

        # --- Estatísticas da 1ª Parte
        with st.form("form_live_base"):
            resultado_intervalo = st.text_input("Resultado ao intervalo", value="0-0")
            xg_casa = st.number_input("xG equipa da CASA (1ª parte)", min_value=0.0, value=0.0, step=0.01)
            xg_fora = st.number_input("xG equipa de FORA (1ª parte)", min_value=0.0, value=0.0, step=0.01)
            xgot_casa = st.number_input("xGOT equipa da CASA (1ª parte)", min_value=0.0, value=0.0, step=0.01)
            xgot_fora = st.number_input("xGOT equipa de FORA (1ª parte)", min_value=0.0, value=0.0, step=0.01)
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
            rating_casa = st.number_input("Rating global da equipa da CASA (0-10)", min_value=0.0, max_value=10.0, value=7.0, step=0.01)
            rating_fora = st.number_input("Rating global da equipa de FORA (0-10)", min_value=0.0, max_value=10.0, value=6.9, step=0.01)
            confirmar_base = st.form_submit_button("✅ Confirmar Dados 1ª Parte")
        if confirmar_base:
            st.session_state['live_base'] = {
                "xg_casa": xg_casa, "xg_fora": xg_fora,
                "xgot_casa": xgot_casa, "xgot_fora": xgot_fora,
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

        # --- ESCUTA DE EVENTOS LIVE ---
        if "eventos_live" not in st.session_state:
            st.session_state["eventos_live"] = []

        st.subheader("➕ Adicionar Evento LIVE")
        tipo_evento = st.selectbox("Tipo de evento", ["Golo", "Expulsão", "Penalty", "Substituição", "Mudança de formação", "Amarelo"])
        equipa_evento = st.selectbox("Equipa", ["Casa", "Fora"])
        detalhes_evento = st.text_input("Detalhes (opcional)", key="detalhes_ev")

        posicao_ev, tipo_troca_ev, nova_form_ev, tipo_form_ev, imp_ev = None, None, None, None, None
        if tipo_evento in ["Expulsão", "Amarelo"]:
            posicao_ev = st.selectbox("Posição do jogador", posicoes_lista, key="pos_ev")
            imp_ev = st.selectbox("Importância do jogador", importancias_lista, key="imp_ev")
        if tipo_evento == "Substituição":
            tipo_troca_ev = st.selectbox("Tipo de substituição", tipos_troca, key="troca_ev")
        if tipo_evento == "Mudança de formação":
            nova_form_ev = st.selectbox("Nova formação", formacoes_lista, key="nova_form_ev")
            tipo_form_ev = st.selectbox("Nova abordagem", tipos_formacao, key="tipo_form_ev")

        if st.button("Adicionar evento LIVE"):
            evento = {
                "tipo": tipo_evento,
                "equipa": equipa_evento,
                "detalhes": detalhes_evento
            }
            if posicao_ev: evento["posicao"] = posicao_ev
            if tipo_troca_ev: evento["tipo_troca"] = tipo_troca_ev
            if nova_form_ev: evento["nova_formacao"] = nova_form_ev
            if tipo_form_ev: evento["tipo_formacao"] = tipo_form_ev
            if imp_ev: evento["importancia"] = imp_ev
            st.session_state["eventos_live"].append(evento)
            st.success("Evento adicionado! Atualiza previsão em baixo.")

        st.markdown("#### Eventos registados:")
        if st.session_state["eventos_live"]:
            for i, ev in enumerate(st.session_state["eventos_live"], 1):
                info_ev = f"{i}. {ev['tipo']} | {ev['equipa']}"
                if "posicao" in ev: info_ev += f" | {ev['posicao']}"
                if "tipo_troca" in ev: info_ev += f" | {ev['tipo_troca']}"
                if "nova_formacao" in ev: info_ev += f" | Nova: {ev['nova_formacao']} ({ev.get('tipo_formacao','')})"
                if "importancia" in ev: info_ev += f" | {ev['importancia']}"
                if ev['detalhes']: info_ev += f" | {ev['detalhes']}"
                st.write(info_ev)
        else:
            st.write("Nenhum evento registado ainda.")

        # ---- PAINEL DE INTELIGÊNCIA: Treinador ChatGPT ----
        st.markdown("### 🤖 **Treinador ChatGPT** — Interpretação Tática Live")
        resultado_actual = 0
        comentario = interpretar_tatica(st.session_state["eventos_live"], st.session_state.get('live_base', {}), resultado_actual)
        st.info(comentario)

        if st.button("🔁 Atualizar Previsão com Eventos Live"):
            if 'live_base' not in st.session_state:
                st.error("Preenche e confirma primeiro as estatísticas da 1ª parte!")
            else:
                xg_2p, ajuste, xg_ponderado = calc_xg_live(st.session_state['live_base'], st.session_state["eventos_live"])
                st.markdown(f"### 🟢 **Golos Esperados para a 2ª parte:** `{xg_2p:.2f}`")
                if xg_2p >= 1.6:
                    st.success("⚽ Perspetiva de pelo menos 1 golo. Over 1.5 na 2ª parte pode ter valor.")
                elif xg_2p >= 1.2:
                    st.info("⚠️ Espera-se 1 golo, com hipótese de 2. Over 1.0/1.25 pode ter valor.")
                else:
                    st.warning("🔒 Jogo mais fechado. Cuidado com apostas em muitos golos na 2ª parte.")

                st.info(f"""
                **Resumo do Ajuste:**  
                xG ponderado: {xg_ponderado:.2f}  
                Ajuste total (rating/eventos): {ajuste:.2f}
                Eventos registados: {len(st.session_state["eventos_live"])}
                """)

        if st.button("🗑️ Limpar eventos LIVE"):
            st.session_state["eventos_live"] = []
            st.success("Lista de eventos live limpa!")

        # EXPORTAÇÃO LIVE (eventos + base)
        if st.button("Exportar para Excel (Live)"):
            base = st.session_state.get('live_base', {})
            df_base = pd.DataFrame([base])
            df_eventos = pd.DataFrame(st.session_state["eventos_live"])
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_base.to_excel(writer, sheet_name='Base', index=False)
                df_eventos.to_excel(writer, sheet_name='Eventos', index=False)
            st.download_button(
                label="📥 Download Excel (Live)",
                data=output.getvalue(),
                file_name="live_analysis.xlsx",
                mime="application/vnd.ms-excel"
            )

    # ========= TAB PLAYER IPTV =========
    with tab3:
        st.header("📺 Player IPTV (M3U/M3U8)")
        st.caption("Suporta streams HLS (.m3u8). Para outras extensões, o browser tenta abrir direto.")

        origem = st.radio("Como queres carregar a playlist?", ["Ficheiro .m3u", "URL da playlist", "URL direto da stream"], horizontal=True)

        canais = []
        selected_url = None

        if origem == "Ficheiro .m3u":
            up = st.file_uploader("Carrega o ficheiro .m3u", type=["m3u", "m3u8"])
            if up is not None:
                txt = up.read().decode("utf-8", errors="ignore")
                canais = parse_m3u(txt)
        elif origem == "URL da playlist":
            m3u_url = st.text_input("URL da playlist .m3u/.m3u8")
            if m3u_url:
                if st.button("Tentar carregar playlist (pode falhar por CORS)"):
                    st.warning("Se não carregar por CORS, cola manualmente abaixo:")
            playlist_raw = st.text_area("Ou cola aqui o conteúdo M3U")
            if playlist_raw:
                canais = parse_m3u(playlist_raw)
        else:  # URL direto
            selected_url = st.text_input("URL direto da stream (.m3u8, .mp4, etc.)")

        if canais:
            nomes = [f"{c.get('group','') + ' | ' if c.get('group') else ''}{c['name']}" for c in canais]
            idx = st.selectbox("Escolhe o canal", list(range(len(nomes))), format_func=lambda i: nomes[i])
            canal = canais[idx]
            selected_url = canal["url"]
            col1, col2 = st.columns([3, 1])
            with col2:
                if canal.get("logo"):
                    st.image(canal["logo"])
            with col1:
                st.write(f"**Canal:** {canal['name']}  {'(' + canal.get('group','') + ')' if canal.get('group') else ''}")
                st.code(selected_url, language="text")

        if selected_url:
            player_html = f"""
            <div style="width:100%;max-width:980px;margin:0 auto;">
              <video id="video" controls playsinline style="width:100%;height:auto;background:#000;" poster="">
                Seu navegador não suporta vídeo.
              </video>
              <div style="margin-top:8px;font:14px Arial, sans-serif;">
                <span>URL:</span> <code style="word-break:break-all">{selected_url}</code>
              </div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
            <script>
            (function() {{
              var url = {selected_url!r};
              var video = document.getElementById('video');
              function playDirect(src) {{
                video.src = src;
                video.play().catch(()=>{{}});
              }}
              if (url.endsWith('.m3u8')) {{
                if (window.Hls && window.Hls.isSupported()) {{
                  var hls = new Hls({{lowLatencyMode:true}});
                  hls.loadSource(url);
                  hls.attachMedia(video);
                  hls.on(Hls.Events.MANIFEST_PARSED, function() {{ video.play().catch(()=>{{}}); }});
                  hls.on(Hls.Events.ERROR, function(e, data) {{
                    if (data && data.fatal) {{
                      console.warn('HLS fatal error, trying native:', data);
                      hls.destroy();
                      playDirect(url);
                    }}
                  }});
                }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                  playDirect(url);
                }} else {{
                  playDirect(url);
                }}
              }} else {{
                playDirect(url);
              }}
            }})();
            </script>
            """
            components.html(player_html, height=520, scrolling=False)

        st.info("Dica: se o canal não abrir por CORS, usa um proxy próprio ou um URL que permita acesso direto.")
        st.caption("⚠️ Certifica-te de que tens direitos para ver os streams. Não uses fontes ilegais.")

# =========== FIM ===========


