"""Envoi du rapport par SMTP (facultatif : sans configuration, on s'abstient)."""

from __future__ import annotations

import html
import json
import logging
import re
import smtplib
from email.message import EmailMessage

from . import secrets
from .config import Config

journal = logging.getLogger(__name__)


def _markdown_vers_html(texte: str) -> str:
    lignes = []
    for ligne in html.escape(texte).splitlines():
        ligne = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", ligne)
        if ligne.startswith("## "):
            lignes.append(f"<h3 style='margin:18px 0 6px'>{ligne[3:]}</h3>")
        elif re.match(r"^\s*([-*]|\d+\.)\s", ligne):
            lignes.append(f"<li>{re.sub(r'^\s*([-*]|\d+\.)\s', '', ligne)}</li>")
        elif ligne.strip():
            lignes.append(f"<p style='margin:4px 0'>{ligne}</p>")
    return "\n".join(lignes)


def construire(etab: dict, rapport: dict) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = (
        f"[WatchMyBusiness] {etab['nom']} — semaine {rapport['semaine_id']} "
        f"({rapport['tendance']})"
    )
    entete = (
        f"{rapport['nb_avis']} avis · note moyenne {rapport['note_moyenne']} · "
        f"{rapport['pct_positif']} % positifs · {rapport['pct_negatif']} % négatifs"
    )
    message.set_content(f"{entete}\n\n{rapport['synthese']}")
    themes = "".join(
        f"<tr><td>{html.escape(t['libelle'])}</td><td align='right'>{t['occurrences']}</td></tr>"
        for t in json.loads(rapport["top_negatifs"])
    )
    message.add_alternative(
        f"""<div style="font-family:Arial,sans-serif;max-width:640px">
<h2 style="margin-bottom:4px">{html.escape(etab['nom'])}</h2>
<p style="color:#666;margin-top:0">
Semaine du {rapport['periode_debut']} au {rapport['periode_fin']}</p>
<p><b>{html.escape(entete)}</b></p>
{_markdown_vers_html(rapport['synthese'])}
<h3>Thèmes négatifs de la semaine</h3>
<table cellpadding="4">{themes or '<tr><td>aucun</td></tr>'}</table>
</div>""",
        subtype="html",
    )
    return message


def envoyer_rapport(config: Config, etab: dict, rapport: dict) -> str:
    if not (config.smtp_hote and config.smtp_utilisateur):
        return "non_configure"
    mot_de_passe = secrets.lire(config, config.secret_smtp, obligatoire=False)
    if not mot_de_passe:
        return "non_configure"

    message = construire(etab, rapport)
    message["From"] = config.email_expediteur or config.smtp_utilisateur
    message["To"] = etab["email_manager"]
    try:
        with smtplib.SMTP(config.smtp_hote, config.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(config.smtp_utilisateur, mot_de_passe)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as erreur:
        journal.error("Envoi e-mail à %s impossible : %s", etab["email_manager"], erreur)
        return "echec"
    return "envoye"
