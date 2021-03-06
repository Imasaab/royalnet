import multiprocessing
import telegrambot
import discordbot
import redditbot
import statsupdate
import time
import logging
import coloredlogs
import os

logging.getLogger().disabled = True
logger = logging.getLogger(__name__)
os.environ["COLOREDLOGS_LOG_FORMAT"] = "%(asctime)s %(levelname)s %(name)s %(message)s"
coloredlogs.install(level="DEBUG", logger=logger)

discord_telegram_pipe = multiprocessing.Pipe()
discord = multiprocessing.Process(target=discordbot.process, args=(discord_telegram_pipe[0],))
telegram = multiprocessing.Process(target=telegrambot.process, args=(discord_telegram_pipe[1],))
reddit = multiprocessing.Process(target=redditbot.process)
stats = multiprocessing.Process(target=statsupdate.process)

if __name__ == "__main__":
    logger.info("Starting Discord Bot process...")
    discord.start()
    logger.info("Starting Telegram Bot process...")
    telegram.start()
    logger.info("Starting Reddit Bot process...")
    reddit.start()
    if not __debug__:
        logger.info("Starting StatsUpdate process...")
        stats.start()
    else:
        logger.warning("StatsUpdate process disabled in debug mode.")
    try:
        while True:
            if discord.exitcode is not None:
                logger.warning(f"Discord Bot exited with {discord.exitcode}")
                del discord
                logger.info("Restarting Discord Bot process...")
                discord = multiprocessing.Process(target=discordbot.process, args=(discord_telegram_pipe[0],))
                discord.start()
            if telegram.exitcode is not None:
                logger.warning(f"Telegram Bot exited with {telegram.exitcode}")
                del telegram
                telegram = multiprocessing.Process(target=telegrambot.process, args=(discord_telegram_pipe[1],))
                logger.info("Restarting Telegram Bot process...")
                telegram.start()
            if reddit.exitcode is not None:
                logger.warning(f"Reddit Bot exited with {reddit.exitcode}")
                del reddit
                reddit = multiprocessing.Process(target=redditbot.process)
                logger.info("Restarting Reddit Bot process...")
                reddit.start()
            if not __debug__ and stats.exitcode is not None:
                logger.warning(f"StatsUpdater exited with {stats.exitcode}")
                del stats
                stats = multiprocessing.Process(target=statsupdate.process)
                logger.info("Restarting StatsUpdate process...")
                stats.start()
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Now stopping...")
        logger.info("Asking Discord process to stop...")
        discord_telegram_pipe[1].send("stop")
        logger.info("Waiting for Discord Bot process to stop...")
        discord.join()
        logger.info("Waiting for Telegram Bot process to stop...")
        telegram.join()
        logger.info("Waiting for Reddit Bot process to stop...")
        reddit.join()
        logger.info("Waiting for StatsUpdate process to stop...")
        stats.join()
