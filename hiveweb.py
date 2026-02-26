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
        Middleman between '_listen_thread()' and 'receive()'.
        Used to manipulate data without interacting with 'receive()'.

        Currentls a passthrough to 'receive()'.
        """
        #custom functionality must be created through overwrites
        self.receive(data)


#USED IN LISTENING THREAD
def _listen_thread(connection, instance):
    """
    Indefinetly listens for input.
    """
    #loop infinitely
    while True:
        #set 'data' to empty bytestring
        data = b''
        #receive a kb of data until <END> tag is reached
        while data[-5:] != END:
            try:
                dr = connection.recv(1024)
                #kill the thread because client abruptly disconnected
                if not dr:
                    return None
                #if data is received, append it to 'data'
                data += dr
            except OSError:
                #otherwise the socket has disconnected so kill the thread
                #returning None kills the thread
                return None
        #pass final data back to the right _private_receive
        instance._private_receive(data)


class Server(_CommunicatingObject):
    def __init__(self, PORT):
        #perform basic initialization
        super().__init__(PORT)
        #create lock
        self.lock = threading.Lock()
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
        self._open = True
        while self._open:
            #since 'accept()' pauses code execution I can't really fix this
            #without try/except.
            try:
                #connect to the client
                #connection is the connection, address is (their IP, their port).
                connection, address = self.s.accept()
            except OSError:
                pass
            #make SURE that the server is still open
            if self._open:
                #add connection to members with key of address
                #address must be string to prevent ACE through <RQST> tags.
                with self.lock:
                    self.members[repr(address)] = connection
                #send adress to client on connection
                self.send(connection,repr(address))
                #create and start a daemon thread for each user to receive data
                self.t=threading.Thread(target=_listen_thread, args=(connection,self,),daemon=True)
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
        clist = []
        with self.lock:
            for address, connection in self.members.items():
                clist.append(connection)
        if clist:
            for con in clist:
                self.send(con,data)

    def _private_receive(self, data):
        """
        Middleman between '_listen_thread()' and 'receive()'.
        Used to parse server commands.

        Server commands should be implemented with a leading tag here,
        and call a method that can be overwritten by extended classes.

        Currently implements these tags:
            <POST> - Sends data to server
            <RQST> - Requests data from the server (currently echoes)
            <CLOS> - Closes connection to device

        Tags must be exactly four characters and enclosed in <braces>.

        '_private_receive()' also handles data decoding.
        """
        #strip <END> tag off data
        data = data[:-5]
        #get <TAG>, return address, and data
        tag,retaddr,data = self._extract_data(data)

        match tag:
            case b'<POST>':
                #call receive with decoded data
                self.receive(data.decode())

            case b'<RQST>':
                #call respond with decoded data and return address
                self.respond(data.decode(),retaddr.decode())

            case b'<CLOS>':
                #close targeted connection
                with self.lock:
                    self.members[retaddr.decode()].close()
                    del self.members[retaddr.decode()]

            case _: #default back to <POST> if tag not found
                #call receive with decoded data
                self.receive(data.decode())

    def _extract_data(self,data):
        """
        Returns a tuple of (<TAG>,name,data)
        """
        #strip off tag
        data = data[6:]
        #get tag
        tag = data[:6]
        #strip <NAMEND> tag and return name, data
        name, data = data.split(b'<NAMEND>')
        #return tuple
        return tag,name,data

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
        self.send(self.members[address],data)

    def close(self):
        #disable the start loop
        self._open = False
        #notify clients
        self.sendall('<SERC>')
        #close the socket
        self.s.close()

    def __del__(self):
        #close on deletion
        self.close()


class Client(_CommunicatingObject):
    def __init__(self, PORT, IP):
        #perform basic initialization
        super().__init__(PORT)
        #connect to server
        self.s.connect((IP, PORT))
        #set self.address to address assigned by server
        self.address = self.s.recv(1024)[:-5].decode()
        #create and start listening daemon thread for return information
        self.t=threading.Thread(target=_listen_thread, args=(self.s,self),daemon=True)
        self.t.start()

    def post(self,data):
        """
        Sends data to the server.
        """
        #send data with post tag
        self.send('<POST>'+self.address+'<NAMEND>'+data)

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

    def _send_closing(self):
        self.send('<CLOS>'+self.address+'<NAMEND>')

    def _private_receive(self,data):
        """
        Middleman between '_listen_thread()' and 'receive()'
        Used to clean server responses.

        '_private_receive()' also handles data decoding.

        Special <SERC> tag sent on server close, closes self.
        """
        if data.decode().startswith('<SERC>'):
            self.close()
        else:
            self.receive(data.decode()[:-5])

    def close(self):
        try:
            #send closing message to server to close connection
            self._send_closing()
            #shut down socket
            self.s.shutdown(socket.SHUT_RDWR)
            #close the socket
            self.s.close()
        except OSError:
            pass


    def __del__(self):
        #close on deletion
        self.close()
