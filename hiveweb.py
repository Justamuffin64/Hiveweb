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
        Used to manipulate data without override.
        """
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

    def _private_receive(self, data):
        """
        Middleman between '_listen_thread()' and 'receive()'
        Used to parse server commands.
        """
        self.data = data[:-5]
        if self.data.startswith(b'<POST>'):
            self.data = self.data[6:]
            self.receive(self.data.decode())

            
        elif self.data.startswith(b'<REQUEST>'):
            self.data = self.data[9:]
            #add request logic


        else: #default back to <POST> if tag not found
            self.receive(self.data.decode())


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

    def post(self,data):
        self.send('<POST>'+data)

    def request(self,data):
        self.send('<REQUEST>'+data)

    def send(self,data):
        """
        Call to send data to target IP.
        """
        self.s.send(data.encode()+b'<END>')

    
