import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parse
import cStringIO
import os
import gtk

from sugar.datastore import datastore

from constants import Constants
from instance import Instance
from color import Color
import record
import utils
import recorded

def fillMediaHash( index, mediaHashs ):
	doc = None
	if (os.path.exists(index)):
		try:
			doc = parse( os.path.abspath(index) )
		except:
			doc = None
	if (doc == None):
		return

	for key,value in Constants.mediaTypes.items():
		recdElements = doc.documentElement.getElementsByTagName(value[Constants.keyName])
		for el in recdElements:
			_loadMediaIntoHash( el, mediaHashs[key] )


def _loadMediaIntoHash( el, hash ):
	addToHash = True
	recd = record.Recorded()
	recd = fillRecdFromNode(recd, el)
	if (recd != None):
		if (recd.datastoreId != None):
			#quickly check: if you have a datastoreId that the file hasn't been deleted,
			#cause if you do, we need to flag your removal
			#2904 trac
			recd.datastoreOb = getMediaFromDatastore( recd )
			if (recd.datastoreOb == None):
				addToHash = False
			else:
				#name might have been changed in the journal, so reflect that here
				if (recd.title != recd.datastoreOb.metadata['title']):
					recd.setTitle(recd.datastoreOb.metadata['title'])
				if (recd.tags != recd.datastoreOb.metadata['tags']):
					recd.setTags(recd.datastoreOb.metadata['tags'])
				if (recd.buddy):
					recd.downloadedFromBuddy = True

			recd.datastoreOb == None

	if (addToHash):
		hash.append( recd )


def getMediaFromDatastore( recd ):
	if (recd.datastoreId == None):
		return None

	if (recd.datastoreOb != None):
		#already have the object
		return recd.datastoreOb

	mediaObject = None
	try:
		mediaObject = datastore.get( recd.datastoreId )
	finally:
		if (mediaObject == None):
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
	if (el.getAttributeNode(Constants.recdType) != None):
		typeInt = int(el.getAttribute(Constants.recdType))
		recd.type = typeInt

	if (el.getAttributeNode(Constants.recdTitle) != None):
		recd.title = el.getAttribute(Constants.recdTitle)

	if (el.getAttributeNode(Constants.recdTime) != None):
		timeInt = int(el.getAttribute(Constants.recdTime))
		recd.time = timeInt

	if (el.getAttributeNode(Constants.recdRecorderName) != None):
		recd.recorderName = el.getAttribute(Constants.recdRecorderName)

	if (el.getAttributeNode(Constants.recdTags) != None):
		recd.tags = el.getAttribute(Constants.recdTags)
	else:
		recd.tags = ""

	if (el.getAttributeNode(Constants.recdRecorderHash) != None):
		recd.recorderHash = el.getAttribute(Constants.recdRecorderHash)

	if (el.getAttributeNode(Constants.recdColorStroke) != None):
		try:
			colorStrokeHex = el.getAttribute(Constants.recdColorStroke)
			colorStroke = Color()
			colorStroke.init_hex(colorStrokeHex)
			recd.colorStroke = colorStroke
		except:
			record.Record.log.error("unable to load recd colorStroke")

	if (el.getAttributeNode(Constants.recdColorFill) != None):
		try:
			colorFillHex = el.getAttribute(Constants.recdColorFill)
			colorFill = Color()
			colorFill.init_hex( colorFillHex )
			recd.colorFill = colorFill
		except:
			record.Record.log.error("unable to load recd colorFill")

	if (el.getAttributeNode(Constants.recdBuddy) != None):
		recd.buddy = (el.getAttribute(Constants.recdBuddy) == "True")

	if (el.getAttributeNode(Constants.recdMediaMd5) != None):
		recd.mediaMd5 = el.getAttribute(Constants.recdMediaMd5)

	if (el.getAttributeNode(Constants.recdThumbMd5) != None):
		recd.thumbMd5 = el.getAttribute(Constants.recdThumbMd5)

	if (el.getAttributeNode(Constants.recdMediaBytes) != None):
		recd.mediaBytes = el.getAttribute(Constants.recdMediaBytes)

	if (el.getAttributeNode(Constants.recdThumbBytes) != None):
		recd.thumbBytes = el.getAttribute(Constants.recdThumbBytes)

	bt = el.getAttributeNode(Constants.recdBase64Thumb)
	if (bt != None):
		try:
			thumbPath = os.path.join(Instance.instancePath, "datastoreThumb.jpg")
			thumbPath = utils.getUniqueFilepath( thumbPath, 0 )
			thumbImg = utils.getPixbufFromString( bt.nodeValue )
			thumbImg.save(thumbPath, "jpeg", {"quality":"85"} )
			recd.thumbFilename = os.path.basename(thumbPath)
			record.Record.log.debug("saved thumbFilename")
		except:
			record.Record.log.error("unable to getRecdBase64Thumb")

	ai = el.getAttributeNode(Constants.recdAudioImage)
	if (not ai == None):
		try:
			audioImagePath = os.path.join(Instance.instancePath, "audioImage.png")
			audioImagePath = utils.getUniqueFilepath( audioImagePath, 0 )
			audioImage = utils.getPixbufFromString( ai.nodeValue )
			audioImage.save(audioImagePath, "png", {} )
			recd.audioImageFilename = os.path.basename(audioImagePath)
			record.Record.log.debug("loaded audio image and set audioImageFilename")
		except:
			record.Record.log.error("unable to load audio image")

	datastoreNode = el.getAttributeNode(Constants.recdDatastoreId)
	if (datastoreNode != None):
		recd.datastoreId = datastoreNode.nodeValue

	return recd


def getRecdXmlMeshString( recd ):
	impl = getDOMImplementation()
	recdXml = impl.createDocument(None, Constants.recdRecd, None)
	root = recdXml.documentElement
	_addRecdXmlAttrs( root, recd, True )

	writer = cStringIO.StringIO()
	recdXml.writexml(writer)
	return writer.getvalue()


def _addRecdXmlAttrs( el, recd, forMeshTransmit ):
	el.setAttribute(Constants.recdType, str(recd.type))

	if ((recd.type == Constants.TYPE_AUDIO) and (not forMeshTransmit)):
		aiPixbuf = recd.getAudioImagePixbuf( )
		aiPixbufString = str( utils.getStringFromPixbuf(aiPixbuf) )
		el.setAttribute(Constants.recdAudioImage, aiPixbufString)

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
	el.setAttribute(Constants.recdRecordVersion, str(Constants.VERSION))

	pixbuf = recd.getThumbPixbuf( )
	thumb64 = str( utils.getStringFromPixbuf(pixbuf) )
	el.setAttribute(Constants.recdBase64Thumb, thumb64)


def saveMediaHash( mediaHashs ):
	impl = getDOMImplementation()
	album = impl.createDocument(None, Constants.recdAlbum, None)
	root = album.documentElement

	#flag everything for saving...
	atLeastOne = False
	for type,value in Constants.mediaTypes.items():
		typeName = value[Constants.keyName]
		hash = mediaHashs[type]
		for i in range (0, len(hash)):
			recd = hash[i]
			recd.savedXml = False
			recd.savedMedia = False
			atLeastOne = True

	#and if there is anything to save, save it
	if (atLeastOne):
		for type,value in Constants.mediaTypes.items():
			typeName = value[Constants.keyName]
			hash = mediaHashs[type]

			for i in range (0, len(hash)):
				recd = hash[i]
				mediaEl = album.createElement( typeName )
				root.appendChild( mediaEl )
				_saveMedia( mediaEl, recd )

	return album


def _saveMedia( el, recd ):
	if ( (recd.buddy == True) and (recd.datastoreId == None) and (not recd.downloadedFromBuddy) ):
		recd.savedMedia = True
		_saveXml( el, recd )
	else:
		recd.savedMedia = False
		_saveMediaToDatastore( el, recd )


def _saveXml( el, recd ):
	if (recd.thumbFilename != None):
		_addRecdXmlAttrs( el, recd, False )
	else:
		record.Record.log.debug("WOAH, ERROR: recd has no thumbFilename?! " + str(recd) )
	recd.savedXml = True


def _saveMediaToDatastore( el, recd ):
	#note that we update the recds that go through here to how they would
	#look on a fresh load from file since this won't just happen on close()

	if (recd.datastoreId != None):
		#already saved to the datastore, don't need to re-rewrite the file since the mediums are immutable
		#However, they might have changed the name of the file
		if (recd.metaChange):
			recd.datastoreOb = getMediaFromDatastore( recd )
			if (recd.datastoreOb.metadata['title'] != recd.title):
				recd.datastoreOb.metadata['title'] = recd.title
				datastore.write(recd.datastoreOb)
			if (recd.datastoreOb.metadata['tags'] != recd.tags):
				recd.datastoreOb.metadata['tags'] = recd.tags
				datastore.write(recd.datastoreOb)

			#reset for the next title change if not closing...
			recd.metaChange = False
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
		mediaObject.metadata['tags'] = recd.tags

		datastorePreviewPixbuf = recd.getThumbPixbuf()
		if (recd.type == Constants.TYPE_AUDIO):
			datastorePreviewPixbuf = recd.getAudioImagePixbuf()
		elif (recd.type == Constants.TYPE_PHOTO):
			datastorePreviewFilepath = recd.getMediaFilepath()
			datastorePreviewPixbuf = gtk.gdk.pixbuf_new_from_file(datastorePreviewFilepath)

		datastorePreviewWidth = 300
		datastorePreviewHeight = 225
		if (datastorePreviewPixbuf.get_width() != datastorePreviewWidth):
			datastorePreviewPixbuf = datastorePreviewPixbuf.scale_simple(datastorePreviewWidth, datastorePreviewHeight, gtk.gdk.INTERP_NEAREST)

		datastorePreviewBase64 = utils.getStringFromPixbuf(datastorePreviewPixbuf)
		mediaObject.metadata['preview'] = datastorePreviewBase64

		colors = str(recd.colorStroke.hex) + "," + str(recd.colorFill.hex)
		mediaObject.metadata['icon-color'] = colors

		mtype = Constants.mediaTypes[recd.type]
		mime = mtype[Constants.keyMime]
		mediaObject.metadata['mime_type'] = mime

		mediaObject.metadata['activity_id'] = Constants.activityId

		mediaFile = recd.getMediaFilepath()
		mediaObject.file_path = mediaFile
		mediaObject.transfer_ownership = True

		datastore.write( mediaObject )

		recd.datastoreId = mediaObject.object_id
		recd.savedMedia = True

		_saveXml( el, recd )

		recd.mediaFilename = None