from polygon import Polygon

class Button:

	def __init__(self, poly, offX, offY):
		self._poly = poly
		self._offX = offX
		self._offY = offY

		self._enabled = True
		self._pressed = False
		self._toggle = False

		self._listeners = []

		self._actionCommand = None

		self._img = None


	def addActionListener(self, listen):
		self._listeners.append(listen)


	def removeActionListener(self, listen):
		self._listeners.remove(listen)


	def setActionCommand(self, command):
		self._actionCommand = command


	def getActionCommand(self):
		return self._actionCommand


	def setImage(self, img):
		self._img = img


	def contains( self, mx, my ):
		x = mx - self._offX
		y = my - self._offY

		contains = self._poly.contains( x, y )
		return contains


	def doPressed( self ):
		for i in range ( 0, len(self._listeners) ):
			self._listeners[i].fireButton( self._actionCommand )


	def isImg( self ):
		return self._img != None