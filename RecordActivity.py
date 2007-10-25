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
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parse
from gettext import gettext as _

from sugar import util
from sugar.activity import activity
from sugar import profile
from sugar.datastore import datastore
from sugar.presence import presenceservice
from sugar.presence.tubeconn import TubeConnection
SERVICE = "org.laptop.RecordActivity"

from model import Model
from ui import UI
from recordtube import RecordTube
from glive import Glive
from gplay import Gplay


class RecordActivity(activity.Activity):

	def __init__(self, handle):
		activity.Activity.__init__(self, handle)
		self.JUST_LAUNCHED = True
		self._logger = logging.getLogger('record-activity')
		self.connect( "notify::active", self._activeCb )
		#wait a moment so that our debug console capture mistakes
		gobject.idle_add( self._initme, None )


	def _initme( self, userdata=None ):
		self.istrActivityName = _('Record')
		self.istrPhoto = _('Photo')
		self.istrVideo = _('Video')
		self.istrAudio = _('Audio')
		self.istrTimelapse = _('Time Lapse')
		self.istrAnimation = _('Animation')
		self.istrPanorama = _('Panorama')
		#TRANS: photo by photographer, e.g., "Sunset by Mary"
		self.istrBy = _("%(1)s by %(2)s")
		self.istrTitle = _('Title:')
		self.istrRecorder = _('Recorder:')
		self.istrDate = _('Date:')
		self.istrTags = _('Tags:')
		self.istrSaving = _('Saving')
		self.istrFinishedRecording = _("Finished recording")
		self.istrMinutesSecondsRemaining = _("%(1)s minutes, %(1)s seconds remaining")
		self.istrSecondsRemaining = _("%(1)s seconds remaining")
		self.istrRemove = _("Remove")
		self.istrStoppedRecording = _("Stopped recording")
		self.istrCopyToClipboard = _("Copy to clipboard")
		self.istrTimer = _("Timer:")
		self.istrDuration = _("Duration:")
		self.istrNow = _("Immediate")
		self.istrSeconds = _("%(1)s seconds")
		self.istrMinutes = _("%(1)s minutes")
		self.istrPlay = _("Play")
		self.istrPause = _("Pause")
		self.istrAddFrame = _("Add frame")
		self.istrRemoveFrame = _("Remove frame")
		self.istrFramesPerSecond = _("%(1)s frames per second")
		self.istrQuality = _("Quality:")
		self.istrBestQuality = _("Best quality")
		self.istrHighQuality = _("High quality")
		self.istrLowQuality = _("Low quality")
		self.istrLargeFile = _("Large file")
		self.istrSmallFile = _("Small file")
		self.istrSilent = _("Silent")
		self.istrRotate = _("Rotate")
		self.istrClickToTakePicture = _("Click to take picture")
		self.istrClickToAddPicture = _("Click to add picture")
		#TRANS: Downloading Photo from Mary
		self.istrDownloadingFrom = _("Downloading %(1)s from %(2)s")
		#TRANS: Cannot download this Photo
		self.istrCannotDownload = _("Cannot download this %(1)s")

		self.recdTitle = "title"
		self.recdTime = "time"
		self.recdPhotographer = "photographer"
		self.recdColorStroke = "colorStroke"
		self.recdColorFill = "colorFill"
		self.recdHashKey = "hashKey"
		self.recdBuddy = "buddy"
		self.recdMediaMd5 = "mediaMd5"
		self.recdThumbMd5 = "thumbMd5"
		self.recdMediaBytes = "mediaBytes"
		self.recdThumbBytes = "thumbBytes"
		self.recdDatastoreId = "datastoreId"
		self.recdAudioImage = "audioImage"
		self.recdAlbum = "album"
		self.recdType = "type"
		self.recdBuddyThumb = "buddyThumb"
		self.recdRecd = "recd"
		self.recdThumb = "thumb"
		self.keyName = "name"
		self.keyMime = "mime"
		self.keyExt = "ext"
		self.keyIstr = "istr"

		self.set_title( self.istrActivityName )

		#flags for controlling the writing to the datastore
		self.I_AM_CLOSING = False
		self.I_AM_SAVED = False

		#get the Presence Service
		self.recTube = None  # Shared session
		self.connect( "shared", self._sharedCb )
		self.pservice = presenceservice.get_instance()
		name, path = self.pservice.get_preferred_connection()
		self.tp_conn_name = name
		self.tp_conn_path = path
		self.conn = telepathy.client.Connection(name, path)

		#whoami?
		key = profile.get_pubkey()
		keyHash = util._sha_data(key)
		self.hashedKey = util.printable_hash(keyHash)
		self.instanceId = self._activity_id
		self.nickName = profile.get_nick_name()

		#paths
		self.basePath = activity.get_bundle_path()
		self.gfxPath = os.path.join(self.basePath, "gfx")
		self.recreateTemp()

		#the main classes
		self.glive = Glive( self )
		self.gplay = Gplay( self )
		self.m = Model( self )
		self.ui = UI( self )

		#CSCL
		if self._shared_activity:
			#have you joined or shared this activity yourself?
			if self.get_shared():
				self._meshJoinedCb()
			else:
				self.connect("joined", self._meshJoinedCb)

		return False


	def read_file(self, file):
		self.m.fillMediaHash(file)


	def write_file(self, file):
		self.I_AM_SAVED = False
		SAVING_AT_LEAST_ONE = False

		xmlFile = open( file, "w" )
		impl = getDOMImplementation()
		album = impl.createDocument(None, self.recdAlbum, None)
		root = album.documentElement

		atLeastOne = False

		#flag everything for saving...
		for type,value in self.m.mediaTypes.items():
			typeName = value[self.keyName]
			hash = self.m.mediaHashs[type]
			for i in range (0, len(hash)):
				recd = hash[i]
				recd.savedXml = False
				recd.savedMedia = False
				atLeastOne = True

		#and if there is anything to save, save it
		if (atLeastOne):
			for type,value in self.m.mediaTypes.items():
				typeName = value[self.keyName]
				hash = self.m.mediaHashs[type]

				for i in range (0, len(hash)):
					recd = hash[i]
					mediaEl = album.createElement( typeName )
					root.appendChild( mediaEl )
					self.saveIt( xmlFile, mediaEl, recd )

		#otherwise, clear it out
		if (not atLeastOne):
			self.checkDestroy( album, xmlFile )


	def getRecdXml( self, recd ):
		impl = getDOMImplementation()
		recdXml = impl.createDocument(None, self.recdRecd, None)
		root = recdXml.documentElement
		self.addRecdXmlAttrs( root, recd )

		pixbuf = recd.getThumbPixbuf( )
		thumb = str( self._get_base64_pixbuf_data(pixbuf) )
		root.setAttribute(self.recdThumb, thumb )

		return recdXml


	def addRecdXmlAttrs( self, el, recd ):
		el.setAttribute(self.recdType, str(recd.type))

		if (recd.type == self.m.TYPE_AUDIO):
			aiPixbuf = recd.getAudioImagePixbuf( )
			aiPixbufString = str( self._get_base64_pixbuf_data(aiPixbuf) )
			el.setAttribute(self.recdAudioImage, aiPixbufString)

		el.setAttribute(self.recdTitle, recd.title)
		el.setAttribute(self.recdTime, str(recd.time))
		el.setAttribute(self.recdPhotographer, recd.photographer)
		el.setAttribute(self.recdColorStroke, str(recd.colorStroke.hex) )
		el.setAttribute(self.recdColorFill, str(recd.colorFill.hex) )
		el.setAttribute(self.recdHashKey, str(recd.hashKey))
		el.setAttribute(self.recdBuddy, str(recd.buddy))
		el.setAttribute(self.recdMediaMd5, str(recd.mediaMd5))
		el.setAttribute(self.recdThumbMd5, str(recd.thumbMd5))
		el.setAttribute(self.recdMediaBytes, str(recd.mediaBytes))
		el.setAttribute(self.recdThumbBytes, str(recd.thumbBytes))
		if (recd.datastoreId != None):
			el.setAttribute(self.recdDatastoreId, str(recd.datastoreId))


	def saveIt( self, xmlFile, el, recd ):
		#presume we don't need to serialize...
		needToDatastoreMedia = False

		if ( (recd.buddy == True) and (recd.datastoreId == None) and (not recd.downloadedFromBuddy) ):
			pixbuf = recd.getThumbPixbuf( )
			buddyThumb = str( self._get_base64_pixbuf_data(pixbuf) )
			el.setAttribute(self.recdBuddyThumb, buddyThumb )
			recd.savedMedia = True
			self.saveXml( xmlFile, el, recd )
		else:
			recd.savedMedia = False
			self.saveMedia( xmlFile, el, recd )


	def saveXml( self, xmlFile, el, recd ):
		self.addRecdXmlAttrs( el, recd )

		recd.savedXml = True
		self.checkDestroy( el.ownerDocument, xmlFile )


	def saveMedia( self, xmlFile, el, recd ):
		#note that we update the recds that go through here to how they would
		#look on a fresh load from file since this won't just happen on close()

		if (recd.datastoreId != None):
			#already saved to the datastore, don't need to re-rewrite the file since the mediums are immutable
			#However, they might have changed the name of the file
			if (recd.titleChange):
				self.m.loadMediaFromDatastore( recd )
				if (recd.datastoreOb.metadata['title'] != recd.title):
					recd.datastoreOb.metadata['title'] = recd.title
					datastore.write(recd.datastoreOb)

				#reset for the next title change if not closing...
				recd.titleChange = False
				#save the title to the xml
				recd.savedMedia = True

				self.saveXml( xmlFile, el, recd )
			else:
				recd.savedMedia = True
				self.saveXml( xmlFile, el, recd )

		else:
			#this will remove the media from being accessed on the local disk since it puts it away into cold storage
			#therefore this is only called when write_file is called by the activity superclass
			mediaObject = datastore.create()
			#todo: what other metadata to set?
			mediaObject.metadata['title'] = recd.title
			#jobject.metadata['keep'] = '0'
			#jobject.metadata['buddies'] = ''

			pixbuf = recd.getThumbPixbuf()
			thumbData = self._get_base64_pixbuf_data(pixbuf)
			mediaObject.metadata['preview'] = thumbData

			colors = str(recd.colorStroke.hex) + "," + str(recd.colorFill.hex)
			mediaObject.metadata['icon-color'] = colors

			mtype = self.m.mediaTypes[recd.type]
			mmime = mtype[self.keyMime]
			mediaObject.metadata['mime_type'] = mmime

			mediaObject.metadata['activity'] = self._activity_id

			#todo: make sure the file is still available before you ever get to this point...
			mediaFile = recd.getMediaFilepath(False)
			mediaObject.file_path = mediaFile
			mediaObject.transfer_ownership = True

			datastore.write( mediaObject )
			self.doPostMediaSave( xmlFile, el, recd, mediaObject )


	def _get_base64_pixbuf_data(self, pixbuf):
		data = [""]
		pixbuf.save_to_callback(self._save_data_to_buffer_cb, "png", {}, data)
		import base64
		return base64.b64encode(str(data[0]))


	def _save_data_to_buffer_cb(self, buf, data):
		data[0] += buf
		return True


	def _mediaSaveCb( self, recd ):
		self.doPostMediaSave( recd )


	def _mediaSaveErrorCb( self, recd ):
		self.doPostMediaSave( recd )


	def doPostMediaSave( self, xmlFile, el, recd, mediaObject ):
		recd.datastoreId = mediaObject.object_id
		recd.mediaFilename = None
		recd.thumbFilename = None

		self.saveXml( xmlFile, el, recd )

		if (self.I_AM_CLOSING):
			mediaObject.destroy()
			del mediaObject

		recd.savedMedia = True
		self.checkDestroy( el.ownerDocument, xmlFile )


	def _activeCb( self, widget, pspec ):
		if (self.JUST_LAUNCHED):
			self.JUST_LAUNCHED = False
			return

		if (not self.props.active):
			self.stopPipes()
		elif (self.props.active):
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


	def recreateTemp( self ):
		#todo: rainbow

		# #4422
#		self.tempPath = os.path.join("tmp", "Record_"+str(self.instanceId))
		self.tempPath = os.path.join( self.get_activity_root(), "tmp" )
		if (os.path.exists(self.tempPath)):
			shutil.rmtree( self.tempPath )
		os.makedirs(self.tempPath)


	def close( self ):
		self.I_AM_CLOSING = True
		#quicker we look like we're gone, the better
		self.hide()

		self.m.UPDATING = False
		self.ui.updateButtonSensitivities( )
		self.ui.doMouseListener( False )
		self.ui.hideLiveWindows( )
		self.ui.hidePlayWindows( )
		self.gplay.stop( )
		self.glive.setPipeType( self.glive.PIPETYPE_SUGAR_JHBUILD )
		self.glive.stop( )

		#this calls write_file
		activity.Activity.close( self )


	def checkDestroy( self, album, xmlFile ):
		allDone = True

		for h in range (0, len(self.m.mediaHashs)):
			mhash = self.m.mediaHashs[h]
			for i in range (0, len(mhash)):
				recd = mhash[i]
				if ( (not recd.savedMedia) or (not recd.savedXml) ):
					allDone = False

		if (allDone):
			album.writexml(xmlFile)
			xmlFile.close()
			self.I_AM_SAVED = True

		#todo: reset all the saved flags or just let them take care of themselves on the next save?
		if (self.I_AM_SAVED and self.I_AM_CLOSING):
			self.destroy()


	def destroy( self ):
		if self.I_AM_CLOSING:
			self.hide()

		if self.I_AM_SAVED:
			self.recreateTemp()
			activity.Activity.destroy( self )


	def _sharedCb( self, activity ):
		self._logger.debug('My activity was shared')
		self._setup()

		self._logger.debug('This is my activity: making a tube...')
		id = self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].OfferDBusTube( SERVICE, {})


	def _meshJoinedCb( self, activity ):
		if not self._shared_activity:
			return

		self._logger.debug('Joined an existing shared activity')
		self._setup()

		self._logger.debug('This is not my activity: waiting for a tube...')
		self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes( reply_handler=self._list_tubes_reply_cb, error_handler=self._list_tubes_error_cb)


	def _list_tubes_reply_cb(self, tubes):
		for tube_info in tubes:
			self._new_tube_cb(*tube_info)


	def _list_tubes_error_cb(self, e):
		self._logger.error('ListTubes() failed: %s', e)


	def _setup(self):
		#sets up the tubes...
		if self._shared_activity is None:
			self._logger.error('Failed to share or join activity')
			return

		# Work out what our room is called and whether we have Tubes already
		bus_name, conn_path, channel_paths = self._shared_activity.get_channels()
		room = None
		tubes_chan = None
		text_chan = None
		for channel_path in channel_paths:
			channel = telepathy.client.Channel(bus_name, channel_path)
			htype, handle = channel.GetHandle()
			if htype == telepathy.HANDLE_TYPE_ROOM:
				self._logger.debug('Found our room: it has handle#%d "%s"', handle, self.conn.InspectHandles(htype, [handle])[0])
				room = handle
				ctype = channel.GetChannelType()
				if ctype == telepathy.CHANNEL_TYPE_TUBES:
					self._logger.debug('Found our Tubes channel at %s', channel_path)
					tubes_chan = channel
				elif ctype == telepathy.CHANNEL_TYPE_TEXT:
					self._logger.debug('Found our Text channel at %s', channel_path)
					text_chan = channel

		if room is None:
			self._logger.error("Presence service didn't create a room")
			return
		if text_chan is None:
				self._logger.error("Presence service didn't create a text channel")
				return

		# Make sure we have a Tubes channel - PS doesn't yet provide one
		if tubes_chan is None:
			self._logger.debug("Didn't find our Tubes channel, requesting one...")
			tubes_chan = self.conn.request_channel(telepathy.CHANNEL_TYPE_TUBES, telepathy.HANDLE_TYPE_ROOM, room, True)

		self.tubes_chan = tubes_chan
		self.text_chan = text_chan

		tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal('NewTube', self._new_tube_cb)


	def _new_tube_cb(self, id, initiator, type, service, params, state):
		self._logger.debug('New tube: ID=%d initator=%d type=%d service=%s params=%r state=%d', id, initiator, type, service, params, state)
		if (type == telepathy.TUBE_TYPE_DBUS and service == SERVICE):
			if state == telepathy.TUBE_STATE_LOCAL_PENDING:
				self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].AcceptDBusTube(id)
			tube_conn = TubeConnection(self.conn, self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES], id, group_iface=self.text_chan[telepathy.CHANNEL_INTERFACE_GROUP])
			self.recTube = RecordTube(tube_conn, self._get_buddy, self.hashedKey, self._logger)
			self.recTube.connect("new-recd", self._newRecdCb)


	def _get_buddy(self, cs_handle):
		"""Get a Buddy from a channel specific handle."""
		self._logger.debug('Trying to find owner of handle %u...', cs_handle)
		group = self.text_chan[telepathy.CHANNEL_INTERFACE_GROUP]
		my_csh = group.GetSelfHandle()
		self._logger.debug('My handle in that group is %u', my_csh)
		if my_csh == cs_handle:
			handle = self.conn.GetSelfHandle()
			self._logger.debug('CS handle %u belongs to me, %u', cs_handle, handle)
		elif group.GetGroupFlags() & telepathy.CHANNEL_GROUP_FLAG_CHANNEL_SPECIFIC_HANDLES:
			handle = group.GetHandleOwners([cs_handle])[0]
			self._logger.debug('CS handle %u belongs to %u', cs_handle, handle)
		else:
			handle = cs_handle
			logger.debug('non-CS handle %u belongs to itself', handle)
			# XXX: deal with failure to get the handle owner
			assert handle != 0
		return self.pservice.get_buddy_by_telepathy_handle(self.tp_conn_name, self.tp_conn_path, handle)


	def _newRecdCb( self, recorder, xmlString ):
		print( "xmlString:", xmlString, "from", recorder )
