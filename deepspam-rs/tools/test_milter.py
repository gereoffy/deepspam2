#!/usr/bin/env python3
"""Exercise a real local Rust milter against the unchanged Python do_eml()."""
import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
import argparse
import ast
import concurrent.futures
import contextlib
import io
from pathlib import Path
import re
import select
import socket
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


class Client:
    def __init__(self, address):
        self.socket = socket.create_connection(address,timeout=10)
        self.socket.settimeout(10)

    def exact(self,size):
        result=b""
        while len(result)<size:
            part=self.socket.recv(size-len(result))
            if not part:
                raise EOFError("milter closed the connection")
            result+=part
        return result

    def send(self,packet,fragment=False):
        frame=struct.pack("!I",len(packet))+packet
        if fragment:
            for byte in frame:
                self.socket.sendall(bytes([byte]))
        else:
            self.socket.sendall(frame)

    def receive(self):
        size=struct.unpack("!I",self.exact(4))[0]
        return self.exact(size)

    def negotiate(self):
        self.send(b"O"+struct.pack("!III",6,0x1ff,0xffffffff),True)
        assert self.receive()==b"O"+struct.pack("!III",2,1,15)

    def message(self,headers,body,fragment=False):
        for name,value in headers:
            self.send(b"L"+name+b"\0"+value+b"\0",fragment)
            assert self.receive()==b"c"
        self.send(b"N");assert self.receive()==b"c"
        for start in range(0,len(body),17):
            self.send(b"B"+body[start:start+17]);assert self.receive()==b"c"
        self.send(b"E")
        header=self.receive();assert self.receive()==b"a"
        return header

    def close(self):
        self.send(b"Q");self.socket.close()


def ready(proc):
    deadline=time.monotonic()+20
    lines=[]
    while time.monotonic()<deadline:
        if select.select([proc.stderr],[],[],0.1)[0]:
            line=proc.stderr.readline()
            lines.append(line)
            match=re.search(r"Serving on 127\.0\.0\.1:(\d+)",line)
            if match:
                return ("127.0.0.1",int(match[1]))
            if not line and proc.poll() is not None:
                break
    raise RuntimeError("milter startup failed: "+"".join(lines))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary",type=Path,default=ROOT/"deepspam-rs/target/release/deepspam4")
    args=p.parse_args()
    from eml2str import eml2str
    from model import DeepSpam
    with contextlib.redirect_stdout(io.StringIO()):
        model=DeepSpam(str(ROOT/"model")+"/")
    # Extract just the original function. Importing deepspam4.py would start a server.
    tree=ast.parse((ROOT/"deepspam4.py").read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="do_eml")
    namespace={"time":time,"ds":model,"eml2str":eml2str,"res_cache":{},"print":lambda *a,**kw:None,"open":lambda *a,**kw:io.StringIO()}
    exec(compile(ast.Module(body=[function],type_ignores=[]),"deepspam4.py", "exec"),namespace)
    fixtures=[
        ([(b"Subject",b"Hello world"),(b"Content-Type",b"text/plain; charset=utf-8")],
         "Simple test email. Árvíztűrő tükörfúrógép. März Straße русский текст.".encode()),
        ([(b"Subject",b"=?UTF-8?Q?M=C3=A4rz_Stra=C3=9Fe?="),(b"Content-Type",b"text/html; charset=utf-8")],
         b"<html><body><style>hidden{}</style><p>Hello &amp; goodbye.</p><div style='display:none'>invisible</div></body></html>"),
        ([(b"Subject",b"Multipart"),(b"Content-Type",b"multipart/alternative; boundary=example")],
         b"--example\r\nContent-Type: text/plain\r\n\r\nNormal text for testing the email classification pipeline.\r\n--example\r\nContent-Type: text/html\r\n\r\n<p>Normal text for testing the email classification pipeline.</p>\r\n--example--\r\n"),
        ([],b"No headers: an ordinary text body without a subject."),
    ]
    expected=[]
    for headers,body in fixtures:
        raw=b"".join(k+b": "+v+b"\n" for k,v in headers)+b"\n"+body
        with contextlib.redirect_stdout(io.StringIO()):
            value=namespace["do_eml"](raw,"test")
        expected.append(b"hX-deepspam\0"+value+b"\0")
    with tempfile.TemporaryDirectory(prefix="deepspam-milter-test-") as tmp:
        log=Path(tmp)/"results.res"
        proc=subprocess.Popen([str(args.binary),"--model-dir",str(ROOT/"model"),"--listen","127.0.0.1:0",
                               "--workers","2","--cache-entries","16","--res-log",str(log),
                               "--max-message-bytes","4096","--max-frame-bytes","65536"],
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            address=ready(proc)
            c=Client(address);c.negotiate()
            c.send(b"DCignored\0value\0");c.send(b"C");assert c.receive()==b"c"
            c.send(b"Lstale\0header\0");assert c.receive()==b"c"
            c.send(b"Bdiscarded");assert c.receive()==b"c"
            c.send(b"A")
            for fixture,target in zip(fixtures,expected):
                assert c.message(*fixture,fragment=True)==target
            # Recycle the same connection after QUIT_NC and verify cache hits.
            c.send(b"K")
            for fixture,target in zip(fixtures,expected):
                assert c.message(*fixture)==target
            c.close()
            def concurrent_request(i):
                c=Client(address);c.negotiate()
                result=c.message(*fixtures[i%len(fixtures)])
                c.close()
                assert result==expected[i%len(fixtures)]
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(concurrent_request,range(12)))
            # Reject bad length, malformed header, and oversized/truncated input.
            for payload in [struct.pack("!I",65537), struct.pack("!I",0),
                            struct.pack("!I",4)+b"Lbad",struct.pack("!I",4098)+b"B"+b"x"*4097,
                            struct.pack("!I",5)+b"B"]:
                c=Client(address);c.socket.sendall(payload);c.socket.shutdown(socket.SHUT_WR)
                assert c.socket.recv(1)==b"";c.socket.close()
            rows=log.read_text().splitlines()
            assert len(rows)==len(fixtures),"cache hit must not be logged again"
            assert all(re.match(r"^\s*\d+%: ",row) for row in rows)
            print("PASS: 20 classifications match Python; negotiation, fragmented frames, macros, abort, message reuse, cache, concurrent clients, logging and 5 invalid-input cases")
        finally:
            proc.terminate()
            try:
                stdout,stderr=proc.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill();stdout,stderr=proc.communicate();raise
        assert proc.returncode==0,(proc.returncode,stderr)


if __name__=="__main__":
    main()
