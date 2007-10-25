#todo: access these same vars from ra
SERVICE = "org.laptop.RecordActivity"
IFACE = SERVICE
PATH = "/org/laptop/RecordActivity"

import gobject
from dbus import Interface
from dbus.service import method, signal
from dbus.gobject_service import ExportedGObject

class RecordTube(ExportedGObject):
	"""The bit that talks over the TUBES!!!"""

	__gsignals__ = {
		'filepart':
			(gobject.SIGNAL_RUN_FIRST, None, [object,object,object,object,object,object,object]),
		'new-recd':
			(gobject.SIGNAL_RUN_FIRST, None, [object,object])
	}


	def __init__(self, tube, get_buddy, myHashKey, logger):
		super(RecordTube, self).__init__(tube, PATH)
		self.tube = tube
		self._get_buddy = get_buddy  # Converts handle to Buddy object
		self.myHashKey = myHashKey
		self._logger = logger

		self.tube.add_signal_receiver(self._newRecdTubeCb, 'notifyBudsOfNewRecd', IFACE, path=PATH, sender_keyword='sender')


	@signal(dbus_interface=IFACE, signature='ss') #dual s for 2x strings
	def notifyBudsOfNewRecd(self, recorder, recdXml):
		"""Say Hello to whoever else is in the tube."""
		self._logger.debug('Ive taken a new photo!')


	def _newRecdTubeCb(self, recorder, recdXml, sender=None):
		self._logger.debug("_newRecdCb from " + recorder )
		if sender == self.tube.get_unique_name():
			self._logger.debug("sender is my bus name, so ignore my own signal")
			return
		elif (recorder == self.myHashKey):
			self._logger.debug('excuse me?  you are asking me to share this with myself?')
			return

		print("here is the xml:" + recdXml)
		self.emit( "new-recd", str(recorder), str(recdXml) )