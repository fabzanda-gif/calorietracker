import type { AppLocale } from "@/components/i18n/I18nProvider";

type RecipeCopy = {
  kicker: string;
  title: string;
  titleZero: string;
  subtitle: string;
  subtitleZero: string;
  openPantry: string;
  manageIngredients: string;
  personalLibrary: string;
  ready: string;
  reliable: string;
  updateLegacy: string;
  search: string;
  clearSearch: string;
  filterMeal: string;
  all: string;
  recipe: string;
  recipes: string;
  sort: string;
  recent: string;
  taste: string;
  ease: string;
  loading: string;
  totalCalories: string;
  totalProtein: string;
  serving: string;
  servings: string;
  perServing: string;
  proteinPerServing: string;
  cook: string;
  log: string;
  detail: string;
  share: string;
  noResults: string;
  noResultsZero: string;
  empty: string;
  emptyZero: string;
  changeFilter: string;
  changeFilterZero: string;
  emptyHelp: string;
  emptyHelpZero: string;
  resetFilters: string;
  breakfast: string;
  lunch: string;
  dinner: string;
  snack: string;
  mealPrep: string;
  cookingTitle: string;
  cancel: string;
  cookedHowMany: string;
  saving: string;
  addToInventory: string;
  todayMeal: string;
  editQuantities: string;
  servingsToEat: string;
  originalRecipe: string;
  logging: string;
  logThisMeal: string;
  edit: string;
  new: string;
  editRecipe: string;
  createRecipe: string;
  name: string;
  replacePhoto: string;
  addPhoto: string;
  type: string;
  unrated: string;
  preparation: string;
  preparationPlaceholder: string;
  ingredients: string;
  existing: string;
  newIngredient: string;
  newIngredientTitle: string;
  aiCalculating: string;
  aiFill: string;
  defaultServingGrams: string;
  optionalServingHelp: string;
  protein: string;
  carbs: string;
  fat: string;
  saveIngredient: string;
  ingredient: string;
  quantityUnit: string;
  recipeReady: string;
  recipeEdited: string;
  saveRecipeHelp: string;
  saveEditHelp: string;
  saveChanges: string;
  saveRecipe: string;
};

export const RECIPES_COPY: Record<AppLocale, RecipeCopy> = {
  it: {
    kicker: "Ricette",
    title: "Le tue ricette",
    titleZero: "Le ricette che almeno sai già gestire",
    subtitle: "I piatti che conosci già, pronti da registrare quando servono.",
    subtitleZero: "Piatti già collaudati. Almeno qui evitiamo di fare i fenomeni.",
    openPantry: "Apri dispensa",
    manageIngredients: "Gestisci ingredienti",
    personalLibrary: "Libreria personale",
    ready: "Pronte quando ti servono",
    reliable: "Le solite affidabili",
    updateLegacy: "Aggiorna ricette legacy",
    search: "Cerca una ricetta…",
    clearSearch: "Cancella ricerca",
    filterMeal: "Filtra per tipo di pasto",
    all: "Tutte",
    recipe: "ricetta",
    recipes: "ricette",
    sort: "Ordina",
    recent: "Più recenti",
    taste: "Gusto",
    ease: "Facilità",
    loading: "Caricamento…",
    totalCalories: "kcal totali",
    totalProtein: "g proteine totali",
    serving: "porzione",
    servings: "porzioni",
    perServing: "kcal / porzione",
    proteinPerServing: "g proteine / porzione",
    cook: "Cucina",
    log: "Registra",
    detail: "Dettaglio",
    share: "Condividi",
    noResults: "Nessuna ricetta trovata",
    noResultsZero: "Niente. I filtri hanno lavorato fin troppo bene.",
    empty: "La tua libreria è ancora vuota",
    emptyZero: "Libreria vuota. Minimalismo non richiesto.",
    changeFilter: "Prova a cambiare ricerca o filtro.",
    changeFilterZero: "Cambia ricerca o filtro. Magari compare qualcosa.",
    emptyHelp: "Salva una ricetta e la troverai qui pronta da riutilizzare.",
    emptyHelpZero: "Salva una ricetta. Prima o poi servirà anche questa organizzazione.",
    resetFilters: "Azzera filtri",
    breakfast: "Colazione",
    lunch: "Pranzo",
    dinner: "Cena",
    snack: "Snack",
    mealPrep: "Meal prep",
    cookingTitle: "Cucina",
    cancel: "Annulla",
    cookedHowMany: "Quante porzioni hai cucinato?",
    saving: "Salvataggio...",
    addToInventory: "Aggiungi all'inventario",
    todayMeal: "Pasto di oggi",
    editQuantities: "modifica liberamente le quantità. La ricetta originale non verrà cambiata.",
    servingsToEat: "Porzioni da mangiare",
    originalRecipe: "Ricetta originale",
    logging: "Registro…",
    logThisMeal: "Registra questo pasto",
    edit: "Modifica",
    new: "Nuova",
    editRecipe: "Modifica ricetta",
    createRecipe: "Crea ricetta",
    name: "Nome",
    replacePhoto: "Sostituisci foto",
    addPhoto: "Aggiungi foto",
    type: "Tipo",
    unrated: "Non valutato",
    preparation: "Preparazione",
    preparationPlaceholder: "Descrivi la preparazione, i passaggi, i tempi di cottura, eventuali sostituzioni o suggerimenti...",
    ingredients: "Ingredienti",
    existing: "Esistente",
    newIngredient: "Nuovo",
    newIngredientTitle: "Nuovo ingrediente",
    aiCalculating: "Calcolo valori…",
    aiFill: "✨ Compila con AI",
    defaultServingGrams: "Porzione predefinita (g)",
    optionalServingHelp: "Opzionale. Esempio: 1 porzione di riso = 70 g.",
    protein: "Proteine",
    carbs: "Carboidrati",
    fat: "Grassi",
    saveIngredient: "Salva ingrediente",
    ingredient: "Ingrediente",
    quantityUnit: "Unità quantità",
    recipeReady: "Ricetta pronta",
    recipeEdited: "Hai modificato questa ricetta",
    saveRecipeHelp: "Salva per aggiungerla alla tua libreria personale.",
    saveEditHelp: "Salva per applicare ingredienti, porzioni e valori aggiornati.",
    saveChanges: "✓ Salva modifiche",
    saveRecipe: "✓ Salva ricetta",
  },

  en: {
    kicker: "Recipes",
    title: "Your recipes",
    titleZero: "The recipes you can actually handle",
    subtitle: "Meals you already know, ready to log whenever you need them.",
    subtitleZero: "Tried and tested meals. At least here we can keep things simple.",
    openPantry: "Open pantry",
    manageIngredients: "Manage ingredients",
    personalLibrary: "Personal library",
    ready: "Ready when you need them",
    reliable: "The usual reliable ones",
    updateLegacy: "Update legacy recipes",
    search: "Search recipes…",
    clearSearch: "Clear search",
    filterMeal: "Filter by meal type",
    all: "All",
    recipe: "recipe",
    recipes: "recipes",
    sort: "Sort",
    recent: "Most recent",
    taste: "Taste",
    ease: "Ease",
    loading: "Loading…",
    totalCalories: "total kcal",
    totalProtein: "g total protein",
    serving: "serving",
    servings: "servings",
    perServing: "kcal / serving",
    proteinPerServing: "g protein / serving",
    cook: "Cook",
    log: "Log",
    detail: "Details",
    share: "Share",
    noResults: "No recipes found",
    noResultsZero: "Nothing. The filters did their job a little too well.",
    empty: "Your library is still empty",
    emptyZero: "Empty library. Unrequested minimalism.",
    changeFilter: "Try changing the search or filter.",
    changeFilterZero: "Change the search or filter. Something might show up.",
    emptyHelp: "Save a recipe and it will be ready to reuse here.",
    emptyHelpZero: "Save a recipe. Eventually even this organization will be useful.",
    resetFilters: "Reset filters",
    breakfast: "Breakfast",
    lunch: "Lunch",
    dinner: "Dinner",
    snack: "Snack",
    mealPrep: "Meal prep",
    cookingTitle: "Cook",
    cancel: "Cancel",
    cookedHowMany: "How many servings did you cook?",
    saving: "Saving...",
    addToInventory: "Add to inventory",
    todayMeal: "Today's meal",
    editQuantities: "adjust the quantities freely. The original recipe will not be changed.",
    servingsToEat: "Servings to eat",
    originalRecipe: "Original recipe",
    logging: "Logging…",
    logThisMeal: "Log this meal",
    edit: "Edit",
    new: "New",
    editRecipe: "Edit recipe",
    createRecipe: "Create recipe",
    name: "Name",
    replacePhoto: "Replace photo",
    addPhoto: "Add photo",
    type: "Type",
    unrated: "Not rated",
    preparation: "Preparation",
    preparationPlaceholder: "Describe the method, steps, cooking times, substitutions or tips...",
    ingredients: "Ingredients",
    existing: "Existing",
    newIngredient: "New",
    newIngredientTitle: "New ingredient",
    aiCalculating: "Calculating values…",
    aiFill: "✨ Fill with AI",
    defaultServingGrams: "Default serving (g)",
    optionalServingHelp: "Optional. Example: 1 serving of rice = 70 g.",
    protein: "Protein",
    carbs: "Carbohydrates",
    fat: "Fat",
    saveIngredient: "Save ingredient",
    ingredient: "Ingredient",
    quantityUnit: "Quantity unit",
    recipeReady: "Recipe ready",
    recipeEdited: "You've edited this recipe",
    saveRecipeHelp: "Save it to add it to your personal library.",
    saveEditHelp: "Save to apply the updated ingredients, servings and values.",
    saveChanges: "✓ Save changes",
    saveRecipe: "✓ Save recipe",
  },

  nl: {
    kicker: "Recepten",
    title: "Jouw recepten",
    titleZero: "De recepten die je tenminste al aankunt",
    subtitle: "Gerechten die je al kent, klaar om te registreren wanneer nodig.",
    subtitleZero: "Beproefde gerechten. Hier hoeven we tenminste niet moeilijk te doen.",
    openPantry: "Open voorraad",
    manageIngredients: "Beheer ingrediënten",
    personalLibrary: "Persoonlijke bibliotheek",
    ready: "Klaar wanneer je ze nodig hebt",
    reliable: "De vertrouwde recepten",
    updateLegacy: "Oude recepten bijwerken",
    search: "Zoek een recept…",
    clearSearch: "Zoekopdracht wissen",
    filterMeal: "Filter op maaltijdtype",
    all: "Alle",
    recipe: "recept",
    recipes: "recepten",
    sort: "Sorteren",
    recent: "Meest recent",
    taste: "Smaak",
    ease: "Gemak",
    loading: "Laden…",
    totalCalories: "kcal totaal",
    totalProtein: "g eiwit totaal",
    serving: "portie",
    servings: "porties",
    perServing: "kcal / portie",
    proteinPerServing: "g eiwit / portie",
    cook: "Bereiden",
    log: "Registreren",
    detail: "Details",
    share: "Delen",
    noResults: "Geen recepten gevonden",
    noResultsZero: "Niets. De filters hebben iets te goed gewerkt.",
    empty: "Je bibliotheek is nog leeg",
    emptyZero: "Lege bibliotheek. Ongevraagd minimalisme.",
    changeFilter: "Probeer een andere zoekopdracht of filter.",
    changeFilterZero: "Pas de zoekopdracht of filter aan. Misschien verschijnt er iets.",
    emptyHelp: "Sla een recept op en je kunt het hier later opnieuw gebruiken.",
    emptyHelpZero: "Sla een recept op. Ooit komt zelfs deze organisatie van pas.",
    resetFilters: "Filters wissen",
    breakfast: "Ontbijt",
    lunch: "Lunch",
    dinner: "Avondeten",
    snack: "Tussendoortje",
    mealPrep: "Meal prep",
    cookingTitle: "Bereiden",
    cancel: "Annuleren",
    cookedHowMany: "Hoeveel porties heb je bereid?",
    saving: "Opslaan...",
    addToInventory: "Aan voorraad toevoegen",
    todayMeal: "Maaltijd van vandaag",
    editQuantities: "pas de hoeveelheden gerust aan. Het oorspronkelijke recept verandert niet.",
    servingsToEat: "Porties om te eten",
    originalRecipe: "Origineel recept",
    logging: "Registreren…",
    logThisMeal: "Deze maaltijd registreren",
    edit: "Bewerken",
    new: "Nieuw",
    editRecipe: "Recept bewerken",
    createRecipe: "Recept maken",
    name: "Naam",
    replacePhoto: "Foto vervangen",
    addPhoto: "Foto toevoegen",
    type: "Type",
    unrated: "Niet beoordeeld",
    preparation: "Bereiding",
    preparationPlaceholder: "Beschrijf de bereiding, stappen, kooktijden, vervangingen of tips...",
    ingredients: "Ingrediënten",
    existing: "Bestaand",
    newIngredient: "Nieuw",
    newIngredientTitle: "Nieuw ingrediënt",
    aiCalculating: "Waarden berekenen…",
    aiFill: "✨ Invullen met AI",
    defaultServingGrams: "Standaardportie (g)",
    optionalServingHelp: "Optioneel. Voorbeeld: 1 portie rijst = 70 g.",
    protein: "Eiwit",
    carbs: "Koolhydraten",
    fat: "Vet",
    saveIngredient: "Ingrediënt opslaan",
    ingredient: "Ingrediënt",
    quantityUnit: "Eenheid",
    recipeReady: "Recept klaar",
    recipeEdited: "Je hebt dit recept aangepast",
    saveRecipeHelp: "Sla het op om het aan je persoonlijke bibliotheek toe te voegen.",
    saveEditHelp: "Sla op om de bijgewerkte ingrediënten, porties en waarden toe te passen.",
    saveChanges: "✓ Wijzigingen opslaan",
    saveRecipe: "✓ Recept opslaan",
  },

  fr: {
    kicker: "Recettes",
    title: "Vos recettes",
    titleZero: "Les recettes que vous savez au moins gérer",
    subtitle: "Les plats que vous connaissez déjà, prêts à être enregistrés quand vous en avez besoin.",
    subtitleZero: "Des plats déjà testés. Ici au moins, inutile d'en faire trop.",
    openPantry: "Ouvrir le garde-manger",
    manageIngredients: "Gérer les ingrédients",
    personalLibrary: "Bibliothèque personnelle",
    ready: "Prêtes quand vous en avez besoin",
    reliable: "Les valeurs sûres",
    updateLegacy: "Mettre à jour les anciennes recettes",
    search: "Rechercher une recette…",
    clearSearch: "Effacer la recherche",
    filterMeal: "Filtrer par type de repas",
    all: "Toutes",
    recipe: "recette",
    recipes: "recettes",
    sort: "Trier",
    recent: "Plus récentes",
    taste: "Goût",
    ease: "Facilité",
    loading: "Chargement…",
    totalCalories: "kcal au total",
    totalProtein: "g de protéines au total",
    serving: "portion",
    servings: "portions",
    perServing: "kcal / portion",
    proteinPerServing: "g protéines / portion",
    cook: "Préparer",
    log: "Enregistrer",
    detail: "Détails",
    share: "Partager",
    noResults: "Aucune recette trouvée",
    noResultsZero: "Rien. Les filtres ont un peu trop bien travaillé.",
    empty: "Votre bibliothèque est encore vide",
    emptyZero: "Bibliothèque vide. Minimalisme non demandé.",
    changeFilter: "Essayez de modifier la recherche ou le filtre.",
    changeFilterZero: "Changez la recherche ou le filtre. Quelque chose apparaîtra peut-être.",
    emptyHelp: "Enregistrez une recette et retrouvez-la ici prête à être réutilisée.",
    emptyHelpZero: "Enregistrez une recette. Cette organisation finira bien par servir.",
    resetFilters: "Réinitialiser les filtres",
    breakfast: "Petit-déjeuner",
    lunch: "Déjeuner",
    dinner: "Dîner",
    snack: "Collation",
    mealPrep: "Meal prep",
    cookingTitle: "Préparer",
    cancel: "Annuler",
    cookedHowMany: "Combien de portions avez-vous préparées ?",
    saving: "Enregistrement...",
    addToInventory: "Ajouter au garde-manger",
    todayMeal: "Repas du jour",
    editQuantities: "modifiez librement les quantités. La recette originale ne sera pas modifiée.",
    servingsToEat: "Portions à manger",
    originalRecipe: "Recette originale",
    logging: "Enregistrement…",
    logThisMeal: "Enregistrer ce repas",
    edit: "Modifier",
    new: "Nouvelle",
    editRecipe: "Modifier la recette",
    createRecipe: "Créer une recette",
    name: "Nom",
    replacePhoto: "Remplacer la photo",
    addPhoto: "Ajouter une photo",
    type: "Type",
    unrated: "Non évalué",
    preparation: "Préparation",
    preparationPlaceholder: "Décrivez la préparation, les étapes, les temps de cuisson, les substitutions ou conseils...",
    ingredients: "Ingrédients",
    existing: "Existant",
    newIngredient: "Nouveau",
    newIngredientTitle: "Nouvel ingrédient",
    aiCalculating: "Calcul des valeurs…",
    aiFill: "✨ Remplir avec l'IA",
    defaultServingGrams: "Portion par défaut (g)",
    optionalServingHelp: "Optionnel. Exemple : 1 portion de riz = 70 g.",
    protein: "Protéines",
    carbs: "Glucides",
    fat: "Lipides",
    saveIngredient: "Enregistrer l'ingrédient",
    ingredient: "Ingrédient",
    quantityUnit: "Unité de quantité",
    recipeReady: "Recette prête",
    recipeEdited: "Vous avez modifié cette recette",
    saveRecipeHelp: "Enregistrez-la pour l'ajouter à votre bibliothèque personnelle.",
    saveEditHelp: "Enregistrez pour appliquer les ingrédients, portions et valeurs mis à jour.",
    saveChanges: "✓ Enregistrer les modifications",
    saveRecipe: "✓ Enregistrer la recette",
  },
};
