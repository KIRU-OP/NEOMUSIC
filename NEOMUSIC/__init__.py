from NEOMUSIC.core.bot import Anony
from NEOMUSIC.core.dir import dirr
from NEOMUSIC.core.git import git
from NEOMUSIC.core.userbot import Userbot
from NEOMUSIC.misc import heroku, dbb

from .logging import LOGGER

dirr()
git()
dbb()
heroku()

app = Anony()
userbot = Userbot()

from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
