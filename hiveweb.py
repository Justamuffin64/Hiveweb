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
        

#USED IN LISTENING THREAD
def _listen_thread(connection, instance):
    """
    Indefinetly listens for input.
    """
    while True:
        data = b''
        while data[-5:] != END:
            data += connection.recv(1024)
        data = data[:-5].decode()
        instance.receive(data)


class Server(_CommunicatingObject):
    def __init__(self, PORT):
        super().__init__(PORT)
        self.members = {}
        #bind to all interfaces
        self.s.bind(('',PORT))
        #listen to all interfaces
        self.s.listen()
    
    def start(self):
        while True:
            #connect to the client
            #connection is the connection, address is their IP I think.
            self.connection, self.address = self.s.accept()
            self.members[self.address] = self.connection
            #send adress to client on connection
            self.send(self.connection,repr(self.address))
            #create a thread for each user to receive data
            self.t=threading.Thread(target=_listen_thread, args=(self.connection,self,))
            self.t.start()

    def send(self,con,data):
        """
        Call to send data to connection ('con').
        """
        con.send(data.encode()+b'<END>')


class Client(_CommunicatingObject):
    def __init__(self, PORT, IP):
        super().__init__(PORT)
        #connect to server
        self.s.connect((IP, PORT))
        #set self.address to address assigned by server
        self.address = self.s.recv(1024)[:-5].decode()
        #start listening for return information
        self.t=threading.Thread(target=_listen_thread, args=(self.s,self))
        self.t.start()

    def send(self,data):
        """
        Call to send data to target IP.
        """
        self.s.send(data.encode()+b'<END>')
