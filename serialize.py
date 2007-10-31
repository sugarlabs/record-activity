import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parse

from constants import Constants



def fillMediaHash( index, m ):
	doc = None
	if (os.path.exists(index)):
		try:
			doc = parse( os.path.abspath(index) )
		except:
			doc = None
	if (doc == None):
		return

	for key,value in m.mediaTypes.items():
		recdElements = doc.documentElement.getElementsByTagName(value[Constants.keyName])
		for el in recdElements:
			loadMediaIntoHash( el, m.mediaHashs[key] )


def loadMediaIntoHash( el, hash ):
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
			thumbPath = self.getUniqueFilepath( thumbPath, 0 )
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


def addRecdXmlAttrs( self, el, recd, forMeshTransmit ):
	el.setAttribute(self.recdType, str(recd.type))

	if ((recd.type == constants.TYPE_AUDIO) and (not forMeshTransmit)):
		aiPixbuf = recd.getAudioImagePixbuf( )
		aiPixbufString = str( utils.getStringFromPixbuf(aiPixbuf) )
		el.setAttribute(self.recdAudioImage, aiPixbufString)

	if ((recd.datastoreId != None) and (not forMeshTransmit)):
		el.setAttribute(self.recdDatastoreId, str(recd.datastoreId))

	el.setAttribute(self.recdTitle, recd.title)
	el.setAttribute(self.recdTime, str(recd.time))
	el.setAttribute(self.recdRecorderName, recd.recorderName)
	el.setAttribute(self.recdRecorderHash, str(recd.recorderHash) )
	el.setAttribute(self.recdColorStroke, str(recd.colorStroke.hex) )
	el.setAttribute(self.recdColorFill, str(recd.colorFill.hex) )
	el.setAttribute(self.recdBuddy, str(recd.buddy))
	el.setAttribute(self.recdMediaMd5, str(recd.mediaMd5))
	el.setAttribute(self.recdThumbMd5, str(recd.thumbMd5))
	el.setAttribute(self.recdMediaBytes, str(recd.mediaBytes))
		el.setAttribute(self.recdThumbBytes, str(recd.thumbBytes))