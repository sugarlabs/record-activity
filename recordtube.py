#todo: access these same vars from ra
SERVICE = "org.laptop.RecordActivity"
IFACE = RecordActivity.SERVICE
PATH = "/org/laptop/RecordActivity"

from dbus import Interface
from dbus.service import method, signal
from dbus.gobject_service import ExportedGObject

class RecordTube(ExportedGObject):
	"""The bit that talks over the TUBES!!!"""

	__gsignals__ = {
		'filepart':
			(gobject.SIGNAL_RUN_FIRST, None, [object,object,object,object,object,object,object]),
		'new-recd':
			(gobject.SIGNAL_RUN_FIRST, None, [object])
	}


	def __init__(self, tube, get_buddy, myHashKey, logger):
		super(HelloTube, self).__init__(tube, PATH)
		self.tube = tube
		self._get_buddy = get_buddy  # Converts handle to Buddy object
		self.myHashKey = myHashKey
		self._logger = logger

		self.tube.add_signal_receiver(self._newRecdCb, 'notifyBudsOfNewRecd', IFACE, path=PATH, sender_keyword='sender')


	@signal(dbus_interface=IFACE, signature='ss') #dual s for 2x strings
	def notifyBudsOfNewRecd(self, recorder, recdXml):
		"""Say Hello to whoever else is in the tube."""
		self._logger.debug('Ive taken a new photo!')


	def _newRecdCb(self, borrower, lender, sender=None):
		"""Somebody Hello'd me. I should share with them my pdf.  i hope they like to read bookz!"""
		self._logger.debug("hello_cb from " + borrower + " for " + sender )
		if sender == self.tube.get_unique_name():
			self._logger.debug("sender is my bus name, so ignore my own signal")
			return
		elif (borrower == self.myHashKey):
			self._logger.debug('excuse me?  you are asking me to share this with myself?')
			return
		elif (self.thePdfPath == None):
			self._logger.debug('i dont have the pdf.  there has been a mistake')
			return
		elif (lender != self.myHashKey):
			self._logger.debug('i do indeed have this pdf, but ive only overheard you asking someone else for it')
			return

		#you should not be here if you don't have the pdf.
		self._logger.debug("ya, i have that pdf, thanks for asking!  here it is!")
		self.send_file( self.thePdfPath, borrower, lender )