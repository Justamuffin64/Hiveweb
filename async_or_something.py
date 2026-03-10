import asyncio
import struct
import json

def handles(name):
    def decorator(func):
        func._tag = name
        return func
    return decorator

class _Communicator:
    def __init__(self,PORT,IP):
        self.PORT = PORT
        self.IP = IP
        self.loop = asyncio.get_event_loop()

        self._next_id = 0
        self._pending = {}

    def __init_subclass__(cls):
        super().__init_subclass__()

        cls._handlers = {}

        #add all methods with a _tag attribute to _handlers
        for name,attr in cls.__dict__.items():
            if callable(attr) and hasattr(attr,'_tag'):
                if attr._tag in cls._handlers:
                    raise KeyError("Duplicate tag '%s' detected"%attr._tag)
                cls._handlers[attr._tag]=attr

    async def call(self,tag,**data):
        #create message
        message = {
            'tag':tag,
            'id':self._next_id,
            **data
            }
        #create a future and add it to _pending
        future = asyncio.get_running_loop().create_future()
        self._pending[self._next_id] = future
        #increment id
        self._next_id += 1
        #send message
        await self._send(message)
        #return future
        return await future
        

    async def _private_receive(self, data):
        """
        calls appropriate handler for received tag
        """
        #get tag from message
        tag = data.get('tag')

        #check if the message is a response
        if tag == 'response':
            #get the message id
            message_id = data['id']
            #check if id is in pending futures
            if message_id in self._pending:
                #if it is, set it's result to data["return"]
                self._pending[message_id].set_result(data.get('return'))
                #delete future
                del self._pending[message_id]
            #end
            return
        
        try:
            #get handler as 'h'
            h = self._handlers[tag]
            #get result from handler
            result = await h(self,data)
        except KeyError:
            raise KeyError('Invalid tag detected')

        addr = data.get('addr')
        addr = tuple(addr) if addr else None
        #respond if the message had an id
        if 'id' in data:
            await self._send({
                'tag':'response',
                'id':data['id'],
                'return':result
                },addr)
        

class Server(_Communicator):
    def __init__(self,PORT,IP):
        super().__init__(PORT,IP)
        self.members = {}
        
    async def start(self):
        #creates a server
        self.server = await asyncio.start_server(
            self.accept, self.IP, self.PORT)

        #lol idfk this just does stuff
        async with self.server as server:
            await server.serve_forever()

    async def accept(self,reader,writer):
        """
        Called whenever a client connects

        What
        """
        #get connecting address
        addr = writer.get_extra_info('peername')
        #add address to self.members
        self.members[addr] = (reader, writer)
        #tell connector their address
        await self._send({'tag':'rec_addr','addr':addr},addr)
        #listen asynchronously in background
        asyncio.create_task(listen(reader,writer,self))

    async def _send(self,data,addr):
        #get writer for address as w
        try:
            w = self.members[addr][1]
        except KeyError:
            raise KeyError("Address '%s' not found in member list"%addr)
        #encode json
        message = json.dumps(data).encode()
        #get four byte length of message
        le = struct.pack('>I',len(message))
        #combine length header and encoded json
        message = le+message
        #write data to writer
        w.write(message)
        #I forgot what drain does lol (it waits for some buffer or something)
        await w.drain()

    async def close_self(self):
        #loop through members
        for addr, tup in self.members.items():
            #send closing message to clients
            await self._send({'tag':'server_close'},addr)
            #close all of them
            tup[1].close()
            await tup[1].wait_closed()
        #close server
        self.server.close()
        await self.server.wait_closed()

    @handles('ps')
    async def ps(self,data):
        print(data)
    @handles('client_close')
    async def client_close(self,data):
        addr = None
        #assign address
        if 'addr' in data:
            addr = tuple(data['addr'])
        else:
            raise KeyError('Address not found in data.')
        #only use address if it is received
        if addr != None:
            #get reader and writer
            reader,writer = self.members[addr]
            #close writer
            writer.close()
            await writer.wait_closed()
            #delete member entry
            del self.members[addr]
        

class Client(_Communicator):
    def __init__(self,PORT,IP):
        super().__init__(PORT,IP)
        self.address = None
    
    async def start(self):
        self.reader, self.writer = await asyncio.open_connection(
            self.IP,self.PORT)

        #listen asynchronously (in the background)
        asyncio.create_task(listen(self.reader,self.writer,self))

        #create a future
        self.future = asyncio.get_running_loop().create_future()
        #wait for the future to be assigned the address
        self.address = await self.future
        #recast as tuple
        self.address = tuple(self.address)

    async def close_self(self):
        #send closing message to server
        await self._send({'tag':'client_close','addr':self.address})
        #close self
        self.writer.close()
        await self.writer.wait_closed()

    @handles('rec_addr')
    async def rec_addr(self,data):
        #save your address if you don't have one
        if self.address == None and not self.future.done():
            self.future.set_result(data['addr'])
            

    @handles('ps')
    async def ps(self,data):
        print(data)
    @handles('server_close')
    async def server_close(self,data):
        await self.close_self()


    async def _send(self,data,addr=None):
        """
        addr is only added for compatability with server commands
        """
        message = json.dumps(data).encode()
        le = struct.pack('>I',len(message))
        message = le+message
        self.writer.write(message)
        await self.writer.drain()
        
    
async def listen(reader, writer, instance):
    #make a global buffer
    buffer = b''
    #loop
    while True:
        #get 4kb data as chunk async
        chunk = await reader.read(4096)
        #if chunk is empty socket is closed so break out to closing logic
        if chunk == b'':
            break
        #append chunk to the buffer
        buffer += chunk
        #loop again
        while True:
            #break out to add more to buffer if buffer is too short for
            #a length header to be present
            if len(buffer) < 4:
                break
            #get the length header as le
            le = struct.unpack('>I',buffer[:4])[0]
            #break out to add more to buffer if buffer is too short to
            #contain entire message
            if len(buffer) < le + 4:
                break
            #save decoded message as message
            message = buffer[4:le+4].decode()
            #decode message JSON and discard erroneous messages
            try:
                message = json.loads(message)
            except json.JSONDecodeError:
                buffer = buffer[le+4:]
                continue
            #get the address
            addr = writer.get_extra_info('peername')
            #insert address into message if not present (unused by client)
            message.setdefault('addr',addr)
            #send final decoded message to instance's private receive async
            await instance._private_receive(message)
            #remove message from buffer
            buffer = buffer[le+4:]
    #close socket
    writer.close()
    await writer.wait_closed()
            
async def main():
    IP = 'localhost'
    PORT = 8331

    server = Server(PORT,IP)
    asyncio.create_task(server.start())

    await asyncio.sleep(0.1)
    
    client = Client(PORT,IP)
    await client.start()

    await server.close_self()

    await asyncio.sleep(1)

asyncio.run(main())
