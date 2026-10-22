"""Accès BigQuery : lecture paramétrée et écriture idempotente.

Toutes les écritures passent par un job de chargement dans une table de
transit, puis un MERGE sur la clé métier. Rejouer un job ne crée donc jamais
de doublon, et les load jobs sont gratuits (contrairement au streaming insert).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any

from .config import Config


@lru_cache(maxsize=4)
def _client(projet: str, region: str):
    from google.cloud import bigquery

    return bigquery.Client(project=projet, location=region)


def client(config: Config):
    return _client(config.projet, config.region)


def serialisable(valeur: Any) -> Any:
    """Convertit les types renvoyés par BigQuery (Decimal, date…) en JSON natif."""
    if isinstance(valeur, Decimal):
        return float(valeur)
    if isinstance(valeur, date | datetime):
        return valeur.isoformat()
    if isinstance(valeur, list):
        return [serialisable(v) for v in valeur]
    if isinstance(valeur, dict):
        return {k: serialisable(v) for k, v in valeur.items()}
    return valeur


def requete(config: Config, sql: str, parametres: dict[str, Any] | None = None) -> list[dict]:
    from google.cloud import bigquery

    types = {bool: "BOOL", int: "INT64", float: "FLOAT64", str: "STRING"}
    params = []
    for nom, valeur in (parametres or {}).items():
        if hasattr(valeur, "isoformat") and not isinstance(valeur, str):
            params.append(bigquery.ScalarQueryParameter(nom, "DATE", valeur))
        else:
            params.append(bigquery.ScalarQueryParameter(nom, types[type(valeur)], valeur))
    job = client(config).query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
    return [dict(ligne) for ligne in job.result()]


def fusionner(
    config: Config,
    table: str,
    lignes: Iterable[dict],
    cles: tuple[str, ...],
    mettre_a_jour: bool = True,
) -> int:
    """Charge `lignes` en transit puis MERGE dans `table` sur `cles`."""
    from google.cloud import bigquery

    lignes = list(lignes)
    if not lignes:
        return 0

    bq = client(config)
    cible = bq.get_table(config.table_id(table))
    transit_id = config.table_id(f"_transit_{table}_{uuid.uuid4().hex[:8]}")

    chargement = bq.load_table_from_json(
        lignes,
        transit_id,
        job_config=bigquery.LoadJobConfig(
            schema=cible.schema,
            write_disposition="WRITE_TRUNCATE",
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        ),
    )
    chargement.result()
    try:
        bq.query(
            f"ALTER TABLE `{transit_id}` SET OPTIONS (expiration_timestamp = "
            "TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR))"
        ).result()
        colonnes = [champ.name for champ in cible.schema]
        jointure = " AND ".join(f"c.{cle} = t.{cle}" for cle in cles)
        maj = ", ".join(f"{col} = t.{col}" for col in colonnes if col not in cles)
        clause_maj = f"WHEN MATCHED THEN UPDATE SET {maj}" if mettre_a_jour and maj else ""
        sql = f"""
            MERGE `{cible.full_table_id.replace(':', '.')}` c
            USING `{transit_id}` t
            ON {jointure}
            {clause_maj}
            WHEN NOT MATCHED THEN INSERT ({", ".join(colonnes)})
            VALUES ({", ".join(f"t.{col}" for col in colonnes)})
        """
        resultat = bq.query(sql)
        resultat.result()
        return resultat.num_dml_affected_rows or 0
    finally:
        bq.delete_table(transit_id, not_found_ok=True)
