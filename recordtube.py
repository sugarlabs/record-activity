#todo: access these same vars from the acitivity subclass
SERVICE = "org.laptop.RecordActivity"
IFACE = SERVICE
PATH = "/org/laptop/RecordActivity"

import gobject
from dbus import Interface
from dbus.service import method, signal
from dbus.gobject_service import ExportedGObject

class RecordTube(ExportedGObject):

	__gsignals__ = {
		'recd-bits-arrived':
			(gobject.SIGNAL_RUN_FIRST, None, [object,object,object,object,object]),
		'recd-request':
			(gobject.SIGNAL_RUN_FIRST, None, [object,object]),
		'new-recd':
			(gobject.SIGNAL_RUN_FIRST, None, [object,object])
	}


	def __init__(self, tube, get_buddy, myHashKey, logger):
		super(RecordTube, self).__init__(tube, PATH)
		self.tube = tube
		self._get_buddy = get_buddy  # Converts handle to Buddy object
		self.myHashKey = myHashKey
		self._logger = logger

		self.idNotify = self.tube.add_signal_receiver(self._newRecdTubeCb, 'notifyBudsOfNewRecd', IFACE, path=PATH, sender_keyword='sender')
		self.idRequest = self.tube.add_signal_receiver(self._reqRecdTubeCb, 'requestRecdBits', IFACE, path=PATH, sender_keyword='sender')
		self.idBroadcast = self.tube.add_signal_receiver(self._getRecdTubeCb, 'broadcastRecdBits', IFACE, path=PATH, sender_keyword='sender', byte_arrays=True)


	@signal(dbus_interface=IFACE, signature='ss') #dual s for 2x strings
	def notifyBudsOfNewRecd(self, recorder, recdXml):
		self._logger.debug('Ive taken a new pho-ideo-audio!  I hereby send you an xml thumb of said media via this interface.')


	def _newRecdTubeCb(self, recorder, recdXml, sender=None):
		self._logger.debug("_newRecdTubeCb from " + recorder )
		if sender == self.tube.get_unique_name():
			self._logger.debug("_newRecdTubeCb: sender is my bus name, so ignore my own signal")
			return
		elif (recorder == self.myHashKey):
			self._logger.debug('_newRecdTubeCb: excuse me?  you are asking me to share a photo with myself?')
			return

		self.emit( "new-recd", str(recorder), str(recdXml) )


	@signal(dbus_interface=IFACE, signature='sss') #triple s for 3x strings
	def requestRecdBits(self, whoWantsIt, whoTheyWantItFrom, recdMd5sumOfIt ):
		self._logger.debug('I am requesting a high-res version of someones media.')


	def _reqRecdTubeCb(self, whoWantsIt, whoTheyWantItFrom, recdMd5sumOfIt, sender=None):
		if sender == self.tube.get_unique_name():
			self._logger.debug("_reqRecdTubeCb: sender is my bus name, so ignore my own signal")
			return
		elif (whoWantsIt == self.myHashKey):
			self._logger.debug('_reqRecdTubeCb: excuse me?  you are asking me to share a photo with myself?')
			return
		elif (whoTheyWantItFrom != self.myHashKey):
			self._logger.debug('_reqRecdTubeCb: ive overhead someone wants a photo, but not from me')
			return

		self.emit( "recd-request", str(whoWantsIt), str(recdMd5sumOfIt) )


	def broadcastRecd(self, md5, filepath, sendThisTo ):
		size = os.path.getsize(filepath)
		f = open(filename)
		chunk_size = 1000
		chunks = size / chunk_size
		if (size%chunk_size != 0):
			chunks += 1

		for chunk in range(chunks):
			bytes = f.read(chunk_size)
			self._logger.debug("sending " + str(chunk+1) + " of " + str(chunks) + " to " + lender )
			self.broadcastRecdBits(md5, os.path.basename(filename), chunk+1, chunks, bytes, sendTo, self.myHashKey)

		f.close()
		return True


	@signal(dbus_interface=IFACE, signature='suuayss')
	def broadcastRecdBits(self, md5, part, numparts, bytes, sendTo, fromWho ):
		pass


	def _getRecdTubeCb(self, md5, part, numparts, bytes, sentTo, fromWho, sender=None):
		if sender == self.tube.get_unique_name():
			self._logger.debug("_reqRecdTubeCb: sender is my bus name, so ignore my own signal")
			return
		if (fromWho == self.myHashKey):
			self._logger.debug('_getRecdTubeCb: i dont want bits from meself, thx anyway.  schizophrenic?')
		if (sentTo != self.myHashKey):
			self._logger.debug('_getRecdTubeCb: ive overhead someone sending bits, but not to me!')
			return

		self.emit( "recd-bits-arrived", md5, part, numparts, bytes, fromWho )