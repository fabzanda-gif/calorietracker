# SanoSync — Phase 6: Training ↔ Nutrition context

## Posizione nella roadmap originale
Phase 1: Training Profile + Exercise Library (PR #20); Phase 2: workout libero e gym logging (PR #21); Phase 3: Athlete State (PR #22); Phase 4: Program Generator v2 (PR #23); Phase 5: Adaptive Coach (PR #24); **Phase 6: contesto Training ↔ Nutrition (questo branch)**. Il ramo è basato sulla Phase 5 e non può essere distribuito autonomamente prima delle dipendenze.

## Implementazione
- `GET /training-nutrition/week?start_date=YYYY-MM-DD&days=7` accetta intervalli da 1 a 14 giorni.
- Esegue letture autorizzate per `user_id` da: pasti, sedute di corsa pianificate, workout forza pianificati, attività completate, log forza completati, ultimo peso e metadata del profilo.
- Per ciascun giorno restituisce il numero di sedute palestra/corsa previste e completate, calorie/proteine/carboidrati/grassi **realmente registrati**, confronto con l'**obiettivo proteico esplicitamente configurato** se presente e indicatori di copertura dei dati.
- Evita il doppio conteggio delle sedute pianificate che risultano già completate (ID collegato), esclude le sedute saltate/annullate e non scambia le attività tipo passi per corsa.
- Il pannello `TrainingNutritionWeekPanel` è disponibile nella pagina Progressi ed espone riepilogo settimanale, selezione data e dettagli giorno per giorno.
- Non crea nuove tabelle e non modifica la logica esistente di `TrainingNutritionService` per corsa/prima e dopo allenamento.

## Vincoli di sicurezza e veridicità
- Le calorie *stimate* di una seduta futura non sono sommate alle calorie consumate né al budget quotidiano.
- Nessun obiettivo calorico o macro viene automaticamente modificato. La Phase 8 resta dedicata agli adattamenti macro evoluti.
- Se l'obiettivo proteico non è stato configurato, non viene inventato un target generico in g/kg.
- Se manca un pasto, `protein_remaining_g` è null: nessun pasto registrato **non significa** zero alimentazione.
- Nessun allenamento registrato **non significa** riposo certo.
- Nessuna diagnosi di recupero, prestazione o carenza nutrizionale.
- Sono inclusi soltanto dati dell'account corrente.
- Le due forme di attività (programmata e completata) non devono essere considerate indipendenti quando riferite alla stessa seduta.
- Non vengono alterati workout, serie, piani, pasti o obiettivi.

## QA e release
1. CI latest-head: test Python, TypeScript, build Next.js, controlli Playwright.
2. Test funzionali su dati fittizi: settimana con sedute completate, sedute programmate, giorni senza pasti, target proteico assente e attività annullate.
3. Collaudo autenticato su staging con due utenti e un workout palestra completato, oltre a una corsa collegata a un piano.
4. Verifica che il budget nutrizionale preesistente abbia numeri invariati prima/dopo rilascio.
5. Integrare e rilasciare in ordine i prerequisiti PR #20–#24; quindi backend e frontend Phase 6 insieme.

## Prossimo passo della roadmap
Phase 7 — integrazione Gym ↔ Running per il cross-training, tenendo distinte le fonti e senza duplicare sedute. Phase 8 — macro adattivi sofisticati, solo dopo un modello osservabile e consensi adeguati.
