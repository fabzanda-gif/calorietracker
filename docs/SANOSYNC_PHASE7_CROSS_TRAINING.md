# SanoSync — Phase 7: Gym ↔ Running cross-training

## Roadmap originale
Phase 1 Training Profile + Exercise Library: PR #20.
Phase 2 Gym logging e workout libero: PR #21.
Phase 3 Athlete State: PR #22.
Phase 4 Program Generator v2: PR #23.
Phase 5 Adaptive Coach: PR #24.
Phase 6 Training ↔ Nutrition: PR #25.
**Phase 7 Gym ↔ Running: questa PR, stacked su Phase 6.**
Phase 8 Macro adattivi sofisticati: separata e successiva.

## Implementato
- `GET /cross-training/timeline?start_date=YYYY-MM-DD&days=14`, da 1 a 21 giorni.
- Unifica corsa e palestra pianificate e completate dal catalogo di attività e dai log di forza esistenti, senza nuove tabelle.
- Usa date di esecuzione per le sedute completate e date programmate per le sedute future; esclude elementi saltati e annullati.
- Non conta due volte una corsa completata collegata alla corsa prevista (`planned_activity_id`) o una palestra completata collegata al workout previsto (`strength_workout_id`).
- Distingue focus lower, upper e full-body; non presume che un log senza focus conosciuto alleni le gambe.
- Segnala, solo come avviso, coincidenze fra seduta gambe e corsa di qualità entro 0–1 giorni (oppure gara entro 2 giorni).
- Le gare non sono mai spostate o modificate dall'analisi; il suggerimento, per le gare, è rivedere la palestra circostante.
- Mostra 14 giorni e gli avvisi nella pagina Progressi tramite un client TypeScript dedicato.
- La priorità Coach gym/running/balanced viene visualizzata, ma non è usata per prescrizioni automatiche.

## Regole e limiti
- La fase 7 è **in sola lettura**. Non aggiorna programmi, prescrizioni, giorni, gare, serie, attività o priorità.
- Gli avvisi non sono diagnosi di recupero/infortunio né indicano un carico clinicamente sicuro.
- L'intensità di una corsa completata viene stimata solo da durata/distanza verificabili; mancano talvolta RPE e tipo sessione, quindi la cautela è necessaria.
- Non si ipotizza l'allenamento lower-body da dati forza incompleti.
- Ogni query applica `user_id` autenticato; le date sono limitate a 21 giorni per richiesta.
- Non sostituisce Adaptive Coach: il Coach rimane la sola interfaccia di conferma delle variazioni, con validazione stale proposal.
- Non unisce le PR in produzione, non applica SQL, non cambia programmi esistenti.

## QA / release
1. CI backend, typecheck, build e browser sul commit finale.
2. Verifica di dati di un account test con corsa e palestra nello stesso giorno e in giorni vicini.
3. Verifica del caso gara e del caso palestra upper-body.
4. Verifica che una corsa completata con `planned_activity_id` non compaia due volte.
5. Verifica delle due identità di test per isolamento dei dati.
6. Integrare le PR in ordine e deploy frontend/backend insieme solo dopo test autenticati in staging.

## Phase 8
Macro adattivi sofisticati. Dovranno usare dati reali e obiettivi espliciti, garantire spiegabilità e controlli dell'utente, e non reinterpretare automaticamente assenza di log alimentari come zero calorie.
