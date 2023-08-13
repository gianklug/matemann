# matemann


Bot to sync CTFtime events to your discord


## Howto
* Build the container `docker build .  -t matemann`
* Set up a cronjob to run the bot with a discord token:
  `docker run -e "BOT_TOKEN=xyz" -e "GUILD_ID=xyz" matemann`
