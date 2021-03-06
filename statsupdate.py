import db
import time
import logging
import raven
import configparser
import os
import typing
# python-telegram-bot has a different name
# noinspection PyPackageRequirements
import telegram
import sys
import coloredlogs
import requests
from dirty import Dirty
from sentry_sdk import configure_scope

logging.getLogger().disabled = True
logger = logging.getLogger(__name__)
os.environ["COLOREDLOGS_LOG_FORMAT"] = "%(asctime)s %(levelname)s %(name)s %(message)s"
coloredlogs.install(level="DEBUG", logger=logger)

# Init the config reader
config = configparser.ConfigParser()
config.read("config.ini")

# Init the Sentry client
sentry = raven.Client(config["Sentry"]["token"],
                      release=raven.fetch_git_sha(os.path.dirname(__file__)),
                      install_logging_hook=False,
                      hook_libraries=[])

telegram_bot = telegram.Bot(config["Telegram"]["bot_token"])


def update_block(session: db.Session, block: list, delay: float=0, change_callback: typing.Callable=None):
    for item in block:
        logger.debug(f"Updating {repr(item)}.")
        t = time.clock()
        try:
            change = item.update(session=session)
        except requests.exceptions.HTTPError as e:
            with configure_scope() as scope:
                if str(e.response.status_code).startswith("5"):
                    scope.level = "warning"
                    logger.warning(f"Server error {sys.exc_info()} while updating {repr(item)}.")
                else:
                    scope.level = "error"
                    logger.error(f"Error {sys.exc_info()} while updating {repr(item)}.")
            sentry.extra_context({
                "item": repr(item),
                "response": {
                    "code": e.response.status_code,
                    "text": e.response.text
                }
            })
            sentry.captureException()
            continue
        except Exception:
            logger.warning(f"Error {sys.exc_info()} while updating {repr(item)}.")
            sentry.extra_context({
                "item": repr(item)
            })
            sentry.captureException()
            continue
        if change:
            change_callback(item, change)
        sleep_time = delay - time.clock() + t
        time.sleep(sleep_time if sleep_time > 0 else 0)


# noinspection PyUnusedLocal
def new_dota_rank(item: db.Dota, change):
    try:
        telegram_bot.send_message(config["Telegram"]["main_group"],
                                  f"✳️ {item.steam.royal.username} è salito a"
                                  f" {item.get_rank_name()} {item.get_rank_number()} su Dota 2!")
    except Exception:
        logger.warning(f"Couldn't notify on Telegram: {item}")


def new_lol_rank(item, change: typing.Tuple[Dirty]):
    # It always gets called, even when there is no change
    # Assignment inspection is wrong
    # noinspection PyTupleAssignmentBalance
    solo, flex, twtr = change
    try:
        if solo:
            telegram_bot.send_message(config["Telegram"]["main_group"],
                                      f"✳️ {item.royal.username} ha un nuovo rank in **SOLO/DUO**"
                                      f" su League of Legends!\n"
                                      f"{solo.initial_value[0]} {solo.initial_value[1]} ->"
                                      f" **{solo.value[0]} {solo.value[1]}**",
                                      parse_mode="Markdown")
        if flex:
            telegram_bot.send_message(config["Telegram"]["main_group"],
                                      f"✳️ {item.royal.username} ha un nuovo rank in **FLEX**"
                                      f" su League of Legends!\n"
                                      f"{flex.initial_value[0]} {flex.initial_value[1]} ->"
                                      f" **{flex.value[0]} {flex.value[1]}**",
                                      parse_mode="Markdown")
        if twtr:
            telegram_bot.send_message(config["Telegram"]["main_group"],
                                      f"✳️ {item.royal.username} ha un nuovo rank in **3V3**"
                                      f" su League of Legends!\n"
                                      f"{twtr.initial_value[0]} {twtr.initial_value[1]} ->"
                                      f" **{twtr.value[0]} {twtr.value[1]}**",
                                      parse_mode="Markdown")
    except Exception:
        logger.warning(f"Couldn't notify on Telegram: {item}")


def process():
    while True:
        session = db.Session()
        logger.info("Now updating Steam data.")
        update_block(session, session.query(db.Steam).all())
        session.commit()
        logger.info("Now updating Dota data.")
        update_block(session, session.query(db.Dota).all(), delay=5, change_callback=new_dota_rank)
        session.commit()
        logger.info("Now updating League of Legends data.")
        update_block(session, session.query(db.LeagueOfLegends).all(), delay=5, change_callback=new_lol_rank)
        session.commit()
        logger.info("Now updating osu! data.")
        update_block(session, session.query(db.Osu).all(), delay=5)
        session.commit()
        logger.info("Now updating Overwatch data.")
        update_block(session, session.query(db.Overwatch).all(), delay=5)
        session.commit()
        logger.info("Pausing for 30 minutes.")
        time.sleep(1800)


if __name__ == "__main__":
    process()
