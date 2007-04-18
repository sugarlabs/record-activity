from sugar.p2p import network
from sugar.presence import presenceservice

class Server:

	def __init__( self, pc ):
		self.c = pc

		#listen to and talk through this port, using this here info #TODO: how to make this "static" to this class
		self.port = 8888
		self.server = network.GlibXMLRPCServer(("", self.port))
		self.server.register_instance(inst)

	def shutdown( self ):
		pass

	def newPicNotice( self, arg1, arg2 ):
		print "Request got " + str(arg1) + ", " + str(arg2)
		return "success"


class Client:

	def __init__( self, pc ):
		self.c = pc
		#listen to and talk through this port, using this here info #TODO: how to make this "static" to this class
		self.port = 8888

		#stay alert!  buddies might show up at any time!
		self.my_acty = self.c._frame._pservice.get_activity(self.activity_id)
		self.my_acty.connect('buddy-joined', self.buddy_joined_cb)
		self.my_acty.connect('buddy-left', self.buddy_left_cb)
		self.my_acty.connect('service-appeared', self.service_appeared_cb)
		self.my_acty.connect('service-disappeared', self.service_disappeared_cb)

		#if you've just arrived at the playground, take a peruse around
		for buddy in self.my_acty.get_joined_buddies():
			print buddy.props.nick
			print buddy.props.ip4_address

	def buddy_joined_cb( self, activity, buddy ):
		pass

	def buddy_left_cb( self, activity, buddy ):
		pass

	def service_appeared_cb( self, activity, buddy ):
		pass

	def service_disappeared_cb( self, activity, buddy ):
		pass

	#herein we notify our buddies of some cool stuff we got going on they mights wants to knows abouts
	def notifyBudsOfNewPic( self ):
		for buddy in self.my_acty.get_joined_buddies():
			bud = network.GlibServerProxy((buddy.props.ip4_address, self.port))
			bud.newPicNotice(notifyBudsOfNewPic_cb, "bar", "test data")

	def notifyBudsOfNewPic_cb(response, user_data=None):
		print "Response was %s, user_data was %s" % (response, user_data)