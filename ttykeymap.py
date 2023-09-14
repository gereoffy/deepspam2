
import sys
import fcntl
import termios
from os import get_terminal_size

class NonBlockingInput(object):

    def __enter__(self):
        # canonical mode, no echo
        self.old = termios.tcgetattr(sys.stdin)
        new = termios.tcgetattr(sys.stdin)
        new[3] = new[3] & ~(termios.ICANON | termios.ECHO)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new)

#        # set for non-blocking io
#        self.orig_fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
#        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, self.orig_fl | os.O_NONBLOCK)

    def __exit__(self, *args):
        print("restore terminal to previous state")
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old)
#        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, self.orig_fl)


keymap={
#    b'\x1b': "esc",
    b'\x1b\x1b': "a+esc",

    b'\x08': "bs", # backspace
    b'\t': "tab",
    b'\n': "enter",
    b'\x7f': "s+bs",
    b'\x1b\x7f': "a+bs",

    b'\x1b[Z': "s+tab",
    b'\x1b\t': "a+tab",
    b'\x1b\n': "a+enter",

    b'\x1bOA': "up",
    b'\x1bOB': "down",
    b'\x1bOC': "right",
    b'\x1bOD': "left",

    b'\x1bO2A': "s+up",
    b'\x1bO2B': "s+down",
    b'\x1bO2C': "s+right",
    b'\x1bO2D': "s+left",
    
    b'\x1b[1;9A': "a+up",
    b'\x1b[1;9B': "a+down",
    b'\x1b[1;9C': "a+right",
    b'\x1b[1;9D': "a+left",

    b'\x1b[1~': "home",
    b'\x1b[2~': "ins",
    b'\x1b[3~': "del",
    b'\x1b[4~': "end",
    b'\x1b[5~': "pgup",
    b'\x1b[6~': "pgdn",

    b'\x1b[7$': "s+home",
    b'\x1b[8$': "s+end",
    b'\x1b[2;2~': "s+ins",
    b'\x1b[3;2~': "s+del",
    b'\x1b[5;2~': "s+pgup",
    b'\x1b[6;2~': "s+pgdn",
    
    b'\x1b[7^':   "c+home",
    b'\x1b[8^':   "c+end",
    b'\x1b[2;5~': "c+ins",
    b'\x1b[3;5~': "c+del",
    b'\x1b[5;5~': "c+pgup",
    b'\x1b[6;5~': "c+pgdn",
    
    b'\x1b\x1b[5~': "a+pgup",
    b'\x1b\x1b[6~': "a+pgdn",
    b'\x1b[1;9H': "a+home",
    b'\x1b[1;9F': "a+end",
    
    b'\x1b[11~': "f1",
    b'\x1b[12~': "f2",
    b'\x1b[13~': "f3",
    b'\x1b[14~': "f4",
    b'\x1b[15~': "f5",
    b'\x1b[17~': "f6",
    b'\x1b[18~': "f7",
    b'\x1b[19~': "f8",
    b'\x1b[20~': "f9",
    b'\x1b[21~': "f10",

    b'\x1b[23~': "s+f1",
    b'\x1b[24~': "s+f2",
    b'\x1b[25~': "s+f3",
    b'\x1b[26~': "s+f4",
    b'\x1b[28~': "s+f5",
    b'\x1b[29~': "s+f6",
    b'\x1b[31~': "s+f7",
    b'\x1b[32~': "s+f8",
    b'\x1b[33~': "s+f9",
    b'\x1b[34~': "s+f10",

    b'\x1b1': "f1", # ALT+1
    b'\x1b2': "f2", # ALT+2
    b'\x1b3': "f3",
    b'\x1b4': "f4",
    b'\x1b5': "f5",
    b'\x1b6': "f6",
    b'\x1b7': "f7",
    b'\x1b8': "f8",
    b'\x1b9': "f9",
    b'\x1b0': "f10",# ALT+0

}

# INIT:
#sys.stdin = sys.stdin.detach()
#sys.stdin = sys.stdin.detach() # 2x kell!!!
#term_w,term_h=os.get_terminal_size(0)

utf8_lengths=[ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,   0, 0, 0, 0, 0, 0, 0, 0,   2, 2, 2, 2,   3, 3, 4, 0 ]
chbuffer=b''

def getch2():
    global chbuffer
    ch=chbuffer
    if len(ch)<1 or ch==b'\x1b': ch+=sys.stdin.read(256)
#    ch=sys.stdin.read(8)
#    print(ch)
    if not ch: return ""

    i=ch.find(b'\x1b',1) # tobb kod egyben?
    if i>1:
        chbuffer=ch[i:]
        ch=ch[:i]
    else:
        chbuffer=b''

    if ch[0] in [27,8,9,10,127]: # ESC & control keys
        if ch in keymap: return keymap[ch]  #  egyszeru eset :)
        for k in keymap:
            if ch.startswith(k):
                chbuffer=ch[len(k):]+chbuffer
                return keymap[k]
        # unknown ESC code
        print(ch)
        #chbuffer=ch[1:]+chbuffer
        #if ch==b'\x1b':
        return "esc"

    # UTF-8?
    l=utf8_lengths[ch[0]>>3]
    if l<=1: # ascii/control
        chbuffer=ch[1:]+chbuffer
        return chr(ch[0])
#    if len(ch)<l:
#        print("[not enough bytes]")
#        chbuffer=ch+chbuffer
#        return ""
    chbuffer=ch[l:]+chbuffer
    return ch[:l].decode("utf-8",errors="backslashreplace")


def clrscr():
    print('\x1b[2J') # erase

def putchar(c):
    sys.stdout.write(c)

def gotoxy(x,y):
    putchar("\x1B[%d;%df"%(y,x))

def set_color(x):
    putchar("\x1B[%dm"%(x))

#void textcolor(int x){set_color(x+30);}         /* Beallitja a betuszint     */
#void backgcolor(int x){set_color(x+40);}        /* Beallitja a hatterszint   */

def draw_box(x1,y1,xs,ys):
#  keret=['+','-','+','|','|','+','-','+'] # FIXME
  keret=['┏','━','┓','┃','┃','┗','━','┛']
#  keret=['╔','═','╗','║','║','╚','═','╝']
  set_color(7)
  gotoxy(x1,y1)
  putchar(keret[0]+keret[1]*xs+keret[2])
  for i in range(y1+1,y1+ys):
    gotoxy(x1,i)
    putchar(keret[3]+" "*xs+keret[4])
  gotoxy(x1,y1+ys)
  putchar(keret[5]+keret[6]*xs+keret[7])
#  set_color(0)
  sys.stdout.flush()

def box_message(texts,extra=2,y=-1):
  term_xs,term_ys=get_terminal_size(0)
#  xs=max(len(t1),len(t2))
  xs=max(len(s) for s in texts)
  x1=(term_xs-xs-10)//2
#  y1=(term_ys-10)//2
  y1=(term_ys-len(texts))//2-2
  draw_box(x1,y1,xs+2*extra, 1+len(texts))
  while True:
    for i in range(len(texts)):
      gotoxy(x1+extra+1,y1+1+i)
      set_color(0 if y==i else 7)
      print("%*s"%(-xs,texts[i]))
    if y<0: return # not menu mode
    gomb=getch2()
    if gomb=="enter" or gomb=="f3": return y # select
    if gomb=="esc" or gomb=='q': return -1   # quit
    if gomb=="home" or gomb=="pgup": y=0
    if gomb=="up" and y>0: y-=1
    if gomb=="down" and y<len(texts)-1: y+=1
    if gomb=="end" or gomb=="pgdn": y=len(texts)-1


def tty_input(x0,y0,xs,sor=""):
  xbase=0
  x=0
  fl1=0
#  sor=+" "*(1024-len(hova))
  while True:
#    gotoxy(1,1);printf("%d/%d (%d) ",x,xs,strlen(sor)); // debug
    gotoxy(x0,y0)
    putchar("%-*.*s"%(xs,xs,sor[xbase:]))
    gotoxy(x0+x,y0)
    sys.stdout.flush()
    gomb=getch2()
    if gomb=="enter": return sor
    if gomb=="esc": return None
    if len(gomb)==1: # insert char
        if not fl1: sor=gomb
        else: sor=sor[:x+xbase]+gomb+sor[x+xbase:] #   memmove(sor+x+xbase+1,sor+x+xbase,strlen(sor)-x-xbase+1);
        gomb="right" # trick
    fl1=1
    if (gomb=="bs") and (x+xbase>0):  # backspace
        sor=sor[:x+xbase-1]+sor[x+xbase:]  #    memmove(sor+x+xbase-1,sor+x+xbase,strlen(sor)-x-xbase+1);
        gomb="left" # trick
    if gomb=="left":
        if x>0: x-=1
        elif xbase>0: xbase-=1
    if gomb=="home": x=xbase=0
    if gomb=="end":
        x=len(sor)
        if x>=xs-1:
            x=xs-1
            xbase=len(sor)-x
    if gomb=="right" and x+xbase<len(sor):
        if x>=xs-1: xbase+=1
        else: x+=1
    if gomb=="del" and x+xbase<len(sor):
        sor=sor[:x+xbase]+sor[x+xbase+1:]  #    memmove(sor+x+xbase,sor+x+xbase+1,strlen(sor)-x-xbase+1);

def box_input(y1=0,xs=0,t1="",sor=""):
  term_xs,term_ys=get_terminal_size(0)
  if xs==0: xs=term_xs//3
  x1=(term_xs-xs-10)//2
  if y1==0: y1=(term_ys-10)//2
  draw_box(x1,y1,xs+6,5)
  gotoxy(x1+4,y1+1)
  putchar(t1)
  set_color(0)
  return tty_input(x1+4,y1+3,xs,sor)


if __name__ == "__main__":

  sys.stdin = sys.stdin.detach()
  sys.stdin = sys.stdin.detach()
#  term_w,term_h=os.get_terminal_size(0)
#  print(term_w,term_h,sys.stdin.isatty())
#  clrscr()

#  box_message("The Block Elements Unicode block includes shading characters. 32 characters are included in the block.","laxy foxzy")

  with NonBlockingInput():

#    draw_box(30,10,50,6)
#    tty_input(35,12,40,sor="Hello")
#    box_input(0,0,"Search:","Hello")

    while True:
        ch=getch2()
        print(ch,len(chbuffer))
