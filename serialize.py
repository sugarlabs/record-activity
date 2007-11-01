import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parse
import cStringIO

from sugar.datastore import datastore

from constants import Constants
import utils

def fillMediaHash( index, mediaTypes, mediaHashs ):
	doc = None
	if (os.path.exists(index)):
		try:
			doc = parse( os.path.abspath(index) )
		except:
			doc = None
	if (doc == None):
		return

	for key,value in mediaTypes.items():
		recdElements = doc.documentElement.getElementsByTagName(value[Constants.keyName])
		for el in recdElements:
			loadMediaIntoHash( el, mediaHashs[key] )


def _loadMediaIntoHash( el, hash ):
	addToHash = True
	recd = Recorded( self.ca )
	recd = serialize.fillRecdFromNode( recd, el )
	if (recd.datastoreId != None):
		#quickly check: if you have a datastoreId that the file hasn't been deleted,
		#cause if you do, we need to flag your removal
		#2904 trac
		recd.datastoreOb = serialize.getMediaFromDatastore( recd )
		if (recd.datastoreOb == None):
			addToHash = False
		else:
			#name might have been changed in the journal, so reflect that here
			if (recd.title != recd.datastoreOb.metadata['title']):
				recd.setTitle(recd.datastoreOb.metadata['title'])
			if (recd.buddy):
				recd.downloadedFromBuddy = True

		recd.datastoreOb == None

	if (addToHash):
		hash.append( recd )


def getMediaFromDatastore( recd ):
	if (recd.datastoreId == None):
		print("RecordActivity error -- request for recd from datastore with no datastoreId")
		return None

	if (recd.datastoreOb != None):
		#already have the object
		return recd.datastoreOb

	mediaObject = None
	try:
		mediaObject = datastore.get( recd.datastoreId )
	finally:
		if (mediaObject == None):
				print("RecordActivity error -- request for recd from datastore returning None")
				return None

	return mediaObject


def removeMediaFromDatastore( recd ):
	#before this method is called, the media are removed from the file
	if (recd.datastoreId == None):
		return
	if (recd.datastoreOb == None):
		return

	try:
		recd.datastoreOb.destroy()
		datastore.delete( recd.datastoreId )

		del recd.datastoreId
		recd.datastoreId = None

		del recd.datastoreOb
		recd.datastoreOb = None

	finally:
		#todo: add error message here
		pass


def fillRecdFromNode( recd, el ):
	if (el.getAttributeNode(Constants.recdType) == None):
		return None
	else:
		try:
			typeInt = int(el.getAttribute(Constants.recdType))
			recd.type = typeInt
		except:
			return None

	if (el.getAttributeNode(Constants.recdTitle) == None):
		return None
	else:
		recd.title = el.getAttribute(Constants.recdTitle)

	if (el.getAttributeNode(Constants.recdTime) == None):
		return None
	else:
		try:
			timeInt = int(el.getAttribute(Constants.recdTime))
			recd.time = timeInt
		except:
			return None

	if (el.getAttributeNode(Constants.recdRecorderName) == None):
		return None
	else:
		recd.recorderName = el.getAttribute(Constants.recdRecorderName)

	if (el.getAttributeNode(Constants.recdRecorderHash) == None):
		return None
	else:
		recd.recorderHash = el.getAttribute(Constants.recdRecorderHash)

	if (el.getAttributeNode(Constants.recdColorStroke) == None):
		return None
	else:
		try:
			colorStrokeHex = el.getAttribute(Constants.recdColorStroke)
			colorStroke = Color()
			colorStroke.init_hex( colorStrokeHex )
			recd.colorStroke = colorStroke
		except:
			return None

	if (el.getAttributeNode(Constants.recdColorFill) == None):
		return None
	else:
		try:
			colorFillHex = el.getAttribute(Constants.recdColorFill)
			colorFill = Color()
			colorFill.init_hex( colorFillHex )
			recd.colorFill = colorFill
		except:
			return None

	if (el.getAttributeNode(Constants.recdBuddy) == None):
		return None
	else:
		recd.buddy = (el.getAttribute(Constants.recdBuddy) == "True")

	if (el.getAttributeNode(Constants.recdMediaMd5) == None):
		return None
	else:
		recd.mediaMd5 = el.getAttribute(Constants.recdMediaMd5)

	if (el.getAttributeNode(Constants.recdThumbMd5) == None):
		return None
	else:
		recd.thumbMd5 = el.getAttribute(Constants.recdThumbMd5)

	if (el.getAttributeNode(Constants.recdMediaBytes) == None):
		return None
	else:
		recd.mediaBytes = el.getAttribute(Constants.recdMediaBytes)

	if (el.getAttributeNode(Constants.recdThumbBytes) == None):
		return None
	else:
		recd.thumbBytes = el.getAttribute(Constants.recdThumbBytes)

	bt = el.getAttributeNode(Constants.recdBuddyThumb)
	if (not bt == None):
		try:
			thumbPath = os.path.join(Instance.tmpPath, "datastoreThumb.jpg")
			thumbPath = utils.getUniqueFilepath( thumbPath, 0 )
			thumbImg = recd.pixbufFromString( bt.nodeValue )
			thumbImg.save(thumbPath, "jpeg", {"quality":"85"} )
			recd.thumbFilename = os.path.basename(thumbPath)
		except:
			return None

	datastoreNode = el.getAttributeNode(Constants.recdDatastoreId)
	if (datastoreNode != None):
		recd.datastoreId = datastoreNode.nodeValue

	return recd


def getRecdXmlString( recd ):
	impl = getDOMImplementation()
	recdXml = impl.createDocument(None, Constants.recdRecd, None)
	root = recdXml.documentElement
	addRecdXmlAttrs( root, recd, True )

	pixbuf = recd.getThumbPixbuf( )
	thumb = str( utils.getStringFromPixbuf(pixbuf) )
	root.setAttribute(self.recdBuddyThumb, thumb )

	writer = cStringIO.StringIO()
	recdXml.writexml(writer)
	return writer.getvalue()


def addRecdXmlAttrs( el, recd, forMeshTransmit ):
	el.setAttribute(self.recdType, str(recd.type))

	if ((recd.type == Constants.TYPE_AUDIO) and (not forMeshTransmit)):
		aiPixbuf = recd.getAudioImagePixbuf( )
		aiPixbufString = str( utils.getStringFromPixbuf(aiPixbuf) )
		el.setAttribute(self.recdAudioImage, aiPixbufString)

	if ((recd.datastoreId != None) and (not forMeshTransmit)):
		el.setAttribute(Constants.recdDatastoreId, str(recd.datastoreId))

	el.setAttribute(Constants.recdTitle, recd.title)
	el.setAttribute(Constants.recdTime, str(recd.time))
	el.setAttribute(Constants.recdRecorderName, recd.recorderName)
	el.setAttribute(Constants.recdRecorderHash, str(recd.recorderHash) )
	el.setAttribute(Constants.recdColorStroke, str(recd.colorStroke.hex) )
	el.setAttribute(Constants.recdColorFill, str(recd.colorFill.hex) )
	el.setAttribute(Constants.recdBuddy, str(recd.buddy))
	el.setAttribute(Constants.recdMediaMd5, str(recd.mediaMd5))
	el.setAttribute(Constants.recdThumbMd5, str(recd.thumbMd5))
	el.setAttribute(Constants.recdMediaBytes, str(recd.mediaBytes))
	el.setAttribute(Constants.recdThumbBytes, str(recd.thumbBytes))


def saveMediaHash( mediaTypes, mediaHashs ):
	impl = getDOMImplementation()
	album = impl.createDocument(None, Constants.recdAlbum, None)
	root = album.documentElement

	#flag everything for saving...
	atLeastOne = False
	for type,value in mediaTypes.items():
		typeName = value[Constants.keyName]
		hash = mediaHashs[type]
		for i in range (0, len(hash)):
			recd = hash[i]
			recd.savedXml = False
			recd.savedMedia = False
			atLeastOne = True

	#and if there is anything to save, save it
	if (atLeastOne):
		for type,value in mediaTypes.items():
			typeName = value[Constants.keyName]
			hash = mediaHashs[type]

			for i in range (0, len(hash)):
				recd = hash[i]
				mediaEl = album.createElement( typeName )
				root.appendChild( mediaEl )

				mtype = mediaTypes[recd.type]
				recd.mime = mtype[Constants.keyMime]
				_saveMedia( mediaEl, recd )

	return album


def _saveMedia( el, recd ):
	if ( (recd.buddy == True) and (recd.datastoreId == None) and (not recd.downloadedFromBuddy) ):
		pixbuf = recd.getThumbPixbuf( )
		buddyThumb = str( utils.getStringFromPixbuf(pixbuf) )
		el.setAttribute(Constants.recdBuddyThumb, buddyThumb )
		recd.savedMedia = True
		_saveXml( el, recd )
	else:
		recd.savedMedia = False
		_saveMediaToDatastore( el, recd )


def _saveXml( el, recd ):
	addRecdXmlAttrs( el, recd, False )
	recd.savedXml = True


def _saveMediaToDatastore( el, recd ):
	#note that we update the recds that go through here to how they would
	#look on a fresh load from file since this won't just happen on close()

	if (recd.datastoreId != None):
		#already saved to the datastore, don't need to re-rewrite the file since the mediums are immutable
		#However, they might have changed the name of the file
		if (recd.titleChange):
			recd.datastoreOb = getMediaFromDatastore( recd )
			if (recd.datastoreOb.metadata['title'] != recd.title):
				recd.datastoreOb.metadata['title'] = recd.title
				datastore.write(recd.datastoreOb)

			#reset for the next title change if not closing...
			recd.titleChange = False
			#save the title to the xml
			recd.savedMedia = True
			_saveXml( el, recd )
		else:
			recd.savedMedia = True
			_saveXml( el, recd )

	else:
		#this will remove the media from being accessed on the local disk since it puts it away into cold storage
		#therefore this is only called when write_file is called by the activity superclass
		mediaObject = datastore.create()
		mediaObject.metadata['title'] = recd.title

		pixbuf = recd.getThumbPixbuf()
		thumbData = utils.getStringFromPixbuf(pixbuf)
		mediaObject.metadata['preview'] = thumbData

		colors = str(recd.colorStroke.hex) + "," + str(recd.colorFill.hex)
		mediaObject.metadata['icon-color'] = colors

		mediaObject.metadata['mime_type'] = recd.mime

		mediaObject.metadata['activity'] = Constants.activityId

		mediaFile = recd.getMediaFilepath(False)
		mediaObject.file_path = mediaFile
		mediaObject.transfer_ownership = True

		datastore.write( mediaObject )

		recd.datastoreId = mediaObject.object_id
		recd.mediaFilename = None
		recd.thumbFilename = None
		recd.savedMedia = True

		_saveXml( el, recd )