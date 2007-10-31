import os

from sugar import profile
from sugar import util
from sugar.activity import activity

from color import Color

class Instance:
	key = profile.get_pubkey()
	keyHash = util._sha_data(key)
	keyHashPrintable = util.printable_hash(keyHash)
	nickName = profile.get_nick_name()

	colorFill = Color()
	colorFill.init_hex( profile.get_color().get_fill_color() )
	colorStroke = Color()
	colorStroke.init_hex( profile.get_color().get_stroke_color() )

	instanceId = None
	tmpPath = None

	def __init__(self, ca):
		self.__class__.instanceId = ca._activity_id
		tmpPath = os.path.join( ca.get_activity_root(), "tmp" )
		self.__class__.tmpPath = os.path.join( tmpPath, str(self.__class__.instanceId))
		recreateTmp()


def recreateTmp():
	if (os.path.exists(Instance.tmpPath)):
		shutil.rmtree(Instance.tmpPath)
	os.makedirs(Instance.tmpPath)