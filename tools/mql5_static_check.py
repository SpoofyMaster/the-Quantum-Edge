"""Mechanical (non-compiler) check of the MQL5 sources: bracket balance outside strings/comments, include
resolution, and function names that are neither defined in the sources nor MQL5 built-ins / CTrade methods.
Usage: python tools/mql5_static_check.py mql5/VideoStrategyEA"""
import re,sys,glob,os
def strip(src):
    out=[];i=0;n=len(src)
    while i<n:
        if src.startswith('//',i):
            j=src.find('\n',i); i=n if j<0 else j
        elif src.startswith('/*',i):
            j=src.find('*/',i); i=n if j<0 else j+2
        elif src[i]=='"':
            j=i+1
            while j<n and src[j]!='"':
                j+= 2 if src[j]=='\\' else 1
            out.append('""'); i=j+1
        elif src[i]=="'":
            j=i+1
            while j<n and src[j]!="'":
                j+= 2 if src[j]=='\\' else 1
            out.append("' '"); i=j+1
        else:
            out.append(src[i]); i+=1
    return ''.join(out)
ok=True
root = sys.argv[1] if len(sys.argv) > 1 else "."
os.chdir(root)
files=glob.glob("*.mq5")+glob.glob("include/*.mqh")
allsrc=''
for f in files:
    s=strip(open(f).read()); allsrc+=s
    st=[]
    for ln,line in enumerate(s.split('\n'),1):
        for ch in line:
            if ch in '({[': st.append((ch,ln))
            elif ch in ')}]':
                if not st or {'(':')','{':'}','[':']'}[st[-1][0]]!=ch:
                    print(f,'unbalanced',ch,'line',ln); ok=False; st=[]; break
                st.pop()
    if st: print(f,'unclosed',st[-3:]); ok=False
    for m in re.finditer(r'#include\s+"([^"]+)"',open(f).read()):
        p=os.path.normpath(os.path.join(os.path.dirname(f),m.group(1)))
        if not os.path.exists(p): print(f,'missing include',p); ok=False
# identifiers called as functions/methods that are not defined anywhere and not MQL5 builtins
calls=set(re.findall(r'\b([A-Z][A-Za-z0-9_]*)\s*\(',allsrc))
defined=set(re.findall(r'\b(?:class|struct|enum)\s+([A-Za-z_]\w*)',allsrc))
defined|=set(re.findall(r'\b[A-Za-z_][\w*&\s]*?\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:const\s*)?(?::[^{;]*)?\{',allsrc))
builtin=set('''ArrayResize ArraySort ArraySize ArraySetAsSeries CopyRates SymbolSelect SymbolInfoDouble SymbolInfoInteger SymbolInfoTick
AccountInfoDouble AccountInfoInteger MathMax MathMin MathAbs MathFloor MathCeil MathLog MathLog10 MathExp MathRound MathIsValidNumber
NormalizeDouble StructToTime TimeToStruct TimeToString TimeCurrent ZeroMemory GetLastError IntegerToString DoubleToString StringFormat
StringFind PrintFormat Print FileOpen FileSize FileSeek FileWriteString FileClose ObjectFind ObjectCreate ObjectMove ObjectSetInteger
ObjectSetString ObjectsDeleteAll PositionsTotal PositionGetTicket PositionGetString PositionGetInteger OrdersTotal OrderGetTicket
OrderGetString OrderGetInteger OrderGetDouble OrderSelect OrderCalcMargin HistoryDealSelect HistoryDealGetInteger HistoryDealGetString
HistoryDealGetDouble HistorySelectByPosition HistoryDealsTotal HistoryDealGetTicket GetPointer EnumToString MQLInfoInteger iTime
'''.split())
ctrade=set('SetExpertMagicNumber SetDeviationInPoints SetTypeFillingBySymbol SetMarginMode LogLevel Buy Sell BuyLimit SellLimit OrderModify OrderDelete PositionClose ResultRetcode ResultRetcodeDescription ResultOrder'.split())
unknown=sorted(c for c in calls-defined-builtin-ctrade if not c.isupper())
print('possibly undefined:',unknown)
print('balance ok' if ok else 'PROBLEMS')
sys.exit(0 if ok and not unknown else 1)
