import streamlit as st
import pandas as pd
from io import BytesIO

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

# ================== Listas e opções ==================
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

# ================== Funções de Cálculo/Análise ==================
def interpretar_tatica(eventos, live_base, resultado_actual):
    if not eventos:
        return "Sem eventos recentes. O treinador mantém o plano inicial."
    comentario = ""
    ultimo = eventos[-1]
    equipa = ultimo["equipa"]
    # --- Substituição
    if ultimo["tipo"] == "Substituição":
        tipo_troca = ultimo.get("tipo_troca", "")
        if tipo_troca in ["Avançado por Médio", "Avançado por Defesa"]:
            if resultado_actual < 0:
                comentario = f"O treinador ({equipa}) abdica de ataque por meio-campo/defesa. Pode querer proteger-se de uma desvantagem maior ou equilibrar jogo."
            else:
                comentario = f"O treinador ({equipa}) está a fechar o jogo, reforçando meio-campo ou defesa, para segurar o resultado."
        elif tipo_troca in ["Defesa por Avançado", "Médio por Avançado"]:
            comentario = f"O treinador ({equipa}) lança mais ataque, quer virar o jogo ou pressionar para marcar."
        elif tipo_troca == "Médio por Médio":
            comentario = f"O treinador ({equipa}) mantém equilíbrio no meio-campo, sem grandes alterações táticas."
        else:
            comentario = f"Substituição sem alteração táctica evidente ({tipo_troca})."
    # --- Mudança de formação
    elif ultimo["tipo"] == "Mudança de formação":
        nova_form = ultimo.get("nova_formacao", "")
        tipo_nova = ultimo.get("tipo_formacao", "")
        if tipo_nova == "Atacante":
            comentario = f"O treinador ({equipa}) muda para formação mais ofensiva ({nova_form}). Procura marcar."
        elif tipo_nova == "Defensivo":
            comentario = f"O treinador ({equipa}) muda para formação defensiva ({nova_form}). Procura segurar resultado."
        else:
            comentario = f"Mudança de formação para ({nova_form}), mas mantém equilíbrio."
    # --- Expulsão/Cartão
    elif ultimo["tipo"] == "Expulsão":
        pos = ultimo.get("posicao", "Desconhecida")
        imp = ultimo.get("importancia", "Normal")
        comentario = f"Expulsão ({imp}) na posição {pos} ({equipa}). A equipa vai ter de reajustar taticamente, provável recuo no bloco."
    elif ultimo["tipo"] == "Amarelo":
        pos = ultimo.get("posicao", "Desconhecida")
        imp = ultimo.get("importancia", "Normal")
        if pos in ["Defesa"]:
            comentario = f"Cartão amarelo para {pos} ({equipa}). Defesa condicionado, pode obrigar a mudanças defensivas."
        else:
            comentario = f"Cartão amarelo para {pos} ({equipa})."
    # --- Penalty/Golo
    elif ultimo["tipo"] == "Penalty":
        comentario = f"Penalty para {equipa}! O treinador pode arriscar tudo (se for a perder) ou manter equilíbrio (se for a ganhar)."
    elif ultimo["tipo"] == "Golo":
        comentario = f"Golo para {equipa}! Expectável resposta táctica do adversário."
    else:
        comentario = "Sem alteração táctica identificada."
    return "🤖 PauloDamas-GPT: " + comentario

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
    # Eventos detalhados com impacto tático
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

# ======= INÍCIO APP =======
st.set_page_config(page_title="PauloDamas-GPT", layout="centered")
st.title("⚽️ PauloDamas-GPT — Análise Pré-Jogo + Live + IA de Treinador")

tab1, tab2 = st.tabs(["⚽ Pré-Jogo", "🔥 Live / 2ª Parte + IA"])

# ========= TAB PRÉ-JOGO =========
with tab1:
    st.header("Análise Pré-Jogo (com fatores avançados)")

    # 1. Formação inicial e abordagem
    st.subheader("Formações e Estratégias")
    colf1, colf2 = st.columns(2)
    with colf1:
        form_casa = st.selectbox("Formação inicial CASA", formacoes_lista, key="form_casa_pre")
        tipo_form_casa = st.selectbox("Abordagem (CASA)", tipos_formacao, key="tipo_form_casa_pre")
    with colf2:
        form_fora = st.selectbox("Formação inicial FORA", formacoes_lista, key="form_fora_pre")
        tipo_form_fora = st.selectbox("Abordagem (FORA)", tipos_formacao, key="tipo_form_fora_pre")

    # 2. Titulares
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

    # 3. Meteorologia e Condições Especiais
    st.subheader("Meteorologia e Condições Especiais")
    meteo = st.selectbox("Tempo esperado", meteos_lista, key="meteo_pre")
    arbitro = st.slider("Nota do Árbitro (0-10)", 0.0, 10.0, 5.0, 0.1, key="arbitro_pre")
    motivacao = st.selectbox("Motivação da equipa", ["Baixa", "Normal", "Alta", "Máxima"], key="motivacao_pre")
    importancia_jogo = st.selectbox("Importância do jogo", ["Pouca", "Normal", "Importante", "Decisivo"], key="importancia_jogo_pre")
    pressao_adeptos = st.selectbox("Pressão dos adeptos", ["Baixa", "Normal", "Alta"], key="pressao_adeptos_pre")
    desgaste_fisico = st.selectbox("Desgaste físico", ["Baixo", "Normal", "Elevado"], key="desgaste_fisico_pre")
    viagem = st.selectbox("Viagem/Calendário", ["Descanso", "Viagem curta", "Viagem longa", "Calendário apertado"], key="viagem_pre")

    # 4. Odds mercado
    st.subheader("Odds da Casa de Apostas (1X2)")
    col_odds1, col_odds2, col_odds3 = st.columns(3)
    with col_odds1:
        odd_casa = st.number_input("Odd Vitória CASA", min_value=1.0, value=1.90)
    with col_odds2:
        odd_empate = st.number_input("Odd EMPATE", min_value=1.0, value=3.10)
    with col_odds3:
        odd_fora = st.number_input("Odd Vitória FORA", min_value=1.0, value=4.10)
    soma_odds = odd_casa + odd_empate + odd_fora
    st.info(f"Soma odds casa de apostas: **{soma_odds:.2f}**")
    banca = st.number_input("💳 Valor atual da banca (€)", min_value=1.0, value=100.0, step=0.01)

    # ---- Totais e médias ----
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

    # 5. Cálculos Odds Justa e EV
    if st.button("Gerar Análise e Odds Justa"):
        # Calcular probabilidade base de cada resultado:
        prob_casa = media_marcados_casa / (media_marcados_casa + media_marcados_fora + 1e-7)
        prob_fora = media_marcados_fora / (media_marcados_casa + media_marcados_fora + 1e-7)
        prob_empate = 1 - (prob_casa + prob_fora)
        # Ajustes de motivação, árbitro, pressão, etc.
        ajuste_motiv = 1.00 + (["Baixa", "Normal", "Alta", "Máxima"].index(motivacao) - 1) * 0.04
        ajuste_arbitro = 1.00 + ((arbitro - 5) / 10) * 0.04
        ajuste_pressao = 1.00 + (["Baixa", "Normal", "Alta"].index(pressao_adeptos)) * 0.02
        ajuste_import = 1.00 + (["Pouca", "Normal", "Importante", "Decisivo"].index(importancia_jogo)) * 0.03
        ajuste_fisico = 1.00 - (["Baixo", "Normal", "Elevado"].index(desgaste_fisico)) * 0.02
        ajuste_viagem = 1.00 - (["Descanso", "Viagem curta", "Viagem longa", "Calendário apertado"].index(viagem)) * 0.01
        # Aplicar todos os ajustes
        ajuste_total = ajuste_motiv * ajuste_arbitro * ajuste_pressao * ajuste_import * ajuste_fisico * ajuste_viagem
        prob_casa *= ajuste_total
        prob_fora *= ajuste_total
        prob_empate = 1 - (prob_casa + prob_fora)

        odd_justa_casa = 1 / (prob_casa + 1e-7)
        odd_justa_empate = 1 / (prob_empate + 1e-7)
        odd_justa_fora = 1 / (prob_fora + 1e-7)

        ev_casa = calc_ev(prob_casa, odd_casa)
        ev_empate = calc_ev(prob_empate, odd_empate)
        ev_fora = calc_ev(prob_fora, odd_fora)

        stake_casa = kelly_criterion(prob_casa, odd_casa, banca)
        stake_empate = kelly_criterion(prob_empate, odd_empate, banca)
        stake_fora = kelly_criterion(prob_fora, odd_fora, banca)

        df_res = pd.DataFrame({
            "Aposta": ["Vitória CASA", "Empate", "Vitória FORA"],
            "Odd": [odd_casa, odd_empate, odd_fora],
            "Odd Justa": [round(odd_justa_casa,2), round(odd_justa_empate,2), round(odd_justa_fora,2)],
            "Prob. (%)": [round(prob_casa*100,1), round(prob_empate*100,1), round(prob_fora*100,1)],
            "EV": [ev_casa, ev_empate, ev_fora],
            "Stake (€)": [round(stake_casa,2), round(stake_empate,2), round(stake_fora,2)],
            "Valor": ["✅" if ev>0 and stake>0 else "❌" for ev,stake in zip([ev_casa,ev_empate,ev_fora],[stake_casa,stake_empate,stake_fora])]
        })

        st.subheader("Resultados da Análise")
        st.dataframe(df_res)
        st.download_button("⬇️ Download Excel", data=to_excel(df_res), file_name="analise_prejogo_paulo_gpt.xlsx")
        st.success("Análise pronta! Consulta apostas recomendadas na tabela acima.")

# ========= TAB LIVE / 2ª PARTE COM ESCUTA =========
with tab2:
    st.header("Live/2ª Parte — Previsão de Golos (Modo Escuta + IA)")

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

    # ---- PAINEL DE INTELIGÊNCIA: PauloDamas-GPT ----
    st.markdown("### 🤖 **PauloDamas-GPT** — Interpretação Tática Live")
    resultado_actual = 0  # Podes ajustar para resultado real do jogo
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
