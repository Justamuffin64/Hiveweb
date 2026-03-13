import asyncio
import struct
import json
from abc import ABC, abstractmethod

def handles(tag:str): #factory
    def decorator(func): #decorator
        func._tag = tag #set private tag on fucntion to 'tag'
        return func #return function (no wrapper because only decoration time logic is needed)
    return decorator #return decorator (this is so the factory returns something that can decorate a function)

class _Communicator(ABC):
    """
    Abstract class for handlers, IP/PORT assignment, and message sending.
    """
    def __init__(self,IP:str,PORT:int):
        self.IP = IP
        self.PORT = PORT

    def __init_subclass__(cls): #this runs on class creation for subclasses btw--thats why 'cls' is used instead of 'self'
        super().__init_subclass__() #call __init_subclass__ of object (probably very important lol)
        cls._handlers = {} #declare _handlers to be an empty dict

        for name,attr in cls.__dict__.items(): #loop through everything in subclass's __dict__
            if callable(attr) and hasattr(attr,'_tag'): #check if attribute is callable and has _tag (basically check if it was decorated with @handles)
                if (tag:=attr._tag) in cls._handlers: #check if the tag is a duplicate and save it using walrus expression for later
                    raise KeyError('Duplicate tag \'%s\' detected.'%tag) #throw an error explaining the problem
                cls._handlers[tag] = attr #add handler func to _handlers, but func is not bound fyi

    async def _handle_handler(self,handler,data:dict): #coroutine to run in background--handles RPC calls and handler calling (maybe shouldn't be in _Communicator but who cares)
        try: #call the handler and store potential error
            result = await handler(self,data) #run handler and store result
        except Exception as e: #catch errors
            result = str(e) #store error (as result)

        if 'ID' in data: #if message has an ID treat as RPC request
            message = {             #
                'tag':'response',   #create message
                'ID':data['ID'],    #
                'return':result,}   #
            await self._send(message,data['writer']) #send message back to writer

    async def _send(self,data:dict,writer:asyncio.StreamWriter): #coroutine to send messages to specific writer
        try: #attempt to encode message json or throw error on failiure
            message = json.dumps(data).encode('utf-8') #save encoded json as message
        except Exception as e:
            raise TypeError('Malformed message: %r\nRaised exception: %s'%(data,e)) #raise formatted error
        length = struct.pack('>I',len(message)) #get four byte length header as length
        message = length + message #add header to message
        writer.write(message) #write message to writer
        await writer.drain() #drain writer buffer

    async def start(self): #passthrough to private start
        await self._start()

    @abstractmethod
    async def _start(self): #abstract method to be overwritten by children with their start logic
        ...

    async def close_self(self): #abstract method to be overwritten by children with their closing logic
        await self._close_self()

    @abstractmethod
    async def _close_self(self): #abstract method to be overwritten by children with their start logic
        ...
        
class _RPCHandler(_Communicator):
    """
    Abstract class for handling RPC calls.
    """
    def __init__(self,IP:str=None,PORT:int=None): #values default to none because they are unused but must exist for _Communicator initialization
        super().__init__(IP,PORT) #initialize _Communicator parent class
        self.next_id = 0 #message ID for rpc requests
        self._pending = {} #pending futures from rpc requests

    async def call(self,tag:str,w=None,**data): #passthrough to private call
        return await self._call(tag,w,**data)

    async def _call(self,tag:str,w=None,**data):
        current_id = self.next_id #get current ID
        self.next_id += 1 #increment ID
        future = asyncio.get_running_loop().create_future() #create a future
        self._pending[current_id] = future #add that future to pending futures
        message = {             #
            'tag':tag,          #create message
            'ID':current_id,    #
            **data}             #
        await self._send(message,w) #send message (it's a coro so await it)
        return await future #return the future when ready

    async def _private_receive(self,data:dict):
        tag = data.get('tag') #get tag from data

        match data: #match data as message
            case dict({'ID':int() as message_id,'tag':'response'}): #response case
                if message_id in self._pending: #check if ID has a pending future
                    self._pending[message_id].set_result(data.get('return')) #if it does, set the result to the 'return' result
                    del self._pending[message_id] #delete finished future
                    return #end logic
            case _: #non-response case
                if tag in self._handlers: #check to be sure message tag is in handlers
                    handler = self._handlers[tag] #identify correct handler
                    asyncio.create_task(self._handle_handler(handler,data)) #deal with handler and potential RPC response in background.

class BaseServer(_RPCHandler):
    def __init__(self,IP:str,PORT:int):
        super().__init__(IP,PORT) #initialize parent classes
        self._members = {} #create empty private members dictionary, format: {addr as tuple: (reader,writer)}

    async def _start(self):
        self.server = await asyncio.start_server(self._accept,self.IP,self.PORT) #create a server
        async with self.server as server: #context manager, might handle server closing idk
            await server.serve_forever() #server forever in background

    async def _accept(self,reader,writer):
        connecting_ip = writer.get_extra_info('peername') #get peername (IPv4,port,??,??)
        self._members[connecting_ip] = (reader,writer) #save reader,writer pair to peername
        asyncio.create_task(_listen(self,reader,writer)) #listen asynchronously in background
        await self._call('rec_addr',writer,address=connecting_ip) #calls rec_addr's handler on connecting object with address as address, will wait until handler returns

    async def _close_self(self):
        pass

class BaseClient(_RPCHandler):
    @handles('rec_addr')
    async def _receive_address(self,data): #handles receiving address on connection
        if not self._future_addr.done(): #ensure future is unresolved
            self._future_addr.set_result(data.get('address')) #save address
        return None #return None to resolve future and stop hanging Server._accept

    async def _start(self):
        self.reader, self.writer = await asyncio.open_connection(self.IP,self.PORT) #open connection to server
        asyncio.create_task(_listen(self,self.reader,self.writer)) #listen asynchronously
        self._future_addr = asyncio.get_running_loop().create_future() #create a future for address
        self.address = tuple(await self._future_addr) #save address

    async def _close_self(self):
        pass
        

async def _listen(instance,reader:asyncio.StreamReader,writer:asyncio.StreamWriter):
    """
    Coroutine meant to run in the background to listen for incoming messages.
    Messages are passed to the '_private_receive' of 'instance'.
    """
    buffer = b'' #create an empty buffer
    while True: #loop
        chunk = await reader.read(4096) # async await data from reader
        if chunk == b'': #break on empty bytestring (socket disconnect)
            break
        buffer += chunk #add chunk to buffer
        while True: #loop
            if (buffer_length:=len(buffer)) < 4: #break if chunk < 4 and save length
                break #go back to data receiving loop
            length = struct.unpack('>I',buffer[:4])[0] #decode length header
            if buffer_length < length+4: #break if chunk doesn't contain all data
                break #go back to data receiving loop
            message = buffer[4:length+4].decode('utf-8') #save & decode message
            buffer = buffer[length+4:] #remove message from buffer
            try: #attempt to decode message json, discard message if error
                message = json.loads(message)
            except json.JSONDecodeError:
                continue #restart loop for next message
            match message: #using match case
                case dict({'tag':str() as tag}): #check if message became a dict with a 'tag' entry
                    message['writer'] = writer #inject writer into message
                    await instance._private_receive(message) #receive valid message
                case _: #catch invalid messages
                    del message
                    continue #restart loop for next message
    #closing logic
    writer.close()
    await writer.wait_closed()



#########################################################################################################################################################################################


async def main():
    IP = 'localhost'
    PORT = 8331

    server = BaseServer(IP,PORT)
    asyncio.create_task(server.start())

    await asyncio.sleep(0.1)
    
    client = BaseClient(IP,PORT)
    await client.start()

    print(client.address)

    await asyncio.sleep(1)

asyncio.run(main())
