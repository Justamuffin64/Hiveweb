"""Docstring :)"""
import socket
import threading

PORT = 8330
HOST = 'localhost'
END = b'<END>'

class _CommunicatingObject(object):
    def __init__(self,PORT):
        """
        Starts the server socket.
        """
        #declare PORT constant
        self.PORT = PORT
        
        #create socket
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        ###ADD CONNECTION CODE DEPENDING ON IF SERVER OR CLASS

    def receive(self,data):
        """
        Called whenever the server receives data!
        """
        pass #Implement in extended class!

    def _private_receive(self, data):
        """
        Middleman between '_listen_thread()' and 'receive()'
        Used to manipulate data without interacting with 'receive()'.
        """
        #custom functionality must be created through overwrites
        self.receive(data)
        

#USED IN LISTENING THREAD
def _listen_thread(connection, instance):
    """
    Indefinetly listens for input.
    """
    while True:
        data = b''
        while data[-5:] != END:
            data += connection.recv(1024)
        instance._private_receive(data)


class Server(_CommunicatingObject):
    def __init__(self, PORT):
        #perform basic initialization
        super().__init__(PORT)
        #create an empty member list
        self.members = {}
        #bind to all interfaces
        self.s.bind(('',PORT))
        #listen to all interfaces
        self.s.listen()
    
    def start(self):
        """
        Cause the server to begin attempting to connect to new devices.
        """
        while True:
            #connect to the client
            #connection is the connection, address is (their IP, their port).
            self.connection, self.address = self.s.accept()
            #add connection to members with key of address
            self.members[self.address] = self.connection
            #send adress to client on connection
            self.send(self.connection,repr(self.address))
            #create and start a thread for each user to receive data
            self.t=threading.Thread(target=_listen_thread, args=(self.connection,self,))
            self.t.start()

    def send(self,con,data):
        """
        Call to send data to connection ('con').
        """
        con.send(data.encode()+b'<END>')

    def sendall(self,data):
        """
        Sends data to all connections.
        """
        for address, connection in self.members.items():
            self.send(connection,data)

    def _private_receive(self, data):
        """
        Middleman between '_listen_thread()' and 'receive()'
        Used to parse server commands.

        Server commands should be implemented with a leading tag here,
        and call a method that can be overwritten by extended classes.

        Currently implements these tags:
            <POST> - Sends data to server
            <RQST> - Requests data from the server (currently echoes)

        Tags must be exactly four characters and enclosed in <braces>

        '_private_receive()' also handles data decoding.
        """
        #initialize empty return adress (is deleted later)
        self.retaddr = None
        #strip <END> tag off data
        self.data = data[:-5]
        #match starting tag (first six characters: <2345>)
        match self.data[:6]:
            case b'<POST>':
                #strip post tag
                self.data = self.data[6:]
                #call receive with decoded data
                self.receive(self.data.decode())

            case b'<RQST>':
                #strip request tag
                self.data = self.data[6:]
                #get all data before <NAMEND> tag and after in retaddr, data
                #also strips <NAMEND> tag as a byproduct
                self.retaddr, self.data = self.data.split(b'<NAMEND>')
                #call respond with decoded data and return address
                self.respond(self.data.decode(),self.retaddr)

            case _: #default back to <POST> if tag not found
                #call receive with decoded data
                self.receive(self.data.decode())

        #delete variables that are no longer in use
        del self.data
        del self.retaddr

    def respond(self, data, address):
        """
        Code to handle server requests. Like 'receive()' it is called
        automatically when necessary.

        When called it is passed both the data and return adress from the
        call, in that order.

        Meant to be overwritten with custom logic.
        """
        #Implement your own code here!
        #Should be overwritten as only echoes right now.
        self.send(self.members[eval(address)],data)


class Client(_CommunicatingObject):
    def __init__(self, PORT, IP):
        #perform basic initialization
        super().__init__(PORT)
        #connect to server
        self.s.connect((IP, PORT))
        #set self.address to address assigned by server
        self.address = self.s.recv(1024)[:-5].decode()
        #create and start listening thread for return information
        self.t=threading.Thread(target=_listen_thread, args=(self.s,self))
        self.t.start()

    def post(self,data):
        """
        Sends data to the server.
        """
        #send data with post tag
        self.send('<POST>'+data)

    def request(self,data):
        """
        Calls the server's 'respond()' method with the data.
        """
        #send data with request tag and return address
        self.send('<RQST>'+self.address+'<NAMEND>'+data)

    def send(self,data):
        """
        Call to send data to target IP.
        """
        #sends data with no tag (not recommended)
        self.s.send(data.encode()+b'<END>')

    def _private_receive(self,data):
        """
        Middleman between '_listen_thread()' and 'receive()'
        Used to clean server responses.

        '_private_receive()' also handles data decoding.
        """
        self.receive(data.decode()[:-5])
