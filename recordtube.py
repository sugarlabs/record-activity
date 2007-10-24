class RecordTube(ExportedGObject):
	"""The bit that talks over the TUBES!!!"""

	__gsignals__ = {
		'filepart':
			(gobject.SIGNAL_RUN_FIRST, None, [object,object,object,object,object,object,object])
	}


	def __init__(self, tube, get_buddy, thePdfPath, myHashKey, logger ):
		super(HelloTube, self).__init__(tube, PATH)
		self._logger = logger
		self.tube = tube
		self._get_buddy = get_buddy  # Converts handle to Buddy object
		self.myHashKey = myHashKey
		self.thePdfPath = thePdfPath
		if (self.thePdfPath != None):
			self.tube.add_signal_receiver(self.hello_cb, 'Hello', IFACE, path=PATH, sender_keyword='sender')
		else:
			self.add_filepart_handler()


	def setThePdfPath( self, pdfPath ):
		self.thePdfPath = pdfPath
		if (self.thePdfPath != None):
			self.tube.add_signal_receiver(self.hello_cb, 'Hello', IFACE, path=PATH, sender_keyword='sender')
		else:
			self._logger.debug("Damn! We didn't really get the pdf when we asked for it!")


	@signal(dbus_interface=IFACE, signature='ss') #dual s for 2x strings
	def Hello(self, borrower, lender):
		"""Say Hello to whoever else is in the tube."""
		self._logger.debug('I said Hello.  Anyone got a pdf for me to read?')


	def hello_cb(self, borrower, lender, sender=None):
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


	def add_filepart_handler(self):
		"""Hook up signal receiver for SendFilePart."""
		self.SENDFILE_ID = self.tube.add_signal_receiver( self.filepart_cb, 'SendFilePart', IFACE, path=PATH, sender_keyword='sender', byte_arrays=True)


	def remove_filepart_handler(self):
		if (self.SENDFILE_ID == None):
			self._logger.debug("unable to remove signal because we were never listening for it!")
			return
		self.tube.remove_signal_receiver(self.SENDFILE_ID)


	@signal(dbus_interface=IFACE, signature='suuayss')
	def SendFilePart(self, filename, part, numparts, bytes, borrower, lender):
		"""Signal which sends part of a file.

		filename -- string, filename to send
		part -- integer, number of this part.
		numparts -- integer, total number of parts.
		bytes -- the bytes making up this part of the file.

		example: self.SendFilePart(1, 1, '<html></html>')
		"""
		pass


	def send_file(self, filename, borrower, lender ):
		"""Send a file over the D-Bus Tube"""
		size = os.path.getsize(filename)
		f = open(filename)
		chunk_size = 1000
		chunks = size / chunk_size

		if (size%chunk_size != 0):
			chunks += 1

		for chunk in range(chunks):
			bytes = f.read(chunk_size)
			self._logger.debug("sending " + str(chunk+1) + " of " + str(chunks) + " from " + borrower + " to " + lender )
			self.SendFilePart(os.path.basename(filename), chunk+1, chunks, bytes, borrower, lender)

		f.close()


	def filepart_cb(self, filename, part, numparts, bytes, borrower, lender, sender=None):
		"""Receive part of a file.

		filename -- filename sent
		part -- integer, number of this part.
		numparts -- expected number of parts.
		bytes -- the bytes making up this part of the file.
		"""
		if sender == self.tube.get_unique_name():
			# sender is my bus name, so ignore my own signal
			return

		self.emit( "filepart", part, numparts, filename, bytes, borrower, lender, sender)