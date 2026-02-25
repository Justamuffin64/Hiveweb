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

        #bind to all interfaces
        self.s.bind(('',PORT))
        #listen to all interfaces
        self.s.listen()

        #declare epmty list of connections
        self.connections = []

        ###ADD CONNECTION CODE DEPENDING ON IF SERVER OR CLASS

    def receive(self,data):
        """
        Called whenever the server receives data!
        """
        pass #Implement in extended class!

    def send(self,IP,data):
        """
        Call to send data to target IP.
        """
        self.se = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.se.connect((IP, PORT))
        self.se.send(data)
        

#USED IN LISTENING THREAD
def listen_thread(connection, server):
    """
    Indefinetly listens for input.
    """
    while True:
        data = b''
        while data[-5:] != END:
            data += connection.recv(1024)
        data = data[:-5].decode()
        server.receive(data)


class Server(_CommunicatingObject):
    def start(self):
        while True:
            #connect to the client
            #connection is the connection, address is their IP I think.
            self.connection, self.address = self.s.accept()
            with self.connection:
                #create a thread for each user to receive data
                self.connections.append(connection)
                t=threading.Thread(target=listen_thread, args=(connection,self))
                t.start()

class Client(_CommunicatingObject):
    def start(self):
        #connect to the server
        #connection is the connection, address is their IP I think.
        self.connection, self.address = self.s.accept()
        #add server to connections
        self.connections.append(connection)
        #create a thread to read server data
        t=threading.Thread(target=listen_thread, args=(connection,self))
        t.start()
