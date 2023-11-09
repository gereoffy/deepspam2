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
import logging
import struct
import time
import traceback

from io import BytesIO

############################################################################################################################################

from eml2str import eml2str

from model import DeepSpam
ds=DeepSpam()


def do_eml(msg,addr):
    t=time.time()
    text=eml2str(msg,True) # extract subject,bodytext
    tokens=ds.tokenized([text])[0]
    print(tokens[:160])
    res=ds(text)
    t=time.time()-t
    print("---  %22s  result: %8.5f  (%5.3f ms)"%(addr,res,1000*t))
    if res<0: return b"toosmall"
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
        return b"ham %d%%"%(res)
    if res<10:
        return b"maybeham %d%%"%(res)
    if res<20:
        return b"20ham %d%%"%(res)
    if res>98:
        return b"spam %d%%"%(res)
    if res>90:
        return b"maybespam %d%%"%(res)
    if res>80:
        return b"80spam %d%%"%(res)
    return b"dunno %d%%"%(res)

############################################################################################################################################



milterinfo={
    b'A': "Abort",
    b'B': "Body chunk",
    b'C': "Connection information",
    b'D': "Define macro",
    b'E': "final body chunk (End)",
    b'H': "HELO/EHLO",
    b'L': "Header",
    b'M': "MAIL from",
    b'N': "EOH",
    b'O': "Option negotation",
    b'R': "RCPT to",
    b'Q': "QUIT",
    b'T': "DATA",
    b'U': "Unknown cmd",
    b'+': "add recipient",
    b'-': "remove recipient",
    b'a': "accept",
    b'b': "replace body (chunk)",
    b'c': "continue",
    b'd': "discard",
    b'f': "cause a connection failure",
    b'h': "add header",
    b'i': "insert header",
    b'm': "change header",
    b'p': "progress",
    b'q': "quarantine",
    b'r': "reject",
    b's': "set-sender",
    b't': "tempfail",
    b'y': "reply code etc" }



thread_cnt=0
thread_id=1000000000

async def handle_milter(reader, writer):

    global thread_id
    myid=(thread_id:=thread_id+1)

    global thread_cnt
    thread_cnt+=1
    t0=time.time()

    history=[]
    eml=[]

    addr = writer.get_extra_info('peername')
    addrs=str(addr[0])+":"+str(addr[1])
    print('%d[%3d]  %22s  Connect'%(myid,thread_cnt, addrs) )

    while True:
      try:
#        print("# waiting...")
        data = await reader.readexactly(4)
        packetlen = int(struct.unpack('!I', data)[0])
#        print("# pktlen=",packetlen)
        data = await reader.readexactly(packetlen)
        cmd=data[:1]
        if cmd==b'D': continue # ignore macros
        history.append(cmd)

#        print(myid,"#data(%d)={%s}"%(len(data),milterinfo.get(cmd,"???")),data[:64])

        if cmd==b'Q': # 'Q'     SMFIC_QUIT      Quit milter communication
            break     #                         Expected response:  Close milter connection

        if cmd==b'A': # 'A'     SMFIC_ABORT     Abort current filter checks   Expected response:  NONE
            eml=[] # reset                      Resets internal state of milter program to before SMFIC_HELO
            continue

        # https://github.com/phalaaxx/milter/blob/master/milter-protocol.txt
        response=[b'c'] if cmd in b'BCEHLMNR' else []  # Expected response:  Accept/reject action

        if cmd==b'O': # 'O'     SMFIC_OPTNEG    Option negotiation             Expected response:  SMFIC_OPTNEG packet
            response=[b'O\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00\x00'] #    version=2  actions=1  proto=0

        # capture headers:
        if cmd==b'L': # 'L'     SMFIC_HEADER    Mail header
            hdr=data[1:].split(b'\x00')
            eml.append(hdr[0]+b': '+hdr[1]+b'\n')
        if cmd==b'N': # 'N'     SMFIC_EOH       End of headers marker
            eml.append(b'\n')

        # capture body:
        if cmd==b'B': # 'B'     SMFIC_BODY      Body chunk
            eml.append(data[1:]) # Up to MILTER_CHUNK_SIZE (65535) bytes
        if cmd==b'E': # 'E'     SMFIC_BODYEOB   End of body marker
            # response=[b'a',b'c'] # Expected response:  Zero or more modification actions, then accept/reject action
            # 'h' SMFIR_ADDHEADER Add header (modification action)
            # 'a' SMFIR_ACCEPT    Accept message completely (accept/reject action)
            ret=do_eml(b''.join(eml),addrs)
            response=[b'hX-deepspam\x00'+ret+b'\x00',b'a']
            eml=[] # reset

        for r in response:
            writer.write(struct.pack('!I', len(r))+r)
            cmd=r[:1]
            history.append(cmd)
#            print(myid,"#resp(%d)={%s}"%(len(r),milterinfo.get(cmd,"???")),r[:64])
            await writer.drain()

      except Exception as ex:
        print(myid,"Exception!!!",repr(ex))
        break

    writer.close()
    await writer.wait_closed()

    t=time.time()-t0
    print('%d[%3d]  %22s  Done   %6.3fs  cmds:'%(myid,thread_cnt, addrs, t ),b''.join(history))
    thread_cnt-=1


async def main():
    server = await asyncio.start_server(handle_milter, '127.0.0.1', 1081)

    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    print(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()


logging.basicConfig(level=logging.DEBUG,
                      format='%(asctime)s %(levelname)s %(message)s',
                      datefmt='%Y-%m-%d@%H:%M:%S')

asyncio.run(main())

