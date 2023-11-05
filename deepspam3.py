#! /usr/bin/python3


###
### DeepSpam milter filter
###
### Uj verzio, ami a ppymilter-re epul (pure python milter), ehhez nem kell a libmilter, nem hasznal C kodot, jobb a memoriakezelese ( = nem leakel :))
### Csak a ppymilterbase.py file szukseges hozza:  https://raw.githubusercontent.com/agaridata/ppymilter/master/lib/ppymilter/ppymilterbase.py
### Az egesz 1 threadban fut, async modu halozatkezelessel. 64k meretu emailekkel tesztelve kb 40 email/masodperc sebesseget tudott!
### Valoszinuleg csak python3-al mukodik, bar talan atirhato py2-re is, ha van ra igeny.
###

import asyncio
import ppymilterbase
import logging
import struct
import time
import traceback

try:
  from io import BytesIO
except:
  from StringIO import StringIO as BytesIO

############################################################################################################################################

from eml2str import eml2str
from model import DeepSpam

ds=DeepSpam()


def do_eml(msg,addr):
    t=time.time()
    text=eml2str(msg,True) # extract subject,bodytext
    tokens=ds.tokenized([text])[0]
    print(tokens)
    res=ds(text)
    t=time.time()-t
    print("---  %22s  result: %8.5f  (%5.3f ms)"%(addr,res,1000*t))
    if res<0: return "toosmall"
    res+=0.1
#    print(res)
#    print("%d%%"%(res))
    try:
        f=open("deepspam2.res","at")
        f.write("%3d%%: %s\n"%(res,tokens))
        f.close()
    except:
        pass
    if res<2:
        return "ham %d%%"%(res)
    if res<10:
        return "maybeham %d%%"%(res)
    if res<20:
        return "20ham %d%%"%(res)
    if res>98:
        return "spam %d%%"%(res)
    if res>90:
        return "maybespam %d%%"%(res)
    if res>80:
        return "80spam %d%%"%(res)
    return "dunno %d%%"%(res)

############################################################################################################################################

class MyHandler(ppymilterbase.PpyMilter):

#    def __init__(self):
#        print("MyHandler.init!")
#        ppymilterbase.PpyMilter.__init__(self)
#        super().__init__()
#        CanChangeHeaders(self)

    def __init__(self,context=None):
        self.addr=context
#        print("MyHandler.init!  ip="+str(context))
        super().__init__()

    def OnOptNeg(self, cmd, ver, actions, protocol):
        self.CanAddHeaders()
        self.emlcount=0
        self.t=0
#        self.mailfrom = ""
        return super().OnOptNeg(cmd, ver, actions, protocol)

    def OnConnect(self, cmd, hostname, family, port, address):
#        print(hostname)
#        print(address)
        print("---  %22s  address: %s"%(self.addr,str(address)))
        self.mailfrom = address
        return self.Continue()

    def OnHelo(self, cmd, data):
#        print(data)
        return self.Continue()

    def OnResetState(self):
#        print("ResetState called!!!")
        self.fp = None
        self.bodysize = 0
        self.reject=0

    def OnMailFrom(self, cmd, addr, esmtp_info):
        self.OnResetState()
        self.mailfrom = addr
        print("---  %22s  sender: %s"%(self.addr,str(addr)))
#        print(addr)
#        print(esmtp_info)
        return self.Continue()

    def OnRcptTo(self, cmd, addr, esmtp_info):
#        print(addr)
#        print(esmtp_info)
        return self.Continue()

    def OnHeader(self, cmd, hdr, data):
        if hdr==b'X-Grey-ng' or hdr==b'From':
            print("---  %22s  %s: %s"%(self.addr,hdr.decode(),str(data)))
        if hdr==b'X-Grey-ng' and data[0:6]==b'REJECT':
            self.reject=1
#        if self.fp:
        if not self.fp:
            self.fp = BytesIO()
            self.emlcount+=1
        self.fp.write(hdr+b': '+data+b'\n')
#        print(hdr)
#        print(data)
        return self.Continue()

    def OnEndHeaders(self, cmd):
        self.fp.write(b'\n')
        return self.Continue()

    def OnBody(self, cmd, data):
#        print(len(data))
#        print(type(data))
        self.fp.write(data)
        self.bodysize += len(data)
        return self.Continue()

    def OnEndBody(self, cmd):
         if not self.fp:
             return self.ReturnOnEndBodyActions([self.Accept()])
         t=time.time()
         self.fp.seek(0)
         res=do_eml(self.fp.read(),self.addr)
         self.t=time.time()-t
         h=[]
         h.append(self.AddHeader('X-deepspam', res))
         h.append(self.Accept())
         return self.ReturnOnEndBodyActions(h)

##    def __del__(self):
#        print("__del__ called!")
#        global thread_cnt
#        thread_cnt-=1
##        print("__del__ called!     processed: %d (%5.3f)  from: %s"%(self.emlcount,self.t,self.mailfrom))



thread_cnt=0

async def handle_milter(reader, writer):

    global thread_cnt
    thread_cnt+=1
    t0=time.time()

    addr = writer.get_extra_info('peername')
    addrs=str(addr[0])+":"+str(addr[1])
    print('%3d  %22s  Connect'%(thread_cnt, addrs) )

    milter_dispatcher = ppymilterbase.PpyMilterDispatcher(MyHandler,context=addrs)

    while True:
      try:
#        print("# waiting...")
        data = await reader.readexactly(4)
        packetlen = int(struct.unpack('!I', data)[0])
#        print("# pktlen=",packetlen)
        data = await reader.readexactly(packetlen)
#        print("# len(data)=",len(data))
        response = milter_dispatcher.Dispatch(data)
        if response:
          if type(response) != list: response=[response]
          for r in response:
            if isinstance(r, str): r=r.encode()
#            print("# len(response)=",len(r))
            writer.write(struct.pack('!I', len(r))+r)
            await writer.drain()
#      except ppymilterbase.PpyMilterCloseConnection as e:
#        print("ppymilterbase.PpyMilterCloseConnection!!!")
#        break # close
      except Exception as ex:
#        print("Exception!!!",traceback.format_exc())
        print("Exception!!!",repr(ex))
        break

#    print("# Close the connection")
    writer.close()
    await writer.wait_closed()

    t=time.time()-t0
    thread_cnt-=1
    print('%3d  %22s  Done   %6.3fs'%(thread_cnt+1, addrs, t ))


async def main():
    server = await asyncio.start_server(handle_milter, '127.0.0.1', 1080)

    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    print(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()


logging.basicConfig(level=logging.DEBUG,
                      format='%(asctime)s %(levelname)s %(message)s',
                      datefmt='%Y-%m-%d@%H:%M:%S')

asyncio.run(main())

