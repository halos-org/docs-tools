"""The wording of the 404 page, in every locale the sites build.

GitHub Pages serves one `404.html` for every URL that does not resolve, in
every edition, so that page ships all of this and picks one in the browser.

None of it is product-specific, which is why it lives here rather than in each
repository's `mkdocs.yml`. A repository that wants different wording overrides
a locale through the plugin's `not_found` option.
"""

WORDING = ("title", "message", "home")

NOT_FOUND: dict[str, dict[str, str]] = {
    "en": {
        "title": "Page not found",
        "message": "The page you asked for does not exist. It may have been moved or renamed.",
        "home": "Go to the documentation home page",
    },
    "fi": {
        "title": "Sivua ei löytynyt",
        "message": "Pyytämääsi sivua ei ole. Se on voitu siirtää tai nimetä uudelleen.",
        "home": "Siirry dokumentaation etusivulle",
    },
    "fr": {
        "title": "Page introuvable",
        "message": "La page que vous demandez n'existe pas. Elle a peut-être été déplacée ou renommée.",
        "home": "Aller à l'accueil de la documentation",
    },
    "de": {
        "title": "Seite nicht gefunden",
        "message": "Die angeforderte Seite existiert nicht. Sie wurde möglicherweise verschoben oder umbenannt.",
        "home": "Zur Startseite der Dokumentation",
    },
    "sv": {
        "title": "Sidan hittades inte",
        "message": "Sidan du efterfrågade finns inte. Den kan ha flyttats eller bytt namn.",
        "home": "Gå till dokumentationens startsida",
    },
    "es": {
        "title": "Página no encontrada",
        "message": "La página solicitada no existe. Es posible que se haya movido o cambiado de nombre.",
        "home": "Ir a la página principal de la documentación",
    },
    "it": {
        "title": "Pagina non trovata",
        "message": "La pagina richiesta non esiste. Potrebbe essere stata spostata o rinominata.",
        "home": "Vai alla pagina iniziale della documentazione",
    },
    "nl": {
        "title": "Pagina niet gevonden",
        "message": "De opgevraagde pagina bestaat niet. Mogelijk is deze verplaatst of hernoemd.",
        "home": "Ga naar de startpagina van de documentatie",
    },
    "nb": {
        "title": "Siden ble ikke funnet",
        "message": "Siden du ba om, finnes ikke. Den kan ha blitt flyttet eller fått nytt navn.",
        "home": "Gå til dokumentasjonens forside",
    },
    "da": {
        "title": "Siden blev ikke fundet",
        "message": "Siden, du bad om, findes ikke. Den kan være flyttet eller omdøbt.",
        "home": "Gå til dokumentationens forside",
    },
}
