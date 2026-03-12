import asyncio
import struct
import json

async def listen(instance,reader,writer):
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
