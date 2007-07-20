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

from sugar import network
from sugar.presence import presenceservice
from sugar import util

import urlparse
import urllib
import posixpath
import shutil
import os

from recorded import Recorded
from color import Color

xmlRpcPort = 8888
httpPort = 8889


#todo: when you take a picture, transmit the name and who took it, and buddy colors too... all things to create a rec'd
#todo: then create a directory in which to put buddy photos
#todo: then display them as thumbs, but when you click them, do resolution on where to get them from...
#todo: on joining activity get all of the existing photos from who has them
#todo: when someone deletes a photo, delete all photos

class MeshXMLRPCServer:
	def __init__( self, pca ):
		self.ca = pca
		#this is ye olde xmlrpc server
		#listen to and talk through this port for xmlrpc, using this here info
		self.server = network.GlibXMLRPCServer(("", xmlRpcPort))
		self.server.register_instance(self) #anything witout an _ is callable by all the hos and joes out there

	def newPhotoNotice(	self,
						ip,
						mediaFilename, thumbFilename, time, photographer, name, colorStroke, colorFill, hashKey ):

		newRecd = Recorded()
		newRecd.type = self.ca.m.TYPE_PHOTO
		newRecd.buddy = True
		newRecd.mediaFilename = mediaFilename
		newRecd.thumbFilename = thumbFilename
		newRecd.time = time
		newRecd.photographer = photographer
		newRecd.name = name
		newRecd.hashKey = hashKey

		colorStrokeHex = colorStroke
		colorStroke = Color()
		colorStroke.init_hex( colorStrokeHex )
		newRecd.colorStroke = colorStroke
		colorFillHex = colorFill
		colorFill = Color()
		colorFill.init_hex( colorFillHex )
		newRecd.colorFill =  colorFill

		self.ca.meshClient.requestThumbBits( ip, newRecd )
		print "requested new bits from that other buddy"
		return "successios"


	def deleteMediaNotice( 	self,
							hashKey, time, type):
		self.ca.m.deleteBuddyMedia( hashKey, int(time), int(type) )
		return "deletedPhoto"

class HttpServer(network.GlibTCPServer):

	def __init__(self, pca):
		self.ca = pca
		server_address = ("", httpPort)
		network.GlibTCPServer.__init__(self, server_address, HttpReqHandler);



class HttpReqHandler(network.ChunkedGlibHTTPRequestHandler):

	def translate_path(self, path):
		#todo: what to return here if not returning a file or how to handle errors?
		urlp = urlparse.urlparse(path)
		urls = urlp[2]
		urls = posixpath.normpath(urllib.unquote(urls))
		urlPath = urls.split('/')
		urlPath = filter(None, urlPath)

		params = urlp[4]
		parama = []
		allParams = params.split('&')
		for i in range (0, len(allParams)):
			parama.append(allParams[i].split('='))

		print( "http parama...", parama )
		#todo: test to make sure file still here and not deleted... and what to return if not there?
		#should be abs path... check it 1st
		ff = parama[0][1]
		fileToSend = os.path.join( self.server.ca.journalPath, ff )
		return fileToSend


class MeshClient:

	def __init__( self, pca ):
		self.ca = pca

		#stay alert!  buddies might show up at any time!
		print("1 meshClient");
		print("1.1 meshClient: ", self.ca)
		self.my_acty = self.ca._shared_activity #_pservice.get_activity(self.c.activity_id)
		print("1.2 meshClient: ", self.my_acty)
		#self.my_acty_id = self.c._frame.activity_id
		#print( "uid:", self.my_acty_id )

		self.my_acty.connect('buddy-joined', self.buddyJoinedCb)
		print("1.3")
		self.my_acty.connect('buddy-left', self.buddyDepartedCb)
		print("1.4")

		print("1.5", len(self.my_acty.get_joined_buddies()) )
		#if you've just arrived at the playground, take a peruse around
		for buddy in self.my_acty.get_joined_buddies():
			print ("a", buddy.props.nick)
			print ("a", buddy.props.ip4_address)
			print ("a", buddy.props.owner) #me boolean
			print ("a", buddy.props.key)

		print("1.6")

	def buddyJoinedCb( self, activity, buddy ):
		print ("b", buddy.props.nick)
		print ("b", buddy.props.ip4_address)
		print ("b", buddy.props.owner) #me boolean
		print ("b", buddy.props.key)

	def buddyDepartedCb( self, activity, buddy ):
		print ("c", buddy.props.nick)
		print ("c", buddy.props.ip4_address)
		print ("c", buddy.props.owner) #me boolean
		print ("c", buddy.props.key)

	#herein we notify our buddies of some cool stuff we got going on they mights wants to knows abouts
	def notifyBudsOfNewPhoto( self, recd ):

		ps = presenceservice.get_instance()
		me = ps.get_owner()

		for buddy in self.my_acty.get_joined_buddies():
			if (not buddy.props.owner):
				bud = network.GlibServerProxy( "http://%s:%d" % (buddy.props.ip4_address, xmlRpcPort))

				bud.newPhotoNotice(	str(me.props.ip4_address),
									recd.mediaFilename, recd.thumbFilename,
									recd.time, recd.photographer,
									recd.name,
									recd.colorStroke.hex, recd.colorFill.hex,
									recd.hashKey,
									reply_handler=self.notifyBudsOfNewPhotoCb,
									error_handler=self.notifyBudsOfNewPhotoErrorCb,
									user_data=buddy)


	def notifyBudsOfNewPhotoCb(self, response, user_data):
		print "Response was %s, user_data was %s" % (response, user_data)


	def notifyBudsOfNewPhotoErrorCb(self, error, user_data):
		print "We've a no go erroro! ", user_data


	def notifyBudsofDeleteMedia(self, recd):
		for buddy in self.my_acty.get_joined_buddies():
			if (not buddy.props.owner):
				bud = network.GlibServerProxy( "http://%s:%d" % (buddy.props.ip4_address, xmlRpcPort))

				bud.deleteMediaNotice(	recd.hashKey,
										recd.time,
										recd.type,
										reply_handler=self.notifyBudsOfDeleteMediaCb,
										error_handler=self.notifyBudsOfDeleteMediaErrorCb,
										user_data=buddy)


	def notifyBudsOfDeleteMediaCb(self, response, user_data):
		print "Response was %s, user_data was %s" % (response, user_data)


	def notifyBudsOfDeleteMediaErrorCb(self, error, user_data):
		print "We've a no go erroro! ", user_data


	def requestThumbBits(self, ip, recd):
		ps = presenceservice.get_instance()
		me = ps.get_owner()

		#todo: differentiate which session in case many cameras are running
		uri = "http://" + str(ip) + ":" + str(httpPort) + "/thumb?thumbFilename=" + str(recd.thumbFilename)
		getter = network.GlibURLDownloader( uri )
		getter.connect( "finished", self.thumbDownloadResultCb, recd )
		getter.connect( "error", self.thumbDownloadErrorCb, recd )
		getter.start()


	def thumbDownloadResultCb(self, getter, tempfile, suggested_name, recd):
		#todo: better way to disambiguate who took which photo (hash, md5sum)?
		#dest = os.path.join(os.path.expanduser("~"), suggested_name)
		#todo: handle empty files here... or errors
		buddyDirPath = os.path.join( self.ca.journalPath, "buddies" )
		if (not os.path.exists(buddyDirPath)):
			os.makedirs(buddyDirPath)

		dest = os.path.join( buddyDirPath, suggested_name )
		shutil.copyfile(tempfile, dest)
		os.remove(tempfile)
		self.ca.m.addPhoto( recd )


	def thumbDownloadErrorCb(self, getter, err, recd):
		print("thumbDownloadError", getter, err, recd )


	#todo: don't request this if requesting this already
	def requestPhotoBits(self, recd):
		print("requestingPhotoBits...", len(self.my_acty.get_joined_buddies()))
		photoTakingBuddy = None
		for buddy in self.my_acty.get_joined_buddies():
			if (not buddy.props.owner):
				keyHash = util._sha_data(buddy.props.key)
				hashKey = util.printable_hash(keyHash)
				print(hashKey, recd.hashKey)
				if (hashKey == recd.hashKey):
					photoTakingBuddy = buddy

		print("photoTakingBuddy...", photoTakingBuddy)
		if (photoTakingBuddy != None):
			uri = "http://" + str(photoTakingBuddy.props.ip4_address) + ":" + str(httpPort) + "/media?mediaFilename=" + str(recd.mediaFilename)
			getter = network.GlibURLDownloader( uri )
			getter.connect( "finished", self.mediaDownloadResultCb, recd )
			getter.connect( "error", self.mediaDownloadErrorCb, recd )
			getter.start()


	def mediaDownloadResultCb(self, getter, tempfile, suggested_name, recd):
		#todo: make lazy maker+getter fot buddy dir
		buddyDirPath = os.path.join( self.ca.journalPath, "buddies" )
		if (not os.path.exists(buddyDirPath)):
			os.makedirs(buddyDirPath)

		dest = os.path.join( buddyDirPath, suggested_name )
		shutil.copyfile(tempfile, dest)
		os.remove(tempfile)
		print( "downloaded media and here it is: " + str(dest) )
		self.ca.ui.updateShownPhoto( recd )


	def mediaDownloadErrorCb(self, getter, err, recd):
		print("mediaDownloadError", getter, err, recd)