#Copyright (c) 2007, Media Modifications Ltd.

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

import gtk
import gobject
import os
import shutil
import telepathy
import telepathy.client
import logging
import xml.dom.minidom

from sugar.activity import activity
from sugar.presence import presenceservice
from sugar.presence.tubeconn import TubeConnection
from sugar import util

from model import Model
from ui import UI
from recordtube import RecordTube
from glive import Glive
from gplay import Gplay
from greplay import Greplay
from recorded import Recorded
from constants import Constants
import instance
from instance import Instance
import serialize
import utils

class Record(activity.Activity):

	log = logging.getLogger('record-activity')

	def __init__(self, handle):
		activity.Activity.__init__(self, handle)
		#flags for controlling the writing to the datastore
		self.I_AM_CLOSING = False
		self.I_AM_SAVED = False
		self.JUST_LAUNCHED = True
		self.connect( "notify::active", self._activeCb )
		#wait a moment so that our debug console capture mistakes
		gobject.idle_add( self._initme, None )


	def _initme( self, userdata=None ):
		Instance(self)
		Constants(self)

		#totally tubular
		self.meshTimeoutTime = 10000
		self.recTube = None
		self.connect( "shared", self._sharedCb )

		#the main classes
		self.m = Model( self )
		self.glive = Glive( self )
		self.gplay = Gplay( self )
		self.ui = UI( self )

		#CSCL
		if self._shared_activity:
			#have you joined or shared this activity yourself?
			if self.get_shared():
				self._meshJoinedCb( self )
			else:
				self.connect("joined", self._meshJoinedCb)

		return False


	def read_file(self, file):
		serialize.fillMediaHash(file, self.m.mediaHashs)


	def write_file(self, file):
		self.I_AM_SAVED = False

		dom = serialize.saveMediaHash(self.m.mediaHashs)
		xmlFile = open( file, "w" )
		dom.writexml(xmlFile)
		xmlFile.close()

		allDone = True
		for h in range (0, len(self.m.mediaHashs)):
			mhash = self.m.mediaHashs[h]
			for i in range (0, len(mhash)):
				recd = mhash[i]

				if ( (not recd.savedMedia) or (not recd.savedXml) ):
					allDone = False
					self.__log__.error("somehow we didn't serialize a recd...")

				if (self.I_AM_CLOSING):
					mediaObject = recd.datastoreOb
					if (mediaObject != None):
						recd.datastoreOb = None
						mediaObject.destroy()
						del mediaObject

		self.I_AM_SAVED = True
		if (self.I_AM_SAVED and self.I_AM_CLOSING):
			self.destroy()


	def _activeCb( self, widget, pspec ):
		self.__class__.log.debug('_activeCb')
		if (self.JUST_LAUNCHED):
			self.JUST_LAUNCHED = False
			return

		if (not self.props.active):
			self.__class__.log.debug('_activeCb:stopPipes')
			self.stopPipes()
		else:
			self.__class__.log.debug('_activeCb:restartPipes')
			self.restartPipes()


	def stopPipes(self):
		self.gplay.stop()
		self.ui.doMouseListener( False )

		if (self.m.RECORDING):
			self.m.setUpdating( False )
			self.m.doShutter()
		else:
			self.glive.stop()


	def restartPipes(self):
		if (not self.m.UPDATING):
			self.ui.updateModeChange( )
			self.ui.doMouseListener( True )


	def close( self ):
		self.I_AM_CLOSING = True
		#quicker we look like we're gone, the better
		self.hide()

		self.m.UPDATING = False
		if (self.ui != None):
			self.ui.updateButtonSensitivities( )
			self.ui.doMouseListener( False )
			self.ui.hideLiveWindows( )
			self.ui.hidePlayWindows( )
		if (self.gplay != None):
			self.gplay.stop( )
		if (self.glive != None):
			self.glive.setPipeType( self.glive.PIPETYPE_SUGAR_JHBUILD )
			self.glive.stop( )

		#this calls write_file
		activity.Activity.close( self )


	def destroy( self ):
		if self.I_AM_CLOSING:
			self.hide()

		if self.I_AM_SAVED:
			instance.recreateTmp()
			activity.Activity.destroy( self )


	def _sharedCb( self, activity ):
		self.__class__.log.debug('_sharedCb: My activity was shared')
		self._setup()

		self.__class__.log.debug('_sharedCb: This is my activity: making a tube...')
		id = self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].OfferDBusTube( Constants.SERVICE, {})


	def _meshJoinedCb( self, activity ):
		self.__class__.log.debug('_meshJoinedCb')
		if not self._shared_activity:
			return

		self.__class__.log.debug('_meshJoinedCb: Joined an existing shared activity')
		self._setup()

		self.__class__.log.debug('_meshJoinedCb: This is not my activity: waiting for a tube...')
		self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes( reply_handler=self._list_tubes_reply_cb, error_handler=self._list_tubes_error_cb)


	def _list_tubes_reply_cb(self, tubes):
		for tube_info in tubes:
			self._newTubeCb(*tube_info)


	def _list_tubes_error_cb(self, e):
		self.__class__.log.error('ListTubes() failed: %s', e)


	def _setup(self):
		self.__class__.log.debug("_setup")

		#sets up the tubes...
		if self._shared_activity is None:
			self.__class__.log.error('_setup: Failed to share or join activity')
			return

		pservice = presenceservice.get_instance()
		try:
			name, path = pservice.get_preferred_connection()
			self.conn = telepathy.client.Connection(name, path)
		except:
			self.__class__.log.error('_setup: Failed to get_preferred_connection')

		# Work out what our room is called and whether we have Tubes already
		bus_name, conn_path, channel_paths = self._shared_activity.get_channels()
		room = None
		tubes_chan = None
		text_chan = None
		for channel_path in channel_paths:
			channel = telepathy.client.Channel(bus_name, channel_path)
			htype, handle = channel.GetHandle()
			if htype == telepathy.HANDLE_TYPE_ROOM:
				self.__class__.log.debug('Found our room: it has handle#%d "%s"', handle, self.conn.InspectHandles(htype, [handle])[0])
				room = handle
				ctype = channel.GetChannelType()
				if ctype == telepathy.CHANNEL_TYPE_TUBES:
					self.__class__.log.debug('Found our Tubes channel at %s', channel_path)
					tubes_chan = channel
				elif ctype == telepathy.CHANNEL_TYPE_TEXT:
					self.__class__.log.debug('Found our Text channel at %s', channel_path)
					text_chan = channel

		if room is None:
			self.__class__.log.error("Presence service didn't create a room")
			return
		if text_chan is None:
				self.__class__.log.error("Presence service didn't create a text channel")
				return

		# Make sure we have a Tubes channel - PS doesn't yet provide one
		if tubes_chan is None:
			self.__class__.log.debug("Didn't find our Tubes channel, requesting one...")
			tubes_chan = self.conn.request_channel(telepathy.CHANNEL_TYPE_TUBES, telepathy.HANDLE_TYPE_ROOM, room, True)

		self.tubes_chan = tubes_chan
		self.text_chan = text_chan

		tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal('NewTube', self._newTubeCb)


	def _newTubeCb(self, id, initiator, type, service, params, state):
		self.__class__.log.debug('New tube: ID=%d initator=%d type=%d service=%s params=%r state=%d', id, initiator, type, service, params, state)
		if (type == telepathy.TUBE_TYPE_DBUS and service == Constants.SERVICE):
			if state == telepathy.TUBE_STATE_LOCAL_PENDING:
				self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].AcceptDBusTube(id)
			tube_conn = TubeConnection(self.conn, self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES], id, group_iface=self.text_chan[telepathy.CHANNEL_INTERFACE_GROUP])
			self.recTube = RecordTube(tube_conn)
			self.recTube.connect("new-recd", self._newRecdCb)
			self.recTube.connect("recd-request", self._recdRequestCb)
			self.recTube.connect("recd-bits-arrived", self._recdBitsArrivedCb)
			self.recTube.connect("recd-unavailable", self._recdUnavailableCb)


	def _newRecdCb( self, objectThatSentTheSignal, recorder, xmlString ):
		self.__class__.log.debug('_newRecdCb: ' + str(xmlString))
		dom = None
		try:
			dom = xml.dom.minidom.parseString(xmlString)
		except:
			self.__class__.log.error('Unable to parse xml from the mesh.')
		if (dom == None):
			return

		recd = Recorded()
		recd = serialize.fillRecdFromNode(recd, dom.documentElement)
		if (recd != None):
			self.__class__.log.debug('_newRecdCb: adding new recd thumb')
			recd.buddy = True
			recd.downloadedFromBuddy = False
			self.m.addMeshRecd( recd )
		else:
			self.__class__.log.debug('_newRecdCb: recd is None. Unable to parse XML')


	def requestMeshDownload( self, recd ):
		#this call will get the bits or request the bits if they're not available
		if (recd.buddy and not recd.downloadedFromBuddy):
			if (not recd.meshDownloading):
				if (self.recTube != None):
					self.meshInitRoundRobin(recd)
				return True
		else:
			return False


	def meshInitRoundRobin( self, recd ):
		if (recd.meshDownloading):
			self.__class__.log.debug("meshInitRoundRobin: we are in midst of downloading this file...")
			return

		#start with who took the photo
		self.meshReqRecFromBuddy( recd, recd.recorderHash )


	def meshNextRoundRobinBuddy( self, recd ):
		self.__class__.log.debug('meshNextRoundRobinBuddy')
		if (recd.meshReqCallbackId != 0):
			gobject.source_remove(recd.meshReqCallbackId)
			recd.meshReqCallbackId = 0

		#delete any stub of a partially downloaded file
		filepath = recd.getMediaFilepath()
		if (filepath != None):
			if (os.path.exists(filepath)):
				os.remove( filepath )

		askingAnotherBud = False
		buds = self._shared_activity.get_joined_buddies();
		for i in range (0, len(buds)):
			nextBudObj = buds[i]
			nextBud = util._sha_data(nextBudObj.props.key)
			nextBud = util.printable_hash(nextBud)
			if (recd.triedMeshBuddies.count(nextBud) > 0):
				self.__class__.log.debug('meshNextRoundRobinBuddy: weve already tried asking this buddy for this photo')
			else:
				self.__class__.log.debug('meshNextRoundRobinBuddy: ask next buddy')
				self.meshReqRecFromBuddy(recd, nextBud)
				askingAnotherBud = True

		if (not askingAnotherBud):
			self.__class__.log.debug('weve tried all buddies here, and no one has this recd')
			#todo: flag this recd, so that when new buddies show up, we can ask them if they've got it (if they are returning).
			#todo: or clear triedMeshBuddies and let them try again.


	def meshReqRecFromBuddy( self, recd, fromWho ):
		self.__class__.log.debug('meshReqRecFromBuddy')
		recd.triedMeshBuddies.append( fromWho )
		recd.meshDownloadingFrom = fromWho
		recd.meshDownloadingProgress = False
		recd.meshDownloading = True
		recd.meshReqCallbackId = gobject.timeout_add(self.meshTimeoutTime, self._meshCheckOnRecdRequest, recd)
		self.recTube.requestRecdBits( Instance.keyHashPrintable, fromWho, recd.mediaMd5 )

		#self.ca.ui.updateDownloadFrom( fromWho ) #todo...


	def _meshCheckOnRecdRequest( self, recdRequesting ):
		self.__class__.log.debug('_meshCheckOnRecdRequest')

		if (recdRequesting.downloadedFromBuddy):
			self.__class__.log.debug('_meshCheckOnRecdRequest: recdRequesting.downloadedFromBuddy')
			if (recdRequesting.meshReqCallbackId != 0):
				gobject.source_remove(recdRequesting.meshReqCallbackId)
				recdRequesting.meshReqCallbackId = 0
			return False
		if (recdRequesting.deleted):
			self.__class__.log.debug('_meshCheckOnRecdRequest: recdRequesting.deleted')
			if (recdRequesting.meshReqCallbackId != 0):
				gobject.source_remove(recdRequesting.meshReqCallbackId)
				recdRequesting.meshReqCallbackId = 0
			return False
		if (recdRequesting.meshDownloadingProgress):
			self.__class__.log.debug('_meshCheckOnRecdRequest: recdRequesting.meshDownloadingProgress')
			#we've received some bits since last we checked, so keep waiting...  they'll all get here eventually!
			recdRequesting.meshDownloadingProgress = False
			return True
		else:
			self.__class__.log.debug('_meshCheckOnRecdRequest: ! recdRequesting.meshDownloadingProgress')
			#that buddy we asked info from isn't responding; next buddy!
			self.meshNextRoundRobinBuddy( recdRequesting )
			return False


	def _recdRequestCb( self, objectThatSentTheSignal, whoWantsIt, md5sumOfIt ):
		#if we are here, it is because someone has been told we have what they want.
		#we need to send them that thing, whatever that thing is
		recd = self.m.getRecdByMd5( md5sumOfIt )
		if (recd == None):
			self.__class__.log.debug('_recdRequestCb: we dont have the recd they asked for')
			self.recTube.unavailableRecd(md5sumOfIt, Instance.keyHashPrintable, whoWantsIt)
			return
		if (recd.deleted):
			self.__class__.log.debug('_recdRequestCb: we have the recd, but it has been deleted, so we wont share')
			self.recTube.unavailableRecd(md5sumOfIt, Instance.keyHashPrintable, whoWantsIt)
			return
		if (recd.buddy and not recd.downloadedFromBuddy):
			self.__class__.log.debug('_recdRequestCb: we have an incomplete recd, so we wont share')
			self.recTube.unavailableRecd(md5sumOfIt, Instance.keyHashPrintable, whoWantsIt)
			return

		recd.meshUploading = True
		filepath = recd.getMediaFilepath()
		sent = self.recTube.broadcastRecd(recd.mediaMd5, filepath, whoWantsIt)
		recd.meshUploading = False
		#if you were deleted while uploading, now throw away those bits now
		if (recd.deleted):
			recd.doDeleteRecorded(recd)


	def _recdBitsArrivedCb( self, objectThatSentTheSignal, md5sumOfIt, part, numparts, bytes, fromWho ):
		#self.__class__.log.debug('_recdBitsArrivedCb: ' + str(part) + "/" + str(numparts))
		recd = self.m.getRecdByMd5( md5sumOfIt )
		if (recd == None):
			self.__class__.log.debug('_recdBitsArrivedCb: thx 4 yr bits, but we dont even have that photo')
			return
		if (recd.deleted):
			self.__class__.log.debug('_recdBitsArrivedCb: thx 4 yr bits, but we deleted that photo')
			return
		if (recd.downloadedFromBuddy):
			self.__class__.log.debug('_recdBitsArrivedCb: weve already downloadedFromBuddy')
			return
		if (not recd.buddy):
			self.__class__.log.debug('_recdBitsArrivedCb: uh, we took this photo, so dont need your bits')
			return
		if (recd.meshDownloadingFrom != fromWho):
			self.__class__.log.debug('_recdBitsArrivedCb: we dont want this guys bits, were getting bits from someoneelse')
			return

		#update that we've heard back about this, reset the timeout
		gobject.source_remove(recd.meshReqCallbackId)
		recd.meshReqCallbackId = gobject.timeout_add(self.meshTimeoutTime, self._meshCheckOnRecdRequest, recd)

		#update the progress bar
		recd.meshDownlodingPercent = (part+0.0)/(numparts+0.0)
		f = open(recd.getMediaFilepath(), 'a+').write(bytes)

		if part == numparts:
			self.__class__.log.debug('Finished receiving %s' % recd.title)
			gobject.source_remove( recd.meshReqCallbackId )
			recd.meshReqCallbackId = 0
			recd.meshDownloading = False
			recd.meshDownlodingPercent = 1.0
			recd.downloadedFromBuddy = True
			if (recd.type == Constants.TYPE_AUDIO):
				self.__class__.log.debug("_recdBitsArrivedCb:TYPE_AUDIO")
				greplay = Greplay()
				greplay.connect("coverart-found", self._getAlbumArtCb, None )
				filepath = recd.getMediaFilelocation(False)
				greplay.findAlbumArt(filepath)
			else:
				self.ui.showMeshRecd( recd )
		elif part > numparts:
			self.__class__.log.error('More parts than required have arrived')


	def _getAlbumArtCb( self, pixbuf, recd ):
		self.__class__.log.debug("_getAlbumArtCb:" + str(pixbuf) + "," + str(recd))

		if (pixbuf != None):
			imagePath = os.path.join(Instance.tmpPath, "audioPicture.png")
			imagePath = utils.getUniqueFilepath( imagePath, 0 )
			pixbuf.save( imagePath, "png", {} )
			recd.audioImageFilename = os.path.basename(imagePath)

		self.ui.showMeshRecd( recd )
		return False


	def _recdUnavailableCb( self, objectThatSentTheSignal, md5sumOfIt, whoDoesntHaveIt ):
		self.__class__.log.debug('_recdUnavailableCb: sux, we want to see that photo')
		recd = self.m.getRecdByMd5( md5sumOfIt )
		if (recd == None):
			self.__class__.log.debug('_recdUnavailableCb: actually, we dont even know about that one..')
			return
		if (recd.deleted):
			self.__class__.log.debug('_recdUnavailableCb: actually, since we asked, we deleted.')
			return
		if (not recd.buddy):
			self.__class__.log.debug('_recdUnavailableCb: uh, odd, we took that photo and have it already.')
			return
		if (recd.downloadedFromBuddy):
			self.__class__.log.debug('_recdUnavailableCb: we already downloaded it...  you might have been slow responding.')
			return
		if (recd.meshDownloadingFrom != whoDoesntHaveIt):
			self.__class__.log.debug('_recdUnavailableCb: we arent asking you for a copy now.  slow response, pbly.')
			return

		self.meshNextRoundRobinBuddy( recd )
