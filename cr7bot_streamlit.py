import streamlit as st
import hashlib
import json
import os
import pandas as pd     # <--- Adiciona isto!
from io import BytesIO  # <--- E isto também!


USERS_FILE = "users.json"

# ---------- Função para hashear passwords ----------
def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

# ---------- Carregar utilizadores do ficheiro ----------
def load_users():
    if not os.path.exists(USERS_FILE):
        # Só tu de início!
        base_users = {
            "paulo": hash_pwd("damas2024"),
            "admin": hash_pwd("admin123")
        }
        with open(USERS_FILE, "w") as f:
            json.dump(base_users, f)
    with open(USERS_FILE, "r") as f:
        return json.load(f)

USERS = load_users()

def login_screen():
    st.title("🔒 Login - PauloDamas-GPT")
    username = st.text_input("Utilizador")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Entrar")

    if login_btn:
        if username in USERS and hash_pwd(password) == USERS[username]:
            st.success(f"Bem-vindo, {username}!")
            st.session_state.login_success = True
            st.session_state.logged_user = username
        else:
            st.error("Credenciais inválidas ou não autorizado!")
    return st.session_state.get("login_success", False)

if "login_success" not in st.session_state or not st.session_state["login_success"]:
    if not login_screen():
        st.stop()

# ---- App continua aqui ----
st.write("⚽ Bem-vindo ao PauloDamas-GPT!")

# --- Bloco de Ligas e Equipas Personalizadas ---
CUSTOM_FILE = "ligas_e_equipas_custom.json"

def load_custom():
    if os.path.exists(CUSTOM_FILE):
        with open(CUSTOM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

def save_custom(data):
    with open(CUSTOM_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Ligas fixas
ligas_fixas = {
    "Liga Betclic": [
        "Benfica", "Porto", "Sporting", "Braga", "Guimarães", "Casa Pia", "Boavista", "Estoril",
        "Famalicão", "Farense", "Gil Vicente", "Moreirense", "Portimonense", "Rio Ave", "Arouca", "Vizela", "Chaves"
    ],
    "Premier League": [
        "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Burnley", "Chelsea",
        "Crystal Palace", "Everton", "Fulham", "Liverpool", "Luton Town", "Manchester City",
        "Manchester United", "Newcastle", "Nottingham Forest", "Sheffield United", "Tottenham",
        "West Ham", "Wolves"
    ],
    "La Liga": [
        "Real Madrid", "Barcelona", "Atlético Madrid", "Sevilla", "Betis", "Valencia", "Villarreal",
        "Real Sociedad", "Athletic Bilbao", "Getafe", "Osasuna", "Celta Vigo", "Granada",
        "Las Palmas", "Mallorca", "Alaves", "Rayo Vallecano", "Almeria", "Girona", "Cadiz"
    ]
}

custom_data = load_custom()
ligas_custom = custom_data.get("ligas", {})

todas_ligas = list(ligas_fixas.keys()) + list(ligas_custom.keys()) + ["Outra (nova liga personalizada)"]

st.subheader("Seleção de Liga")
liga_escolhida = st.selectbox("Liga:", todas_ligas, key="liga")

# Adicionar nova liga personalizada
if liga_escolhida == "Outra (nova liga personalizada)":
    nova_liga = st.text_input("Nome da nova liga personalizada:", key="nova_liga")
    if nova_liga:
        if nova_liga not in todas_ligas:
            ligas_custom[nova_liga] = []
            custom_data["ligas"] = ligas_custom
            save_custom(custom_data)
            st.success(f"Liga '{nova_liga}' criada! Vai aparecer no menu ao recarregar.")
        else:
            st.info("Esta liga já existe.")
    st.stop()

# Equipas disponíveis para a liga selecionada
if liga_escolhida in ligas_fixas:
    equipas_disponiveis = ligas_fixas[liga_escolhida]
elif liga_escolhida in ligas_custom:
    equipas_disponiveis = ligas_custom[liga_escolhida]
else:
    equipas_disponiveis = []

# Adicionar nova equipa personalizada à liga custom
if liga_escolhida in ligas_custom:
    equipa_nova = st.text_input(f"Adicionar nova equipa à '{liga_escolhida}':", key="equipa_nova")
    if equipa_nova:
        if equipa_nova not in equipas_disponiveis:
            equipas_disponiveis.append(equipa_nova)
            ligas_custom[liga_escolhida] = equipas_disponiveis
            custom_data["ligas"] = ligas_custom
            save_custom(custom_data)
            st.success(f"Equipa '{equipa_nova}' adicionada à liga '{liga_escolhida}'!")
        else:
            st.info("Esta equipa já existe nesta liga.")

# Seleção CASA e FORA, sempre diferentes
equipa_casa = st.selectbox(
    "Equipa da CASA",
    equipas_disponiveis + (["Outra (personalizada)"] if "Outra (personalizada)" not in equipas_disponiveis else []),
    key="equipa_casa"
)
equipa_fora = st.selectbox(
    "Equipa FORA",
    [e for e in equipas_disponiveis if e != equipa_casa] + (["Outra (personalizada)"] if equipa_casa != "Outra (personalizada)" and "Outra (personalizada)" not in equipas_disponiveis else []),
    key="equipa_fora"
)

# Adicionar equipa personalizada à lista, se selecionado
if equipa_casa == "Outra (personalizada)":
    nova_casa = st.text_input("Nome da equipa CASA (personalizada)", key="input_casa")
    if nova_casa:
        if nova_casa not in equipas_disponiveis:
            equipas_disponiveis.append(nova_casa)
            if liga_escolhida in ligas_fixas:
                st.warning("Apenas ligas personalizadas permitem guardar equipas para o futuro!")
            else:
                ligas_custom[liga_escolhida] = equipas_disponiveis
                custom_data["ligas"] = ligas_custom
                save_custom(custom_data)
                st.success(f"Equipa '{nova_casa}' adicionada às opções!")
        equipa_casa = nova_casa

if equipa_fora == "Outra (personalizada)":
    nova_fora = st.text_input("Nome da equipa FORA (personalizada)", key="input_fora")
    if nova_fora:
        if nova_fora not in equipas_disponiveis:
            equipas_disponiveis.append(nova_fora)
            if liga_escolhida in ligas_fixas:
                st.warning("Apenas ligas personalizadas permitem guardar equipas para o futuro!")
            else:
                ligas_custom[liga_escolhida] = equipas_disponiveis
                custom_data["ligas"] = ligas_custom
                save_custom(custom_data)
                st.success(f"Equipa '{nova_fora}' adicionada às opções!")
        equipa_fora = nova_fora

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

    # # ================== Meteorologia e Condições Especiais (Ajustado: Dia/Noite único) ==================
st.subheader("Meteorologia e Condições Especiais")

# Dia ou noite? (único para o jogo)
periodo = st.selectbox("⏰ O jogo é de Dia ou Noite?", ["Dia", "Noite"], key="periodo_jogo")

# Meteorologia (único para o jogo)
meteo_jogo = st.selectbox("☀️ Meteorologia esperada para o jogo", meteos_lista, key="meteo_jogo")



# --- Árbitro (nota, tendência e média cartões) ---
st.subheader("Árbitro")
col_arb = st.columns(3)
with col_arb[0]:
    arbitro = st.slider("Nota do Árbitro (0-10)", 0.0, 10.0, 5.0, 0.1, key="arbitro_pre")
with col_arb[1]:
    tendencia_cartoes = st.selectbox("Tendência de Cartões", ["Poucos", "Normal", "Muitos"], key="tendencia_cartoes")
with col_arb[2]:
    media_cartoes = st.number_input("Média de Cartões por Jogo", min_value=0.0, max_value=10.0, value=4.5, step=0.1, key="media_cartoes")

# --- Motivações, Importância, Pressão, Desgaste, Viagem (Casa e Fora) ---
st.subheader("Motivação e Condições Especiais (CASA e FORA)")
col_casa, col_fora = st.columns(2)

with col_casa:
    motivacao_casa = st.selectbox("Motivação da equipa CASA", ["Baixa", "Normal", "Alta", "Máxima"], key="motivacao_casa")
    importancia_jogo_casa = st.selectbox("Importância do jogo CASA", ["Pouca", "Normal", "Importante", "Decisivo"], key="importancia_jogo_casa")
    pressao_adeptos_casa = st.selectbox("Pressão dos adeptos CASA", ["Baixa", "Normal", "Alta"], key="pressao_adeptos_casa")
    desgaste_fisico_casa = st.selectbox("Desgaste físico CASA", ["Baixo", "Normal", "Elevado"], key="desgaste_fisico_casa")
    viagem_casa = st.selectbox("Viagem/Calendário CASA", ["Descanso", "Viagem curta", "Viagem longa", "Calendário apertado"], key="viagem_casa")

with col_fora:
    motivacao_fora = st.selectbox("Motivação da equipa FORA", ["Baixa", "Normal", "Alta", "Máxima"], key="motivacao_fora")
    importancia_jogo_fora = st.selectbox("Importância do jogo FORA", ["Pouca", "Normal", "Importante", "Decisivo"], key="importancia_jogo_fora")
    pressao_adeptos_fora = st.selectbox("Pressão dos adeptos FORA", ["Baixa", "Normal", "Alta"], key="pressao_adeptos_fora")
    desgaste_fisico_fora = st.selectbox("Desgaste físico FORA", ["Baixo", "Normal", "Elevado"], key="desgaste_fisico_fora")
    viagem_fora = st.selectbox("Viagem/Calendário FORA", ["Descanso", "Viagem curta", "Viagem longa", "Calendário apertado"], key="viagem_fora")

# <--- ACABA AQUI as colunas!!!

# 4. Odds mercado (FORA DE QUALQUER with col_X:)
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
    # --- Ajustes individuais CASA ---
    ajuste_motiv_casa = 1.00 + (["Baixa", "Normal", "Alta", "Máxima"].index(motivacao_casa) - 1) * 0.04
    ajuste_arbitro_casa = 1.00 + ((arbitro - 5) / 10) * 0.04
    ajuste_pressao_casa = 1.00 + (["Baixa", "Normal", "Alta"].index(pressao_adeptos_casa)) * 0.02
    ajuste_import_casa = 1.00 + (["Pouca", "Normal", "Importante", "Decisivo"].index(importancia_jogo_casa)) * 0.03
    ajuste_fisico_casa = 1.00 - (["Baixo", "Normal", "Elevado"].index(desgaste_fisico_casa)) * 0.02
    ajuste_viagem_casa = 1.00 - (["Descanso", "Viagem curta", "Viagem longa", "Calendário apertado"].index(viagem_casa)) * 0.01
    ajuste_total_casa = ajuste_motiv_casa * ajuste_arbitro_casa * ajuste_pressao_casa * ajuste_import_casa * ajuste_fisico_casa * ajuste_viagem_casa

    # --- Ajustes individuais FORA ---
    ajuste_motiv_fora = 1.00 + (["Baixa", "Normal", "Alta", "Máxima"].index(motivacao_fora) - 1) * 0.04
    ajuste_arbitro_fora = 1.00 + ((arbitro - 5) / 10) * 0.04
    ajuste_pressao_fora = 1.00 + (["Baixa", "Normal", "Alta"].index(pressao_adeptos_fora)) * 0.02
    ajuste_import_fora = 1.00 + (["Pouca", "Normal", "Importante", "Decisivo"].index(importancia_jogo_fora)) * 0.03
    ajuste_fisico_fora = 1.00 - (["Baixo", "Normal", "Elevado"].index(desgaste_fisico_fora)) * 0.02
    ajuste_viagem_fora = 1.00 - (["Descanso", "Viagem curta", "Viagem longa", "Calendário apertado"].index(viagem_fora)) * 0.01
    ajuste_total_fora = ajuste_motiv_fora * ajuste_arbitro_fora * ajuste_pressao_fora * ajuste_import_fora * ajuste_fisico_fora * ajuste_viagem_fora

    # --- Cálculo base das probabilidades ---
    prob_casa = media_marcados_casa / (media_marcados_casa + media_marcados_fora + 1e-7)
    prob_fora = media_marcados_fora / (media_marcados_casa + media_marcados_fora + 1e-7)
    prob_empate = 1 - (prob_casa + prob_fora)

    # --- Aplicar ajustes individuais a cada equipa ---
    prob_casa *= ajuste_total_casa
    prob_fora *= ajuste_total_fora
    prob_empate = 1 - (prob_casa + prob_fora)

    # --- Restantes cálculos ---
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








