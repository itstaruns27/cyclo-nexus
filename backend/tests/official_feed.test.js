/**
 * Official feed parsers (JTWC JMV 3.0 .tcw and TCFA text) — offline tests.
 * Fixtures follow the exact layout of live JTWC products fetched 2026-09-29.
 */

const { parseTcw, parseTcfa, parseIssued, pressureFromWind, inNio } = require('../src/workers/ingest_worker');

const TCW_NIO = `WTIO31 PGTW 291500
WARNING    ATCG MIL 03B NIO 260929133256
2026092912 03B MONTHA     004  01 330 07 SATL 030
T000 152N 0874E 055 R034 060 NE QD 080 SE QD 080 SW QD 040 NW QD
T012 163N 0868E 065 R034 060 NE QD 080 SE QD 070 SW QD 035 NW QD
T024 178N 0861E 075 R034 065 NE QD 085 SE QD 070 SW QD 035 NW QD
T048 205N 0852E 060 R034 065 NE QD 100 SE QD 080 SW QD 030 NW QD
AMP
SUBJ:  TROPICAL CYCLONE 03B (MONTHA) WARNING NR 004
   MINIMUM CENTRAL PRESSURE AT 291200Z IS 984 MB.
`;

const TCFA_ACTIVE = `WTIO21 PGTW 281730
SUBJ/TROPICAL CYCLONE FORMATION ALERT (INVEST 94B)//
RMKS/
1. THE AREA OF CONVECTION (INVEST 94B) PREVIOUSLY LOCATED NEAR 12.1N 88.0E IS NOW
LOCATED NEAR 13.4N 87.2E, APPROXIMATELY 420 NM SOUTH OF KOLKATA.
MAXIMUM SUSTAINED SURFACE WINDS ARE ESTIMATED AT 25 TO 30 KNOTS.
MINIMUM SEA LEVEL PRESSURE IS ESTIMATED TO BE NEAR 1002 MB.//
NNNN`;

const TCFA_CANCELLED = `WTIO21 PGTW 281730
SUBJ/TROPICAL CYCLONE FORMATION ALERT (INVEST 92W) CANCELLATION//
RMKS/
1. THIS CANCELS REF A (WTIO21 PGTW 271730) THE AREA OF
CONVECTION (INVEST 92W) PREVIOUSLY LOCATED NEAR 14.4N 98.0E IS NOW
LOCATED NEAR 17.4N 97.4E.//`;

describe('JTWC warning (.tcw) parser', () => {
  const w = parseTcw(TCW_NIO);

  it('reads id, name and synoptic time', () => {
    expect(w.atcfId).toBe('03B');
    expect(w.name).toBe('MONTHA');
    expect(w.obsTime.toISOString()).toBe('2026-09-29T12:00:00.000Z');
  });

  it('reads the current position and forecast track', () => {
    expect(w.points[0]).toEqual({ hour: 0, lat: 15.2, lon: 87.4, windKt: 55 });
    expect(w.points.map(p => p.hour)).toEqual([0, 12, 24, 48]);
    expect(w.points[3]).toMatchObject({ lat: 20.5, lon: 85.2, windKt: 60 });
  });

  it('reads the bulletin central pressure', () => {
    expect(w.pressureHpa).toBe(984);
  });

  it('handles southern / western hemisphere tokens', () => {
    const s = parseTcw(TCW_NIO.replace('152N 0874E', '152S 0874W'));
    expect(s.points[0]).toMatchObject({ lat: -15.2, lon: -87.4 });
  });

  it('rejects files without a header', () => {
    expect(() => parseTcw('garbage')).toThrow();
  });
});

describe('JTWC formation alert parser', () => {
  it('parses an active invest', () => {
    const a = parseTcfa(TCFA_ACTIVE, new Date('2026-09-28T17:30:00Z'));
    expect(a).toMatchObject({ atcfId: '94B', lat: 13.4, lon: 87.2, windKt: 30, pressureHpa: 1002 });
  });

  it('ignores cancelled alerts', () => {
    expect(parseTcfa(TCFA_CANCELLED)).toBeNull();
  });
});

describe('helpers', () => {
  it('parses DD/HHMMZ relative to the feed month, rolling back across month ends', () => {
    expect(parseIssued('29/1500Z', new Date('2026-09-29T15:06:00Z')).toISOString()).toBe('2026-09-29T15:00:00.000Z');
    expect(parseIssued('30/1800Z', new Date('2026-10-01T01:00:00Z')).toISOString()).toBe('2026-09-30T18:00:00.000Z');
  });

  it('estimates pressure from wind (Atkinson–Holliday)', () => {
    expect(pressureFromWind(0)).toBe(1008);
    expect(pressureFromWind(65)).toBeGreaterThan(970);
    expect(pressureFromWind(65)).toBeLessThan(990);
  });

  it('keeps only North Indian Ocean positions', () => {
    expect(inNio(15.2, 87.4)).toBe(true);
    expect(inNio(29.2, 136.3)).toBe(false);
  });
});
