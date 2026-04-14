# -*- coding: utf-8 -*-
import json
import streamlit as st
import plotly.express as px
from src import (DatiPila, valida_dati, k1_da_forma, calcola_report,
                 sintesi_indicatori, serie_sensitivita_velocita,
                 serie_sensitivita_tirante, tabella_passaggi,
                 genera_pdf, commenti_progettuali,
                 verifiche_scalzamento, melville_coleman_2000,
                 velocita_critica_incipiente, classificazione_regime,
                 numero_froude)
from scalzamento_word import create_enhanced_word_report
from src_ui_utils import show_results_table

st.set_page_config(page_title="Scalzamento - Pila da ponte", layout="wide")
st.title("Scalzamento locale presso una pila da ponte")
st.caption("Software professionale: CSU/HEC-18, Melville & Coleman (2000), classificazione clear-water/live-bed, verifiche normative, report PDF.")

# ---------------------------------------------------------------------------
# Defaults e session state
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "scal_a": 1.50, "scal_L": 6.00,
    "scal_forma": "naso arrotondato",
    "scal_ang": 0.0,
    "scal_y1": 3.00, "scal_V1": 2.00,
    "scal_k1_auto": True,
    "scal_k1": 1.0, "scal_k2": 1.0, "scal_k3": 1.1, "scal_k4": 1.0,
    "scal_k2_auto": True,
    "scal_round_nose": True,
    "scal_k_fatt": 1.50,
    "scal_D50_mm": 1.0,
    "scal_Ss": 2.65,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Sidebar - Input
# ---------------------------------------------------------------------------
with st.sidebar:
    with st.expander("Salva / Carica parametri", expanded=False):
        uploaded = st.file_uploader("Carica parametri (JSON)", type=["json"],
                                    key="scal_upload")
        if uploaded is not None:
            try:
                loaded = json.loads(uploaded.read())
                if st.button("Applica parametri caricati", key="scal_apply"):
                    for k in _DEFAULTS:
                        if k in loaded:
                            st.session_state[k] = loaded[k]
                    st.rerun()
                st.caption(f"File: {uploaded.name}")
            except Exception:
                st.error("File JSON non valido.")

        params_json = json.dumps(
            {k: st.session_state[k] for k in _DEFAULTS}, indent=2
        ).encode()
        st.download_button("Scarica parametri JSON", params_json,
                           "scalzamento_parametri.json", "application/json")

    st.divider()
    st.header("Geometria della pila")
    larghezza_pila = st.number_input("Larghezza caratteristica a [m]",
                                     min_value=0.01, step=0.05, key="scal_a")
    lunghezza_pila = st.number_input("Lunghezza pila L [m]",
                                     min_value=0.01, step=0.10, key="scal_L")
    _forme = ["naso arrotondato", "naso quadrato", "cilindro circolare",
              "naso affilato", "gruppo di cilindri"]
    forma_naso = st.selectbox("Forma del naso della pila", _forme,
                              index=_forme.index(st.session_state["scal_forma"]),
                              key="scal_forma")
    angolo_attacco_gradi = st.number_input("Angolo di attacco del flusso [\u00b0]",
                                           min_value=0.0, max_value=90.0, step=1.0,
                                           key="scal_ang")

    st.header("Idraulica di monte")
    tirante_monte = st.number_input("Tirante indisturbato y\u2081 [m]",
                                    min_value=0.05, step=0.05, key="scal_y1")
    velocita_monte = st.number_input("Velocit\u00e0 media a monte V\u2081 [m/s]",
                                     min_value=0.01, step=0.05, key="scal_V1")

    st.header("Sedimento del fondo")
    D50_mm = st.number_input("D50 del sedimento [mm]", min_value=0.01,
                              max_value=500.0, step=0.5, key="scal_D50_mm")
    Ss = st.number_input("Peso specifico relativo Ss [-]", min_value=1.1,
                          max_value=4.0, step=0.05, key="scal_Ss")
    V_c = velocita_critica_incipiente(tirante_monte, D50_mm)
    regime_str = classificazione_regime(velocita_monte, V_c)
    _regime_table = [
        {"parametro": "V_c", "valore": round(V_c, 3), "unita": "m/s",
         "descrizione": "Velocità critica per inizio moto del sedimento (HEC-18, eq. 3.1)"},
        {"parametro": "Regime", "valore": regime_str, "unita": "-",
         "descrizione": "Classificazione regime di trasporto (clear-water / live-bed)"},
    ]
    show_results_table(_regime_table, titolo="Regime di trasporto")

    st.header("Coefficienti CSU / HEC-18")
    usa_k1_tipico = st.checkbox("Usa K1 tipico dalla forma del naso", key="scal_k1_auto")
    k1_default = k1_da_forma(forma_naso)
    k1 = st.number_input("K1 [-]", min_value=0.50, max_value=2.00, step=0.05,
                          disabled=usa_k1_tipico, key="scal_k1")
    usa_k2_automatico = st.checkbox("Calcola K2 automaticamente da L/a e angolo",
                                    key="scal_k2_auto")
    k2 = st.number_input("K2 manuale [-]", min_value=0.50, max_value=4.00, step=0.05,
                          disabled=usa_k2_automatico, key="scal_k2")
    k3 = st.number_input("K3 - condizioni del fondo [-]",
                          min_value=0.80, max_value=2.00, step=0.05, key="scal_k3")
    k4 = st.number_input("K4 - armoring [-]",
                          min_value=0.50, max_value=1.20, step=0.05, key="scal_k4")
    applica_limite_round_nose = st.checkbox("Applica limite per round nose allineata al flusso",
                                            key="scal_round_nose")

    st.header("Confronto fattoriale / placeholder")
    k_total_fattoriale = st.number_input("K_total fattoriale [-]",
                                         min_value=0.50, max_value=5.00, step=0.05,
                                         key="scal_k_fatt")

    

# Override K1 se checkbox attivo
if usa_k1_tipico:
    k1 = k1_default

# ---------------------------------------------------------------------------
# Calcolo
# ---------------------------------------------------------------------------
dati = DatiPila(
    larghezza_pila, lunghezza_pila, tirante_monte, velocita_monte,
    angolo_attacco_gradi, forma_naso, usa_k2_automatico,
    k1, k2, k3, k4, applica_limite_round_nose, k_total_fattoriale,
    D50_mm=D50_mm, Ss=Ss,
)
errori = valida_dati(dati)
if errori:
    for err in errori:
        st.error(err)
    st.stop()

report = calcola_report(dati)
indicatori = sintesi_indicatori(dati)
df_sens_v = serie_sensitivita_velocita(dati)
df_sens_y = serie_sensitivita_tirante(dati)
df_pass = tabella_passaggi(dati)
df_ver = verifiche_scalzamento(dati)
note = commenti_progettuali(dati)

# ---------------------------------------------------------------------------
# Sidebar - Esportazione Report (dopo il calcolo)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.divider()
    st.subheader("Esportazione Report")
    try:
        word_bytes = create_enhanced_word_report(dati)
        st.download_button(
            "Scarica Relazione Word (.docx)",
            data=word_bytes,
            file_name="Relazione_Scalzamento_Pila.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    except ImportError:
        st.warning("python-docx non installato. Eseguire: pip install python-docx")
    except Exception as e:
        st.error(f"Errore generazione Word: {e}")

    try:
        pdf_bytes = genera_pdf(dati, note)
        st.download_button(
            "Scarica Report PDF",
            data=pdf_bytes,
            file_name="scalzamento_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except ImportError:
        st.warning("fpdf2 non installato. Eseguire: pip install fpdf2")
    except Exception as e:
        st.error(f"Errore generazione PDF: {e}")

# ---------------------------------------------------------------------------
# Indicatori sintetici
# ---------------------------------------------------------------------------
n_ok  = (df_ver["Esito"] == "OK").sum()
n_att = (df_ver["Esito"] == "ATTENZIONE").sum()
n_no  = (df_ver["Esito"] == "NON OK").sum()

_indicatori_table = [
        {"parametro": "Fr", "valore": round(indicatori['Fr [-]'], 3), "unita": "-",
         "descrizione": "Numero di Froude (V₁/√(g·y₁))"},
        {"parametro": "V_c", "valore": round(indicatori['V_c [m/s]'], 3), "unita": "m/s",
         "descrizione": "Velocità critica per inizio moto del sedimento (HEC-18, eq. 3.1)"},
        {"parametro": "V/V_c", "valore": round(indicatori['V / V_c [-]'], 3), "unita": "-",
         "descrizione": f"Rapporto velocità/velocità critica → {indicatori['Regime']}"},
        {"parametro": "a/y₁", "valore": round(indicatori['a / y1 [-]'], 3), "unita": "-",
         "descrizione": "Rapporto larghezza pila / tirante"},
        {"parametro": "K2_eff", "valore": round(indicatori['K2 effettivo [-]'], 3), "unita": "-",
         "descrizione": "Coefficiente K2 effettivo (angolo d'attacco e L/a)"},
        {"parametro": "ys_max", "valore": round(indicatori['ys max [m]'], 4), "unita": "m",
         "descrizione": "Profondità di scalzamento conservativa (max tutte le formulazioni)"},
        {"parametro": "Verifica", "valore": f"{n_ok} OK / {n_att} ATTENZIONE / {n_no} NON OK", "unita": "-",
         "descrizione": "Riepilogo esiti verifiche normative"},
    ]
    show_results_table(_indicatori_table, titolo="Indicatori sintetici")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["Risultati", "Grafici", "Verifiche avanzate", "Note tecniche"])

with tab1:
    st.subheader("Passaggi di calcolo (passo per passo)")
    st.dataframe(df_pass, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Tabella di confronto formulazioni")
    st.dataframe(report, use_container_width=True, hide_index=True)

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        _input_table = [
            {"parametro": "a", "valore": round(larghezza_pila, 3), "unita": "m",
             "descrizione": "Larghezza caratteristica della pila"},
            {"parametro": "L", "valore": round(lunghezza_pila, 3), "unita": "m",
             "descrizione": f"Lunghezza della pila (L/a = {indicatori['L / a [-]']:.2f})"},
            {"parametro": "Forma naso", "valore": forma_naso, "unita": "-",
             "descrizione": f"Forma del naso della pila (K1 = {k1:.3f})"},
            {"parametro": "\u03b8", "valore": round(angolo_attacco_gradi, 1), "unita": "\u00b0",
             "descrizione": f"Angolo di attacco del flusso (K2 eff. = {indicatori['K2 effettivo [-]']:.4f})"},
            {"parametro": "y\u2081", "valore": round(tirante_monte, 3), "unita": "m",
             "descrizione": "Tirante indisturbato a monte"},
            {"parametro": "V\u2081", "valore": round(velocita_monte, 3), "unita": "m/s",
             "descrizione": f"Velocità media a monte (Fr = {indicatori['Fr [-]']:.4f})"},
            {"parametro": "D\u2085\u2080", "valore": round(D50_mm, 2), "unita": "mm",
             "descrizione": f"Diametro mediano del sedimento (Ss = {Ss:.2f})"},
        ]
        show_results_table(_input_table, titolo="Input geometria e idraulica")
    with col_b:
        _ys_csu = float(report.loc[report['Formulazione']=='CSU / HEC-18', 'ys [m]'].values[0])
        _ys_mc = float(report.loc[report['Formulazione']=='Melville & Coleman (2000)', 'ys [m]'].values[0])
        _risultati_table = [
            {"parametro": "V_c", "valore": round(indicatori['V_c [m/s]'], 3), "unita": "m/s",
             "descrizione": "Velocità critica per inizio moto (HEC-18, eq. 3.1)"},
            {"parametro": "V/V_c", "valore": round(indicatori['V / V_c [-]'], 3), "unita": "-",
             "descrizione": f"Rapporto velocità/velocità critica → {indicatori['Regime']}"},
            {"parametro": "ys CSU/HEC-18", "valore": round(_ys_csu, 4), "unita": "m",
             "descrizione": "Profondità di scalzamento CSU/HEC-18"},
            {"parametro": "ys Melville & Coleman", "valore": round(_ys_mc, 4), "unita": "m",
             "descrizione": "Profondità di scalzamento Melville & Coleman (2000)"},
            {"parametro": "ys conservativo (max)", "valore": round(indicatori['ys max [m]'], 4), "unita": "m",
             "descrizione": "Valore conservativo (massimo tra tutte le formulazioni)"},
            {"parametro": "Spread formulazioni", "valore": round(indicatori['spread [m]'], 4), "unita": "m",
             "descrizione": "Incertezza tra formulazioni (ys_max − ys_min)"},
        ]
        show_results_table(_risultati_table, titolo="Regime di trasporto e risultati")

    st.divider()
    col_dl1, col_dl2, col_dl3, col_dl4 = st.columns(4)
    with col_dl1:
        st.download_button("Scarica passaggi CSV",
                           df_pass.to_csv(index=False).encode("utf-8"),
                           "scalzamento_passaggi.csv", "text/csv")
    with col_dl2:
        st.download_button("Scarica risultati CSV",
                           report.to_csv(index=False).encode("utf-8"),
                           "scalzamento_risultati.csv", "text/csv")
    with col_dl3:
        try:
            pdf_bytes = genera_pdf(dati, note)
            st.download_button("Scarica Report PDF", pdf_bytes,
                               "scalzamento_report.pdf", "application/pdf")
        except ImportError:
            st.warning("fpdf2 non installato. Eseguire: pip install fpdf2")
    with col_dl4:
        try:
            word_bytes = create_enhanced_word_report(dati)
            st.download_button("Scarica Relazione Word", word_bytes,
                               "Relazione_Scalzamento_Pila.docx",
                               "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        except ImportError:
            st.warning("python-docx non installato. Eseguire: pip install python-docx")
        except Exception as e:
            st.error(f"Errore generazione Word: {e}")

with tab2:
    st.subheader("Confronto diretto delle formulazioni")
    fig_bar = px.bar(report, x="Formulazione", y="ys [m]", color="Formulazione",
                     text_auto=".3f", title="Profondit\u00e0 di scalzamento a confronto")
    fig_bar.update_layout(showlegend=False, xaxis_title="Formulazione", yaxis_title="ys [m]")
    st.plotly_chart(fig_bar, use_container_width=True)

    fig_ratio = px.bar(report, x="Formulazione", y="ys / a [-]", color="Formulazione",
                       text_auto=".2f", title="Profondit\u00e0 normalizzata ys / a")
    fig_ratio.update_layout(showlegend=False, xaxis_title="Formulazione", yaxis_title="ys / a [-]")
    st.plotly_chart(fig_ratio, use_container_width=True)

    st.subheader("Analisi di sensitivit\u00e0")
    opt = st.radio("Variabile di sensitivit\u00e0", ["Velocit\u00e0", "Tirante"], horizontal=True)
    if opt == "Velocit\u00e0":
        fig_sens_v = px.line(df_sens_v, x="Velocita [m/s]", y="ys [m]", color="Formulazione",
                             title="Sensitivit\u00e0 di ys rispetto alla velocit\u00e0 a monte")
        fig_sens_v.add_vline(x=V_c, line_dash="dash", line_color="red",
                             annotation_text=f"V_c={V_c:.2f} m/s", annotation_position="top right")
        fig_sens_v.update_layout(xaxis_title="Velocit\u00e0 [m/s]", yaxis_title="ys [m]")
        st.plotly_chart(fig_sens_v, use_container_width=True)
        st.download_button("Scarica CSV sensitivit\u00e0 velocit\u00e0",
                           df_sens_v.to_csv(index=False).encode("utf-8"),
                           "scalzamento_sensitivita_velocita.csv", "text/csv")
    else:
        fig_sens_y = px.line(df_sens_y, x="Tirante [m]", y="ys [m]", color="Formulazione",
                             title="Sensitivit\u00e0 di ys rispetto al tirante a monte")
        fig_sens_y.update_layout(xaxis_title="Tirante [m]", yaxis_title="ys [m]")
        st.plotly_chart(fig_sens_y, use_container_width=True)
        st.download_button("Scarica CSV sensitivit\u00e0 tirante",
                           df_sens_y.to_csv(index=False).encode("utf-8"),
                           "scalzamento_sensitivita_tirante.csv", "text/csv")

with tab3:
    st.subheader("Verifiche normative")
    _colori = {"OK": "background-color: #d4edda",
               "ATTENZIONE": "background-color: #fff3cd",
               "NON OK": "background-color: #f8d7da",
               "INFO": "background-color: #d1ecf1"}

    def _colora_righe(row):
        c = _colori.get(row["Esito"], "")
        return [c] * len(row)

    styled = df_ver.style.apply(_colora_righe, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Regime di trasporto - Dettaglio")
    col_reg1, col_reg2 = st.columns(2)
    with col_reg1:
        _regime_dettaglio_table = [
            {"parametro": "V_c", "valore": round(V_c, 4), "unita": "m/s",
             "descrizione": "Velocità critica per inizio moto (HEC-18, eq. 3.1)"},
            {"parametro": "V\u2081", "valore": round(velocita_monte, 4), "unita": "m/s",
             "descrizione": "Velocità media a monte della pila"},
            {"parametro": "V/V_c", "valore": round(velocita_monte / V_c, 4), "unita": "-",
             "descrizione": f"Rapporto velocità → {regime_str}"},
        ]
        show_results_table(_regime_dettaglio_table, titolo="Regime di trasporto")
        st.caption("Formula V_c = 6.19 \u00b7 y\u2081^(1/6) \u00b7 D50^(1/3)  (HEC-18, eq. 3.1)")
    with col_reg2:
        from src import _k_yb_melville, _k_intensity_melville
        K_yb = _k_yb_melville(tirante_monte, larghezza_pila)
        K_I = _k_intensity_melville(velocita_monte, V_c)
        _melville_table = [
            {"parametro": "K_yb", "valore": round(K_yb, 4), "unita": "-",
             "descrizione": "Fattore geometrico profondità/larghezza (Melville & Coleman, 2000)"},
            {"parametro": "K_I", "valore": round(K_I, 4), "unita": "-",
             "descrizione": "Fattore intensità del flusso (Melville & Coleman, 2000)"},
            {"parametro": "ys_MC", "valore": round(2 * K_yb * K_I * larghezza_pila, 4), "unita": "m",
             "descrizione": "Profondità di scalzamento = 2·K_yb·K_I·a (Melville & Coleman, 2000)"},
        ]
        show_results_table(_melville_table, titolo="Melville & Coleman — Dettaglio")

    st.divider()
    st.download_button("Scarica verifiche CSV",
                       df_ver.to_csv(index=False).encode("utf-8"),
                       "scalzamento_verifiche.csv", "text/csv")

with tab4:
    st.subheader("Commenti automatici di supporto")
    for item in note:
        st.markdown(f"- {item}")
    with st.expander("Come leggere i risultati e riferimenti normativi"):
        st.markdown("""
**CSU / HEC-18:**
ys = 2 \u00b7 K1 \u00b7 K2 \u00b7 K3 \u00b7 K4 \u00b7 a^0.65 \u00b7 y\u2081^0.35 \u00b7 Fr^0.43
- K1: forma naso (quadrato=1.1, arrotondato/cilindro=1.0, affilato=0.9)
- K2: angolo d'attacco e rapporto L/a
- K3: condizioni del fondo (plane bed=1.1, dune medie=1.15, dune grandi=1.3)
- K4: fattore armoring (< 1.0 se il fondo e' protetto da ghiaia grossa)

**Melville & Coleman (2000):**
ys = 2 \u00b7 K_yb \u00b7 K_I \u00b7 a
- K_yb: fattore geometrico profondita'/larghezza (1.0 se y\u2081/a >= 3)
- K_I: min(1, V/V_c) - considera il regime clear-water/live-bed

**Velocit\u00e0 critica per inizio moto (HEC-18):**
V_c = 6.19 \u00b7 y\u2081^(1/6) \u00b7 D50^(1/3)  [m/s, m, m]

**Classificazione regime:**
- Clear-water (V \u2264 V_c): trasporto assente, scalzamento progressivo verso equilibrio
- Live-bed (V > V_c): trasporto generalizzato, scalzamento \u00e8 dinamico

**Riferimenti normativi:**
- HEC-18 (5\u00aa ed., FHWA): formula CSU principale
- Melville & Coleman (2000): formula alternativa con regime di trasporto
- EN 1997 (Eurocodice 7): aspetti geotecnici di progetto
        """)
