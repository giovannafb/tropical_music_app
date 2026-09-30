"""Worker Python : indexation Elasticsearch (outbox), envoi des emails, flush des compteurs.

Lancement : python -m app.workers.main
"""
import asyncio
import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.redis_client import get_redis
from app.repositories.search import ensure_indices, get_es
from app.workers import tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("worker")

OUTBOX_INTERVAL_S = 1
COUNTERS_INTERVAL_S = 10


def _with_db(fn, *args):
    with get_sessionmaker()() as db:
        return fn(db, *args)


async def wait_for_elasticsearch() -> None:
    while True:
        try:
            await asyncio.to_thread(ensure_indices, get_es())
            log.info("Index Elasticsearch prêts")
            return
        except Exception as exc:
            log.warning("Elasticsearch indisponible (%s), nouvel essai dans 5 s", exc)
            await asyncio.sleep(5)


async def outbox_loop() -> None:
    while True:
        try:
            done = await asyncio.to_thread(_with_db, tasks.process_outbox, get_es())
            if done:
                log.info("Outbox : %d événement(s) indexé(s)", done)
                continue
        except Exception:
            log.exception("Erreur pendant l'indexation")
        await asyncio.sleep(OUTBOX_INTERVAL_S)


async def counters_loop() -> None:
    while True:
        await asyncio.sleep(COUNTERS_INTERVAL_S)
        try:
            plays = await asyncio.to_thread(_with_db, tasks.flush_play_counts, get_redis())
            history = await asyncio.to_thread(_with_db, tasks.flush_history, get_redis())
            if plays or history:
                log.info("Compteurs : %d titre(s), %d écoute(s) enregistrée(s)", plays, history)
        except Exception:
            log.exception("Erreur pendant le flush des compteurs")


async def send_email(mail: dict) -> None:
    s = get_settings()
    message = EmailMessage()
    message["From"] = s.mail_from
    message["To"] = mail["to"]
    message["Subject"] = mail["subject"]
    message.set_content(mail["body"])
    await aiosmtplib.send(
        message,
        hostname=s.smtp_host,
        port=s.smtp_port,
        username=s.smtp_user or None,
        password=s.smtp_password or None,
        start_tls=s.smtp_starttls,
    )


async def mail_loop() -> None:
    r = get_redis()
    while True:
        mail = await asyncio.to_thread(tasks.pop_email, r)
        if mail is None:
            continue
        try:
            await send_email(mail)
            log.info("Email envoyé à %s : %s", mail["to"], mail["subject"])
        except Exception:
            log.exception("Échec d'envoi d'email, nouvel essai dans 10 s")
            await asyncio.to_thread(tasks.requeue_email, r, mail)
            await asyncio.sleep(10)


async def main() -> None:
    mail = asyncio.create_task(mail_loop())
    await wait_for_elasticsearch()
    await asyncio.gather(mail, outbox_loop(), counters_loop())


if __name__ == "__main__":
    asyncio.run(main())
