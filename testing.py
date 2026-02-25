import hiveweb
import threading

class Server(hiveweb.Server):
    def receive(self, data):
        print('S: '+data)

class Client(hiveweb.Client):
    def __init__(self, PORT, IP):
        super().__init__(PORT, IP)
        
    
    def receive(self, data):
        print('C: '+data)


#Imagine this is on a seperate device
server = Server(8330)
th=threading.Thread(target=server.start).start()

me = Client(8330,'localhost')


