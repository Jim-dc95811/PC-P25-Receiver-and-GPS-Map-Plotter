import numpy as np, wave
from scipy.signal import resample_poly
from math import gcd
# ---- OP25 BCH(63,16) tables + decoder, ported verbatim ----
GFexp=[1,2,4,8,16,32,3,6,12,24,48,35,5,10,20,40,19,38,15,30,60,59,53,41,17,34,7,14,28,56,51,37,9,18,36,11,22,44,27,54,47,29,58,55,45,25,50,39,13,26,52,43,21,42,23,46,31,62,63,61,57,49,33,0]
GFlog=[-1,0,1,6,2,12,7,26,3,32,13,35,8,48,27,18,4,24,33,16,14,52,36,54,9,45,49,38,28,41,19,56,5,62,25,11,34,31,17,47,15,23,53,51,37,44,55,40,10,61,46,30,50,22,39,43,29,60,42,21,20,59,57,58]
def bchDec(cw):   # cw: list>=63 bits; corrects in place; returns #errs or <0
    S=[0]*23; SynError=0
    for i in range(1,23):
        s=0
        for j in range(63):
            if cw[j]: s^=GFexp[(i*j)%63]
        if s: SynError=1
        S[i]=GFlog[s]
    if not SynError: return 0
    elp=[[0]*22 for _ in range(24)]; D=[0]*23; L=[0]*24; uLu=[0]*24
    L[0]=0;uLu[0]=-1;D[0]=0;elp[0][0]=0
    L[1]=0;uLu[1]=0;D[1]=S[1];elp[1][0]=1
    for i in range(1,22): elp[0][i]=-1; elp[1][i]=0
    U=0
    while True:
        U+=1
        if D[U]==-1:
            L[U+1]=L[U]
            for i in range(L[U]+1): elp[U+1][i]=elp[U][i]; elp[U][i]=GFlog[elp[U][i]]
        else:
            q=U-1
            while D[q]==-1 and q>0: q-=1
            if q>0:
                j=q
                while True:
                    j-=1
                    if D[j]!=-1 and uLu[q]<uLu[j]: q=j
                    if j<=0: break
            L[U+1]=L[U] if L[U]>L[q]+U-q else L[q]+U-q
            for i in range(22): elp[U+1][i]=0
            for i in range(L[q]+1):
                if elp[q][i]!=-1: elp[U+1][i+U-q]=GFexp[(D[U]+63-D[q]+elp[q][i])%63]
            for i in range(L[U]+1): elp[U+1][i]^=elp[U][i]; elp[U][i]=GFlog[elp[U][i]]
        uLu[U+1]=U-L[U+1]
        if U<22:
            D[U+1]=GFexp[S[U+1]] if S[U+1]!=-1 else 0
            for i in range(1,L[U+1]+1):
                if S[U+1-i]!=-1 and elp[U+1][i]!=0: D[U+1]^=GFexp[(S[U+1-i]+GFlog[elp[U+1][i]])%63]
            D[U+1]=GFlog[D[U+1]]
        if not (U<22 and L[U+1]<=11): break
    U+=1
    if L[U]<=11:
        for i in range(L[U]+1): elp[U][i]=GFlog[elp[U][i]]
        reg=[0]*12
        for i in range(1,L[U]+1): reg[i]=elp[U][i]
        count=0; locn=[0]*11
        for i in range(1,64):
            q=1
            for j in range(1,L[U]+1):
                if reg[j]!=-1: reg[j]=(reg[j]+j)%63; q^=GFexp[reg[j]]
            if q==0: locn[count]=63-i; count+=1
        if count==L[U]:
            for i in range(L[U]): cw[locn[i]]^=1
            return count
        return -1
    return -2
def nid_codeword(acc):  # acc=64-bit int MSB-first; returns (nac,duid,ec)
    acc_parity=acc&1; a=acc; cw=[0]*64
    for i in range(64): a>>=1; cw[i]=a&1
    ec=bchDec(cw)
    acc2=0
    for i in range(63,-1,-1): acc2|=cw[i]; acc2<<=1
    acc2|=acc_parity
    return (acc2>>52)&0xfff,(acc2>>48)&0xf,ec
