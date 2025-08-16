# =============================== #
#  PauloDamas-GPT (Streamlit App)
#  Com leitor HLS/M3U8 integrado
# =============================== #

import streamlit as st
import hashlib
import json
import os
import pandas as pd
from io import BytesIO
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import time
import re
from urllib.parse import urlparse
import streamlit.components.v1 as components
from html import escape
import math
from typing import Optional

# --------- CONFIG DA PÁGINA ---------
st.set_page_config(page_title="PauloDamas-GPT", layout="wide")

# --------- HELPERS NUMÉRICOS / SANEAMENTO ---------
def fmt_num(v, nd: int = 2, dash: str = "—"):
    if v is None:
        return dash
    try:
        x = float(str(v).replace(",", "."))
        if math.isnan(x) or math.isinf(x):
            return dash
        return f"{x:.{nd}f}"
    except Exception:
        return dash

def to_float_or_none(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ".").strip())
    except Exception:
        return None

def sanitize_analysis(d: dict, keys=("xg_1p","xg_2p","xg_total")) -> dict:
    if not isinstance(d, dict):
        return {}
    dd = dict(d)
    for k in keys:
        dd[k] = to_float_or_none(dd.get(k))
    return dd

def fmt_any(v, nd: int = 2, dash: str = "—"):
    if isinstance(v, (list, tuple)):
        if not v:
            return dash
        return ", ".join(fmt_num(x, nd=nd, dash=dash) for x in v)
    return fmt_num(v, nd=nd, dash=dash)

def first_float(v) -> float:
    if isinstance(v, (list, tuple)):
        return (to_float_or_none(v[0]) or 0.0) if v else 0.0
    return to_float_or_none(v) or 0.0

def odds_from_prob(p: float, eps: float = 1e-9) -> float:
    p = max(float(p), eps)
    return 1.0 / p

# ===== Mercados de golos (Poisson total) =====
def prob_over(total_lambda: float, line: float) -> float:
    """P(total > line). Ex.: 1.5 => 1 - P(0)-P(1)."""
    lam = max(float(total_lambda), 1e-9)
    kmax = int(math.floor(line))
    s = 0.0
    for k in range(kmax + 1):
        s += math.exp(-lam) * (lam**k) / math.factorial(k)
    return max(0.0, min(1.0, 1.0 - s))

def prob_btts(l_home: float, l_away: float) -> float:
    """1 - P(casa=0) - P(fora=0) + P(0-0)."""
    lh = max(float(l_home), 1e-9)
    la = max(float(l_away), 1e-9)
    p_home_0 = math.exp(-lh)
    p_away_0 = math.exp(-la)
    p_00 = math.exp(-(lh + la))
    return max(0.0, min(1.0, 1.0 - p_home_0 - p_away_0 + p_00))

# --------- AJUSTE METEO + POISSON ---------
METEO_MULT = {
    "Sol": 1.00, "Nublado": 0.98, "Chuva": 0.88, "Vento": 0.90,
    "Frio": 0.92, "Calor": 0.90, "Calor extremo": 0.85, "Outro": 1.00,
}

def pois_pmf(k: int, lam: float) -> float:
    if k < 0:
        return 0.0
    lam = max(float(lam), 1e-9)
    return math.exp(-lam) * (lam**k) / math.factorial(k)

def poisson_outcome_probs(l_home: float, l_away: float, max_goals: int = 12):
    l_home = max(float(l_home), 1e-9)
    l_away = max(float(l_away), 1e-9)
    pmf_home = [pois_pmf(k, l_home) for k in range(max_goals + 1)]
    pmf_away = [pois_pmf(k, l_away) for k in range(max_goals + 1)]
    p_home = p_draw = p_away = 0.0
    for gh in range(max_goals + 1):
        ph = pmf_home[gh]
        for ga in range(max_goals + 1):
            pa = pmf_away[ga]
            p = ph * pa
            if gh > ga:
                p_home += p
            elif gh == ga:
                p_draw += p
            else:
                p_away += p
    s = p_home + p_draw + p_away
    if s <= 0: return 1/3, 1/3, 1/3
    return p_home/s, p_draw/s, p_away/s
# --------- PARSER DE STREAMS ---------
def parse_m3u_or_url(raw: str) -> Optional[str]:
    if not raw: return None
    s = raw.strip()
    if s.lower().startswith(("http://","https://")) and (".m3u8" in s.lower() or ".mpd" in s.lower()):
        return s
    if "#EXTM3U" in s:
        for line in s.splitlines():
            line = line.strip()
            if line.lower().startswith(("http://","https://")) and ".m3u8" in line.lower():
                return line
    return None

M3U_ENTRY_RE = re.compile(r'#EXTINF:-?\d+.*?,(?P<name>.+)\n(?P<url>https?://[^\s]+)', re.IGNORECASE)

def parse_m3u(text: str):
    chans = []
    payload = text.replace('\r','').strip()
    for m in M3U_ENTRY_RE.finditer(payload):
        chans.append({"name": m.group('name').strip(), "url": m.group('url').strip()})
    if not chans:
        for line in payload.splitlines():
            line = line.strip()
            if line.lower().startswith(("http://","https://")) and ".m3u8" in line.lower():
                chans.append({"name": line.rsplit("/",1)[-1], "url": line})
    return chans

def looks_safe_m3u8(url: str) -> bool:
    try:
        u = urlparse(url)
        return u.scheme in ('http','https') and (u.path.endswith('.m3u8') or '.m3u8' in u.path)
    except Exception:
        return False

def hls_player(url: str, height: int = 420):
    if not url:
        st.info("Cole uma URL HLS (.m3u8) válida ou carregue um ficheiro M3U/M3U8.")
        return
    safe_url = url.replace('"','%22').replace("'", "%27")
    html = f"""
    <div style="position:relative;width:100%;max-width:1000px;margin:0 auto;">
      <video id="v" controls playsinline style="width:100%;height:auto;background:#000;" poster="">
        Your browser does not support the video tag.
      </video>
      <div style="position:absolute;top:8px;right:8px;display:flex;gap:6px;">
        <button onclick="pip()" style="padding:6px 10px;">PiP</button>
        <button onclick="fs()"  style="padding:6px 10px;">Fullscreen</button>
      </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <script>
      const url = "{safe_url}";
      const video = document.getElementById('v');
      function start(){{
        if (Hls.isSupported()) {{
          const hls = new Hls({{lowLatencyMode:true}});
          hls.loadSource(url); hls.attachMedia(video);
        }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
          video.src = url;
        }} else {{
          video.outerHTML = "<div style='color:#fff;padding:8px;font-family:system-ui'>HLS não suportado neste browser.</div>";
        }}
      }}
      async function pip() {{
        try {{
          if (document.pictureInPictureElement) {{ await document.exitPictureInPicture(); }}
          else {{ await video.requestPictureInPicture(); }}
        }} catch(e){{ console.log(e); }}
      }}
      function fs(){{ if (video.requestFullscreen) video.requestFullscreen(); }}
      start();
    </script>
    """
    components.html(html, height=height, scrolling=False)

# ---- Favoritos (persistentes) ----
FAVORITES_FILE = "favoritos_m3u.json"
def load_favs() -> dict:
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_favs(data: dict) -> None:
    tmp = FAVORITES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, FAVORITES_FILE)

# --------- UI PRINCIPAL DO PLAYER ---------
st.subheader("📺 Leitor HLS / M3U8")
if "hls_url" not in st.session_state: st.session_state["hls_url"] = None
if "channels" not in st.session_state: st.session_state["channels"] = []
if "favs" not in st.session_state: st.session_state["favs"] = load_favs()

col_src, col_up = st.columns([2,1])
with col_src:
    raw_stream = st.text_area("Cole a URL .m3u8 OU o conteúdo .m3u8 / .m3u",
                              height=100,
                              placeholder="https://servidor/playlist.m3u8  ou  #EXTM3U ...")
with col_up:
    uploaded = st.file_uploader("Ficheiro .m3u / .m3u8", type=["m3u","m3u8"])

col_btn1, col_btn2, col_btn3 = st.columns(3)
with col_btn1:
    if st.button("Carregar lista/stream"):
        chans = []
        if raw_stream:
            chans = parse_m3u(raw_stream)
            if not chans:
                url = parse_m3u_or_url(raw_stream)
                if url: st.session_state["hls_url"] = url
        if chans:
            st.session_state["channels"] = chans
            st.success(f"Lista carregada: {len(chans)} canais.")
with col_btn2:
    if st.button("Limpar lista"):
        st.session_state["channels"] = []
with col_btn3:
    if st.button("Limpar player"):
        st.session_state["hls_url"] = None

if uploaded is not None:
    try:
        content = uploaded.getvalue().decode("utf-8", errors="ignore")
        chans = parse_m3u(content)
        if chans:
            st.session_state["channels"] = chans
            st.success(f"Lista carregada: {len(chans)} canais.")
        else:
            url = parse_m3u_or_url(content)
            if url:
                st.session_state["hls_url"] = url
                st.success("Stream .m3u8 extraído do ficheiro.")
            else:
                st.warning("Não foi possível extrair canais nem um .m3u8 do ficheiro.")
    except Exception as e:
        st.error(f"Erro a ler ficheiro: {e}")

st.markdown("---")
left, right = st.columns([3,2])
with left:
    st.markdown("### 📜 Canais")
    channels = st.session_state["channels"]
    search = st.text_input("Pesquisar canal", placeholder="nome parcial…")
    if search:
        channels = [c for c in channels if search.lower() in c["name"].lower()]
    if channels:
        names = [c["name"] for c in channels]
        idx = st.selectbox("Escolhe um canal", range(len(names)), format_func=lambda i: names[i])
        sel = channels[idx]
        st.write(f"URL: `{sel['url']}`")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("▶️ Reproduzir", key="play_sel"):
                st.session_state["hls_url"] = sel["url"]
        with c2:
            fav_cats = ["(nova)"] + list(st.session_state["favs"].keys())
            fav_choice = st.selectbox("Categoria", fav_cats, key="fav_cat_sel")
        with c3:
            new_cat = st.text_input("Nova categoria", value="" if fav_choice != "(nova)" else "", key="fav_new_cat")
        if st.button("⭐ Guardar nos favoritos", key="add_fav"):
            cat = new_cat.strip() if fav_choice == "(nova)" else fav_choice
            if not cat:
                st.warning("Indica um nome para a categoria.")
            else:
                favs = st.session_state["favs"]
                favs.setdefault(cat, [])
                if not any(x["url"] == sel["url"] for x in favs[cat]):
                    favs[cat].append({"name": sel["name"], "url": sel["url"]})
                    st.session_state["favs"] = favs
                    save_favs(favs)
                    st.success(f"Adicionado a '{cat}'.")
                else:
                    st.info("Esse canal já existe na categoria.")
    else:
        st.info("Sem lista de canais carregada.")

with right:
    st.markdown("### ⭐ Favoritos")
    favs = st.session_state["favs"]
    cats = list(favs.keys())
    if cats:
        cat_sel = st.selectbox("Categoria", cats, key="fav_cat_play")
        items = favs.get(cat_sel, [])
        if items:
            names_f = [i["name"] for i in items]
            idx_f = st.selectbox("Canal favorito", range(len(names_f)), format_func=lambda i: names_f[i], key="fav_idx")
            sel_f = items[idx_f]
            st.write(f"URL: `{sel_f['url']}`")
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("▶️ Reproduzir favorito"):
                    st.session_state["hls_url"] = sel_f["url"]
            with b2:
                if st.button("🗑️ Remover favorito"):
                    items.pop(idx_f)
                    favs[cat_sel] = items
                    st.session_state["favs"] = favs
                    save_favs(favs)
                    st.success("Removido.")
            with b3:
                if st.button("🗑️ Remover categoria"):
                    del favs[cat_sel]
                    st.session_state["favs"] = favs
                    save_favs(favs)
                    st.success("Categoria removida.")
        else:
            st.info("Esta categoria está vazia.")
    else:
        st.info("Ainda não existem categorias de favoritos.")

st.markdown("---")
st.markdown("### 🎬 Player")
if st.session_state["hls_url"]:
    st.caption(f"Fonte: `{st.session_state['hls_url']}`")
    hls_player(st.session_state["hls_url"], height=420)
else:
    st.info("Insere uma URL .m3u8 válida, carrega uma lista .m3u e escolhe um canal, ou usa os favoritos.")
# ======== FICHEIROS ========
USERS_FILE = "users.json"
CUSTOM_FILE = "ligas_e_equipas_custom.json"
PESOS_FILE = "pesos_personalizados.json"
CHAT_FILE = "chat.json"
ONLINE_FILE = "online_users.json"

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
def hash_pwd(pwd): return hashlib.sha256(pwd.encode()).hexdigest()

def load_users():
    if not os.path.exists(USERS_FILE):
        base_users = {"paulo": hash_pwd("damas2024"), "admin": hash_pwd("admin123")}
        safe_json_write(USERS_FILE, base_users)
    with open(USERS_FILE, "r") as f:
        return json.load(f)
USERS = load_users()

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
    if st.button("Entrar"):
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

# ======== TÍTULO ========
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

def save_custom(data): safe_json_write(CUSTOM_FILE, data)
def load_custom():
    if os.path.exists(CUSTOM_FILE):
        with open(CUSTOM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}
def save_pesos(pesos): safe_json_write(PESOS_FILE, pesos)
def load_pesos():
    if os.path.exists(PESOS_FILE):
        with open(PESOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
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
    if dt is None: dt = datetime.now().strftime('%H:%M')
    chat.append({"user": user, "msg": msg, "dt": dt})
    safe_json_write(CHAT_FILE, chat)

def load_chat():
    if os.path.exists(CHAT_FILE):
        with open(CHAT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def export_detalhado(base_inputs, eventos, xg_2p=None, ajuste=None, xg_ponderado=None):
    pesos = load_pesos()
    linhas, acumulado, ordem = [], (xg_ponderado if xg_ponderado is not None else 1.0), 1
    linhas.append({
        "Ordem": ordem, "Etapa": "xG ponderado inicial",
        "Input": f"{xg_ponderado:.2f}" if xg_ponderado is not None else "-",
        "Peso aplicado": "-", "Ajuste parcial": "-", "Resultado acumulado": acumulado,
        "Nota": "Base inicial do cálculo"
    }); ordem += 1
    for key, val in base_inputs.items():
        peso = pesos.get(key, 0)
        ajuste_parcial = peso * (val if isinstance(val, (int, float)) else 1)
        acumulado += ajuste_parcial
        linhas.append({
            "Ordem": ordem, "Etapa": key, "Input": val, "Peso aplicado": peso,
            "Ajuste parcial": ajuste_parcial, "Resultado acumulado": acumulado, "Nota": "Input pré-jogo"
        }); ordem += 1
    for ev in eventos:
        tipo = ev.get("tipo", "Evento"); equipa = ev.get("equipa", "-")
        ajuste_parcial, nota = 0.0, ""
        if tipo == "Golo": ajuste_parcial = 0.20 if equipa == "Casa" else -0.20; nota = "Impacto de golo"
        elif tipo == "Expulsão": ajuste_parcial = -0.15 if equipa == "Casa" else 0.15; nota = "Impacto de expulsão"
        elif tipo == "Penalty": ajuste_parcial = 0.25 if equipa == "Casa" else -0.25; nota = "Impacto de penalty"
        elif tipo == "Substituição":
            troca = ev.get("tipo_troca", "")
            if   troca == "Avançado por Médio":   ajuste_parcial = -0.08 if equipa == "Casa" else 0.08
            elif troca == "Avançado por Defesa":  ajuste_parcial = -0.12 if equipa == "Casa" else 0.12
            elif troca == "Médio por Avançado":   ajuste_parcial =  0.07 if equipa == "Casa" else -0.07
            elif troca == "Defesa por Avançado":  ajuste_parcial =  0.10 if equipa == "Casa" else -0.10
            nota = f"Substituição ({troca})"
        elif tipo == "Mudança de formação":
            form = ev.get("tipo_formacao", "")
            if   form == "Atacante":  ajuste_parcial =  0.08 if equipa == "Casa" else -0.08
            elif form == "Defensivo": ajuste_parcial = -0.08 if equipa == "Casa" else  0.08
            nota = f"Mudança de formação ({form})"
        elif tipo == "Amarelo":
            pos = ev.get("posicao", "")
            if   pos == "Defesa":  ajuste_parcial = -0.05 if equipa == "Casa" else 0.05
            elif pos == "Médio":   ajuste_parcial = -0.03 if equipa == "Casa" else 0.03
            elif pos == "Avançado":ajuste_parcial = -0.01 if equipa == "Casa" else 0.01
            nota = f"Amarelo ({pos})"
        acumulado += ajuste_parcial
        linhas.append({
            "Ordem": ordem, "Etapa": tipo, "Input": equipa, "Peso aplicado": "-",
            "Ajuste parcial": ajuste_parcial, "Resultado acumulado": acumulado, "Nota": nota
        }); ordem += 1
    linhas.append({
        "Ordem": ordem, "Etapa": "Resultado Final", "Input": "-", "Peso aplicado": "-",
        "Ajuste parcial": "-", "Resultado acumulado": acumulado, "Nota": "xG/odds finais"
    })
    df = pd.DataFrame(linhas)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Detalhe_Analise", index=False)
    return output.getvalue()

# ======== LISTAS ========
formacoes_lista = [
    "4-4-2","4-3-3","4-2-3-1","3-5-2","3-4-3","5-3-2","4-1-4-1","4-5-1",
    "3-4-2-1","3-4-1-2","3-6-1","4-4-1-1","4-3-1-2","4-2-2-2","4-3-2-1",
    "5-4-1","5-2-3","5-2-1-2","4-1-2-1-2","3-5-1-1","4-1-2-3","3-3-3-1",
    "3-2-3-2","3-3-1-3","4-2-4","4-3-2","3-2-5","2-3-5","4-2-1-3","Outro"
]
tipos_formacao = ["Atacante", "Equilibrado", "Defensivo"]
tipos_troca = [
    "Avançado por Avançado","Avançado por Médio","Avançado por Defesa",
    "Médio por Avançado","Médio por Médio","Médio por Defesa",
    "Defesa por Avançado","Defesa por Médio","Defesa por Defesa","Outro"
]
posicoes_lista = ["GR","Defesa","Médio","Avançado"]
importancias_lista = ["Peça chave","Importante","Normal"]
meteos_lista = ["Sol","Nublado","Chuva","Vento","Frio","Calor","Calor extremo","Outro"]

# ======== PAINEL DE PESOS ========
if "pesos" not in st.session_state:
    st.session_state["pesos"] = load_pesos()
pesos = st.session_state["pesos"]

st.sidebar.title("📊 Painel de Pesos (ajustável)")
for i, fator in enumerate(["Motivação","Árbitro","Pressão","Importância","Desgaste","Viagem","Formação","Titulares"]):
    key_c = f"peso_{fator.lower()}_c_{i}"
    key_f = f"peso_{fator.lower()}_f_{i}"
    pesos[f"{fator}_C"] = st.sidebar.number_input(
        f"Peso {fator} CASA", min_value=-0.1, max_value=0.1,
        value=pesos.get(f"{fator}_C", 0.01), step=0.001, key=key_c
    )
    pesos[f"{fator}_F"] = st.sidebar.number_input(
        f"Peso {fator} FORA", min_value=-0.1, max_value=0.1,
        value=pesos.get(f"{fator}_F", 0.01), step=0.001, key=key_f
    )

# ======== LIGAS E EQUIPAS ========
custom_data = load_custom()
ligas_fixas = {
    "Liga Betclic": [
        "Benfica","Porto","Sporting","Braga","Guimarães","Casa Pia","Boavista","Estoril",
        "Famalicão","Farense","Gil Vicente","Moreirense","Portimonense","Rio Ave","Arouca","Vizela","Chaves"
    ],
    "Premier League": [
        "Arsenal","Aston Villa","Bournemouth","Brentford","Brighton","Burnley","Chelsea",
        "Crystal Palace","Everton","Fulham","Liverpool","Luton Town","Manchester City",
        "Manchester United","Newcastle","Nottingham Forest","Sheffield United","Tottenham",
        "West Ham","Wolves"
    ],
    "La Liga": [
        "Real Madrid","Barcelona","Atlético Madrid","Sevilla","Betis","Valencia","Villarreal",
        "Real Sociedad","Athletic Bilbao","Getafe","Osasuna","Celta Vigo","Granada",
        "Las Palmas","Mallorca","Alaves","Rayo Vallecano","Almeria","Girona","Cadiz"
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

    equipas_disponiveis_base = ligas_fixas.get(liga_escolhida, [])
    equipas_pers = ligas_custom.get(liga_escolhida, [])
    seen, equipas_disponiveis = set(), []
    for x in (equipas_disponiveis_base + equipas_pers):
        if x not in seen:
            equipas_disponiveis.append(x); seen.add(x)

    equipa_nova = st.text_input(f"Adicionar nova equipa à '{liga_escolhida}':", key="equipa_nova")
    if equipa_nova:
        if equipa_nova not in equipas_disponiveis:
            equipas_disponiveis.append(equipa_nova)
            ligas_custom.setdefault(liga_escolhida, [])
            if equipa_nova not in ligas_custom[liga_escolhida]:
                ligas_custom[liga_escolhida].append(equipa_nova)
            custom_data["ligas"] = ligas_custom
            save_custom(custom_data)
            st.success(f"Equipa '{equipa_nova}' adicionada à liga '{liga_escolhida}'!")
        else:
            st.info("Esta equipa já existe nesta liga.")

    extra_opt = ["Outra (personalizada)"] if "Outra (personalizada)" not in equipas_disponiveis else []
    equipa_casa = st.selectbox("Equipa da CASA", equipas_disponiveis + extra_opt, key="equipa_casa")
    equipa_fora = st.selectbox(
        "Equipa FORA",
        [e for e in equipas_disponiveis if e != equipa_casa] +
        (["Outra (personalizada)"] if equipa_casa != "Outra (personalizada)" and "Outra (personalizada)" not in equipas_disponiveis else []),
        key="equipa_fora"
    )

    if equipa_casa == "Outra (personalizada)":
        nova_casa = st.text_input("Nome da equipa CASA (personalizada)", key="input_casa")
        if nova_casa:
            if nova_casa not in equipas_disponiveis:
                equipas_disponiveis.append(nova_casa)
                ligas_custom.setdefault(liga_escolhida, [])
                if nova_casa not in ligas_custom[liga_escolhida]:
                    ligas_custom[liga_escolhida].append(nova_casa)
                custom_data["ligas"] = ligas_custom
                save_custom(custom_data)
                st.success(f"Equipa '{nova_casa}' adicionada à liga '{liga_escolhida}'!")
            equipa_casa = nova_casa

    if equipa_fora == "Outra (personalizada)":
        nova_fora = st.text_input("Nome da equipa FORA (personalizada)", key="input_fora")
        if nova_fora:
            if nova_fora not in equipas_disponiveis:
                equipas_disponiveis.append(nova_fora)
                ligas_custom.setdefault(liga_escolhida, [])
                if nova_fora not in ligas_custom[liga_escolhida]:
                    ligas_custom[liga_escolhida].append(nova_fora)
                custom_data["ligas"] = ligas_custom
                save_custom(custom_data)
                st.success(f"Equipa '{nova_fora}' adicionada à liga '{liga_escolhida}'!")
            equipa_fora = nova_fora

    # ---- Odds & banca
    st.subheader("Odds da Casa de Apostas (1X2)")
    col_odds1, col_odds2, col_odds3 = st.columns(3)
    with col_odds1: odd_casa = st.number_input("Odd Vitória CASA", min_value=1.0, value=1.90)
    with col_odds2: odd_empate = st.number_input("Odd EMPATE", min_value=1.0, value=3.10)
    with col_odds3: odd_fora = st.number_input("Odd Vitória FORA", min_value=1.0, value=4.10)
    st.info(f"Soma odds casa de apostas: **{(odd_casa+odd_empate+odd_fora):.2f}**")
    banca = st.number_input("💳 Valor atual da banca (€)", min_value=1.0, value=100.0, step=0.01)

    # ---- Formações / titulares / meteo / árbitro / motivação
    st.subheader("Formações e Estratégias")
    colf1, colf2 = st.columns(2)
    with colf1:
        form_casa = st.selectbox("Formação inicial CASA", formacoes_lista, key="form_casa_pre")
        tipo_form_casa = st.selectbox("Abordagem (CASA)", tipos_formacao, key="tipo_form_casa_pre")
    with colf2:
        form_fora = st.selectbox("Formação inicial FORA", formacoes_lista, key="form_fora_pre")
        tipo_form_fora = st.selectbox("Abordagem (FORA)", tipos_formacao, key="tipo_form_fora_pre")

    st.subheader("Titulares disponíveis")
    titulares_casa = st.number_input("Titulares CASA (0-11)", 0, 11, 11, key="titulares_casa")
    titulares_fora = st.number_input("Titulares FORA (0-11)", 0, 11, 11, key="titulares_fora")

    st.subheader("Meteorologia e Condições Especiais")
    periodo_jogo = st.selectbox("Quando se realiza o jogo?", ["Dia","Noite"], key="periodo_jogo")
    meteo = st.selectbox("Tempo esperado", meteos_lista, key="meteo_pre")

    st.subheader("Árbitro e Tendência de Cartões")
    col_arbitro1, col_arbitro2, col_arbitro3 = st.columns(3)
    with col_arbitro1:
        arbitro = st.slider("Nota do Árbitro (0-10)", 0.0, 10.0, 5.0, 0.1, key="arbitro_pre")
    with col_arbitro2:
        tendencia_cartoes = st.selectbox("Tendência para cartões", ["Poucos","Normal","Muitos"], key="tendencia_cartoes")
    with col_arbitro3:
        media_cartoes = st.number_input("Média de cartões por jogo", min_value=0.0, value=4.0, step=0.1, key="media_cartoes")

    st.subheader("Motivação e Condições Especiais")
    col_casa, col_fora = st.columns(2)
    with col_casa:
        motivacao_casa = st.selectbox("Motivação CASA", ["Baixa","Normal","Alta","Máxima"], key="motivacao_casa")
        importancia_jogo_casa = st.selectbox("Importância CASA", ["Pouca","Normal","Importante","Decisivo"], key="importancia_jogo_casa")
        pressao_adeptos_casa = st.selectbox("Pressão adeptos CASA", ["Baixa","Normal","Alta"], key="pressao_adeptos_casa")
        desgaste_fisico_casa = st.selectbox("Desgaste físico CASA", ["Baixo","Normal","Elevado"], key="desgaste_fisico_casa")
        viagem_casa = st.selectbox("Viagem/Calendário CASA", ["Descanso","Viagem curta","Viagem longa","Calendário apertado"], key="viagem_casa")
    with col_fora:
        motivacao_fora = st.selectbox("Motivação FORA", ["Baixa","Normal","Alta","Máxima"], key="motivacao_fora")
        importancia_jogo_fora = st.selectbox("Importância FORA", ["Pouca","Normal","Importante","Decisivo"], key="importancia_jogo_fora")
        pressao_adeptos_fora = st.selectbox("Pressão adeptos FORA", ["Baixa","Normal","Alta"], key="pressao_adeptos_fora")
        desgaste_fisico_fora = st.selectbox("Desgaste físico FORA", ["Baixo","Normal","Elevado"], key="desgaste_fisico_fora")
        viagem_fora = st.selectbox("Viagem/Calendário FORA", ["Descanso","Viagem curta","Viagem longa","Calendário apertado"], key="viagem_fora")

    # ------ MÉDIAS E H2H -------
    with st.form("totais_golos_form"):
        st.subheader("Equipa da CASA")
        total_golos_casa = st.number_input("Total marcados (CASA)", min_value=0, value=0, key="golos_casa")
        total_sofridos_casa = st.number_input("Total sofridos (CASA)", min_value=0, value=0, key="sofridos_casa")
        jogos_casa = st.number_input("Nº jogos (CASA)", min_value=1, value=5, key="jogos_casa")
        media_marcados_casa = total_golos_casa / jogos_casa if jogos_casa else 0
        media_sofridos_casa = total_sofridos_casa / jogos_casa if jogos_casa else 0
        st.info(f"Média marcados: **{media_marcados_casa:.2f}** | Média sofridos: **{media_sofridos_casa:.2f}**")

        st.subheader("Equipa de FORA")
        total_golos_fora = st.number_input("Total marcados (FORA)", min_value=0, value=0, key="golos_fora")
        total_sofridos_fora = st.number_input("Total sofridos (FORA)", min_value=0, value=0, key="sofridos_fora")
        jogos_fora = st.number_input("Nº jogos (FORA)", min_value=1, value=5, key="jogos_fora")
        media_marcados_fora = total_golos_fora / jogos_fora if jogos_fora else 0
        media_sofridos_fora = total_sofridos_fora / jogos_fora if jogos_fora else 0
        st.info(f"Média marcados: **{media_marcados_fora:.2f}** | Média sofridos: **{media_sofridos_fora:.2f}**")

        st.subheader("Confrontos Diretos (H2H)")
        total_golos_h2h_casa = st.number_input("Marcados H2H (CASA)", min_value=0, value=0, key="golos_h2h_casa")
        total_golos_h2h_fora = st.number_input("Marcados H2H (FORA)", min_value=0, value=0, key="golos_h2h_fora")
        jogos_h2h = st.number_input("Nº jogos (H2H)", min_value=1, value=5, key="jogos_h2h")
        media_h2h_casa = total_golos_h2h_casa / jogos_h2h if jogos_h2h else 0
        media_h2h_fora = total_golos_h2h_fora / jogos_h2h if jogos_h2h else 0
        st.info(f"Média H2H CASA: **{media_h2h_casa:.2f}** | Média H2H FORA: **{media_h2h_fora:.2f}**")
        confirm1 = st.form_submit_button("✅ Confirmar Totais")
    if confirm1:
        st.session_state['medias'] = {
            'marc_casa': media_marcados_casa, 'sofr_casa': media_sofridos_casa,
            'marc_fora': media_marcados_fora, 'sofr_fora': media_sofridos_fora,
            'marc_h2h_casa': media_h2h_casa, 'marc_h2h_fora': media_h2h_fora,
        }
        st.success("Totais confirmados!")

# ===================== GERAR ANÁLISE E ODDS JUSTA =====================
if st.button("Gerar Análise e Odds Justa"):
    def fator_delta(v_casa, v_fora, lista, peso_c, peso_f):
        idx_c = lista.index(v_casa); idx_f = lista.index(v_fora); diff = idx_c - idx_f
        return 1 + diff * peso_c, 1 - diff * peso_f

    form_aj_casa, form_aj_fora   = fator_delta(form_casa, form_fora, formacoes_lista, pesos["Formação_C"], pesos["Formação_F"])
    tipo_aj_casa, tipo_aj_fora   = fator_delta(tipo_form_casa, tipo_form_fora, tipos_formacao, pesos["Formação_C"], pesos["Formação_F"])
    tit_aj_casa = 1 + (titulares_casa - 11) * pesos["Titulares_C"]
    tit_aj_fora = 1 + (titulares_fora - 11) * pesos["Titulares_F"]
    motiv_aj_casa = 1 + (["Baixa","Normal","Alta","Máxima"].index(motivacao_casa)-1) * pesos["Motivação_C"]
    motiv_aj_fora = 1 + (["Baixa","Normal","Alta","Máxima"].index(motivacao_fora)-1) * pesos["Motivação_F"]
    arb_aj_casa = 1 + ((arbitro - 5) / 10) * pesos["Árbitro_C"]
    arb_aj_fora = 1 + ((arbitro - 5) / 10) * pesos["Árbitro_F"]
    press_aj_casa = 1 + (["Baixa","Normal","Alta"].index(pressao_adeptos_casa)) * pesos["Pressão_C"]
    press_aj_fora = 1 + (["Baixa","Normal","Alta"].index(pressao_adeptos_fora)) * pesos["Pressão_F"]
    imp_aj_casa = 1 + (["Pouca","Normal","Importante","Decisivo"].index(importancia_jogo_casa)) * pesos["Importância_C"]
    imp_aj_fora = 1 + (["Pouca","Normal","Importante","Decisivo"].index(importancia_jogo_fora)) * pesos["Importância_F"]
    des_aj_casa = 1 - (["Baixo","Normal","Elevado"].index(desgaste_fisico_casa)) * pesos["Desgaste_C"]
    des_aj_fora = 1 - (["Baixo","Normal","Elevado"].index(desgaste_fisico_fora)) * pesos["Desgaste_F"]
    viag_aj_casa = 1 - (["Descanso","Viagem curta","Viagem longa","Calendário apertado"].index(viagem_casa)) * pesos["Viagem_C"]
    viag_aj_fora = 1 - (["Descanso","Viagem curta","Viagem longa","Calendário apertado"].index(viagem_fora)) * pesos["Viagem_F"]

    ajuste_total_casa = form_aj_casa * tipo_aj_casa * tit_aj_casa * motiv_aj_casa * arb_aj_casa * press_aj_casa * imp_aj_casa * des_aj_casa * viag_aj_casa
    ajuste_total_fora = form_aj_fora * tipo_aj_fora * tit_aj_fora * motiv_aj_fora * arb_aj_fora * press_aj_fora * imp_aj_fora * des_aj_fora * viag_aj_fora

    meteo_factor = METEO_MULT.get(meteo, 1.00)
    l_home_base = max(0.1, (media_marcados_casa + media_sofridos_fora) / 2)
    l_away_base = max(0.1, (media_marcados_fora + media_sofridos_casa) / 2)
    lh = l_home_base * ajuste_total_casa * meteo_factor
    la = l_away_base * ajuste_total_fora * meteo_factor
    prob_casa_aj, prob_empate_aj, prob_fora_aj = poisson_outcome_probs(lh, la, max_goals=12)

    eps = 1e-9
    odd_justa_casa   = 1.0 / max(eps, prob_casa_aj)
    odd_justa_empate = 1.0 / max(eps, prob_empate_aj)
    odd_justa_fora   = 1.0 / max(eps, prob_fora_aj)

    ev_casa   = calc_ev(prob_casa_aj, odd_casa)
    ev_empate = calc_ev(prob_empate_aj, odd_empate)
    ev_fora   = calc_ev(prob_fora_aj, odd_fora)

    stake_casa   = kelly_criterion(prob_casa_aj, odd_casa, banca)
    stake_empate = kelly_criterion(prob_empate_aj, odd_empate, banca)
    stake_fora   = kelly_criterion(prob_fora_aj, odd_fora, banca)

    # ---- Over/BTTS (MATCH)
    total_lambda = lh + la
    p_over15 = prob_over(total_lambda, 1.5)
    p_over25 = prob_over(total_lambda, 2.5)
    p_btts   = prob_btts(lh, la)

    df_res = pd.DataFrame({
        "Aposta": ["Vitória CASA","Empate","Vitória FORA"],
        "Odd": [odd_casa, odd_empate, odd_fora],
        "Odd Justa": [round(odd_justa_casa,2), round(odd_justa_empate,2), round(odd_justa_fora,2)],
        "Prob. (%)": [round(prob_casa_aj*100,1), round(prob_empate_aj*100,1), round(prob_fora_aj*100,1)],
        "EV": [ev_casa, ev_empate, ev_fora],
        "Stake (€)": [round(stake_casa,2), round(stake_empate,2), round(stake_fora,2)],
        "Valor": ["✅" if ev>0 and stv>0 else "❌"
                  for ev, stv in zip([ev_casa,ev_empate,ev_fora],[stake_casa,stake_empate,stake_fora])]
    })

    extra_markets = pd.DataFrame({
        "Aposta": ["Over 1.5 (Match)", "Over 2.5 (Match)", "BTTS (Match)"],
        "Odd": ["—","—","—"],
        "Odd Justa": [round(1/max(eps,p_over15),2), round(1/max(eps,p_over25),2), round(1/max(eps,p_btts),2)],
        "Prob. (%)": [round(p_over15*100,1), round(p_over25*100,1), round(p_btts*100,1)],
        "EV": ["—","—","—"], "Stake (€)": ["—","—","—"], "Valor": ["","",""],
    })
    df_res = pd.concat([df_res, extra_markets], ignore_index=True)

    dist_ajustes = [
        ["Formação", round(form_aj_casa,3), round(form_aj_fora,3)],
        ["Abordagem", round(tipo_aj_casa,3), round(tipo_aj_fora,3)],
        ["Titulares", round(tit_aj_casa,3), round(tit_aj_fora,3)],
        ["Motivação", round(motiv_aj_casa,3), round(motiv_aj_fora,3)],
        ["Árbitro", round(arb_aj_casa,3), round(arb_aj_fora,3)],
        ["Pressão", round(press_aj_casa,3), round(press_aj_fora,3)],
        ["Importância", round(imp_aj_casa,3), round(imp_aj_fora,3)],
        ["Desgaste", round(des_aj_casa,3), round(des_aj_fora,3)],
        ["Viagem", round(viag_aj_casa,3), round(viag_aj_fora,3)],
        ["AJUSTE TOTAL", round(ajuste_total_casa,3), round(ajuste_total_fora,3)],
        ["λ (golos) aj.", round(lh,3), round(la,3)],
        ["Meteo factor", round(meteo_factor,2), round(meteo_factor,2)],
        ["Prob. CASA", round(prob_casa_aj,3), ""],
        ["Prob. FORA", "", round(prob_fora_aj,3)],
    ]
    distrib_df = pd.DataFrame(dist_ajustes, columns=["Fator","Casa","Fora"])

    resumo_dict = {
        "Liga":[liga_escolhida], "Equipa CASA":[equipa_casa], "Equipa FORA":[equipa_fora],
        "Formação CASA":[form_casa], "Formação FORA":[form_fora],
        "Abordagem CASA":[tipo_form_casa], "Abordagem FORA":[tipo_form_fora],
        "Titulares CASA":[titulares_casa], "Titulares FORA":[titulares_fora],
        "Período do Jogo":[periodo_jogo], "Meteo":[meteo],
        "Nota Árbitro":[arbitro], "Tendência Cartões":[tendencia_cartoes], "Média Cartões":[media_cartoes],
        "Motivação CASA":[motivacao_casa], "Importância Jogo CASA":[importancia_jogo_casa], "Pressão Adeptos CASA":[pressao_adeptos_casa],
        "Desgaste CASA":[desgaste_fisico_casa], "Viagem CASA":[viagem_casa],
        "Motivação FORA":[motivacao_fora], "Importância Jogo FORA":[importancia_jogo_fora], "Pressão Adeptos FORA":[pressao_adeptos_fora],
        "Desgaste FORA":[desgaste_fisico_fora], "Viagem FORA":[viagem_fora],
        "Odd CASA":[odd_casa], "Odd EMPATE":[odd_empate], "Odd FORA":[odd_fora], "Banca (€)":[banca],
        "Média Marcados CASA":[media_marcados_casa], "Média Sofridos CASA":[media_sofridos_casa],
        "Média Marcados FORA":[media_marcados_fora], "Média Sofridos FORA":[media_sofridos_fora],
        "Média H2H CASA":[media_h2h_casa], "Média H2H FORA":[media_h2h_fora],
        "λ CASA (aj.)":[lh], "λ FORA (aj.)":[la], "Meteo factor":[meteo_factor],
        "Over1.5 prob":[round(p_over15*100,1)], "Over2.5 prob":[round(p_over25*100,1)], "BTTS prob":[round(p_btts*100,1)],
        "Over1.5 justa":[round(1/max(eps,p_over15),2)], "Over2.5 justa":[round(1/max(eps,p_over25),2)], "BTTS justa":[round(1/max(eps,p_btts),2)],
    }
    resumo_df = pd.DataFrame(resumo_dict)
    pesos_df = pd.DataFrame([pesos])

    st.session_state["analise_final"] = {
        "df_res": df_res, "distrib_df": distrib_df, "resumo_df": resumo_df, "pesos_df": pesos_df,
        "xg_2p": None, "ajuste": (ajuste_total_casa, ajuste_total_fora),
        "xg_ponderado": (prob_casa_aj, prob_empate_aj, prob_fora_aj)
    }

# ===================== MOSTRAR RESULTADOS (fora do botão) =====================
if "analise_final" in st.session_state:
    analise = st.session_state["analise_final"]
    st.subheader("Resultados da Análise")
    st.dataframe(analise["df_res"])
    st.subheader("Distribuição dos Ajustes & Pesos (Casa / Fora)")
    st.dataframe(analise["distrib_df"])
    st.subheader("📊 Pesos em uso")
    st.dataframe(analise["pesos_df"].T, use_container_width=True)
    relatorio = to_excel(analise["df_res"], analise["distrib_df"], analise["resumo_df"], analise["pesos_df"])
    st.download_button("⬇️ Download Relatório Completo (Excel)", data=relatorio, file_name="analise_prejogo_completa.xlsx")
    st.success("Análise pronta! Consulta apostas recomendadas, detalhes dos ajustes e exporta tudo para Excel.")
# ======== BLOCO LIVE / 2ª PARTE ========
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
        rating_casa = st.number_input("Rating global CASA (0-10)", min_value=0.0, max_value=10.0, value=7.0, step=0.01)
        rating_fora = st.number_input("Rating global FORA (0-10)", min_value=0.0, max_value=10.0, value=6.9, step=0.01)
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
        evento = {"tipo": tipo_evento, "equipa": equipa_evento, "detalhes": detalhes_evento}
        if posicao_ev:   evento["posicao"] = posicao_ev
        if tipo_troca_ev:evento["tipo_troca"] = tipo_troca_ev
        if nova_form_ev: evento["nova_formacao"] = nova
        if nova_form_ev: evento["nova_formacao"] = nova_form_ev
        if tipo_form_ev: evento["tipo_formacao"] = tipo_form_ev
        if imp_ev:       evento["importancia"] = imp_ev
        st.session_state["eventos_live"].append(evento)
        st.success("Evento adicionado! Atualiza previsão em baixo.")

    st.markdown("#### Eventos registados:")
    if st.session_state["eventos_live"]:
        for i, ev in enumerate(st.session_state["eventos_live"], 1):
            info_ev = f"{i}. {ev['tipo']} | {ev['equipa']}"
            if "posicao" in ev:        info_ev += f" | {ev['posicao']}"
            if "tipo_troca" in ev:     info_ev += f" | {ev['tipo_troca']}"
            if "nova_formacao" in ev:  info_ev += f" | Nova: {ev['nova_formacao']} ({ev.get('tipo_formacao','')})"
            if "importancia" in ev:    info_ev += f" | {ev['importancia']}"
            if ev.get('detalhes'):     info_ev += f" | {ev['detalhes']}"
            st.write(info_ev)
    else:
        st.write("Nenhum evento registado ainda.")

    # ---- Heurísticas simples para comentário / xG 2ª parte ----
    def interpretar_tatica(eventos, live_base, resultado):
        # placeholder simples; adapta à tua lógica
        n_evt = len(eventos)
        base = live_base.get("xg_casa", 0) + live_base.get("xg_fora", 0)
        if n_evt >= 4 or base >= 1.4:
            return "Jogo aberto: tendência para ocasiões na 2ª parte."
        if n_evt == 0 and base <= 0.6:
            return "Jogo fechado: poucas ocasiões claras até agora."
        return "Equilíbrio moderado com potencial de crescer."

    def calc_xg_live(live_base, eventos):
        # base: média dos xG das equipas na 1ª parte
        base_xg = (live_base.get("xg_casa", 0.0) + live_base.get("xg_fora", 0.0)) / 2.0
        # cada evento acrescenta um pequeno ajuste
        ajuste_eventos = 0.07 * len(eventos)
        # cartões vermelhos pesam mais
        reds = sum(1 for ev in eventos if ev.get("tipo") == "Expulsão")
        ajuste_reds = 0.20 * reds
        ajuste_total = ajuste_eventos + ajuste_reds
        return base_xg + ajuste_total, ajuste_total, base_xg

    st.markdown("### 🤖 **PauloDamas-GPT** — Interpretação Tática Live")
    comentario = interpretar_tatica(st.session_state["eventos_live"], st.session_state.get('live_base', {}), 0)
    st.info(comentario)

    if st.button("🔁 Atualizar Previsão com Eventos Live"):
        if 'live_base' not in st.session_state:
            st.error("Preenche e confirma primeiro as estatísticas da 1ª parte!")
        else:
            xg_2p, ajuste, xg_ponderado = calc_xg_live(
                st.session_state['live_base'],
                st.session_state["eventos_live"]
            )
            st.markdown(f"### 🟢 **Golos Esperados para a 2ª parte:** `{xg_2p:.2f}`")
            if xg_2p >= 1.6:
                st.success("⚽ Perspetiva de pelo menos 1 golo. Over 1.5 na 2ª parte pode ter valor.")
            elif xg_2p >= 1.2:
                st.info("⚠️ Espera-se 1 golo, com hipótese de 2. Over 1.0/1.25 pode ter valor.")
            else:
                st.warning("🔒 Jogo mais fechado. Cuidado com apostas em muitos golos na 2ª parte.")

            st.info(
                f"**Resumo do Ajuste:**\n\n"
                f"- xG ponderado (1ª parte): {xg_ponderado:.2f}\n"
                f"- Ajuste total (eventos): {ajuste:.2f}\n"
                f"- Eventos registados: {len(st.session_state['eventos_live'])}"
            )

# ---- ANÁLISE FINAL E EXPORTAÇÃO (ABA LIVE) ----
st.markdown("---")
st.subheader("📦 Análise Final (com base na 1ª parte + eventos)")
btn_disable = 'live_base' not in st.session_state
if st.button("Gerar Análise Final", disabled=btn_disable):
    if 'live_base' not in st.session_state:
        st.error("Preenche e confirma primeiro as estatísticas da 1ª parte!")
    else:
        xg_2p, ajuste, xg_ponderado = calc_xg_live(
            st.session_state['live_base'],
            st.session_state.get("eventos_live", [])
        )
        st.session_state["analise_final"] = {
            "xg_2p": xg_2p,
            "ajuste": ajuste,
            "xg_ponderado": xg_ponderado
        }
        st.success("✅ Análise final gerada e guardada!")

# Mostrar análise + exportação SE já existir
if "analise_final" in st.session_state:
    analise_final = st.session_state["analise_final"] or {}
    eventos = st.session_state.get("eventos_live", []) or []
    base = st.session_state.get("live_base", {}) or {}

    analise_final = sanitize_analysis(analise_final, keys=("xg_1p", "xg_2p", "xg_total"))

    st.markdown(f"### 🟢 Golos Esperados (2ª parte): {fmt_num(analise_final.get('xg_2p'))}")
    st.info(
        f"**Resumo do Ajuste:**\n\n"
        f"- xG ponderado: {fmt_any(analise_final.get('xg_ponderado'))}\n"
        f"- Ajuste total: {fmt_any(analise_final.get('ajuste'))}\n"
        f"- Eventos registados: {len(eventos)}"
    )

    xg_2p_val        = first_float(analise_final.get("xg_2p"))
    ajuste_val       = first_float(analise_final.get("ajuste"))
    xg_ponderado_val = first_float(analise_final.get("xg_ponderado"))

    excel_data = export_detalhado(base, eventos, xg_2p_val, ajuste_val, xg_ponderado_val)
    st.download_button(
        label="📥 Download Excel Detalhado (Live)",
        data=excel_data,
        file_name="live_detalhado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Botão independente de limpar eventos
if st.button("🗑️ Limpar eventos LIVE"):
    st.session_state["eventos_live"] = []
    st.success("Lista de eventos live limpa!")
