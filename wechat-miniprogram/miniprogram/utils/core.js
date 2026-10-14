const SOURCES={
 rain:{name:'氣象站過去一小時雨量',url:'https://data.weather.gov.hk/weatherAPI/opendata/hourlyRainfall.php?lang=tc',format:'json',cadence:'15 分鐘',maxAge:45},
 weather:{name:'本港地區天氣報告',url:'https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc',format:'json',cadence:'按官方更新',maxAge:90},
 warnings:{name:'天氣警告一覽',url:'https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warnsum&lang=tc',format:'json',cadence:'有更新時',maxAge:15},
 warningInfo:{name:'詳細天氣警告',url:'https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warningInfo&lang=tc',format:'json',cadence:'有更新時',maxAge:15},
 forecast:{name:'九天天氣預報',url:'https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc',format:'json',cadence:'每日兩次及有更新時',maxAge:900},
 local:{name:'本港地區天氣預報',url:'https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=flw&lang=tc',format:'json',cadence:'每小時及有更新時',maxAge:180},
 tides:{name:'最新實測潮位',url:'https://data.weather.gov.hk/weatherAPI/hko_data/tide/ALL_en.csv',format:'csv',cadence:'5 分鐘',maxAge:30},
 nowcast:{name:'香港網格降雨臨近預報',url:'https://data.weather.gov.hk/weatherAPI/hko_data/F3/Gridded_rainfall_nowcast.csv',format:'csv',cadence:'12 分鐘',maxAge:36}
};
const REGIONS=[
 ['中西區',22.282,114.151],['東區',22.284,114.221],['南區',22.247,114.158],['灣仔',22.278,114.183],['九龍城',22.329,114.191],['觀塘',22.312,114.226],['深水埗',22.330,114.162],['黃大仙',22.342,114.195],['油尖旺',22.306,114.171],['離島區',22.262,113.962],['葵青',22.357,114.124],['北區',22.496,114.138],['西貢',22.382,114.272],['沙田',22.381,114.189],['大埔',22.449,114.169],['荃灣',22.371,114.114],['屯門',22.391,113.978],['元朗',22.445,114.025]
].map(([name,lat,lon])=>({name,lat,lon}));
function numeric(v){if(v===null||v===undefined||String(v).trim()==='')return null;const n=Number(v);return Number.isFinite(n)?n:null}
function csv(text){const rows=[];let row=[],cell='',quote=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quote&&text[i+1]==='"'){cell+='"';i++}else quote=!quote}else if(c===','&&!quote){row.push(cell);cell=''}else if((c==='\n'||c==='\r')&&!quote){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(x=>x.trim()))rows.push(row);row=[];cell=''}else cell+=c}if(cell||row.length){row.push(cell);rows.push(row)}return rows}
function hkCompact(s){return /^\d{12}$/.test(s)?`${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}T${s.slice(8,10)}:${s.slice(10,12)}:00+08:00`:null}
function normalize(key,data){if(key==='tides')return csv(data).slice(1).filter(r=>r.length>=4).map(r=>({name:r[0],time:`${r[1]}T${r[2]}:00+08:00`,value:numeric(r[3]),unit:'mCD'}));if(key==='nowcast')return csv(data).slice(1).filter(r=>r.length>=5&&+r[2]>=22.1&&+r[2]<=22.6&&+r[3]>=113.8&&+r[3]<=114.5).map(r=>({issued:hkCompact(r[0]),end:hkCompact(r[1]),lat:+r[2],lon:+r[3],value:numeric(r[4])}));return data}
function observationTime(key,data){if(key==='rain')return data.obsTime;if(key==='weather')return data.rainfall?.endTime||data.updateTime;if(key==='tides')return data.map(r=>r.time).sort().slice(-1)[0];if(key==='nowcast')return data[0]?.issued;if(key==='warnings'||key==='warningInfo')return null;return data.updateTime}
function isStale(key,packet,now=Date.now()){if(!packet)return true;const stamp=observationTime(key,packet.data)||packet.receivedAt;const t=Date.parse(stamp);return !Number.isFinite(t)||now-t>SOURCES[key].maxAge*60000||t>now+300000}
function regionRain(data,name){return data?.rainfall?.data?.find(r=>r.place===name)||null}
function nearestNowcast(points,lat,lon){if(!points?.length)return[];const nearest=points.reduce((a,p)=>{const d=(p.lat-lat)**2+((p.lon-lon)*Math.cos(lat*Math.PI/180))**2;return d<a.d?{d,lat:p.lat,lon:p.lon}:a},{d:Infinity});return points.filter(p=>p.lat===nearest.lat&&p.lon===nearest.lon).sort((a,b)=>Date.parse(a.end)-Date.parse(b.end))}
function evaluate({rain,tide,warning,rainLimit,tideLimit,unavailable=false}){const reasons=[];if(unavailable)return{level:'unknown',label:'資料待核對',reasons:['觀測缺失、延遲或正使用歷史快照']};if(warning)reasons.push('官方天氣警告生效');if(rain!==null&&rain>=rainLimit)reasons.push('雨量達到自訂關注值');if(tide!==null&&tide>=tideLimit)reasons.push('潮位達到自訂關注值');return{level:reasons.length>=2?'high':reasons.length?'watch':'normal',label:reasons.length>=2?'優先核對':reasons.length?'需要關注':'例行觀察',reasons:reasons.length?reasons:['未觸及自訂關注規則；不代表沒有風險']}}

module.exports={SOURCES,REGIONS,numeric,observationTime,isStale,regionRain,nearestNowcast,evaluate};
