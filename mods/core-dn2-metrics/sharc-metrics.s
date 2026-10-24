// SPDX-License-Identifier: GPL-2.0-or-later
// Exact DN2 1.12 optional L2 measurement core; see README.md.
// Tail scratch registers are restored before use by the exact stock epilogue.
// Cumulative count/sum wrap unsigned; consumers use differences, not sum/count.
.SECTION/SW seg_swco;
.GLOBAL metrics_render.;
.GLOBAL metrics_tail.;
metrics_render.:
    R1=DM(metrics_callback.);
    R1=PASS R1;
    IF EQ JUMP render_return;
    I12=R1;
    R1=EMUCLK;
    DM(metrics_start.)=R1;
    R2=I6;
    I6=I7;
    JUMP(M13,I12) (DB);
    DM(I7,M7)=R2;
    DM(I7,M7)=render_done-1;
render_done:
    R0=EMUCLK;
    R1=DM(metrics_start.);
    R0=R0-R1;
    R1=DM(metrics_count.);
    R1=R1+1;
    DM(metrics_count.)=R1;
    R1=DM(metrics_sum_lo.);
    R2=R1+R0;
    DM(metrics_sum_lo.)=R2;
    COMPU(R2,R1);
    IF GE JUMP render_max;
    R3=DM(metrics_sum_hi.);
    R3=R3+1;
    DM(metrics_sum_hi.)=R3;
render_max:
    R1=DM(metrics_max.);
    COMPU(R0,R1);
    IF LE JUMP render_return;
    DM(metrics_max.)=R0;
render_return:
    I12=DM(M7,I6);
    JUMP(M14,I12) (DB);
    RFRAME;
    NOP;

metrics_tail.:
    R11=ASTATX;
    DM(metrics_sv_astat.)=R11;
    R11=STKYX;
    DM(metrics_sv_stky.)=R11;
    R11=L2;
    I5=R11;
    L2=0;
    R10=DM(metrics_index.);
    R10=PASS R10;
    IF NE JUMP serial_value;
    R11=0x44485331;
    DM(metrics_snapshot.)=R11;
    R11=DM(metrics_count.);
    DM(snapshot_count.)=R11;
    R11=DM(metrics_sum_hi.);
    DM(snapshot_sum_hi.)=R11;
    R11=DM(metrics_sum_lo.);
    DM(snapshot_sum_lo.)=R11;
    R11=DM(metrics_max.);
    DM(snapshot_max.)=R11;
    R11=EMUCLK;
    DM(snapshot_clock.)=R11;
    R11=0;
    DM(snapshot_reserved.)=R11;
    R13=DM(metrics_callback.);
    R13=PASS R13;
    IF EQ JUMP serial_flags;
    R11=1;
serial_flags:
    DM(snapshot_flags.)=R11;
    R11=DM(metrics_sequence.);
    R11=R11+1;
    R13=7;
    R11=R11 AND R13;
    DM(metrics_sequence.)=R11;
    R11=0xffff;
    DM(metrics_crc.)=R11;
serial_value:
    R10=DM(metrics_index.);
    R11=16;
    COMPU(R10,R11);
    IF GE JUMP serial_crc;
    R13=-1;
    R11=LSHIFT R10 BY R13;
    R13=2;
    R11=LSHIFT R11 BY R13;
    R13=metrics_snapshot.;
    R11=R11+R13;
    I2=R11;
    R15=DM(0,I2);
    R11=1;
    R11=R10 AND R11;
    R11=PASS R11;
    IF NE JUMP serial_half;
    R13=-16;
    R15=LSHIFT R15 BY R13;
serial_half:
    R13=0xffff;
    R15=R15 AND R13;
    R14=DM(metrics_crc.);
    R14=R14 XOR R15;
    R10=16;
serial_bit:
    R13=0x8000;
    R13=R14 AND R13;
    R14=R14+R14;
    R13=PASS R13;
    IF EQ JUMP serial_next_bit;
    R13=0x1021;
    R14=R14 XOR R13;
serial_next_bit:
    R10=R10-1;
    IF NE JUMP serial_bit;
    R13=0xffff;
    R14=R14 AND R13;
    DM(metrics_crc.)=R14;
    R10=DM(metrics_index.);
    R10=R10+1;
    DM(metrics_index.)=R10;
    R10=R10-1;
    JUMP serial_pack;
serial_crc:
    R15=DM(metrics_crc.);
    R11=0;
    DM(metrics_index.)=R11;
serial_pack:
    R11=DM(metrics_sequence.);
    R13=21;
    R11=LSHIFT R11 BY R13;
    R13=16;
    R10=LSHIFT R10 BY R13;
    R10=R10 OR R11;
    R11=0xd6000000;
    R10=R10 OR R11;
    R10=R10 OR R15;
    JUMP metrics_tail_return;
metrics_tail_return:
    R11=16;
    R13=LSHIFT R10 BY R11;
    R11=-16;
    R10=LSHIFT R10 BY R11;
    R10=R10 OR R13;
    R11=I4;
    R13=8;
    R11=R11+R13;
    I2=R11;
    DM(0,I2)=R10;
    R11=I5;
    L2=R11;
    R11=DM(metrics_sv_astat.);
    ASTATX=R11;
    R11=DM(metrics_sv_stky.);
    STKYX=R11;
    DM(0x268a38)=R1;
    JUMP 0x1c9e62;
.ENDSEG;

.SECTION/DOUBLE32 seg_dmda;
.GLOBAL metrics_callback., metrics_count., metrics_sum_lo., metrics_sum_hi.;
.GLOBAL metrics_max., metrics_index., metrics_sequence., metrics_crc.;
.GLOBAL metrics_start., metrics_snapshot.;
.VAR metrics_callback. = 0;
.VAR metrics_count. = 0;
.VAR metrics_sum_lo. = 0;
.VAR metrics_sum_hi. = 0;
.VAR metrics_max. = 0;
.VAR metrics_index. = 0;
.VAR metrics_sequence. = 0;
.VAR metrics_crc. = 0;
.VAR metrics_start. = 0;
.VAR metrics_snapshot. = 0;
.VAR snapshot_count. = 0;
.VAR snapshot_sum_hi. = 0;
.VAR snapshot_sum_lo. = 0;
.VAR snapshot_max. = 0;
.VAR snapshot_clock. = 0;
.VAR snapshot_flags. = 0;
.VAR snapshot_reserved. = 0;
.VAR metrics_sv_astat. = 0;
.VAR metrics_sv_stky. = 0;
.ENDSEG;
