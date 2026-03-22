# -*- coding: utf-8 -*-
"""
SCALZAMENTO LOCALE - Pila da ponte.
Versione professionale:
- Formula CSU / HEC-18 con tutti i coefficienti K1...K4
- Formula Melville & Coleman (2000) semplificata
- Classificazione live-bed / clear-water (velocita' critica di Shields/HEC-18)
- Verifiche normative tabellari
- Tabella passaggi completa (25 passi)
- Analisi di sensitivita' (velocita' e tirante)
- Generazione report PDF
"""
from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, asdict
from typing import Callable, Dict, List, Tuple, Optional

import numpy as np
import pandas as pd

G = 9.81


# ---------------------------------------------------------------------------
# Dataclass input
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DatiPila:
    larghezza_pila: float
    lunghezza_pila: float
    tirante_monte: float
    velocita_monte: float
    angolo_attacco_gradi: float = 0.0
    forma_naso: str = "naso arrotondato"
    usa_k2_automatico: bool = True
    k1: float = 1.0
    k2: float = 1.0
    k3: float = 1.1
    k4: float = 1.0
    applica_limite_round_nose: bool = True
    k_total_fattoriale: float = 1.50
    # Parametri sedimento (per Melville & Coleman e regime)
    D50_mm: float = 1.0       # diametro mediano sedimento [mm]
    Ss: float = 2.65          # peso specifico relativo del sedimento [-]


@dataclass(frozen=True)
class MetaFormula:
    nome: str
    riferimento: str
    nota: str


# ---------------------------------------------------------------------------
# Validazione
# ---------------------------------------------------------------------------

def valida_dati(dati: DatiPila) -> List[str]:
    errori: List[str] = []
    if dati.larghezza_pila <= 0:
        errori.append("La larghezza della pila deve essere maggiore di 0 m.")
    if dati.lunghezza_pila <= 0:
        errori.append("La lunghezza della pila deve essere maggiore di 0 m.")
    if dati.tirante_monte <= 0:
        errori.append("Il tirante a monte deve essere maggiore di 0 m.")
    if dati.velocita_monte <= 0:
        errori.append("La velocita a monte deve essere maggiore di 0 m/s.")
    if not (0 <= dati.angolo_attacco_gradi <= 90):
        errori.append("L'angolo di attacco deve essere compreso tra 0 e 90 gradi.")
    for nome, valore in [("K1", dati.k1), ("K2", dati.k2), ("K3", dati.k3), ("K4", dati.k4)]:
        if valore <= 0:
            errori.append(f"Il coefficiente {nome} deve essere positivo.")
    if dati.k_total_fattoriale <= 0:
        errori.append("Il coefficiente K_total della formulazione fattoriale deve essere positivo.")
    if dati.forma_naso not in {"naso arrotondato", "naso quadrato", "cilindro circolare",
                               "naso affilato", "gruppo di cilindri"}:
        errori.append("La forma del naso selezionata non e' supportata.")
    if dati.D50_mm <= 0:
        errori.append("Il D50 del sedimento deve essere positivo.")
    if dati.Ss <= 1.0:
        errori.append("Il peso specifico relativo Ss deve essere maggiore di 1.0.")
    return errori


# ---------------------------------------------------------------------------
# Parametri idraulici e di trasporto
# ---------------------------------------------------------------------------

def numero_froude(velocita: float, tirante: float) -> float:
    return velocita / math.sqrt(G * tirante) if tirante > 0 else float("nan")


def rapporto_a_su_y1(a: float, y1: float) -> float:
    return a / y1 if y1 > 0 else float("nan")


def rapporto_l_su_a(lunghezza: float, larghezza: float) -> float:
    return lunghezza / larghezza if larghezza > 0 else float("nan")


def velocita_critica_incipiente(y1: float, D50_mm: float) -> float:
    """
    Velocita' critica per l'inizio del moto del sedimento (HEC-18):
    V_c = 6.19 * y1^(1/6) * D50^(1/3)   [m/s, m, m]
    Riferimento: Richardson & Davis HEC-18 (5a ed.), eq. (3.1).
    """
    D50_m = D50_mm / 1000.0
    return 6.19 * (y1 ** (1.0 / 6.0)) * (D50_m ** (1.0 / 3.0))


def classificazione_regime(V: float, V_c: float) -> str:
    """Live-bed se V > V_c, clear-water altrimenti."""
    return "Live-bed (trasporto generalizzato)" if V > V_c else "Clear-water (senza trasporto)"


# ---------------------------------------------------------------------------
# Coefficienti CSU / HEC-18
# ---------------------------------------------------------------------------

def k1_da_forma(forma_naso: str) -> float:
    mapping = {
        "naso quadrato": 1.1,
        "naso arrotondato": 1.0,
        "cilindro circolare": 1.0,
        "gruppo di cilindri": 1.0,
        "naso affilato": 0.9,
    }
    return mapping.get(forma_naso, 1.0)


def k2_automatico(lunghezza_pila: float, larghezza_pila: float,
                  angolo_attacco_gradi: float) -> float:
    theta_rad = math.radians(angolo_attacco_gradi)
    la = min(12.0, rapporto_l_su_a(lunghezza_pila, larghezza_pila))
    base = math.cos(theta_rad) + la * math.sin(theta_rad)
    return base ** 0.65


def descrizione_coeff_k3(k3: float) -> str:
    if k3 <= 1.10:
        return "clear-water / plane bed / antidune"
    if k3 <= 1.20:
        return "dune medie"
    return "dune grandi o condizioni piu' penalizzanti"


# ---------------------------------------------------------------------------
# Formula CSU / HEC-18
# ---------------------------------------------------------------------------

def csu_hec18(dati: DatiPila) -> float:
    fr = numero_froude(dati.velocita_monte, dati.tirante_monte)
    k2_eff = (k2_automatico(dati.lunghezza_pila, dati.larghezza_pila, dati.angolo_attacco_gradi)
              if dati.usa_k2_automatico else dati.k2)
    ys = (2.0 * dati.k1 * k2_eff * dati.k3 * dati.k4 *
          (dati.larghezza_pila ** 0.65) * (dati.tirante_monte ** 0.35) * (fr ** 0.43))
    return max(0.0, ys)


def csu_hec18_con_limite_round_nose(dati: DatiPila) -> float:
    ys = csu_hec18(dati)
    if not dati.applica_limite_round_nose:
        return ys
    if dati.forma_naso != "naso arrotondato":
        return ys
    if abs(dati.angolo_attacco_gradi) > 1e-9:
        return ys
    fr = numero_froude(dati.velocita_monte, dati.tirante_monte)
    limite = 2.4 * dati.larghezza_pila if fr <= 0.8 else 3.0 * dati.larghezza_pila
    return min(ys, limite)


# ---------------------------------------------------------------------------
# Formula Melville & Coleman (2000) - semplificata
# ---------------------------------------------------------------------------

def _k_yb_melville(y1: float, a: float) -> float:
    """
    Fattore geometrico K_yb (profondita'/larghezza) per la formula Melville & Coleman.
    - y1/a >= 3   -> K_yb = 1.0 (pila "stretta" rispetto al tirante)
    - 0.2 <= y1/a < 3 -> K_yb = sqrt(y1 * a) / (sqrt(3) * a) = sqrt(y1/(3*a))
    - y1/a < 0.2  -> K_yb = 0.1 * sqrt(y1/a) (pila "larga", flusso quasi 2D)
    Rif.: Melville & Coleman (2000), Bridge Scour, cap. 3.
    """
    ratio = y1 / a if a > 0 else float("nan")
    if math.isnan(ratio):
        return float("nan")
    if ratio >= 3.0:
        return 1.0
    elif ratio >= 0.2:
        return math.sqrt(ratio / 3.0)
    else:
        return 0.1 * math.sqrt(ratio)


def _k_intensity_melville(V: float, V_c: float) -> float:
    """
    Fattore intensita' del flusso K_I (Melville & Coleman).
    - V/V_c <= 1 (clear-water): K_I = V/V_c
    - V/V_c > 1 (live-bed):     K_I = 1.0 (approssimazione conservativa)
    """
    if V_c <= 0:
        return float("nan")
    ratio_v = V / V_c
    return min(1.0, ratio_v)


def melville_coleman_2000(dati: DatiPila) -> float:
    """
    Profondita' di scalzamento secondo Melville & Coleman (2000) - semplificata.
    ys = 2.0 * K_yb * K_I * a
    dove:
    - K_yb: fattore geometrico profondita'/larghezza (vedi _k_yb_melville)
    - K_I: fattore intensita' flusso (V/V_c, cappato a 1 in live-bed)
    - a: larghezza caratteristica della pila
    Nota: la formula completa include anche K_D (granulometria), K_s (forma pila),
    K_theta (angolo). Qui K_s e K_theta sono trattati tramite K1 e K2 CSU.
    Rif.: Melville & Coleman (2000), Bridge Scour, Water Resources Publications.
    """
    a = dati.larghezza_pila
    y1 = dati.tirante_monte
    V = dati.velocita_monte
    V_c = velocita_critica_incipiente(y1, dati.D50_mm)
    K_yb = _k_yb_melville(y1, a)
    K_I = _k_intensity_melville(V, V_c)
    ys = 2.0 * K_yb * K_I * a
    return max(0.0, ys)


# ---------------------------------------------------------------------------
# Metodo fattoriale (placeholder estendibile)
# ---------------------------------------------------------------------------

def fattoriale_utente(dati: DatiPila) -> float:
    return dati.k_total_fattoriale * dati.larghezza_pila


# ---------------------------------------------------------------------------
# Registry formule
# ---------------------------------------------------------------------------

FormulaFunc = Callable[[DatiPila], float]


def registry_formule() -> Dict[str, Tuple[FormulaFunc, MetaFormula]]:
    return {
        "CSU / HEC-18": (
            csu_hec18,
            MetaFormula("CSU / HEC-18", "HEC-RAS Hydraulic Reference Manual / HEC-18",
                        "Formula generale con K1, K2, K3, K4; K2 calcolato automaticamente o manuale."),
        ),
        "CSU / HEC-18 con limite round nose": (
            csu_hec18_con_limite_round_nose,
            MetaFormula("CSU / HEC-18 con limite round nose",
                        "HEC-RAS Hydraulic Reference Manual / HEC-18",
                        "Applica limite per pila a naso arrotondato allineata al flusso."),
        ),
        "Melville & Coleman (2000)": (
            melville_coleman_2000,
            MetaFormula("Melville & Coleman (2000)",
                        "Melville & Coleman, Bridge Scour, Water Resources Publications, 2000",
                        "Formula Kyb*KI*a semplificata; considera regime clear-water/live-bed."),
        ),
        "Fattoriale utente (estendibile)": (
            fattoriale_utente,
            MetaFormula("Fattoriale utente (estendibile)", "Schema parametrico trasparente",
                        "Metodo esplicito: ys = K_total * a. Utile per confronto e estensioni."),
        ),
    }


# ---------------------------------------------------------------------------
# Calcola report confronto formulazioni
# ---------------------------------------------------------------------------

def calcola_report(dati: DatiPila) -> pd.DataFrame:
    righe = []
    for nome, (func, meta) in registry_formule().items():
        ys = func(dati)
        righe.append({
            "Formulazione": nome,
            "ys [m]": round(ys, 4),
            "ys / a [-]": round(ys / dati.larghezza_pila, 4),
            "Riferimento": meta.riferimento,
            "Nota tecnica": meta.nota,
        })
    return pd.DataFrame(righe).sort_values("ys [m]", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Sintesi indicatori
# ---------------------------------------------------------------------------

def sintesi_indicatori(dati: DatiPila) -> dict:
    report = calcola_report(dati)
    ys_max = float(report["ys [m]"].max())
    ys_min = float(report["ys [m]"].min())
    V_c = velocita_critica_incipiente(dati.tirante_monte, dati.D50_mm)
    return {
        "Fr [-]": numero_froude(dati.velocita_monte, dati.tirante_monte),
        "a / y1 [-]": rapporto_a_su_y1(dati.larghezza_pila, dati.tirante_monte),
        "L / a [-]": rapporto_l_su_a(dati.lunghezza_pila, dati.larghezza_pila),
        "K2 effettivo [-]": (k2_automatico(dati.lunghezza_pila, dati.larghezza_pila,
                                           dati.angolo_attacco_gradi)
                             if dati.usa_k2_automatico else dati.k2),
        "V_c [m/s]": V_c,
        "V / V_c [-]": dati.velocita_monte / V_c if V_c > 0 else float("nan"),
        "Regime": classificazione_regime(dati.velocita_monte, V_c),
        "ys max [m]": ys_max,
        "ys min [m]": ys_min,
        "spread [m]": ys_max - ys_min,
    }


# ---------------------------------------------------------------------------
# Verifiche normative
# ---------------------------------------------------------------------------

def verifiche_scalzamento(dati: DatiPila) -> pd.DataFrame:
    """
    Tabella verifiche normative per scalzamento locale.
    Colonne: N., Verifica, Valore calcolato, Limite/soglia, Esito, Riferimento normativo
    """
    fr = numero_froude(dati.velocita_monte, dati.tirante_monte)
    a_y1 = rapporto_a_su_y1(dati.larghezza_pila, dati.tirante_monte)
    l_a = rapporto_l_su_a(dati.lunghezza_pila, dati.larghezza_pila)
    k2_eff = (k2_automatico(dati.lunghezza_pila, dati.larghezza_pila, dati.angolo_attacco_gradi)
              if dati.usa_k2_automatico else dati.k2)
    V_c = velocita_critica_incipiente(dati.tirante_monte, dati.D50_mm)
    V_Vc = dati.velocita_monte / V_c if V_c > 0 else float("nan")
    ys_csu = csu_hec18(dati)
    ys_max = max(func(dati) for func, _ in registry_formule().values())

    rows: List[dict] = []

    # 1. Numero di Froude
    if fr < 0.8:
        esito, esito_note = "OK", "moto subcritico"
    elif fr < 1.0:
        esito, esito_note = "ATTENZIONE", "prossimo al critico"
    else:
        esito, esito_note = "NON OK", "moto supercritico"
    rows.append({
        "N.": 1, "Verifica": "Numero di Froude",
        "Valore calcolato": f"{fr:.4f}",
        "Limite/soglia": "< 0.80 (consigliato)",
        "Esito": esito,
        "Riferimento normativo": f"HEC-18; {esito_note}",
    })

    # 2. Regime di trasporto
    if V_Vc <= 1.0:
        esito_reg = "INFO"
        note_reg = "Clear-water: la formula CSU e' applicabile direttamente"
    else:
        esito_reg = "ATTENZIONE"
        note_reg = "Live-bed: verificare con cura la selezione di K3 e D50"
    rows.append({
        "N.": 2, "Verifica": "Regime di trasporto (V/V_c)",
        "Valore calcolato": f"{V_Vc:.4f}" if not math.isnan(V_Vc) else "n.d.",
        "Limite/soglia": "V/V_c <= 1 (clear-water)",
        "Esito": esito_reg,
        "Riferimento normativo": f"HEC-18 eq.3.1; {note_reg}",
    })

    # 3. Angolo di attacco
    ang = dati.angolo_attacco_gradi
    if ang <= 5:
        esito_ang = "OK"
    elif ang <= 15:
        esito_ang = "ATTENZIONE"
    else:
        esito_ang = "NON OK"
    rows.append({
        "N.": 3, "Verifica": "Angolo di attacco del flusso",
        "Valore calcolato": f"{ang:.1f} gradi",
        "Limite/soglia": "<= 5 gradi (preferibile)",
        "Esito": esito_ang,
        "Riferimento normativo": "HEC-18; K2 cresce fortemente con l'angolo",
    })

    # 4. Rapporto a / y1
    if a_y1 <= 0.8:
        esito_ay = "OK"
    elif a_y1 <= 2.0:
        esito_ay = "ATTENZIONE"
    else:
        esito_ay = "NON OK"
    rows.append({
        "N.": 4, "Verifica": "Rapporto a / y1 (larghezza / tirante)",
        "Valore calcolato": f"{a_y1:.4f}",
        "Limite/soglia": "<= 0.80 (intervallo tipico)",
        "Esito": esito_ay,
        "Riferimento normativo": "Melville & Coleman (2000); HEC-18",
    })

    # 5. K2 effettivo
    if k2_eff <= 1.0:
        esito_k2 = "OK"
    elif k2_eff <= 1.5:
        esito_k2 = "ATTENZIONE"
    else:
        esito_k2 = "NON OK"
    rows.append({
        "N.": 5, "Verifica": "Coefficiente K2 effettivo",
        "Valore calcolato": f"{k2_eff:.4f}",
        "Limite/soglia": "<= 1.0 (allineato al flusso)",
        "Esito": esito_k2,
        "Riferimento normativo": "HEC-18; aumenta con angolo e L/a",
    })

    # 6. ys/a ratio (adimensionale scalzamento)
    ys_a = ys_csu / dati.larghezza_pila
    if ys_a <= 2.4:
        esito_ysa = "OK"
    elif ys_a <= 3.0:
        esito_ysa = "ATTENZIONE"
    else:
        esito_ysa = "NON OK"
    rows.append({
        "N.": 6, "Verifica": "Scalzamento normalizzato ys / a (CSU/HEC-18)",
        "Valore calcolato": f"{ys_a:.4f}",
        "Limite/soglia": "<= 2.4 (round nose, allineata)",
        "Esito": esito_ysa,
        "Riferimento normativo": "HEC-18; limite teorico per round nose allineata",
    })

    # 7. K4 armoring
    if dati.k4 >= 1.0:
        esito_k4 = "OK"
        note_k4 = "Nessuna riduzione da armoring"
    else:
        esito_k4 = "INFO"
        note_k4 = "Documentare analisi granulometrica"
    rows.append({
        "N.": 7, "Verifica": "Fattore armoring K4",
        "Valore calcolato": f"{dati.k4:.3f}",
        "Limite/soglia": "= 1.0 (no armoring) oppure < 1.0",
        "Esito": esito_k4,
        "Riferimento normativo": f"HEC-18; {note_k4}",
    })

    # 8. K3 condizioni fondo
    desc_k3 = descrizione_coeff_k3(dati.k3)
    if dati.k3 <= 1.10:
        esito_k3 = "OK"
    elif dati.k3 <= 1.20:
        esito_k3 = "ATTENZIONE"
    else:
        esito_k3 = "NON OK"
    rows.append({
        "N.": 8, "Verifica": "Condizioni fondo K3",
        "Valore calcolato": f"{dati.k3:.3f} ({desc_k3})",
        "Limite/soglia": "<= 1.10 (clear-water / plane bed)",
        "Esito": esito_k3,
        "Riferimento normativo": "HEC-18",
    })

    # 9. ys massimo tra tutte le formule
    rows.append({
        "N.": 9, "Verifica": "ys conservativo (massimo tra tutte le formule)",
        "Valore calcolato": f"{ys_max:.4f} m",
        "Limite/soglia": "Valore progettuale da usare",
        "Esito": "INFO",
        "Riferimento normativo": "HEC-18; Melville & Coleman (2000)",
    })

    # 10. Spread formulazioni
    ys_min_all = min(func(dati) for func, _ in registry_formule().values())
    spread = ys_max - ys_min_all
    spread_pct = spread / ys_max * 100 if ys_max > 0 else 0.0
    rows.append({
        "N.": 10, "Verifica": "Incertezza tra formulazioni (spread)",
        "Valore calcolato": f"{spread:.4f} m ({spread_pct:.1f}%)",
        "Limite/soglia": "< 30% (buona coerenza)",
        "Esito": "OK" if spread_pct <= 30 else "ATTENZIONE",
        "Riferimento normativo": "Analisi comparativa multi-formula",
    })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Sensitivita'
# ---------------------------------------------------------------------------

def serie_sensitivita_velocita(dati: DatiPila, v_min: Optional[float] = None,
                               v_max: Optional[float] = None, n_punti: int = 40) -> pd.DataFrame:
    if v_min is None:
        v_min = max(0.10, 0.50 * dati.velocita_monte)
    if v_max is None:
        v_max = 1.50 * dati.velocita_monte
    records = []
    for v in np.linspace(v_min, v_max, n_punti):
        dati_v = DatiPila(**{**asdict(dati), "velocita_monte": float(v)})
        for nome, (func, _) in registry_formule().items():
            records.append({"Velocita [m/s]": float(v), "Formulazione": nome,
                            "ys [m]": func(dati_v)})
    return pd.DataFrame(records)


def serie_sensitivita_tirante(dati: DatiPila, y_min: Optional[float] = None,
                              y_max: Optional[float] = None, n_punti: int = 40) -> pd.DataFrame:
    if y_min is None:
        y_min = max(0.10, 0.50 * dati.tirante_monte)
    if y_max is None:
        y_max = 1.50 * dati.tirante_monte
    records = []
    for y in np.linspace(y_min, y_max, n_punti):
        dati_y = DatiPila(**{**asdict(dati), "tirante_monte": float(y)})
        for nome, (func, _) in registry_formule().items():
            records.append({"Tirante [m]": float(y), "Formulazione": nome,
                            "ys [m]": func(dati_y)})
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Tabella passaggi di calcolo
# ---------------------------------------------------------------------------

def tabella_passaggi(dati: DatiPila) -> pd.DataFrame:
    fr = numero_froude(dati.velocita_monte, dati.tirante_monte)
    a_y1 = rapporto_a_su_y1(dati.larghezza_pila, dati.tirante_monte)
    l_a = rapporto_l_su_a(dati.lunghezza_pila, dati.larghezza_pila)
    k2_eff = (k2_automatico(dati.lunghezza_pila, dati.larghezza_pila, dati.angolo_attacco_gradi)
              if dati.usa_k2_automatico else dati.k2)
    theta_rad = math.radians(dati.angolo_attacco_gradi)
    la_capped = min(12.0, l_a)
    base_k2 = math.cos(theta_rad) + la_capped * math.sin(theta_rad)

    ys_csu = csu_hec18(dati)
    ys_csu_lim = csu_hec18_con_limite_round_nose(dati)
    ys_mc = melville_coleman_2000(dati)
    ys_fatt = fattoriale_utente(dati)

    fr_exp = fr ** 0.43
    a_exp = dati.larghezza_pila ** 0.65
    y_exp = dati.tirante_monte ** 0.35

    V_c = velocita_critica_incipiente(dati.tirante_monte, dati.D50_mm)
    K_yb = _k_yb_melville(dati.tirante_monte, dati.larghezza_pila)
    K_I = _k_intensity_melville(dati.velocita_monte, V_c)
    regime = classificazione_regime(dati.velocita_monte, V_c)

    rows = [
        (1,  "Larghezza pila (input)",        "a",       "input",
             f"{dati.larghezza_pila:.4f}", "m",      "Dimensione caratteristica della pila: larghezza perpendicolare al flusso"),
        (2,  "Lunghezza pila (input)",         "L",       "input",
             f"{dati.lunghezza_pila:.4f}", "m",      "Lunghezza della pila nella direzione del flusso"),
        (3,  "Tirante a monte (input)",        "y1",      "input",
             f"{dati.tirante_monte:.4f}",  "m",      "Profondita' dell'acqua a monte indisturbato"),
        (4,  "Velocita' a monte (input)",      "V1",      "input",
             f"{dati.velocita_monte:.4f}", "m/s",    "Velocita' media del flusso a monte della pila"),
        (5,  "D50 sedimento (input)",          "D50",     "input",
             f"{dati.D50_mm:.3f}",         "mm",     "Diametro mediano del sedimento del fondo"),
        (6,  "Numero di Froude",               "Fr",      "V1/sqrt(g*y1)",
             f"{fr:.5f}",                  "-",      "Fr<1: subcritico; Fr>1: supercritico. Influenza lo scalzamento (Fr^0.43 in CSU)"),
        (7,  "Rapporto a / y1",                "a/y1",    "a / y1",
             f"{a_y1:.5f}",               "-",      "Rapporto larghezza pila / tirante: pilastro 'largo' se > 1"),
        (8,  "Rapporto L / a",                 "L/a",     "L / a",
             f"{l_a:.5f}",                "-",      "Allungamento della pila: influenza K2 per angoli di attacco non nulli"),
        (9,  "L/a cappato a 12",               "la*",     "min(12, L/a)",
             f"{la_capped:.5f}",          "-",      "L/a viene cappato a 12 nella formula K2 per evitare sovrastima"),
        (10, "Base calcolo K2 (CSU)",          "base",    "cos(ang)+la*sin(ang)",
             f"{base_k2:.5f}",            "-",      "Termine intermedio che combina angolo d'attacco e allungamento"),
        (11, "K2 effettivo (CSU)",             "K2",      "base^0.65",
             f"{k2_eff:.5f}",             "-",      "Fattore angolo d'attacco e forma: K2=1 se allineata, K2>1 se obliqua"),
        (12, "K1 (forma naso)",                "K1",      f"forma: {dati.forma_naso}",
             f"{dati.k1:.4f}",            "-",      "Fattore forma naso pila: quadrato=1.1, arrotondato/cil.=1.0, affilato=0.9"),
        (13, "K3 (condizioni fondo)",          "K3",      "input",
             f"{dati.k3:.4f}",            "-",      "Fattore morfologia del fondo: plane bed=1.1, dune medie=1.15, grandi=1.3"),
        (14, "K4 (armoring)",                  "K4",      "input",
             f"{dati.k4:.4f}",            "-",      "Fattore armoring: riduce ys se il fondo e' protetto da ghiaia grossa"),
        (15, "a^0.65 (CSU)",                   "a^0.65",  "a^0.65",
             f"{a_exp:.5f}",              "m^0.65", "Termine non lineare della pila nella formula CSU"),
        (16, "y1^0.35 (CSU)",                  "y1^0.35", "y1^0.35",
             f"{y_exp:.5f}",              "m^0.35", "Termine non lineare del tirante nella formula CSU"),
        (17, "Fr^0.43 (CSU)",                  "Fr^0.43", "Fr^0.43",
             f"{fr_exp:.5f}",             "-",      "Termine non lineare del Froude nella formula CSU"),
        (18, "ys CSU/HEC-18",                  "ys_CSU",  "2*K1*K2*K3*K4*a^0.65*y1^0.35*Fr^0.43",
             f"{ys_csu:.5f}",             "m",      "Profondita' di scalzamento formula CSU/HEC-18 (senza limite round nose)"),
        (19, "ys con limite round nose (CSU)", "ys_lim",  "min(ys_CSU, limite)",
             f"{ys_csu_lim:.5f}",         "m",      "CSU con il limite per pila a naso arrotondato allineata al flusso"),
        (20, "Velocita' critica (HEC-18)",     "V_c",     "6.19*y1^(1/6)*D50^(1/3)",
             f"{V_c:.5f}",               "m/s",    "Velocita' per l'inizio del moto del sedimento (formula HEC-18)"),
        (21, "Regime trasporto",               "regime",  "V1 vs V_c",
             regime,                      "-",      "Clear-water: V<=V_c, no trasporto; Live-bed: V>V_c, trasporto attivo"),
        (22, "K_yb (Melville)",                "K_yb",    "f(y1/a)",
             f"{K_yb:.5f}",              "-",      "Fattore geometrico Melville: K_yb=1 se y1/a>=3 (flusso profondo)"),
        (23, "K_I (Melville)",                 "K_I",     "min(1, V/V_c)",
             f"{K_I:.5f}",               "-",      "Fattore intensita' del flusso Melville: K_I=V/V_c in clear-water"),
        (24, "ys Melville & Coleman (2000)",   "ys_MC",   "2 * K_yb * K_I * a",
             f"{ys_mc:.5f}",             "m",      "Scalzamento formula Melville & Coleman (2000), semplificata"),
        (25, "ys fattoriale utente",           "ys_fatt", "K_total * a",
             f"{ys_fatt:.5f}",           "m",      "Metodo esplicito parametrico: utile per confronto e calibrazione"),
        (26, "ys conservativo (max)",          "ys_max",  "max(CSU, MC, fatt.)",
             f"{max(ys_csu, ys_csu_lim, ys_mc, ys_fatt):.5f}", "m",
             "Valore di progetto: il massimo tra tutte le formulazioni"),
    ]
    return pd.DataFrame(rows, columns=["Passo", "Grandezza", "Simbolo",
                                       "Formula", "Valore", "Unita", "Descrizione"])


# ---------------------------------------------------------------------------
# Generazione report PDF
# ---------------------------------------------------------------------------

def _pdf_sezione(pdf, titolo: str) -> None:
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(41, 98, 155)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, titolo, ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)


def _pdf_riga_kv(pdf, chiave: str, valore: str) -> None:
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(70, 5, chiave + ":", border="B")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 5, valore, border="B", ln=True)


def _pdf_tabella(pdf, df: pd.DataFrame) -> None:
    cols = list(df.columns)
    larghezze = {
        "Passo": 9, "Grandezza": 35, "Simbolo": 18,
        "Formula": 45, "Valore": 24, "Unita": 14, "Descrizione": 45,
        "Formulazione": 55, "ys [m]": 18, "ys / a [-]": 18,
        "Riferimento": 55, "Nota tecnica": 44,
        "N.": 8, "Verifica": 50, "Valore calcolato": 32,
        "Limite/soglia": 32, "Esito": 18, "Riferimento normativo": 40,
    }
    default_w = 28
    row_h = 5

    pdf.set_font("Helvetica", "B", 7)
    pdf.set_fill_color(210, 225, 245)
    for col in cols:
        w = larghezze.get(col, default_w)
        pdf.cell(w, row_h + 1, col, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    for _, row in df.iterrows():
        for col in cols:
            w = larghezze.get(col, default_w)
            val = row[col]
            txt = f"{val:.4f}" if isinstance(val, float) else str(val)
            align = "C" if col in ("Passo", "N.", "Simbolo", "Valore", "Unita",
                                   "ys [m]", "ys / a [-]", "Esito") else "L"
            max_c = max(4, int(w / 2.1))
            if len(txt) > max_c:
                txt = txt[: max_c - 2] + ".."
            pdf.cell(w, row_h, txt, border=1, align=align)
        pdf.ln()


def genera_pdf(dati: DatiPila, note: List[str]) -> bytes:
    from fpdf import FPDF

    df_pass = tabella_passaggi(dati)
    df_report = calcola_report(dati)
    df_ver = verifiche_scalzamento(dati)
    indicatori = sintesi_indicatori(dati)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_fill_color(20, 60, 120)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 12, "Report - Scalzamento Locale Pila da Ponte",
             ln=True, align="C", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 6, f"Generato il {datetime.date.today().strftime('%d/%m/%Y')}  |  "
             "Formule: CSU/HEC-18, Melville & Coleman (2000)",
             ln=True, align="C")
    pdf.ln(4)

    _pdf_sezione(pdf, "1. Parametri di input")
    _pdf_riga_kv(pdf, "Larghezza pila a", f"{dati.larghezza_pila:.3f} m")
    _pdf_riga_kv(pdf, "Lunghezza pila L", f"{dati.lunghezza_pila:.3f} m")
    _pdf_riga_kv(pdf, "Forma naso", dati.forma_naso)
    _pdf_riga_kv(pdf, "Angolo di attacco", f"{dati.angolo_attacco_gradi:.1f} gradi")
    _pdf_riga_kv(pdf, "Tirante a monte y1", f"{dati.tirante_monte:.3f} m")
    _pdf_riga_kv(pdf, "Velocita' a monte V1", f"{dati.velocita_monte:.3f} m/s")
    _pdf_riga_kv(pdf, "D50 sedimento", f"{dati.D50_mm:.3f} mm")
    _pdf_riga_kv(pdf, "Ss (peso spec. rel.)", f"{dati.Ss:.3f}")
    _pdf_riga_kv(pdf, "K1", f"{dati.k1:.3f}")
    _pdf_riga_kv(pdf, "K2 (auto)" if dati.usa_k2_automatico else "K2 (manuale)",
                 f"{indicatori['K2 effettivo [-]']:.4f}")
    _pdf_riga_kv(pdf, "K3", f"{dati.k3:.3f}")
    _pdf_riga_kv(pdf, "K4", f"{dati.k4:.3f}")
    pdf.ln(4)

    _pdf_sezione(pdf, "2. Indicatori sintetici")
    _pdf_riga_kv(pdf, "Numero di Froude Fr", f"{indicatori['Fr [-]']:.4f}")
    _pdf_riga_kv(pdf, "Rapporto a / y1", f"{indicatori['a / y1 [-]']:.4f}")
    _pdf_riga_kv(pdf, "Rapporto L / a", f"{indicatori['L / a [-]']:.4f}")
    _pdf_riga_kv(pdf, "K2 effettivo", f"{indicatori['K2 effettivo [-]']:.4f}")
    _pdf_riga_kv(pdf, "Velocita' critica V_c", f"{indicatori['V_c [m/s]']:.4f} m/s")
    _pdf_riga_kv(pdf, "V / V_c", f"{indicatori['V / V_c [-]']:.4f}")
    _pdf_riga_kv(pdf, "Regime trasporto", indicatori["Regime"])
    _pdf_riga_kv(pdf, "ys massimo (cautelativo)", f"{indicatori['ys max [m]']:.4f} m")
    _pdf_riga_kv(pdf, "ys minimo", f"{indicatori['ys min [m]']:.4f} m")
    _pdf_riga_kv(pdf, "Spread ys max - ys min", f"{indicatori['spread [m]']:.4f} m")
    pdf.ln(4)

    _pdf_sezione(pdf, "3. Passaggi di calcolo (passo per passo)")
    _pdf_tabella(pdf, df_pass)
    pdf.ln(4)

    pdf.add_page()
    _pdf_sezione(pdf, "4. Confronto formulazioni")
    _pdf_tabella(pdf, df_report)
    pdf.ln(4)

    _pdf_sezione(pdf, "5. Verifiche normative")
    _pdf_tabella(pdf, df_ver)
    pdf.ln(4)

    pdf.add_page()
    _pdf_sezione(pdf, "6. Note tecniche e commenti progettuali")
    pdf.set_font("Helvetica", "", 8)
    for item in note:
        txt = "- " + item.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 5, txt)
        pdf.ln(1)

    return pdf.output()


# ---------------------------------------------------------------------------
# Commenti progettuali
# ---------------------------------------------------------------------------

def commenti_progettuali(dati: DatiPila) -> List[str]:
    note = []
    fr = numero_froude(dati.velocita_monte, dati.tirante_monte)
    k2_eff = (k2_automatico(dati.lunghezza_pila, dati.larghezza_pila, dati.angolo_attacco_gradi)
              if dati.usa_k2_automatico else dati.k2)
    V_c = velocita_critica_incipiente(dati.tirante_monte, dati.D50_mm)
    regime = classificazione_regime(dati.velocita_monte, V_c)

    if dati.velocita_monte > V_c:
        note.append(
            f"Regime live-bed rilevato (V={dati.velocita_monte:.2f} m/s > V_c={V_c:.2f} m/s): "
            "lo scalzamento e' associato al trasporto generalizzato del fondo. "
            "Verificare K3 e valutare la ripresa della morfologia dopo la piena."
        )
    else:
        note.append(
            f"Regime clear-water (V={dati.velocita_monte:.2f} m/s <= V_c={V_c:.2f} m/s): "
            "la formula CSU/HEC-18 e' applicabile direttamente. "
            "Lo scalzamento raggiunge il massimo quando il flusso si avvicina a V_c."
        )

    if fr < 0.20:
        note.append(
            "Froude molto basso: verificare la rappresentativita' della velocita' media "
            "di monte rispetto alla sezione completa."
        )
    if fr > 1.0:
        note.append(
            "Moto supercritico: le formule empiriche CSU/HEC-18 e Melville & Coleman "
            "sono calibrate principalmente per moto subcritico; usare con cautela."
        )
    if k2_eff > 1.30:
        note.append(
            f"K2 effettivo = {k2_eff:.3f}: angolo d'attacco e/o rapporto L/a penalizzante. "
            "Valutare interventi di orientamento della corrente (difensori, raddrizzatori)."
        )
    if dati.k4 < 1.0:
        note.append(
            "K4 < 1.0 (armoring applicato): documentare rigorosamente l'analisi granulometrica "
            "e la persistenza dell'armatura nel tempo."
        )
    if dati.angolo_attacco_gradi > 15:
        note.append(
            f"Angolo di attacco {dati.angolo_attacco_gradi:.1f} gradi: "
            "impatto significativo su K2 e quindi sullo scalzamento. "
            "Valutare protezioni locali o modifica geometria spalle."
        )
    if not note:
        note.append(
            "Input in intervallo tipico per una verifica preliminare. "
            "Completare con analisi morfologica, rilievi granulometrici e giudizio ingegneristico."
        )
    note.append(
        "Lo scalzamento conservativo da usare in progetto e' il valore massimo tra tutte "
        "le formulazioni: applicare sempre un adeguato margine di sicurezza."
    )
    return note
