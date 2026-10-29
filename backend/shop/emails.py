"""Minuit transactional emails with inline email-safe styles and a text alternative."""

from dataclasses import dataclass
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urlsplit

from shop.domain import EventType

INK = "#202820"
CREAM = "#faf7f0"
ORANGE = "#ce5b2f"
MUTED = "#74796d"
LINE = "#dedfd4"
EMAIL_TEMPLATE = Template((Path(__file__).parent / "templates/order_email.html").read_text())


@dataclass(frozen=True)
class OrderEmail:
    subject: str
    text: str
    html: str


def money(cents: int) -> str:
    return f"{cents // 100:,}".replace(",", "\u202f") + f",{cents % 100:02d}\u00a0€"


def render_order_email(order, event_type: EventType, site_url: str = "") -> OrderEmail:
    if event_type == EventType.ORDER_CREATED:
        subject = "Minuit — Votre commande est confirmée"
        badge = "COMMANDE CONFIRMÉE"
        heading = (
            'Le sort est jeté.<br><em style="color:#ce5b2f;font-weight:normal;">'
            "Merci pour votre commande.</em>"
        )
        introduction = (
            "Vos petites trouvailles ont bien rejoint notre cabinet de curiosités. "
            "Nous préparons votre butin avec soin : un nouvel email vous préviendra "
            "dès son expédition."
        )
        plain_intro = f"Merci ! Votre commande {order.id} est confirmée."
        active = 0
        symbol = "✦"
    elif event_type == EventType.ORDER_SHIPPED:
        subject = "Minuit — Votre commande est expédiée"
        badge = "COMMANDE EXPÉDIÉE"
        heading = 'La magie<br>est <em style="color:#ce5b2f;font-weight:normal;">en route.</em>'
        introduction = (
            "L’emballage de votre commande est terminé et son expédition a été simulée. "
            "Retrouvez le détail de votre butin et toutes les étapes de son parcours "
            "dans votre carnet de commandes."
        )
        plain_intro = f"Votre commande {order.id} est expédiée."
        active = 2
        symbol = "✧"
    else:
        raise ValueError("Unsupported notification event")

    orders_url = ""
    if site_url:
        parsed = urlsplit(site_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Email links require an HTTPS site URL without credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("Email site URL must not contain a query or fragment")
        orders_url = site_url.rstrip("/") + "/orders.html"

    rows = []
    plain_lines = []
    for item in order.lines:
        name = escape(item.product_name)
        amount = money(item.quantity * item.unit_price_cents)
        rows.append(f"""<tr>
<td style="padding:18px 0;border-bottom:1px solid {LINE};vertical-align:top;">
<div style="font-size:15px;line-height:22px;font-weight:bold;overflow-wrap:anywhere;">{name}</div>
<div style="font-size:12px;line-height:20px;color:{MUTED};
">Quantité : {item.quantity} · {money(item.unit_price_cents)} l’unité</div>
</td><td width="105" align="right" style="padding:18px 0 18px 12px;border-bottom:1px solid {LINE};
vertical-align:top;font-size:15px;line-height:22px;white-space:nowrap;">{amount}</td>
</tr>""")
        plain_lines.append(f"{item.quantity} × {item.product_name} — {amount}")

    steps = []
    for index, label in enumerate(("Confirmée", "Emballée", "Expédiée")):
        color = INK if index <= active else MUTED
        background = "#dfe5d6" if index <= active else "#eeeee5"
        steps.append(f"""<td width="33%" valign="top" style="padding:0 3px;">
<div style="border-top:3px solid {color if index <= active else LINE};padding-top:12px;">
<span style="display:inline-block;background:{background};color:{color};font-size:11px;
line-height:24px;width:24px;text-align:center;border-radius:50%;">{index + 1:02d}</span>
<div style="padding-top:7px;font-size:12px;line-height:18px;color:{color};
font-weight:{"bold" if index <= active else "normal"};">{label}</div>
</div></td>""")

    cta = ""
    if orders_url:
        cta = f'''<table role="presentation" cellspacing="0" cellpadding="0" border="0"
style="margin:28px 0 12px;">
<tr><td bgcolor="{INK}" style="border-radius:5px;mso-padding-alt:18px 26px;">
<a href="{escape(orders_url, quote=True)}" style="display:inline-block;padding:18px 26px;
color:#fffefa;font-size:14px;font-weight:bold;text-decoration:none;border:1px solid {INK};
border-radius:5px;">Suivre ma commande&nbsp; ↗</a>
</td></tr></table>
<p style="margin:0;font-size:12px;line-height:20px;color:{MUTED};
">Connectez-vous avec le compte utilisé pour votre commande.</p>'''

    order_id = escape(str(order.id))
    short_id = escape(str(order.id)[:8].upper())
    total = money(order.total_cents)
    preheader = escape(f"{badge.capitalize()} · Votre butin Minuit, n° {short_id} · {total}")
    html = EMAIL_TEMPLATE.substitute(
        subject=escape(subject),
        INK=INK,
        CREAM=CREAM,
        ORANGE=ORANGE,
        MUTED=MUTED,
        LINE=LINE,
        preheader=preheader,
        badge=badge,
        symbol=symbol,
        heading=heading,
        introduction=introduction,
        steps="".join(steps),
        rows="".join(rows),
        short_id=short_id,
        total=total,
        cta=cta,
        order_id=order_id,
    )
    text = "\n\n".join(
        [
            "MINUIT ✦ — De petites frayeurs, de grands souvenirs.",
            plain_intro,
            introduction,
            "Votre butin\n" + "\n".join(plain_lines),
            f"Total : {total}",
            f"Suivre ma commande : {orders_url}" if orders_url else "",
            "Boutique de démonstration : aucun paiement ni envoi physique. "
            "L’emballage et l’expédition sont simulés.",
        ]
    )
    return OrderEmail(subject=subject, text=text, html=html)
