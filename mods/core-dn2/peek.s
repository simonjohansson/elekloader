// SPDX-License-Identifier: GPL-2.0-or-later
// DN2 OS 1.12 DSP peek: the end of the block handler (PC16 0x1c9e5f) answers the ColdFire's
// request with one halfword of DSP memory per block, in reply word 2, which stock never writes.
// The request is in the frame's tail (byte 0xa80), four DSP words:
//   magic 0xd5ee | seq << 16, address, count (words, 1..1024), check (the three xor 0x5a5a5a5a).
// The answer is tag << 16 | halfword, the tag (seq & 15) << 12 | the halfword's index; the index
// 0xfff refuses the request (no read has that many halfwords), 0 means none. Halfwords repeat
// from the first after the last.
// R1, R2, I4 and I6 are live here; R10, R11, R13..R15, I2 and I3 are the handler's, reloaded
// by its epilogue, so this uses only those. State: the last seq at 0x2e0600, the cursor at 0x2e0604.
// Right shifts take their count from a register: this Selache pin encodes a negative immediate
// count without its sign extension, which halts a real DSP (the emulator runs it).
.SECTION/SW seg_swco;
.GLOBAL dn2_peek_entry;
dn2_peek_entry:
DM(0x268a38)=R1;            // the store the hook displaced
R10=DM(-3,I6);              // the frame the handler received
R11=0xa80;
R10=R10+R11;
I2=R10;
R13=DM(0,I2);
R11=0xffff;
R11=R13 AND R11;
R14=0xd5ee;
COMP(R11,R14);
IF NE JUMP idle;
R14=DM(1,I2);               // address
R15=DM(2,I2);               // words
R10=R13 XOR R14;
R10=R10 XOR R15;
R11=0x5a5a5a5a;
R10=R10 XOR R11;
R11=DM(3,I2);
COMP(R10,R11);
IF NE JUMP idle;
// A new seq starts from its first halfword.
R11=-16;
R10=LSHIFT R13 BY R11;
R11=DM(0x2e0600);
COMP(R10,R11);
IF EQ JUMP same;
DM(0x2e0600)=R10;
R11=0;
DM(0x2e0604)=R11;
same:
// 1..1024 aligned words, all inside one readable L1 or L2 range.
R11=R15-1;
R13=1023;
COMPU(R11,R13);
IF GT JUMP refuse;
R11=3;
R11=R14 AND R11;
IF NE JUMP refuse;
R11=LSHIFT R15 BY 2;
R11=R11+R14;                // the end
R13=0x240000;
COMPU(R14,R13);
IF LT JUMP refuse;
R13=0x270000;
COMPU(R11,R13);
IF LE JUMP readable;
R13=0x2c0000;
COMPU(R14,R13);
IF LT JUMP refuse;
R13=0x2ec000;               // L1 block 1, below its cache
COMPU(R11,R13);
IF LE JUMP readable;
R13=0x300000;
COMPU(R14,R13);
IF LT JUMP refuse;
R13=0x31c000;               // L1 block 2, below its cache
COMPU(R11,R13);
IF LE JUMP readable;
R13=0x380000;
COMPU(R14,R13);
IF LT JUMP refuse;
R13=0x39c000;               // L1 block 3, below its cache
COMPU(R11,R13);
IF LE JUMP readable;
R13=0x20000000;
COMPU(R14,R13);
IF LT JUMP refuse;
R13=0x200fa000;             // L2, below the special window
COMPU(R11,R13);
IF GT JUMP refuse;
readable:
R13=DM(0x2e0604);           // the halfword index
R11=-1;
R11=LSHIFT R13 BY R11;
R11=LSHIFT R11 BY 2;
R11=R11+R14;
I3=R11;
R11=DM(0,I3);
BTST R13 BY 0;
IF SZ JUMP low;
R14=-16;
R11=LSHIFT R11 BY R14;
low:
R14=0xffff;
R11=R11 AND R14;
R14=0xf;
R14=R10 AND R14;
R14=LSHIFT R14 BY 12;
R14=R14 OR R13;
R14=LSHIFT R14 BY 16;
R14=R14 OR R11;
DM(2,I4)=R14;
R13=R13+1;
R11=LSHIFT R15 BY 1;
COMP(R13,R11);
IF LT JUMP next;
R13=0;
next:
DM(0x2e0604)=R13;
JUMP 0x1c9e62;
refuse:
R14=0xf;
R14=R10 AND R14;
R14=LSHIFT R14 BY 12;
R13=0xfff;
R14=R14 OR R13;
R14=LSHIFT R14 BY 16;
DM(2,I4)=R14;
JUMP 0x1c9e62;
idle:
R14=0;
DM(2,I4)=R14;
JUMP 0x1c9e62;
.ENDSEG;
