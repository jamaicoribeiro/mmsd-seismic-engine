import math
import csv
import os

import streamlit as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# --- 1. O MOTOR MMSD v3.2.3 ---
class MMSDEngine:
    def __init__(self, vs30_ref=760.0, exponent=0.43, sigma_ln=0.60):
        self.vs30_ref = vs30_ref
        self.exponent = exponent
        self.sigma_ln = sigma_ln

    def classificar_solo_ec8(self, vs30):
        if vs30 > 800:
            return "Classe A (Rocha sã / V_S30 > 800 m/s)"
        elif 360 <= vs30 <= 800:
            return "Classe B (Depósitos densos ou rocha branda / 360-800 m/s)"
        elif 180 <= vs30 < 360:
            return "Classe C/D (Solos de consistência média a fofa / 180-360 m/s)"
        else:
            return "Classe E (Solos moles com camada aluvial / V_S30 < 180 m/s)"

    def calcular_fator_solo(self, vs30, pga_rocha_g=0.0):
        fator_linear = (self.vs30_ref / vs30) ** self.exponent
        if pga_rocha_g > 0.10 and vs30 < 360.0:
            fator_nao_linear = 1.0 - 0.25 * (pga_rocha_g - 0.10) * ((360.0 - vs30) / 360.0)
            fator_final = max(1.0, fator_linear * fator_nao_linear)
        else:
            fator_final = fator_linear
        return fator_final, fator_linear

    def estimar_pga(self, mw, r_hipocentral, vs30):
        c0, c1, c2, c3 = 0.5, 0.8, -1.1, -0.003
        log_pga_rocha = c0 + (c1 * mw) + (c2 * math.log10(r_hipocentral)) + (c3 * r_hipocentral)
        pga_rocha_cm_s2 = min(10 ** log_pga_rocha, 2.5 * 980.665)
        pga_rocha_g = pga_rocha_cm_s2 / 980.665

        fator_solo, fator_linear = self.calcular_fator_solo(vs30, pga_rocha_g)
        pga_superficie_cm_s2 = pga_rocha_cm_s2 * fator_solo
        pga_g = pga_superficie_cm_s2 / 980.665
        
        fator_sigma = math.exp(self.sigma_ln)
        pga_g_p84 = pga_g * fator_sigma
        pga_g_p16 = max(0.01, pga_g / fator_sigma)

        return {
            "mw": mw,
            "r": r_hipocentral,
            "vs30": vs30,
            "classe_solo": self.classificar_solo_ec8(vs30),
            "fator_solo": round(fator_solo, 4),
            "pga_rocha_g": round(pga_rocha_g, 4),
            "pga_g": round(pga_g, 4),
            "pga_g_p16": round(pga_g_p16, 4),
            "pga_g_p84": round(pga_g_p84, 4)
        }

    def calcular_espectro_resposta(self, pga_g, vs30):
        periodos = [0.1, 0.2, 0.5, 1.0, 2.0]
        psa_resultados = {}
        fator_sigma = math.exp(self.sigma_ln)
        fator_solo_efetivo = (760.0 / vs30) ** 0.3
        
        for T in periodos:
            if T <= 0.2:
                amplificacao_T = 2.2 * fator_solo_efetivo * (T / 0.2)
            elif 0.2 < T <= 1.0:
                amplificacao_T = 2.5 * fator_solo_efetivo
            else:
                amplificacao_T = (2.5 * fator_solo_efetivo) * (1.0 / T)
                
            psa_med = pga_g * max(1.0, amplificacao_T)
            psa_resultados[f"T_{T}s_medio"] = round(psa_med, 4)
            psa_resultados[f"T_{T}s_p84"] = round(psa_med * fator_sigma, 4)
            psa_resultados[f"T_{T}s_p16"] = round(max(0.01, psa_med / fator_sigma), 4)
            
        return psa_resultados

    def calcular_cav(self, mw, pga_g):
        duracao_estimada = 5.0 * math.exp(0.4 * max(0.0, mw - 5.0))
        cav_gs = pga_g * duracao_estimada * 0.75
        return round(cav_gs, 3)

# --- 2. INTERFACE GRÁFICA STREAMLIT ---
st.set_page_config(page_title="MMSD v3.2.3 - Sismologia", page_icon="📈", layout="wide")

st.title("🌍 MMSD v3.2.3 — Motor de Engenharia Sísmica")
st.markdown("Plataforma interactiva para estimativa de PGA, classificação de solos (EC8), índice de energia (CAV) e espetros de resposta com incerteza.")

motor = MMSDEngine()

# Barra lateral para inputs
st.sidebar.header("⚙️ Parâmetros do Cenário")
nome_cenario = st.sidebar.text_input("Nome do Cenário", "Sismo_Customizado")
mw = st.sidebar.slider("Magnitude (Mw)", 4.0, 8.5, 6.5, 0.1)
r_dist = st.sidebar.slider("Distância Hipocentral (km)", 5.0, 500.0, 30.0, 5.0)
vs30 = st.sidebar.slider("Velocidade VS30 (m/s)", 100.0, 1000.0, 360.0, 10.0)

# Executar cálculos
res_pga = motor.estimar_pga(mw, r_dist, vs30)
espectro = motor.calcular_espectro_resposta(res_pga["pga_g"], vs30)
cav = motor.calcular_cav(mw, res_pga["pga_g"])

# Layout Principal em Colunas
col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("📊 Resultados da Análise")
    st.info(f"**Classificação do Solo:**\n{res_pga['classe_solo']}")
    
    st.metric(label="Aceleração de Pico (PGA Superfície)", value=f"{res_pga['pga_g']:.4f} g", delta=f"±1σ: [{res_pga['pga_g_p16']:.4f}g - {res_pga['pga_g_p84']:.4f}g]")
    st.metric(label="Energia Acumulada (CAV)", value=f"{cav} g-s")
    st.metric(label="PSA (Período T = 0.5s)", value=f"{espectro['T_0.5s_medio']:.4f} g", delta=f"+1σ: {espectro['T_0.5s_p84']:.4f}g")

with col2:
    st.subheader("📈 Espetro de Resposta (PSA)")
    
    periodos = [0.1, 0.2, 0.5, 1.0, 2.0]
    psa_medios = [espectro[f"T_{t}s_medio"] for t in periodos]
    psa_p84 = [espectro[f"T_{t}s_p84"] for t in periodos]
    psa_p16 = [espectro[f"T_{t}s_p16"] for t in periodos]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(periodos, psa_medios, 'o-', color='navy', lw=2, label='Média Esperada')
    ax.fill_between(periodos, psa_p16, psa_p84, color='skyblue', alpha=0.4, label='Banda de Incerteza (±1σ)')
    ax.set_title(f"Espetro de Resposta - {nome_cenario}", fontsize=11, fontweight='bold')
    ax.set_xlabel("Período Estrutural T (s)")
    ax.set_ylabel("PSA (g)")
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='upper right')
    fig.tight_layout()
    
    st.pyplot(fig)

# Botão para exportar dados para CSV diretamente na app web
if st.button("💾 Guardar Registo no Histórico CSV"):
    registo = {"Cenario": nome_cenario, **res_pga, "CAV_gs": cav, **espectro}
    existe = os.path.exists("resultados_web.csv")
    with open("resultados_web.csv", mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=registo.keys())
        if not existe:
            writer.writeheader()
        writer.writerow(registo)
    st.success("Registo guardado com sucesso em 'resultados_web.csv'!")