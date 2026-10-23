// SPDX-License-Identifier: GPL-2.0-or-later
// Synthetic caller only: R4 argument, I12 function, explicit software frame.
.SECTION/SW seg_swco;
.GLOBAL probe_call;
.GLOBAL probe_returned;
probe_call:
    R2=I6;
    I6=I7;
    JUMP(M13,I12) (DB);
    DM(I7,M7)=R2;
    DM(I7,M7)=probe_returned-1;
probe_returned:
    NOP;
.ENDSEG;
