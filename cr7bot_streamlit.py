import streamlit as st
import pandas as pd
from io import BytesIO
import streamlit_authenticator as stauth
import re
import streamlit.components.v1 as components

# ================== AUTENTICAÇÃO ===================
names = ['Paulo Silva', 'João Ribeiro']
usernames = ['paulo', 'joao']
passwords = ['1234', 'abcd']  # MUDA estas passwords depois!
hashed_passwords = stauth.Hasher(passwords).generate()
authenticator = stauth.Authenticate(
    names, usernames, hashed_passwords, 'cr7bot_app', 'abcdef', cookie_expiry_days=30
)
name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status is False:
    st.error('Username ou password incorretos!')
if authentication_status is None:
    st.warning('Por favor faz login.')
if authentication_status:

    authenticator.logout('Logout', 'sidebar')
    st.sidebar.success(f"Bem-vindo, {name}!")

    # ======= Funções utilitárias =======
    def kelly_criterion(prob, odd, banca, fracao=1):
        b = odd - 1
        q = 1 - prob
        f = ((b * prob - q) / b) * fracao
        return max(0, banca * f)

    def calc_ev(p, o): return round(o * p - 1, 2)

    def to_excel(df):
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Resultados')
        writer.close()
        processed_data = output.getvalue()
        return processed_data

    # ======= NOVA FUNÇÃO DETALHADA =======
    def export_detalhado(live_base, eventos, xg_2p, ajuste, xg_ponderado):
        pesos_aplicados = []
        xg_total_1p = live_base["xg_casa"] + live_base["xg_fora"]
        xgot_total_1p = live_base["xgot_casa"] + live_base["xgot_fora"]
        xg_pond = 0.7 * xg_total_1p + 0.3 * xgot_total_1p
        diff_rating = live_base["rating_casa"] - live_base["rating_fora"]
        pesos_aplicados.append(("Diferença rating", diff_rating * 0.10))
        if live_base["grandes_ocasioes_casa"] + live_base["grandes_ocasioes_fora"] >= 3:
            pesos_aplicados.append(("Grandes ocasiões >=3", 0.10))
        if live_base["remates_baliza_casa"] + live_base["remates_baliza_fora"] >= 6:
            pesos_aplicados.append(("Remates baliza >=6", 0.05))
        if xg_pond >= 1.0:
            pesos_aplicados.append(("xG ponderado >=1", 0.10))
        if live_base["remates_ferro_casa"] + live_base["remates_ferro_fora"]:
            pesos_aplicados.append(("Remates ao ferro", (live_base["remates_ferro_casa"] + live_base["remates_ferro_fora"]) * 0.07))
        if live_base["amarelos_casa"] >= 3:
            pesos_aplicados.append(("3+ amarelos CASA", -0.05))
        if live_base["amarelos_fora"] >= 3:
            pesos_aplicados.append(("3+ amarelos FORA", -0.05))
        if live_base["vermelhos_casa"]:
            pesos_aplicados.append(("Vermelhos CASA", -0.20 * live_base["vermelhos_casa"]))
        if live_base["vermelhos_fora"]:
            pesos_aplicados.append(("Vermelhos FORA", 0.20 * live_base["vermelhos_fora"]))
        for ev in eventos:
            peso = 0
            if ev["tipo"] == "Golo":
                peso = 0.2 if ev["equipa"] == "Casa" else -0.2
            elif ev["tipo"] == "Expulsão":
                peso = -0.15 if ev["equipa"] == "Casa" else 0.15
            elif ev["tipo"] == "Penalty":
                peso = 0.25 if ev["equipa"] == "Casa" else -0.25
            elif ev["tipo"] == "Substituição":
                mapping = {
                    "Avançado por Médio": -0.08, "Avançado por Defesa": -0.12,
                    "Médio por Avançado": 0.07, "Defesa por Avançado": 0.10, "Médio por Médio": 0
                }
                base = mapping.get(ev.get("tipo_troca"), 0)
                peso = base if ev["equipa"] == "Casa" else -base
            elif ev["tipo"] == "Mudança de formação":
                impacto = 0.08 if ev.get("tipo_formacao") == "Atacante" else -0.08 if ev.get("tipo_formacao") == "Defensivo" else 0
                peso = impacto if ev["equipa"] == "Casa" else -impacto
            elif ev["tipo"] == "Amarelo":
                mapping = {"Defesa": -0.05, "Médio": -0.03, "Avançado": -0.01}
                base = mapping.get(ev.get("posicao"), 0)
                peso = base if ev["equipa"] == "Casa" else -base
            pesos_aplicados.append((f"{ev['tipo']} ({ev['equipa']})", peso))
        df_base = pd.DataFrame([live_base])
        df_eventos = pd.DataFrame(eventos)
        df_pesos = pd.DataFrame(pesos_aplicados, columns=["Fator", "Peso aplicado"])
        df_resultado = pd.DataFrame([{"xg_ponderado": xg_ponderado, "Ajuste final": ajuste, "xg_2p": xg_2p}])
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_base.to_excel(writer, sheet_name='Base', index=False)
            df_eventos.to_excel(writer, sheet_name='Eventos', index=False)
            df_pesos.to_excel(writer, sheet_name='Pesos', index=False)
            df_resultado.to_excel(writer, sheet_name='Resultado', index=False)
        return output.getvalue()
    # ================== INÍCIO APP ===================
    st.set_page_config(page_title="CR7 BOT — Treinador ChatGPT", layout="centered")
    st.title("⚽️ CR7 BOT — Treinador ChatGPT (Pré-Jogo + Live + Inteligência)")

    tab1, tab2 = st.tabs(["⚽ Pré-Jogo", "🔥 Live / 2ª Parte + Treinador ChatGPT"])

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

        # ----- 4. Totais de Golos & Jogos -----
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
            evento = {"tipo": tipo_evento, "equipa": equipa_evento, "detalhes": detalhes_evento}
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
                st.session_state["analise_final"] = {"xg_2p": xg_2p, "ajuste": ajuste, "xg_ponderado": xg_ponderado}
                st.markdown(f"### 🟢 **Golos Esperados para a 2ª parte:** `{xg_2p:.2f}`")
                if xg_2p >= 1.6:
                    st.success("⚽ Perspetiva de pelo menos 1 golo. Over 1.5 na 2ª parte pode ter valor.")
                elif xg_2p >= 1.2:
                    st.info("⚠️ Espera-se 1 golo, com hipótese de 2. Over 1.0/1.25 pode ter valor.")
                else:
                    st.warning("🔒 Jogo mais fechado. Cuidado com apostas em muitos golos na 2ª parte.")
                st.info(f"xG ponderado: {xg_ponderado:.2f} | Ajuste: {ajuste:.2f} | Eventos: {len(st.session_state['eventos_live'])}")

        if "analise_final" in st.session_state:
            if st.button("📥 Exportar Análise Detalhada"):
                data_excel = export_detalhado(st.session_state['live_base'], st.session_state['eventos_live'],
                                              st.session_state["analise_final"]["xg_2p"],
                                              st.session_state["analise_final"]["ajuste"],
                                              st.session_state["analise_final"]["xg_ponderado"])
                st.download_button(label="Download Excel Detalhado", data=data_excel,
                                   file_name="analise_detalhada.xlsx", mime="application/vnd.ms-excel")

            if st.button("🗑️ Limpar Análise Final"):
                del st.session_state["analise_final"]
                st.success("Análise final limpa!")

        if st.button("🗑️ Limpar eventos LIVE"):
            st.session_state["eventos_live"] = []
            st.success("Lista de eventos live limpa!")
