import os

from sugar import profile
from sugar import util
from sugar.activity import activity
import shutil

from color import Color
import record

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
	instancePath = None

	def __init__(self, ca):
		self.__class__.instanceId = ca._activity_id
		tmpPath = os.path.join( ca.get_activity_root(), "tmp" )
		self.__class__.tmpPath = os.path.join( tmpPath, str(self.__class__.instanceId))
		recreateTmp()

		self.__class__.instancePath = os.path.join( ca.get_activity_root(), "instance" )
		recreateInstance()


def recreateTmp():
	#todo: figure out how to have multiple spaces for my media
	#problem is, if new instance is created, with this code, it clears the whole tmp directory!
	if (os.path.exists(Instance.tmpPath)):
		shutil.rmtree(Instance.tmpPath)
	if (not os.path.exists(Instance.tmpPath)):
		os.makedirs(Instance.tmpPath)


def recreateInstance():
	#todo: figure out how to have multiple spaces for my media
	#problem is, if new instance is created, with this code, it clears the whole tmp directory!
	if (os.path.exists(Instance.tmpPath)):
		shutil.rmtree(Instance.tmpPath)
	if (not os.path.exists(Instance.instancePath)):
		os.makedirs(Instance.instancePath)