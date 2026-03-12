import asyncio
import struct
import json
from abc import ABC, abstractmethod

def handles(tag:str): #factory
    def decorator(func): #decorator
        func._tag = tag #set private tag on fucntion to 'tag'
        return func #return function (no wrapper because only decoration time logic is used)
    return decorator #return decorator (Ok you just do this I forgot why lol)

class _Communicator(ABC):
    """
    Abstract class for handlers and IP/PORT assignment.
    """
    def __init__(self,IP:str,PORT:int):
        self.IP = IP
        self.PORT = PORT

    def __init_subclass__(cls): #this runs on class creation for subclasses btw--thats why 'cls' is used instead of 'self'
        super().__init_subclass__() #call __init_subclass__ of object (probably very important lol)
        cls._handlers = {} #declare _handlers to be an empty dict

        for name,attr in cls.__dict__.items(): #loop through everything in subclass's __dict__
            if callable(attr) and hasattr(attr,'_tag'): #check if attribute is callable and has _tag (basically check if it was decorated with @handles)
                if tag:=attr._tag in cls._handlers: #check if the tag is a duplicate and save it using walrus expression for later
                    raise KeyError('Duplicate tag \'%s\' detected.'%tag) #throw an error explaining the problem
                cls._handlers[tag] = attr #add handler func to _handlers, but func is not bound fyi

    async def _handle_handler(self,handler,data:dict): #coroutine to run in background--handles RPC calls and handler calling
        try: #call the handler and store potential error
            result = await handler(self,data) #run handler and store result
        except Exception as e: #catch errors
            result = str(e) #store error (as result)

        if 'ID' in data: #if message has an ID treat as RPC request
            message = {             #
                'tag':'response',   #create message
                'ID':data['ID'],    #
                'return':result,}   #
            self._send(message,data['writer']) #send message back to writer

    async def _send(self,data:dict,writer:asyncio.StreamWriter): #coroutine to send messages to specific writer
        try: #attempt to encode message json or throw error on failiure
            message = json.dumps(data).encode() #save encoded json as message
        except Exception as e:
            raise TypeError('Malformed message: %r\nRaised exception: %s'%(data,e)) #raise formatted error
        length = struct.pack('>I',len(message)) #get four byte length header as length
        message = length + message #add header to message
        writer.write(message) #write message to writer
        await writer.drain() #drain writer buffer

    @abstractmethod
    async def start(self): #abstract method to be overwritten by children with their start logic
        ...

    @abstractmethod
    async def close_self(self): #abstract method to be overwritten by children with their closing logic
        ...
        

class _RPCHandler(_Communicator):
    """
    Abstract class for handling RPC calls and message sending.
    """
    def __init__(self):
        self.next_id = 0 #message ID for rpc requests
        self._pending = {} #pending futures from rpc requests

    async def call(self,tag:str,w=None,**data):
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

        match message:=data: #match data as message
            case dict({'ID':int() as message_id,'tag':'response'}): #response case
                if message_id in self._pending: #check if ID has a pending future
                    self._pending[message_id].set_result(message.get('return')) #if it does, set the result to the 'return' result
                    del self._pending[message_id] #delete finished future
                    return #end logic
            case _: #non-response case
                if tag in self._handlers:
                    handler = self._handlers[tag]
                    asyncio.create_task(self._handle_handler(handler,data))
                
        
        

async def listen(instance,reader:asyncio.StreamReader,writer:asyncio.StreamWriter):
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
            if buffer_length:=len(buffer) < 4: #break if chunk < 4 and save length
                break #go back to data receiving loop
            length = struct.unpack('>I',buffer_length) #decode length header
            if buffer_length < length+4: #break if chunk doesn't contain all data
                break #go back to data receiving loop
            message = chunk[4:buffer_length+4].decode() #save & decode message
            buffer = buffer[buffer_length+4:] #remove message from buffer
            try: #attempt to decode message json, discard message if error
                message = json.loads(message)
            except json.JSONDecodeError:
                del message
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
