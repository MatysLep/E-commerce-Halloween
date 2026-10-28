"""Small, deterministic demo catalogue; existing stock is never reset."""

from shop.models import Product

CATALOGUE = [
    (
        "citrouille",
        "La citrouille malicieuse",
        "Une lanterne réutilisable pour éclairer la nuit.",
        "Décoration",
        "🎃",
        1890,
    ),
    (
        "fantome",
        "Le fantôme de minuit",
        "Un compagnon suspendu qui n’effraie que les courants d’air.",
        "Décoration",
        "👻",
        1290,
    ),
    (
        "chapeau",
        "Le chapeau de sorcière",
        "La touche finale de votre tenue, en velours noir.",
        "Costumes",
        "🧙",
        2490,
    ),
    (
        "bonbons",
        "Le butin des petits monstres",
        "Un assortiment de douceurs emballées, format 500 g.",
        "Gourmandises",
        "🍬",
        890,
    ),
    (
        "bougie",
        "La bougie du manoir",
        "Une bougie LED à la lumière douce et mystérieuse.",
        "Décoration",
        "🕯️",
        1590,
    ),
    (
        "chauve-souris",
        "La nuée de chauves-souris",
        "Douze silhouettes à suspendre pour une entrée remarquée.",
        "Décoration",
        "🦇",
        990,
    ),
]


def seed(session):
    for product_id, name, description, category, emoji, price in CATALOGUE:
        if not session.get(Product, product_id):
            session.add(
                Product(
                    id=product_id,
                    name=name,
                    description=description,
                    category=category,
                    emoji=emoji,
                    price_cents=price,
                    stock=100,
                )
            )
