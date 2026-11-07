# SanoSync — Audit tecnico per il rilascio, 7 novembre 2026

**Ambito:** PR #20–#27, dipendenze fra le otto fasi della roadmap, verifiche CI, schema/RLS Supabase e rischio di perdita dati.  
**Operazioni svolte:** letture GitHub e query SQL `SELECT` sul progetto Supabase; correzioni versionate nei branch GitHub. **Nessun merge, nessun deploy e nessuna scrittura SQL sul database live.**

## Verdetto

**Non ancora pronto per il rilascio.** Le PR avevano CI verde all'apertura dell'audit, ma la CI corrente non copre un ambiente autenticato con le nuove migrazioni e ci sono prerequisiti operativi non risolti. Il blocco critico di perdita dello storico trovato in PR #23 è stato corretto nel codice e propagato ai branch #24–#27. Non confondere la correzione versionata con una verifica end-to-end su dati reali.

## Inventario e catena di dipendenze

| PR | Fase | Branch | Base | Stato audit |
| --- | --- | --- | --- | --- |
| #20 | Training Profile + Exercise Library | `codex/exercise-library-v1-curation-audit` | `main` | Migrazioni e RLS da collaudare |
| #21 | Workout libero + gym logging | `codex/phase2-gym-free-workout-continuity` | `main` | Collaudo storico e account |
| #22 | Athlete State | `codex/phase3-athlete-state-v1` | `main` | Collaudo dati con serie reali |
| #23 | Program Generator v2 | `codex/phase4-program-generator-v2` | #22 branch | Critico corretto; attivazione catalogo incompleto |
| #24 | Adaptive Coach | `codex/phase5-adaptive-coach-v1` | #23 branch | Salvaguardie propagate; consenso da collaudare |
| #25 | Training ↔ Nutrition | `codex/phase6-training-nutrition-context` | #24 branch | Da collaudare con pasti e attività reali |
| #26 | Gym ↔ Running | `codex/phase7-gym-running-cross-training` | #25 branch | Da collaudare con gare e sessioni collegate |
| #27 | Adaptive Macros | `codex/phase8-adaptive-macros-v1` | #26 branch | Doppia conferma / stale check da verificare autenticati |

**Attenzione:** le PR #20, #21 e #22 sono tre rami autonomi basati su `main`, non una singola catena. PR #23–#27 sono stacked su #22; contengono dunque il codice accumulato delle fasi 3–8, ma non incorporano direttamente i branch #20 e #21. Integrare per ordine e ricontrollare diff e CI dopo ogni variazione della base. La PR #19 del vecchio Adaptive Coach è sovrapposta alla #24: non unirla automaticamente.

## F0 — Rischio perdita storico durante sostituzione piano forza: RISOLTO NEL CODICE

**Trovato:** in `backend/api/routers/program_v2.py` la sostituzione del piano attivo chiamava `plans_repo.delete(old_id, user_id)`. Verificato nel DB live: le chiavi esterne `strength_workouts.strength_plan_id`, `strength_workout_logs.strength_workout_id` e `strength_set_logs.strength_workout_log_id` hanno `ON DELETE CASCADE`. L'eliminazione del piano poteva quindi cancellare workout, log completati e singole serie.

**Correzione:** il piano precedente viene marcato `paused` tramite `update_status`, non eliminato. Il valore `paused` è ammesso dal vincolo SQL. Aggiunta compensazione best-effort che mette in pausa il nuovo piano se non riesce a mettere in pausa il precedente, invece di lasciare due piani attivi. Aggiunto test che fallisce esplicitamente se viene invocato `delete`. La stessa correzione è stata copiata sui branch #24–#27.

**Residuo:** il flusso usa più richieste REST, non una transazione atomica; una pausa non cancella le sedute future con stato `planned`. Bisogna verificare che calendario, Coach e attività nascondano o gestiscano le sedute di un piano `paused`. Prima del rilascio testare failure-injection, collisioni e rollback su staging.

## F1 — Attrezzatura non specificata nel Generator v2: RISOLTO NEL CODICE

**Trovato:** un esercizio approvato ma senza mapping `exercise_equipment` produceva un insieme vuoto di attrezzatura necessaria; un sottoinsieme vuoto passa qualunque filtro.

**Correzione:** il generatore ora scarta esercizi senza mapping verificabile e richiede che le attrezzature necessarie siano tutte esplicitamente presenti. Nuovo test con varianti squat prive di mapping; replicato sui branch #23–#27.

## F2 — Storico migrazioni in disallineamento: BLOCCO RILASCIO

Nel database live la tabella `supabase_migrations.schema_migrations` contiene fra le altre versioni:

- `20261107190642` — `add_exercise_library_v1`
- `20261107190715` — `seed_exercise_library_v1`
- `20261107190911` — `curate_exercise_library_golden_v1`
- `20261107191043` — `index_exercise_library_foreign_keys`
- `20261107192501` — `restore_strength_workout_logs`
- `20261107192511` — `add_workout_logger_v2`
- `20261107193200` — `index_strength_set_logs_user`

Nel repository `main` i rispettivi nomi file/versioni sono `20261107191500`, `191600`, `191700`, `191800`, `192900`, `193000`, `193100`. **Versioni diverse non dimostrano contenuti differenti**, ma lo strumento di migrazione può considerare non applicate delle migrazioni che sono già operative. Non eseguire un `supabase db push` live finché la storia non sia riconciliata in un clone isolato.

Verificato in sola lettura: database con 317 esercizi attivi, 10 approvati per generazione, 0 relazioni; `public.training_exercise_preferences` non esiste ancora. I dati corrispondono allo stato precedente ai batch Phase 1 (che sono intenzionalmente non distribuiti). I tipi live degli ID esercizio sono `uuid`, `similarity_score` delle relazioni è nullable, e i vincoli di `relationship` comprendono `progression`.

**Azione:** backup verificato, diff dei contenuti di migrazione, riproduzione/staging e RLS con almeno due account. Solo dopo una strategia esplicita di allineamento della history, applicare gli incrementi `20261107210000`–`20261107214000`. Non “riparare” la history live a tentativi.

## F3 — Program Generator v2 non attivabile completamente: BLOCCO FUNZIONALE

Nel DB live solo 10 esercizi approvati, con nessun `hinge` approvato; il generatore richiede almeno squat, hinge, spinte e tirate orizzontali e verticali. Il comportamento fail-closed è corretto; l'interfaccia deve dichiarare esplicitamente che l'attivazione è bloccata. Una classificazione metadata dei 144 esercizi aggiuntivi **non equivale** all'approvazione del generatore.

**Azione:** revisione editoriale del gruppo minimo di movimenti ed equipaggiamenti, approvazioni individuali e verifiche scenario multi-attrezzatura in staging. Nessuna approvazione massiva automatica.

## F4 — Copertura CI non equivale a E2E autenticato: BLOCCO QA

Il workflow `.github/workflows/quality.yml` esegue pytest, TypeScript, build Next.js, check Home e Playwright con `NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co` e API locale fittizia. Verifica compilazione e flussi pubblici ma **non** persistenza di dati nelle nuove tabelle, sessioni reali, policy RLS, migrazioni o coerenza cross-module. Le suite unit/backend hanno fake repository e dati sintetici; ciò è utile ma insufficiente per il gate di rilascio.

**Azione:** ambiente isolato con copie anonimizzate, due utenti test, account demo read-only, veri JWT e browser autenticato. Provare preferiti/esclusioni, sessione libera, storico, Athlete State, programma, Coach consent-only, macro consent-only, date storiche, giorno al confine timezone e recupero dopo rete persa.

## F5 — Coerenza fra programmi e stato del piano: DA VERIFICARE

L'aggiornamento `strength_plans.status='paused'` salva lo storico, ma workout futuri collegati possono mantenere `strength_workouts.status='planned'`. Verificare gli endpoint calendario e Coach (che potrebbero elencare workout senza filtrare status del piano). Prima di rilasciare la sostituzione dei programmi, garantire che il calendario non mostri come attive sedute di piani sospesi. L'operazione a più scritture resta non-atomica; valutare una RPC transazionale in successiva hardening release.

## F6 — Osservabilità, regressioni e rollout: DA COMPLETARE

- Test e audit dei permessi effettivi delle policy su `training_exercise_preferences` dopo deploy staging.
- Baseline pre/post dei conteggi di workout, log e serie; nessuna scrittura su storico completato durante analisi Coach/Generator/Adaptive Macros.
- Correlazione e metriche di errori per i nuovi endpoint; tempo di caricamento pagina Progressi con pannelli concorrenti.
- Verifica soft-launch con rollback backend/frontend. Le migrazioni additive dovrebbero restare compatibili con il vecchio frontend; non fare rollback distruttivo dello schema.
- Ricontrollare ogni PR stacked dopo sync del branch base: merge GitHub e 'CI verde' del vecchio SHA non garantiscono il nuovo SHA integrato.

## Sequenza di interventi consigliata

1. **No release:** risolvere F2 con clone/staging e history migrations.
2. Completare propagazione fix F0/F1 e CI latest-head in #23–#27.
3. Costruire un branch temporaneo di integrazione dagli otto PR nell'ordine delle dipendenze, mantenendo produzione intatta.
4. Chiudere F5: calendario dei piani paused e condizioni di errore nella sostituzione.
5. Implementare i test autenticati F4 e verificare la separazione dei dati.
6. Decidere come sbloccare F3 tramite approvazione puntuale degli esercizi senza sovrascrivere il dataset.
7. Solo con i gate documentati verdi, autorizzare merge e deploy incrementali, con backup e rollback.

### Limitazioni di questo audit

Non è stato eseguito un dry-run SQL in staging né una sessione browser autenticata: la CI sintetica **non** prova quei passaggi. I controlli Supabase eseguiti sono stati soltanto `SELECT` di catalogo, schema, migrazioni e policy. Questo rapporto evita di dichiarare pronto al rilascio ciò che non è stato verificato.
