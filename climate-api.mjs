import {DatabaseSync} from 'node:sqlite';
import {existsSync} from 'node:fs';
export function createClimateReader(path){
 let database;
 return {close(){database?.close()},handle(request){
  const json=(value,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store'}});
  if(request.method!=='GET')return json({error:'仅支持读取'},405);
  if(!existsSync(path))return json({error:'先下载并校验扩展数据包，再查询历史温湿压系列。'},503);
  const params=new URL(request.url).searchParams,station=params.get('station'),variable=params.get('variable'),from=Number(params.get('from')),to=Number(params.get('to'));
  if(!/^[A-Z0-9]{2,6}$/.test(station||'')||!['MAXT','MINT','TEMP','RH','MSLP'].includes(variable)||!Number.isInteger(from)||!Number.isInteger(to)||from<1884||to>2026||from>to||to-from>9)return json({error:'站点/变量或年份无效，最多查询10年'},400);
  database??=new DatabaseSync(path,{readOnly:true});
  const rows=database.prepare('SELECT date,value,unit,quality_status,completeness,source_id FROM climate_daily WHERE station=? AND variable=? AND date>=? AND date<=? ORDER BY date LIMIT 4000').all(station,variable,from+'-01-01',to+'-12-31');
  return json({station,variable,rows,source:'香港天文台官方历史日资料',limitation:'月度更新，缺测和不完整标记保留；不是当前实时观测'});
 }};
}
