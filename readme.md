# Scalzamento

Web app professionale in **Python + Streamlit** per il **calcolo e il confronto dello scalzamento locale** presso una **pila da ponte in alveo**.

Questa versione è pensata come **app pilota** della suite di strumenti per l’ingegneria idraulica: la struttura del codice, la UI, i grafici e la documentazione sono stati organizzati per costituire una base solida, estendibile e riutilizzabile in future implementazioni.

## Fondamento tecnico della versione attuale
- Implementa la formulazione **CSU / HEC-18** nella forma riportata nella documentazione tecnica HEC-RAS / HEC-18, con coefficienti `K1`, `K2`, `K3`, `K4`.
- Implementa il calcolo automatico di **K2** tramite `K2 = (cosθ + (L/a) sinθ)^0.65`, con limite `L/a <= 12`.
- Implementa il limite per **pila a naso arrotondato allineata al flusso**, con `ys <= 2.4a` per `Fr <= 0.8` e `ys <= 3.0a` per `Fr > 0.8`, se attivato.
- Include una formulazione **fattoriale utente** (`ys = K_total * a`) come schema trasparente e placeholder per future estensioni progettuali.

## Struttura del progetto
```text
Scalzamento/
├── app.py
├── src.py
├── requirements.txt
├── readme.md
└── prompt.txt
```

## Input principali
- Geometria: `a`, `L`, forma del naso, angolo di attacco
- Idraulica: `y1`, `V1`
- Coefficienti: `K1`, `K2`, `K3`, `K4`
- Parametro di confronto: `K_total`

## Output principali
- tabella di confronto delle formulazioni;
- profondità di scalzamento `ys [m]`;
- grandezza normalizzata `ys/a [-]`;
- indicatori sintetici (`Fr`, `a/y1`, `L/a`, `K2 effettivo`, `ys max`, `ys min`, `spread`);
- grafici Plotly di confronto diretto;
- grafici Plotly di sensitività rispetto a velocità e tirante;
- export CSV dei risultati e delle curve parametriche.

## Avvio rapido
```bash
pip install -r requirements.txt
streamlit run app.py
```
