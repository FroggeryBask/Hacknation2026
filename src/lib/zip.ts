// A ZIP archive of text files built in the browser, so "Pobierz wszystkie" saves one file (several
// downloads from one click are blocked by Safari and held behind a prompt by Chrome). Files are
// stored, not compressed: the archive format only (PKWARE APPNOTE 4.3.7), no dependency.

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(data: Uint8Array) {
  let c = 0xffffffff;
  for (const b of data) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

/** MS-DOS time and date, as ZIP headers store them. */
function dosTime(d: Date) {
  return {
    time: (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1),
    date:
      ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate(),
  };
}

// General purpose flag bit 11: names are UTF-8 (Polish letters in file names).
const UTF8 = 0x0800;

export function zip(
  files: { name: string; text: string }[],
  now = new Date(),
): Blob {
  const enc = new TextEncoder();
  const { time, date } = dosTime(now);
  const body: Uint8Array<ArrayBuffer>[] = [];
  const central: Uint8Array<ArrayBuffer>[] = [];
  let offset = 0;
  for (const f of files) {
    const name = enc.encode(f.name);
    const data = enc.encode(f.text);
    const crc = crc32(data);

    const local = new Uint8Array(30 + name.length);
    const l = new DataView(local.buffer);
    l.setUint32(0, 0x04034b50, true); // local file header
    l.setUint16(4, 20, true); // version needed: 2.0
    l.setUint16(6, UTF8, true);
    l.setUint16(8, 0, true); // stored
    l.setUint16(10, time, true);
    l.setUint16(12, date, true);
    l.setUint32(14, crc, true);
    l.setUint32(18, data.length, true);
    l.setUint32(22, data.length, true);
    l.setUint16(26, name.length, true);
    local.set(name, 30);

    const entry = new Uint8Array(46 + name.length);
    const c = new DataView(entry.buffer);
    c.setUint32(0, 0x02014b50, true); // central directory header
    c.setUint16(4, 20, true); // made by
    c.setUint16(6, 20, true); // version needed
    c.setUint16(8, UTF8, true);
    c.setUint16(10, 0, true);
    c.setUint16(12, time, true);
    c.setUint16(14, date, true);
    c.setUint32(16, crc, true);
    c.setUint32(20, data.length, true);
    c.setUint32(24, data.length, true);
    c.setUint16(28, name.length, true);
    c.setUint32(42, offset, true); // where the local header starts
    entry.set(name, 46);

    body.push(local, data);
    central.push(entry);
    offset += local.length + data.length;
  }
  const size = central.reduce((n, e) => n + e.length, 0);
  const end = new Uint8Array(22);
  const e = new DataView(end.buffer);
  e.setUint32(0, 0x06054b50, true); // end of central directory
  e.setUint16(8, files.length, true);
  e.setUint16(10, files.length, true);
  e.setUint32(12, size, true);
  e.setUint32(16, offset, true);
  return new Blob([...body, ...central, end], { type: "application/zip" });
}

/**
 * Names for the files of one archive: "wniosek.json" from "wniosek.pdf"; when two sources share a
 * name ("wniosek.pdf", "wniosek.docx") the extension stays ("wniosek.docx.json"), then a number.
 */
export function uniqueNames(sources: string[], ext: string): string[] {
  const base = (s: string) => s.replace(/\.[^.]+$/, "") || "formularz";
  const taken = new Set<string>();
  return sources.map((s) => {
    const clash = sources.filter((o) => base(o) === base(s)).length > 1;
    const stem = clash ? s : base(s);
    let name = `${stem}.${ext}`;
    for (let i = 2; taken.has(name); i++) name = `${stem} (${i}).${ext}`;
    taken.add(name);
    return name;
  });
}
