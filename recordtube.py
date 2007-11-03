import gobject
from dbus import Interface
from dbus.service import method, signal
from dbus.gobject_service import ExportedGObject
import os

from constants import Constants
from instance import Instance
import record

class RecordTube(ExportedGObject):

	__gsignals__ = {
		'recd-bits-arrived':
			(gobject.SIGNAL_RUN_FIRST, None, [object,object,object,object,object]),
		'recd-request':
			(gobject.SIGNAL_RUN_FIRST, None, [object,object]),
		'new-recd':
			(gobject.SIGNAL_RUN_FIRST, None, [object,object]),
		'recd-unavailable':
			(gobject.SIGNAL_RUN_FIRST, None, [object,object])
	}


	def __init__(self, tube):
		super(RecordTube, self).__init__(tube, Constants.PATH)
		self.tube = tube

		self.idNotify = self.tube.add_signal_receiver(self._newRecdTubeCb, 'notifyBudsOfNewRecd', Constants.IFACE, path=Constants.PATH, sender_keyword='sender')
		self.idRequest = self.tube.add_signal_receiver(self._reqRecdTubeCb, 'requestRecdBits', Constants.IFACE, path=Constants.PATH, sender_keyword='sender')
		self.idBroadcast = self.tube.add_signal_receiver(self._getRecdTubeCb, 'broadcastRecdBits', Constants.IFACE, path=Constants.PATH, sender_keyword='sender', byte_arrays=True)
		self.idUnavailable = self.tube.add_signal_receiver(self._unavailableRecdTubeCb, 'unavailableRecd', Constants.IFACE, path=Constants.PATH, sender_keyword='sender')


	@signal(dbus_interface=Constants.IFACE, signature='ss') #dual s for 2x strings
	def notifyBudsOfNewRecd(self, recorder, recdXml):
		record.Record.log.debug('Ive taken a new pho-ideo-audio!  I hereby send you an xml thumb of said media via this interface.')


	def _newRecdTubeCb(self, recorder, recdXml, sender=None):
		record.Record.log.debug("_newRecdTubeCb from " + recorder )
		if sender == self.tube.get_unique_name():
			record.Record.log.debug("_newRecdTubeCb: sender is my bus name, so ignore my own signal")
			return
		elif (recorder == Instance.keyHashPrintable):
			record.Record.log.debug('_newRecdTubeCb: excuse me?  you are asking me to share a photo with myself?')
			return

		self.emit( "new-recd", str(recorder), str(recdXml) )


	@signal(dbus_interface=Constants.IFACE, signature='sss') #triple s for 3x strings
	def requestRecdBits(self, whoWantsIt, whoTheyWantItFrom, recdMd5sumOfIt ):
		record.Record.log.debug('I am requesting a high-res version of someones media.')


	def _reqRecdTubeCb(self, whoWantsIt, whoTheyWantItFrom, recdMd5sumOfIt, sender=None):
		if sender == self.tube.get_unique_name():
			record.Record.log.debug("_reqRecdTubeCb: sender is my bus name, so ignore my own signal")
			return
		elif (whoWantsIt == Instance.keyHashPrintable):
			record.Record.log.debug('_reqRecdTubeCb: excuse me?  you are asking me to share a photo with myself?')
			return
		elif (whoTheyWantItFrom != Instance.keyHashPrintable):
			record.Record.log.debug('_reqRecdTubeCb: ive overhead someone wants a photo, but not from me')
			return

		self.emit( "recd-request", str(whoWantsIt), str(recdMd5sumOfIt) )


	def broadcastRecd(self, md5, filepath, sendThisTo ):
		size = os.path.getsize(filepath)
		f = open(filepath)
		chunk_size = 1000
		chunks = size / chunk_size
		if (size%chunk_size != 0):
			chunks += 1

		for chunk in range(chunks):
			bytes = f.read(chunk_size)
			if (chunk == 0):
				record.Record.log.debug("sending " + str(chunk+1) + " of " + str(chunks) + " to " + sendThisTo )
			if (chunk == chunks-1):
				record.Record.log.debug("sending " + str(chunk+1) + " of " + str(chunks) + " to " + sendThisTo )
			self.broadcastRecdBits(md5, chunk+1, chunks, bytes, sendThisTo, Instance.keyHashPrintable)

		f.close()
		return True


	@signal(dbus_interface=Constants.IFACE, signature='suuayss')
	def broadcastRecdBits(self, md5, part, numparts, bytes, sendTo, fromWho ):
		pass


	def _getRecdTubeCb(self, md5, part, numparts, bytes, sentTo, fromWho, sender=None):
		if sender == self.tube.get_unique_name():
			#record.Record.log.debug("_reqRecdTubeCb: sender is my bus name, so ignore my own signal")
			return
		if (fromWho == Instance.keyHashPrintable):
			#record.Record.log.debug('_getRecdTubeCb: i dont want bits from meself, thx anyway.  schizophrenic?')
			return
		if (sentTo != Instance.keyHashPrintable):
			#record.Record.log.debug('_getRecdTubeCb: ive overhead someone sending bits, but not to me!')
			return

		self.emit( "recd-bits-arrived", md5, part, numparts, bytes, fromWho )


	@signal(dbus_interface=Constants.IFACE, signature='sss') #triple s for 3x strings
	def unavailableRecd(self, md5sumOfIt, whoDoesntHaveIt, whoAskedForIt):
		record.Record.log.debug('unavailableRecd: id love to share this photo, but i am without a copy meself chum')


	def _unavailableRecdTubeCb( self, md5sumOfIt, whoDoesntHaveIt, whoAskedForIt, sender=None):
		if sender == self.tube.get_unique_name():
			record.Record.log.debug("_unavailableRecdTubeCb: sender is my bus name, so ignore my own signal")
			return
		if (whoDoesntHaveIt == Instance.keyHashPrintable):
			record.Record.log.debug('_unavailableRecdTubeCb: yes, i know i dont have it, i just told you/me/us.')
			return
		if (whoAskedForIt != Instance.keyHashPrintable):
			record.Record.log.debug('_unavailableRecdTubeCb: ive overheard someone doesnt have a photo, but i didnt ask for that one anyways')
			return

		self.emit("recd-unavailable", md5sumOfIt, whoDoesntHaveIt)