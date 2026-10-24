import fs from 'node:fs/promises';
import { Workbook } from '@oai/artifact-tool';
const root=process.argv[2] ?? process.cwd();
const input=JSON.parse(await fs.readFile(`${root}/docs/qa/ri02/data01/matrix_rows.json`,'utf8'));
const wb=Workbook.create(); const sh=wb.worksheets.add('Field matrix');
const values=[input.columns,...input.rows.map(r=>input.columns.map(k=>r[k]))];
sh.getRangeByIndexes(0,0,values.length,17).values=values;
wb.recalculate();
const checked=sh.getRangeByIndexes(0,0,values.length,17).values;
if(JSON.stringify(checked)!==JSON.stringify(values)) throw Error('Cell round trip differs');
// CSV is the explicitly requested output. No formatting/formulas are applicable.
// CSV export is absent from the documented Artifact Tool surface; serialize verified cells.
const csv=checked.map(row=>row.map(v=>'"'+String(v??'').replaceAll('"','""')+'"').join(',')).join('\r\n')+'\r\n';
await fs.writeFile(`${root}/docs/RI_02_DATA_01_FIELD_MATRIX.csv`,csv);
await fs.writeFile(`${root}/docs/qa/ri02/data01/matrix_validation.json`,JSON.stringify({rows:checked.length-1,columns:17,cell_roundtrip:'PASS',format:'CSV UTF-8, quoted fields, CRLF',render:'NOT_APPLICABLE: CSV has no visual formatting',formula_count:0},null,2));
console.log(JSON.stringify({rows:checked.length-1,columns:17,roundtrip:'PASS'}));
