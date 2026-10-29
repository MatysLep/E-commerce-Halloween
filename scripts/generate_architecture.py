"""Draw the hybrid Terraform topology using locally embedded official AWS icons."""

import re
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "doc/architecture/architecture-aws-hybride.svg"
SYMBOLS = ROOT / "doc/architecture/aws-service-symbols.svg"
NS = "{http://www.w3.org/2000/svg}"
INK = "#172b46"
MUTED = "#52637a"
LINE = "#73849a"
ORANGE = "#ad5414"
PURPLE = "#7952c8"


class Diagram:
    def __init__(self):
        self.parts = []
        self.used_icons = set()

    def rect(self, x, y, width, height, fill="#fff", stroke="#dbe3ed", dashed=False):
        dash = ' stroke-dasharray="7 5"' if dashed else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="16" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"{dash}/>'
        )

    def text(self, x, y, value, size=20, color=MUTED, bold=False, anchor="start"):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-weight="{700 if bold else 400}" text-anchor="{anchor}">'
            f"{escape(str(value))}</text>"
        )

    def icon(self, name, x, y, size=60):
        self.used_icons.add(name)
        self.parts.append(
            f'<use href="#{name}" xlink:href="#{name}" x="{x}" y="{y}" '
            f'width="{size}" height="{size}"/>'
        )

    def arrow(self, path, dashed=False, color=LINE):
        dash = ' stroke-dasharray="7 6"' if dashed else ""
        marker = "arrow-orange" if color == ORANGE else "arrow"
        self.parts.append(
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.5" '
            f'marker-end="url(#{marker})" stroke-linejoin="round"{dash}/>'
        )

    def section(self, number, y, height, title, description):
        self.rect(40, y, 1920, height, "#f3f6fb")
        self.text(70, y + 42, number, 22, ORANGE, True)
        self.text(120, y + 42, title, 27, INK, True)
        self.text(70, y + 77, description, 19)

    def card(self, x, y, width, height, icon, title, lines, title_size=23, body_size=19):
        self.rect(x, y, width, height)
        if icon:
            self.icon(icon, x + 20, y + 22)
        tx = x + (100 if icon else 24)
        self.text(tx, y + 43, title, title_size, INK, True)
        for index, line in enumerate(lines):
            self.text(tx, y + 75 + index * 27, line, body_size)

    def save(self, title, description):
        source = ET.parse(SYMBOLS).getroot().find(NS + "defs")
        icons = {element.attrib["id"]: element for element in source}
        missing = self.used_icons - icons.keys()
        if missing:
            raise ValueError(f"Missing official icons: {missing}")
        symbols = "\n".join(
            ET.tostring(icons[name], encoding="unicode") for name in sorted(self.used_icons)
        )
        markers = "".join(
            f'<marker id="{name}" markerWidth="10" markerHeight="10" refX="9" refY="4" '
            f'orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L9 4L0 8" '
            f'fill="{color}"/></marker>'
            for name, color in [("arrow", LINE), ("arrow-orange", ORANGE)]
        )
        document = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" width="2000" height="3070" '
            'viewBox="0 0 2000 3070" role="img" aria-labelledby="title description">'
            f'<title id="title">{escape(title)}</title>'
            f'<desc id="description">{escape(description)}</desc>'
            f"<defs>{symbols}{markers}</defs>"
            '<g font-family="Arial, Helvetica, sans-serif">'
            + "\n".join(self.parts)
            + "</g></svg>\n"
        )
        OUTPUT.write_text("\n".join(line.rstrip() for line in document.splitlines()) + "\n")


def configuration():
    path = ROOT / "infrastructure/terraform.tfvars"
    content = path.read_text() if path.exists() else ""
    availability = re.search(r"^high_availability\s*=\s*(true|false)\s*$", content, re.M)
    budget = re.search(r"^monthly_budget_usd\s*=\s*(\d+(?:\.\d+)?)\s*$", content, re.M)
    return bool(availability and availability[1] == "true"), budget[1] if budget else "20"


def draw_access(d):
    d.section(
        "01",
        150,
        370,
        "Accès au site et authentification",
        "Adresse HTTPS *.cloudfront.net et certificat AWS par défaut ; aucun "
        "domaine personnalisé à acheter.",
    )
    d.card(80, 280, 230, 130, None, "Client web", ["Navigateur", "HTTPS + jeton"])
    d.card(
        410,
        280,
        390,
        130,
        "Amazon-CloudFront",
        "CloudFront",
        ["Frontend : /*", "API : /api/*, sans cache"],
    )
    d.card(
        910,
        280,
        430,
        130,
        "Amazon-Simple-Storage-Service",
        "S3 · frontend privé",
        ["HTML, CSS, JavaScript", "Accès CloudFront par OAC"],
    )
    d.card(
        1450,
        280,
        470,
        130,
        "Amazon-Cognito",
        "Cognito User Pool",
        ["Inscription + email vérifié", "Code OAuth / PKCE ; JWT"],
    )
    d.arrow("M310 345H410")
    d.text(330, 329, "HTTPS", 17, LINE)
    d.arrow("M800 345H910")
    d.text(838, 329, "OAC", 17, LINE)
    d.arrow("M195 280V250H1680V280", True)
    d.text(1050, 240, "Connexion du client", 17, LINE)
    d.rect(410, 440, 390, 60)
    d.icon("AWS-WAF", 430, 450, 40)
    d.text(490, 477, "WAF · règles + limite de débit", 20, INK, True)
    d.arrow("M600 440V410", True)
    d.rect(910, 440, 430, 60)
    d.icon("AWS-Shield", 930, 450, 40)
    d.text(990, 477, "Shield Standard · inclus", 20, INK, True)
    d.text(1450, 465, "CloudFront global ; WAF géré en us-east-1.", 18)
    d.text(1450, 491, "Cognito et données métier à Paris.", 18)


def draw_network(d, ha):
    d.section(
        "02",
        560,
        630,
        "API et données — VPC avec sous-réseaux dans deux AZ",
        "ALB, EC2 et RDS privés. "
        + (
            "Deux EC2 minimum, RDS Multi-AZ, deux NAT."
            if ha
            else "Au démarrage : une EC2, RDS Single-AZ et un NAT ; absence de haute disponibilité."
        ),
    )
    d.icon("Amazon-Virtual-Private-Cloud", 1840, 580, 60)
    d.card(
        80,
        725,
        350,
        170,
        "Elastic-Load-Balancing",
        "ALB interne",
        ["Deux sous-réseaux privés", "HTTP : port 80", "En-tête secret exigé"],
    )
    d.rect(530, 685, 760, 230, "#fff7ed", "#f6bf87")
    d.text(555, 719, "Auto Scaling Group EC2 — instances privées", 23, ORANGE, True)
    d.card(
        555,
        745,
        345,
        145,
        "Amazon-EC2",
        "EC2 · API",
        ["Catalogue + commandes", "Service publisher outbox"],
        22,
        18,
    )
    d.card(
        920,
        745,
        345,
        145,
        None,
        "Capacité configurée",
        [
            "Minimum / désiré : " + ("2 / 2" if ha else "1 / 1"),
            "Maximum : " + ("4" if ha else "2"),
            "Scaling : requêtes ALB",
        ],
        22,
        18,
    )
    d.card(
        1420,
        725,
        500,
        170,
        "Amazon-RDS",
        "RDS PostgreSQL · D1",
        [
            "Produits, commandes, historique",
            "Événements, outbox, reçus",
            "Multi-AZ : " + ("activé" if ha else "désactivé (Single-AZ)"),
        ],
    )
    d.arrow("M410 385H385V540H55V700H255V725")
    d.text(650, 548, "Origine VPC CloudFront → ALB : connexion privée, HTTP", 18, LINE)
    d.arrow("M430 810H530")
    d.text(438, 793, "HTTP", 17, LINE)
    d.arrow("M1290 810H1420")
    d.text(1300, 793, "SQL / TLS", 17, LINE)
    d.rect(530, 945, 1390, 70, "#edf4ff", "#c4d8f1")
    d.text(555, 974, "Transaction atomique : commande + lignes + événement + OUTBOX", 22, INK, True)
    d.text(
        555,
        1000,
        "Confirmation après commit SQL ; clé d’idempotence et contrôle du stock côté serveur.",
        19,
    )
    d.card(
        80,
        1050,
        430,
        100,
        "VPC-NAT-Gateway",
        "NAT Gateway · " + ("2" if ha else "1"),
        ["Sorties EC2/Lambda vers API AWS"],
        21,
        18,
    )
    d.card(
        560,
        1050,
        430,
        100,
        "VPC-Endpoint",
        "VPC endpoint S3",
        ["Type Gateway ; accès S3 sans NAT"],
        21,
        18,
    )
    d.card(
        1040,
        1050,
        430,
        100,
        "Amazon-Simple-Storage-Service",
        "S3 · artefacts privés",
        ["Archives EC2 et Lambda versionnées"],
        21,
        18,
    )
    d.arrow("M990 1100H1040")
    d.card(
        1520,
        1050,
        400,
        100,
        "VPC-Internet-Gateway",
        "Internet Gateway",
        ["Attachée au VPC ; prérequis"],
        21,
        18,
    )
    d.text(
        80,
        1177,
        "NAT : SNS, SES, Secrets Manager, Cognito, CloudWatch, SSM et invocation "
        "Lambda. Le flux CloudFront → ALB ne passe pas par le NAT.",
        18,
    )


def draw_events(d):
    d.section(
        "03",
        1230,
        760,
        "Traitements événementiels — SNS, SQS et Lambda",
        "Publisher sur EC2 : OUTBOX → SNS, avec retries. Filtres SNS selon le type "
        "d’événement ; livraison au moins une fois.",
    )
    d.card(
        80,
        1410,
        400,
        170,
        "Amazon-Simple-Notification-Service",
        "SNS · événements",
        ["CommandeCreee", "EmballageTermine", "ExpeditionTerminee"],
    )
    d.arrow("M280 1410V1350H1700V1410", True)
    d.arrow("M800 1350V1410", True)
    d.arrow("M1250 1350V1410", True)
    d.text(600, 1384, "Abonnements filtrés → files distinctes", 18, LINE)
    for x, label, event_type, detail in [
        (600, "Emballage", "CommandeCreee", "CONFIRMED → PACKED"),
        (1050, "Expédition", "EmballageTermine", "PACKED → SHIPPED"),
        (1500, "Notification", "CommandeCreee", "Confirmation email via SES"),
    ]:
        d.card(x, 1410, 400, 120, "Amazon-Simple-Queue-Service", f"SQS · {label}", [event_type])
        d.card(
            x,
            1610,
            400,
            150,
            "AWS-Lambda",
            f"Lambda · {label}",
            [detail, "Idempotence : reçus SQL D1", "VPC privé ; concurrence : 2"],
            body_size=18,
        )
        d.arrow(f"M{x + 200} 1530V1610", True)
        d.text(x + 215, 1575, "Déclenche", 17, LINE)
        d.rect(x, 1810, 400, 80, "#fff8ef", "#edc291")
        d.icon("Amazon-Simple-Queue-Service", x + 20, 1825, 45)
        d.text(x + 85, 1843, "DLQ dédiée + alarme", 21, ORANGE, True)
        d.text(x + 85, 1870, "Après 5 réceptions infructueuses", 17, ORANGE)
        d.arrow(f"M{x + 400} 1470H{x + 420}V1850H{x + 400}", True, ORANGE)
    d.card(
        80,
        1640,
        400,
        230,
        None,
        "Fiabilité des traitements",
        [
            "1 message par invocation",
            "Lambda : timeout 30 secondes",
            "SQS : visibilité 180 secondes",
            "Échec partiel : message réessayé",
            "Email : doublon rare possible",
        ],
        22,
        18,
    )
    d.rect(600, 1930, 850, 40, "#edf4ff", "#c4d8f1")
    d.text(
        1025,
        1956,
        "D1 → RDS privé : état, audit, outbox et reçus de déduplication",
        19,
        INK,
        anchor="middle",
    )
    d.rect(1500, 1915, 400, 65)
    d.icon("Amazon-Simple-Email-Service", 1520, 1927, 40)
    d.text(1580, 1957, "SES · email au client", 21, INK, True)
    d.arrow("M1900 1705H1940V1948H1900", True)


def draw_deployment(d):
    d.section(
        "04",
        2030,
        350,
        "Déploiement et préparation de la base",
        "Une Lambda d’administration isolée applique les migrations avant le "
        "démarrage de l’API et du publisher.",
    )
    d.card(
        80,
        2150,
        400,
        140,
        "Amazon-Simple-Storage-Service",
        "S3 · archives",
        ["release.tar.gz pour EC2", "lambda.zip pour les fonctions"],
        body_size=18,
    )
    d.card(
        560,
        2150,
        400,
        140,
        "Amazon-EC2",
        "Démarrage EC2",
        ["Téléchargement via endpoint S3", "Services gérés par systemd"],
        body_size=18,
    )
    d.card(
        1040,
        2150,
        400,
        140,
        "AWS-Lambda",
        "Lambda · migration",
        [
            "Alembic + catalogue initial",
            "Compte SQL applicatif limité",
            "VPC privé ; timeout 120 s ; max 1",
        ],
        body_size=18,
    )
    d.card(
        1520,
        2150,
        400,
        140,
        "Amazon-RDS",
        "RDS · D1",
        ["Secret admin : migration seule", "API / métier : compte limité"],
        body_size=18,
    )
    d.arrow("M480 2220H560")
    d.text(488, 2202, "release", 16, LINE)
    d.arrow("M960 2220H1040")
    d.text(974, 2202, "invoke", 17, LINE)
    d.arrow("M1440 2220H1520")
    d.text(1448, 2202, "SQL/TLS", 16, LINE)
    d.text(
        80,
        2333,
        "Terraform provisionne les ressources et les archives. "
        "scripts/deploy_frontend.py publie le site dans S3 et invalide le cache "
        "CloudFront.",
        19,
    )
    d.text(
        80,
        2360,
        "Les Lambdas métier écrivent leurs transitions et événements en base ; le "
        "publisher EC2 republie ensuite l’outbox vers SNS.",
        19,
    )


def draw_operations(d, budget):
    d.section(
        "05",
        2420,
        435,
        "Sécurité, supervision et budget",
        "Services transversaux configurés dans Terraform. Les droits "
        "d’administration restent distincts des traitements métier.",
    )
    services = [
        (
            80,
            2540,
            "Amazon-CloudWatch",
            "CloudWatch",
            ["Logs, métriques, DLQ, âge outbox", "Alarmes → SNS → 3 destinataires"],
        ),
        (
            705,
            2540,
            "AWS-CloudTrail",
            "CloudTrail → S3 audit",
            ["Appels AWS ; validation des logs", "Bucket privé, chiffré et versionné"],
        ),
        (
            1330,
            2540,
            "AWS-Identity-and-Access-Management",
            "IAM",
            ["Rôles EC2 et Lambda distincts", "Permissions limitées aux ressources"],
        ),
        (
            80,
            2700,
            "AWS-Secrets-Manager",
            "Secrets Manager",
            ["Secrets SQL admin et applicatif", "Connexions RDS en TLS vérifié"],
        ),
        (
            705,
            2700,
            "AWS-Systems-Manager",
            "Systems Manager",
            ["Administration EC2 sans SSH", "Aucune IP publique sur les EC2"],
        ),
        (
            1330,
            2700,
            "AWS-Budgets",
            "AWS Budgets",
            [f"Alerte mensuelle : 80 % de {budget} USD", "3 destinataires ; aucun plafond"],
        ),
    ]
    for x, y, icon, title, lines in services:
        d.card(x, y, 590, 130, icon, title, lines, body_size=18)


def draw_footer(d, ha):
    d.text(
        60,
        2910,
        "Configuration dessinée : "
        + (
            "mode haute disponibilité activé."
            if ha
            else "mode démo réduit ; ASG désiré=1, max=2 ; RDS Single-AZ ; un NAT dans une AZ."
        ),
        20,
        INK,
        True,
    )
    d.text(
        60,
        2945,
        "Option high_availability=true : ASG min/désiré=2, max=4 ; RDS Multi-AZ ; "
        "un NAT par AZ. Les deux modes peuvent être facturés.",
        19,
    )
    d.text(
        60,
        2980,
        "D1 est un renvoi logique vers le même RDS ; les sections sont des "
        "regroupements de flux, pas des frontières réseau supplémentaires.",
        19,
    )
    d.text(
        60,
        3015,
        "Code Terraform validé, infrastructure non déployée. Sauvegardes RDS : "
        + ("7 jours" if ha else "1 jour")
        + ". Emballage et expédition simulés.",
        19,
    )
    d.text(
        60,
        3050,
        "Logos officiels AWS · paquet du 31 juillet 2026 · Schéma vérifié le 28 octobre 2026.",
        17,
    )


def main():
    ha, budget = configuration()
    d = Diagram()
    d.rect(0, 0, 2000, 3070, "#fff", "#fff")
    d.text(60, 62, "E-commerce Halloween", 39, INK, True)
    d.text(60, 105, "Architecture Terraform actuelle : API EC2 + traitements Lambda", 25)
    d.text(1940, 60, "AWS · eu-west-3 · Paris", 21, anchor="end")
    d.text(1940, 100, "Mode HA" if ha else "Mode démo · high_availability=false", 18, anchor="end")

    draw_access(d)
    draw_network(d, ha)
    draw_events(d)
    draw_deployment(d)
    draw_operations(d, budget)
    draw_footer(d, ha)
    d.save(
        "Architecture AWS hybride — configuration Terraform actuelle",
        "Boutique sans domaine personnalisé : CloudFront HTTPS, S3 privé, Cognito, "
        "ALB interne par origine VPC, EC2 et RDS privés, outbox et SNS/SQS/Lambda, "
        "SES, migration SQL, supervision et alertes.",
    )
    print(f"Generated {OUTPUT.relative_to(ROOT)} ({'HA' if ha else 'demo'} mode)")


if __name__ == "__main__":
    main()
