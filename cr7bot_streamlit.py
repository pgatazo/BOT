import streamlit as st
import hashlib
import json
import os
import pandas as pd
from io import BytesIO
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import time

# ======== FICHEIROS ========
USERS_FILE = "users.json"
CUSTOM_FILE = "ligas_e_equipas_custom.json"
PESOS_FILE = "pesos_personalizados.json"
CHAT_FILE = "chat.json"
ONLINE_FILE = "online_users.json"

# ======== SAFE JSON WRITE (escrita atómica, evita corrupção) ========
def safe_json_write(filepath, data, retries=5):
    for _ in range(retries):
        try:
            tmp = filepath + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, filepath)
            return True
        except Exception:
            time.sleep(0.1)
    return False

# ======== LOGIN =========
def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def load_users():
    if not os.path.exists(USERS_FILE):
        base_users = {
            "paulo": hash_pwd("damas2024"),
            "admin": hash_pwd("admin123")
        }
        safe_json_write(USERS_FILE, base_users)
    with open(USERS_FILE, "r") as f:
        return json.load(f)
USERS = load_users()

# Função para gerir presença online dos utilizadores
def set_online(username, online=True):
    data = {}
    if os.path.exists(ONLINE_FILE):
        with open(ONLINE_FILE, "r") as f:
            data = json.load(f)
    data[username] = {"online": online, "dt": datetime.now().strftime('%H:%M')}
    safe_json_write(ONLINE_FILE, data)

def get_all_online():
    if os.path.exists(ONLINE_FILE):
        with open(ONLINE_FILE, "r") as f:
            return json.load(f)
    return {}

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
            set_online(username, True)
        else:
            st.error("Credenciais inválidas ou não autorizado!")
    return st.session_state.get("login_success", False)

if "login_success" not in st.session_state or not st.session_state["login_success"]:
    if not login_screen():
        st.stop()
else:
    set_online(st.session_state['logged_user'], True)

st.set_page_config(page_title="PauloDamas-GPT", layout="wide")

import streamlit as st
# ... (restantes imports)

# ====== FUNÇÃO PARA CARREGAR E GUARDAR OS PESOS ======
def load_pesos():
    if os.path.exists(PESOS_FILE):
        with open(PESOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Se não existir, devolve default
    return {
        "Formação_C": 0.01, "Formação_F": 0.01,
        "Motivação_C": 0.01, "Motivação_F": 0.01,
        "Árbitro_C": 0.01, "Árbitro_F": 0.01,
        "Pressão_C": 0.01, "Pressão_F": 0.01,
        "Importância_C": 0.01, "Importância_F": 0.01,
        "Desgaste_C": 0.01, "Desgaste_F": 0.01,
        "Viagem_C": 0.01, "Viagem_F": 0.01,
        "Titulares_C": 0.01, "Titulares_F": 0.01,
        "Meteo_C": 0.01, "Meteo_F": 0.01,
        "H2H": 0.01,
    }

def save_pesos(pesos):
    with open(PESOS_FILE, "w", encoding="utf-8") as f:
        json.dump(pesos, f, ensure_ascii=False, indent=2)

# ====== INICIALIZAÇÃO DOS PESOS E STATUS DE ATUALIZAÇÃO ======
if "pesos" not in st.session_state:
    st.session_state["pesos"] = load_pesos()
if "pesos_atualizados" not in st.session_state:
    st.session_state["pesos_atualizados"] = {}

pesos = st.session_state["pesos"]


# ====== PAINEL DE PESOS (SIDE BAR) ======
st.sidebar.title("📊 Painel de Pesos (ajustável)")

pesos_nomes = [
    ("Motivação", "Motivação_C", "Motivação_F"),
    ("Árbitro", "Árbitro_C", "Árbitro_F"),
    ("Pressão", "Pressão_C", "Pressão_F"),
    ("Importância", "Importância_C", "Importância_F"),
    ("Desgaste", "Desgaste_C", "Desgaste_F"),
    ("Viagem", "Viagem_C", "Viagem_F"),
    ("Formação", "Formação_C", "Formação_F"),
    ("Titulares", "Titulares_C", "Titulares_F"),
    ("Meteo", "Meteo_C", "Meteo_F"),
    ("H2H", "H2H", None),  # H2H só 1 peso
]

for nome, key_c, key_f in pesos_nomes:
    col = st.sidebar.columns(2 if key_f else 1)
    # Peso CASA
    with col[0]:
        val_c = st.sidebar.number_input(
            f"{nome} CASA",
            min_value=-0.1,
            max_value=0.1,
            value=pesos.get(key_c, 0.01),
            step=0.001,
            key=f"{key_c}_sidebar"
        )
        # Mostrar sinal de ok se foi atualizado automaticamente
        ok_str_c = "✅" if st.session_state["pesos_atualizados"].get(key_c, False) else ""
        st.sidebar.markdown(f"<span style='color:green;font-weight:bold'>{ok_str_c}</span>", unsafe_allow_html=True)
        # Atualizar no estado se mudou manualmente
        if val_c != pesos.get(key_c, 0.01):
            pesos[key_c] = val_c
            st.session_state["pesos_atualizados"][key_c] = False

    # Peso FORA
    if key_f:
        with col[1]:
            val_f = st.sidebar.number_input(
                f"{nome} FORA",
                min_value=-0.1,
                max_value=0.1,
                value=pesos.get(key_f, 0.01),
                step=0.001,
                key=f"{key_f}_sidebar"
            )
            ok_str_f = "✅" if st.session_state["pesos_atualizados"].get(key_f, False) else ""
            st.sidebar.markdown(f"<span style='color:green;font-weight:bold'>{ok_str_f}</span>", unsafe_allow_html=True)
            if val_f != pesos.get(key_f, 0.01):
                pesos[key_f] = val_f
                st.session_state["pesos_atualizados"][key_f] = False


st.title("⚽️ PauloDamas-GPT — Análise Pré-Jogo + Live + IA + Chat")

# ======== FUNÇÕES UTILITÁRIAS ========
def kelly_criterion(prob, odd, banca, fracao=1):
    b = odd - 1
    q = 1 - prob
    f = ((b * prob - q) / b) * fracao
    return max(0, banca * f)

def calc_ev(p, o): return round(o * p - 1, 2)

def to_excel(df, distrib, resumo, pesos_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Análise Principal')
        distrib.to_excel(writer, index=False, sheet_name='Distribuição Ajustes')
        resumo.to_excel(writer, index=False, sheet_name='Resumo Inputs')
        pesos_df.to_excel(writer, index=False, sheet_name='Pesos em Uso')
    return output.getvalue()

def save_custom(data):
    safe_json_write(CUSTOM_FILE, data)

def load_custom():
    if os.path.exists(CUSTOM_FILE):
        with open(CUSTOM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

def save_pesos(pesos):
    safe_json_write(PESOS_FILE, pesos)

def load_pesos():
    if os.path.exists(PESOS_FILE):
        with open(PESOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {
            "Motivação_C": 0.01, "Motivação_F": 0.01,
            "Árbitro_C": 0.00, "Árbitro_F": 0.00,
            "Pressão_C": 0.02, "Pressão_F": 0.02,
            "Importância_C": 0.01, "Importância_F": 0.01,
            "Desgaste_C": 0.01, "Desgaste_F": 0.01,
            "Viagem_C": 0.01, "Viagem_F": 0.01,
            "Formação_C": 0.01, "Formação_F": 0.01,
            "Titulares_C": 0.01, "Titulares_F": 0.01
        }

def save_message(user, msg, dt=None):
    chat = load_chat()
    if dt is None:
        dt = datetime.now().strftime('%H:%M')
    chat.append({"user": user, "msg": msg, "dt": dt})
    safe_json_write(CHAT_FILE, chat)

def load_chat():
    if os.path.exists(CHAT_FILE):
        with open(CHAT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ======== LISTAS ========
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

# ======== PAINEL DE PESOS (ESQUERDA) ========
if "pesos" not in st.session_state:
    st.session_state["pesos"] = load_pesos()
pesos = st.session_state["pesos"]

st.sidebar.title("📊 Painel de Pesos (ajustável)")
for i, fator in enumerate(["Motivação", "Árbitro", "Pressão", "Importância", "Desgaste", "Viagem", "Formação", "Titulares"]):
    key_c = f"peso_{fator.lower().replace('ç','c').replace('ã','a').replace('í','i').replace('á','a').replace('ú','u').replace('ó','o').replace('é','e')}_c_{i}"
    key_f = f"peso_{fator.lower().replace('ç','c').replace('ã','a').replace('í','i').replace('á','a').replace('ú','u').replace('ó','o').replace('é','e')}_f_{i}"
    pesos[f"{fator}_C"] = st.sidebar.number_input(
        f"Peso {fator} CASA",
        min_value=-0.1,
        max_value=0.1,
        value=pesos.get(f"{fator}_C", 0.01),
        step=0.001,
        key=key_c
    )
    pesos[f"{fator}_F"] = st.sidebar.number_input(
        f"Peso {fator} FORA",
        min_value=-0.1,
        max_value=0.1,
        value=pesos.get(f"{fator}_F", 0.01),
        step=0.001,
        key=key_f
    )

# NOVOS PESOS: Meteorologia e H2H
pesos["Meteo_C"] = st.sidebar.number_input(
    "Peso Meteorologia CASA", 
    min_value=-0.1, max_value=0.1, 
    value=pesos.get("Meteo_C", 0.00), 
    step=0.001, 
    key="peso_meteo_c"
)
pesos["Meteo_F"] = st.sidebar.number_input(
    "Peso Meteorologia FORA", 
    min_value=-0.1, max_value=0.1, 
    value=pesos.get("Meteo_F", 0.00), 
    step=0.001, 
    key="peso_meteo_f"
)
pesos["H2H"] = st.sidebar.number_input(
    "Peso H2H (Confrontos Diretos)", 
    min_value=-0.1, max_value=0.1, 
    value=pesos.get("H2H", 0.00), 
    step=0.001, 
    key="peso_h2h"
)

# ======== LIGAS E EQUIPAS ========
custom_data = load_custom()
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
ligas_custom = custom_data.get("ligas", {})
todas_ligas = list(ligas_fixas.keys()) + list(ligas_custom.keys()) + ["Outra (nova liga personalizada)"]

# ======== TABS ========
tab1, tab2 = st.tabs(["⚽ Pré-Jogo", "🔥 Live / 2ª Parte + IA"])

# ========================= BLOCO PRÉ-JOGO =========================
with tab1:
    st.markdown('<div class="mainblock">', unsafe_allow_html=True)

    st.header("Análise Pré-Jogo (com fatores avançados)")
    liga_escolhida = st.selectbox("Liga:", todas_ligas, key="liga")
    # ... [Restante lógica das equipas igual, não mexe]

    # --------- PESOS: FORMAÇÃO / ABORDAGEM --------------
    st.subheader("Formações e Estratégias")
    colf1, colf2 = st.columns(2)
    with colf1:
        form_casa = st.selectbox("Formação inicial CASA", formacoes_lista, key="form_casa_pre")
        tipo_form_casa = st.selectbox("Abordagem (CASA)", tipos_formacao, key="tipo_form_casa_pre")
        # Marca peso atualizado ao interagir
        st.session_state["pesos_atualizados"]["Formação_C"] = True
    with colf2:
        form_fora = st.selectbox("Formação inicial FORA", formacoes_lista, key="form_fora_pre")
        tipo_form_fora = st.selectbox("Abordagem (FORA)", tipos_formacao, key="tipo_form_fora_pre")
        st.session_state["pesos_atualizados"]["Formação_F"] = True

    # --------- PESOS: TITULARES --------------
    st.subheader("Titulares disponíveis")
    titulares_casa = st.number_input("Quantos titulares disponíveis na CASA? (0-11)", 0, 11, 11, key="titulares_casa")
    titulares_fora = st.number_input("Quantos titulares disponíveis na FORA? (0-11)", 0, 11, 11, key="titulares_fora")
    st.session_state["pesos_atualizados"]["Titulares_C"] = True
    st.session_state["pesos_atualizados"]["Titulares_F"] = True

    # --------- PESOS: METEOROLOGIA --------------
    st.subheader("Meteorologia e Condições Especiais")
    periodo_jogo = st.selectbox("Quando se realiza o jogo?", ["Dia", "Noite"], key="periodo_jogo")
    meteo = st.selectbox("Tempo esperado", meteos_lista, key="meteo_pre")
    st.session_state["pesos_atualizados"]["Meteo_C"] = True
    st.session_state["pesos_atualizados"]["Meteo_F"] = True

    # --------- PESOS: ÁRBITRO / CARTÕES --------------
    st.subheader("Árbitro e Tendência de Cartões")
    col_arbitro1, col_arbitro2, col_arbitro3 = st.columns(3)
    with col_arbitro1:
        arbitro = st.slider("Nota do Árbitro (0-10)", 0.0, 10.0, 5.0, 0.1, key="arbitro_pre")
        st.session_state["pesos_atualizados"]["Árbitro_C"] = True
        st.session_state["pesos_atualizados"]["Árbitro_F"] = True
    with col_arbitro2:
        tendencia_cartoes = st.selectbox("Tendência para cartões", ["Poucos", "Normal", "Muitos"], key="tendencia_cartoes")
    with col_arbitro3:
        media_cartoes = st.number_input("Média de cartões por jogo", min_value=0.0, value=4.0, step=0.1, key="media_cartoes")

    # --------- PESOS: MOTIVAÇÃO, ETC --------------
    st.subheader("Motivação e Condições Especiais (CASA e FORA)")
    col_casa, col_fora = st.columns(2)
    with col_casa:
        motivacao_casa = st.selectbox("Motivação da equipa CASA", ["Baixa", "Normal", "Alta", "Máxima"], key="motivacao_casa")
        importancia_jogo_casa = st.selectbox("Importância do jogo CASA", ["Pouca", "Normal", "Importante", "Decisivo"], key="importancia_jogo_casa")
        pressao_adeptos_casa = st.selectbox("Pressão dos adeptos CASA", ["Baixa", "Normal", "Alta"], key="pressao_adeptos_casa")
        desgaste_fisico_casa = st.selectbox("Desgaste físico CASA", ["Baixo", "Normal", "Elevado"], key="desgaste_fisico_casa")
        viagem_casa = st.selectbox("Viagem/Calendário CASA", ["Descanso", "Viagem curta", "Viagem longa", "Calendário apertado"], key="viagem_casa")
        # Marca todos pesos casa como atualizados
        st.session_state["pesos_atualizados"]["Motivação_C"] = True
        st.session_state["pesos_atualizados"]["Importância_C"] = True
        st.session_state["pesos_atualizados"]["Pressão_C"] = True
        st.session_state["pesos_atualizados"]["Desgaste_C"] = True
        st.session_state["pesos_atualizados"]["Viagem_C"] = True
    with col_fora:
        motivacao_fora = st.selectbox("Motivação da equipa FORA", ["Baixa", "Normal", "Alta", "Máxima"], key="motivacao_fora")
        importancia_jogo_fora = st.selectbox("Importância do jogo FORA", ["Pouca", "Normal", "Importante", "Decisivo"], key="importancia_jogo_fora")
        pressao_adeptos_fora = st.selectbox("Pressão dos adeptos FORA", ["Baixa", "Normal", "Alta"], key="pressao_adeptos_fora")
        desgaste_fisico_fora = st.selectbox("Desgaste físico FORA", ["Baixo", "Normal", "Elevado"], key="desgaste_fisico_fora")
        viagem_fora = st.selectbox("Viagem/Calendário FORA", ["Descanso", "Viagem curta", "Viagem longa", "Calendário apertado"], key="viagem_fora")
        # Marca todos pesos fora como atualizados
        st.session_state["pesos_atualizados"]["Motivação_F"] = True
        st.session_state["pesos_atualizados"]["Importância_F"] = True
        st.session_state["pesos_atualizados"]["Pressão_F"] = True
        st.session_state["pesos_atualizados"]["Desgaste_F"] = True
        st.session_state["pesos_atualizados"]["Viagem_F"] = True

    # ------ MÉDIAS E H2H -------
    with st.form("totais_golos_form"):
        st.subheader("Equipa da CASA")
        total_golos_casa = st.number_input("Total de golos marcados (CASA)", min_value=0, value=0, key="golos_casa")
        total_sofridos_casa = st.number_input("Total de golos sofridos (CASA)", min_value=0, value=0, key="sofridos_casa")
        jogos_casa = st.number_input("Nº de jogos (CASA)", min_value=1, value=5, key="jogos_casa")
        media_marcados_casa = total_golos_casa / jogos_casa if jogos_casa else 0
        media_sofridos_casa = total_sofridos_casa / jogos_casa if jogos_casa else 0
        st.info(f"Média marcados: **{media_marcados_casa:.2f}** | Média sofridos: **{media_sofridos_casa:.2f}**")

        st.subheader("Equipa de FORA")
        total_golos_fora = st.number_input("Total de golos marcados (FORA)", min_value=0, value=0, key="golos_fora")
        total_sofridos_fora = st.number_input("Total de golos sofridos (FORA)", min_value=0, value=0, key="sofridos_fora")
        jogos_fora = st.number_input("Nº de jogos (FORA)", min_value=1, value=5, key="jogos_fora")
        media_marcados_fora = total_golos_fora / jogos_fora if jogos_fora else 0
        media_sofridos_fora = total_sofridos_fora / jogos_fora if jogos_fora else 0
        st.info(f"Média marcados: **{media_marcados_fora:.2f}** | Média sofridos: **{media_sofridos_fora:.2f}**")

        st.subheader("Confrontos Diretos (H2H)")
        total_golos_h2h_casa = st.number_input("Total golos marcados H2H (CASA)", min_value=0, value=0, key="golos_h2h_casa")
        total_golos_h2h_fora = st.number_input("Total golos marcados H2H (FORA)", min_value=0, value=0, key="golos_h2h_fora")
        jogos_h2h = st.number_input("Nº de jogos (H2H)", min_value=1, value=5, key="jogos_h2h")
        media_h2h_casa = total_golos_h2h_casa / jogos_h2h if jogos_h2h else 0
        media_h2h_fora = total_golos_h2h_fora / jogos_h2h if jogos_h2h else 0
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
        st.session_state["pesos_atualizados"]["H2H"] = True  # Marca H2H como atualizado

    # ... resto do cálculo e outputs
    
    # ... resto do cálculo e outputs
    
if st.button("Gerar Análise e Odds Justa"):
    def fator_delta(v_casa, v_fora, lista, peso_c, peso_f):
        idx_c = lista.index(v_casa)
        idx_f = lista.index(v_fora)
        diff = idx_c - idx_f
        return 1 + diff * peso_c, 1 - diff * peso_f

    # AJUSTES DOS FATORES (usar sempre os pesos do st.session_state["pesos"])
    pesos = st.session_state["pesos"]

    form_aj_casa, form_aj_fora = fator_delta(
        form_casa, form_fora, formacoes_lista,
        pesos["Formação_C"], pesos["Formação_F"]
    )
    tipo_aj_casa, tipo_aj_fora = fator_delta(
        tipo_form_casa, tipo_form_fora, tipos_formacao,
        pesos["Formação_C"], pesos["Formação_F"]
    )
    tit_aj_casa = 1 + (titulares_casa - 11) * pesos["Titulares_C"]
    tit_aj_fora = 1 + (titulares_fora - 11) * pesos["Titulares_F"]
    motiv_aj_casa = 1 + (["Baixa", "Normal", "Alta", "Máxima"].index(motivacao_casa)-1) * pesos["Motivação_C"]
    motiv_aj_fora = 1 + (["Baixa", "Normal", "Alta", "Máxima"].index(motivacao_fora)-1) * pesos["Motivação_F"]
    arb_aj_casa = 1 + ((arbitro - 5) / 10) * pesos["Árbitro_C"]
    arb_aj_fora = 1 + ((arbitro - 5) / 10) * pesos["Árbitro_F"]
    press_aj_casa = 1 + (["Baixa", "Normal", "Alta"].index(pressao_adeptos_casa)) * pesos["Pressão_C"]
    press_aj_fora = 1 + (["Baixa", "Normal", "Alta"].index(pressao_adeptos_fora)) * pesos["Pressão_F"]
    imp_aj_casa = 1 + (["Pouca", "Normal", "Importante", "Decisivo"].index(importancia_jogo_casa)) * pesos["Importância_C"]
    imp_aj_fora = 1 + (["Pouca", "Normal", "Importante", "Decisivo"].index(importancia_jogo_fora)) * pesos["Importância_F"]
    des_aj_casa = 1 - (["Baixo", "Normal", "Elevado"].index(desgaste_fisico_casa)) * pesos["Desgaste_C"]
    des_aj_fora = 1 - (["Baixo", "Normal", "Elevado"].index(desgaste_fisico_fora)) * pesos["Desgaste_F"]
    viag_aj_casa = 1 - (["Descanso", "Viagem curta", "Viagem longa", "Calendário apertado"].index(viagem_casa)) * pesos["Viagem_C"]
    viag_aj_fora = 1 - (["Descanso", "Viagem curta", "Viagem longa", "Calendário apertado"].index(viagem_fora)) * pesos["Viagem_F"]

    # METEOROLOGIA
    meteo_idx = meteos_lista.index(meteo)
    meteo_aj_casa = 1 + meteo_idx * pesos["Meteo_C"]
    meteo_aj_fora = 1 + meteo_idx * pesos["Meteo_F"]

    # H2H
    diff_h2h = media_h2h_casa - media_h2h_fora
    h2h_ajuste = 1 + diff_h2h * pesos["H2H"]

    ajuste_total_casa = (
        form_aj_casa * tipo_aj_casa * tit_aj_casa * motiv_aj_casa *
        arb_aj_casa * press_aj_casa * imp_aj_casa * des_aj_casa *
        viag_aj_casa * meteo_aj_casa * h2h_ajuste
    )
    ajuste_total_fora = (
        form_aj_fora * tipo_aj_fora * tit_aj_fora * motiv_aj_fora *
        arb_aj_fora * press_aj_fora * imp_aj_fora * des_aj_fora *
        viag_aj_fora * meteo_aj_fora
    )

    prob_casa = media_marcados_casa / (media_marcados_casa + media_marcados_fora + 1e-7) if (media_marcados_casa + media_marcados_fora + 1e-7) else 0
    prob_fora = media_marcados_fora / (media_marcados_casa + media_marcados_fora + 1e-7) if (media_marcados_casa + media_marcados_fora + 1e-7) else 0
    prob_empate = 1 - (prob_casa + prob_fora)
    prob_casa_aj = prob_casa * ajuste_total_casa
    prob_fora_aj = prob_fora * ajuste_total_fora
    prob_empate_aj = max(1 - (prob_casa_aj + prob_fora_aj), 0.01)
    total_prob_aj = prob_casa_aj + prob_empate_aj + prob_fora_aj
    prob_casa_aj, prob_empate_aj, prob_fora_aj = [p/total_prob_aj for p in [prob_casa_aj, prob_empate_aj, prob_fora_aj]]

    odd_justa_casa = 1 / (prob_casa_aj + 1e-7)
    odd_justa_empate = 1 / (prob_empate_aj + 1e-7)
    odd_justa_fora = 1 / (prob_fora_aj + 1e-7)
    ev_casa = calc_ev(prob_casa_aj, odd_casa)
    ev_empate = calc_ev(prob_empate_aj, odd_empate)
    ev_fora = calc_ev(prob_fora_aj, odd_fora)
    stake_casa = kelly_criterion(prob_casa_aj, odd_casa, banca)
    stake_empate = kelly_criterion(prob_empate_aj, odd_empate, banca)
    stake_fora = kelly_criterion(prob_fora_aj, odd_fora, banca)

    df_res = pd.DataFrame({
        "Aposta": ["Vitória CASA", "Empate", "Vitória FORA"],
        "Odd": [odd_casa, odd_empate, odd_fora],
        "Odd Justa": [round(odd_justa_casa,2), round(odd_justa_empate,2), round(odd_justa_fora,2)],
        "Prob. (%)": [round(prob_casa_aj*100,1), round(prob_empate_aj*100,1), round(prob_fora_aj*100,1)],
        "EV": [ev_casa, ev_empate, ev_fora],
        "Stake (€)": [round(stake_casa,2), round(stake_empate,2), round(stake_fora,2)],
        "Valor": ["✅" if ev>0 and stake>0 else "❌" for ev,stake in zip([ev_casa,ev_empate,ev_fora],[stake_casa,stake_empate,stake_fora])]
    })

    # Soma dos pesos usados
    soma_pesos_casa = sum([pesos[k] for k in pesos if "_C" in k])
    soma_pesos_fora = sum([pesos[k] for k in pesos if "_F" in k])
    st.info(f"Soma dos pesos CASA: **{soma_pesos_casa:.4f}** | Soma dos pesos FORA: **{soma_pesos_fora:.4f}**")
    st.info(f"Diff Odd Calculada - Odd da Casa: CASA {round(odd_casa - odd_justa_casa,2)} | EMPATE {round(odd_empate-odd_justa_empate,2)} | FORA {round(odd_fora-odd_justa_fora,2)}")

    dist_ajustes = [
        ["Formação", form_aj_casa, form_aj_fora],
        ["Abordagem", tipo_aj_casa, tipo_aj_fora],
        ["Titulares", tit_aj_casa, tit_aj_fora],
        ["Motivação", motiv_aj_casa, motiv_aj_fora],
        ["Árbitro", arb_aj_casa, arb_aj_fora],
        ["Pressão", press_aj_casa, press_aj_fora],
        ["Importância", imp_aj_casa, imp_aj_fora],
        ["Desgaste", des_aj_casa, des_aj_fora],
        ["Viagem", viag_aj_casa, viag_aj_fora],
        ["Meteorologia", meteo_aj_casa, meteo_aj_fora],
        ["H2H (Confrontos Diretos)", h2h_ajuste, "-"],
        ["AJUSTE TOTAL", ajuste_total_casa, ajuste_total_fora],
        ["Probabilidade ajustada", prob_casa_aj, prob_fora_aj]
    ]
    distrib_df = pd.DataFrame(dist_ajustes, columns=["Fator", "Casa", "Fora"])

    resumo_dict = {
        "Liga": [liga_escolhida], "Equipa CASA": [equipa_casa], "Equipa FORA": [equipa_fora],
        "Formação CASA": [form_casa], "Formação FORA": [form_fora],
        "Abordagem CASA": [tipo_form_casa], "Abordagem FORA": [tipo_form_fora],
        "Titulares CASA": [titulares_casa], "Titulares FORA": [titulares_fora],
        "Período do Jogo": [periodo_jogo], "Meteo": [meteo],
        "Nota Árbitro": [arbitro], "Tendência Cartões": [tendencia_cartoes], "Média Cartões": [media_cartoes],
        "Motivação CASA": [motivacao_casa], "Importância Jogo CASA": [importancia_jogo_casa], "Pressão Adeptos CASA": [pressao_adeptos_casa],
        "Desgaste CASA": [desgaste_fisico_casa], "Viagem CASA": [viagem_casa],
        "Motivação FORA": [motivacao_fora], "Importância Jogo FORA": [importancia_jogo_fora], "Pressão Adeptos FORA": [pressao_adeptos_fora],
        "Desgaste FORA": [desgaste_fisico_fora], "Viagem FORA": [viagem_fora],
        "Odd CASA": [odd_casa], "Odd EMPATE": [odd_empate], "Odd FORA": [odd_fora], "Banca (€)": [banca],
        "Média Marcados CASA": [media_marcados_casa], "Média Sofridos CASA": [media_sofridos_casa],
        "Média Marcados FORA": [media_marcados_fora], "Média Sofridos FORA": [media_sofridos_fora],
        "Média H2H CASA": [media_h2h_casa], "Média H2H FORA": [media_h2h_fora]
    }
    resumo_df = pd.DataFrame(resumo_dict)
    pesos_df = pd.DataFrame([pesos])

    st.subheader("Resultados da Análise")
    st.dataframe(df_res)
    st.subheader("Distribuição dos Ajustes & Pesos (Casa / Fora)")
    st.dataframe(distrib_df)
    st.subheader("📊 Pesos em uso")
    st.dataframe(pesos_df.T, use_container_width=True)
    relatorio = to_excel(df_res, distrib_df, resumo_df, pesos_df)
    st.download_button("⬇️ Download Relatório Completo (Excel)", data=relatorio, file_name="analise_prejogo_completa.xlsx")
    st.success("Análise pronta! Consulta apostas recomendadas, detalhes dos ajustes e exporta tudo para Excel.")
    st.markdown('</div>', unsafe_allow_html=True)  # <-- ATENÇÃO: aqui deve estar INDENTADO com os outputs acima

with tab2:
    st.markdown('<div class="mainblock">', unsafe_allow_html=True)
    st.header("Live/2ª Parte — Previsão de Golos (Modo Escuta + IA)")

    col_livef1, col_livef2 = st.columns(2)
    with col_livef1:
        form_casa_live = st.selectbox("Formação CASA (Live)", formacoes_lista, key="form_casa_live")
        tipo_form_casa_live = st.selectbox("Abordagem CASA", tipos_formacao, key="tipo_form_casa_live")
    with col_livef2:
        form_fora_live = st.selectbox("Formação FORA (Live)", formacoes_lista, key="form_fora_live")
        tipo_form_fora_live = st.selectbox("Abordagem FORA", tipos_formacao, key="tipo_form_fora_live")

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

    def interpretar_tatica(eventos, live_base, resultado):
        return "Comentário de exemplo. Adapta com a tua lógica de IA ou heurística."

    def calc_xg_live(live_base, eventos):
        base_xg = (live_base.get("xg_casa", 0) + live_base.get("xg_fora", 0))/2
        ajuste = len(eventos) * 0.07
        return base_xg + ajuste, ajuste, base_xg

    st.markdown("### 🤖 **PauloDamas-GPT** — Interpretação Tática Live")
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

    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="mainblock">', unsafe_allow_html=True)
    st.header("Live/2ª Parte — Previsão de Golos (Modo Escuta + IA)")

    col_livef1, col_livef2 = st.columns(2)
    with col_livef1:
        form_casa_live = st.selectbox("Formação CASA (Live)", formacoes_lista, key="form_casa_live")
        tipo_form_casa_live = st.selectbox("Abordagem CASA", tipos_formacao, key="tipo_form_casa_live")
    with col_livef2:
        form_fora_live = st.selectbox("Formação FORA (Live)", formacoes_lista, key="form_fora_live")
        tipo_form_fora_live = st.selectbox("Abordagem FORA", tipos_formacao, key="tipo_form_fora_live")

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

    def interpretar_tatica(eventos, live_base, resultado):
        return "Comentário de exemplo. Adapta com a tua lógica de IA ou heurística."

    def calc_xg_live(live_base, eventos):
        base_xg = (live_base.get("xg_casa", 0) + live_base.get("xg_fora", 0))/2
        ajuste = len(eventos) * 0.07
        return base_xg + ajuste, ajuste, base_xg

    st.markdown("### 🤖 **PauloDamas-GPT** — Interpretação Tática Live")
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

    st.markdown('</div>', unsafe_allow_html=True)

# ====== AUTOREFRESH DO CHAT ======
st_autorefresh(interval=5000, key="chatrefresh")

# ====== FUNÇÃO PARA EMOJIS ======
def emoji_bar():
    emojis = ["😀","👍","⚽","🔥","🤔","😭","🙌","💰","😎","🤡","🤩","🤬","😂","🥳","👏","🟢","🔴","🔵","🟠","🟣","⚠️","❤️"]
    bar = ''.join([f'<span class="chat-emoji" onclick="addEmoji(\'{e}\')">{e}</span>' for e in emojis])
    st.markdown(f"""
    <div style='margin-bottom:5px;'>{bar}</div>
    <script>
    function addEmoji(e) {{
        var chat_input = window.parent.document.querySelector('textarea[aria-label="Message to PauloDamas-GPT"]');
        if (chat_input) {{
            chat_input.value += e;
            chat_input.focus();
        }}
    }}
    </script>
    """, unsafe_allow_html=True)

st.sidebar.markdown("---")  # separador visual

st.sidebar.markdown("### 💬 Chat Global")
chat_msgs = load_chat()[-50:]
for m in chat_msgs:
    u, msg, dt = m['user'], m['msg'], m['dt']
    userstyle = "font-weight:700;color:#3131b0" if u==st.session_state['logged_user'] else "font-weight:500"
    st.sidebar.markdown(
        f"<div style='{userstyle}'>{u} <span style='font-size:13px;color:#bbb'>{dt}</span>:<br>{msg}</div>",
        unsafe_allow_html=True
    )

if st.sidebar.button("🗑️ Limpar Chat"):
    if os.path.exists(CHAT_FILE):
        os.remove(CHAT_FILE)
        st.sidebar.success("Chat limpo!")
        st.rerun()

def emoji_bar_sidebar():
    emojis = ["😀","👍","⚽","🔥","🤔","😭","🙌","💰","😎","🤡","🤩","🤬","😂","🥳","👏","🟢","🔴","🔵","🟠","🟣","⚠️","❤️"]
    bar = ''.join([f'<span style="font-size:20px;cursor:pointer;" onclick="addEmoji(\'{e}\')">{e}</span>' for e in emojis])
    st.sidebar.markdown(bar, unsafe_allow_html=True)

emoji_bar_sidebar()

with st.sidebar.form(key="chat_form_sidebar", clear_on_submit=True):
    msg = st.text_input("Mensagem:", key="chatinput_sidebar")
    enviar = st.form_submit_button("Enviar")
    if enviar and msg.strip():
        try:
            user = st.session_state.get("logged_user", "desconhecido")
            save_message(user, msg.strip())
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Erro ao enviar mensagem: {e}")
