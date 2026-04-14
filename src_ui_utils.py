# -*- coding: utf-8 -*-
"""
Utilità UI per la presentazione conforme dei risultati (standard CivilBox).
Standard: ogni risultato numerico in tabella 4 colonne — Parametro, Valore, Unità, Descrizione.
"""
import streamlit as st
import pandas as pd


def show_results_table(risultati: list, titolo: str = "") -> None:
    """
    Presenta risultati in forma tabellare conforme allo standard CivilBox.

    Colonne: Parametro | Valore | Unità | Descrizione

    Args:
        risultati: lista di dict con chiavi
            'parametro', 'valore', 'unita', 'descrizione'
        titolo: titolo opzionale della sezione (st.subheader)

    Example:
        risultati = [
            {"parametro": "ys", "valore": 2.3456, "unita": "m",
             "descrizione": "Profondità di scalzamento CSU/HEC-18"},
        ]
        show_results_table(risultati, titolo="Risultati principali")
    """
    if titolo:
        st.subheader(titolo)

    df = pd.DataFrame(risultati)
    df = df[["parametro", "valore", "unita", "descrizione"]]
    df.columns = ["Parametro", "Valore", "Unità", "Descrizione"]
    st.dataframe(df, use_container_width=True, hide_index=True)


def formatta_valore(valore, tipo: str = "generale") -> str:
    """
    Formatta un valore numerico secondo la notazione standard CivilBox.

    Args:
        valore: numero da formattare
        tipo: 'forza' (1 decimale), 'tensione' (2 decimali),
              'deformazione' (3 decimali), 'generale' (4 decimali)
    """
    formato = {
        "forza": ".1f",
        "tensione": ".2f",
        "deformazione": ".3f",
        "generale": ".4f",
    }
    fmt = formato.get(tipo, ".4f")
    if isinstance(valore, (int, float)):
        return format(valore, fmt)
    return str(valore)