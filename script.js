let role='owner',running=false,scenarioKey='ble_auth',ws=null,stepIndex=0;
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const SCENARIOS={ble_auth:{symptom:'踩刹车按启动按钮，车辆无法上电，屏幕弹出"钥匙未找到"',signals:{'sv-pm':['err','0:Off (St1)'],'sv-kv':['err','INVALID'],'sv-brk':['ok','PRESSED'],'sv-gear':['ok','P (0x5)'],'sv-ble':['warn','DETECTED_FAIL'],'sv-bleerr':['err','AUTH_ERR(0x05)']},ontoCounts:{cls:42,prop:87,ind:156},steps:[{title:'症状解析 & 场景匹配',agent:'sym',body:'NLU 解析 → 匹配 T_1_2 Off→LocalOn',details:[['触发路径','T_1_2 (VEEA-SysR-2117)','warn'],['当前状态','St1: 0:Off','err']]},{title:'T_1_2 前置条件校验',agent:'ont',body:'读取 Ontology C3:Constraints',details:[['BrkPedalStVD','VALID ✅','ok'],['GE_Fahrstufe','0x5 P ✅','ok'],['ZATButtonSwSt','PRESSED ✅','ok'],['结论','→ 触发 tKeyValid(30s)','warn']]},{title:'KeyValidSt 超时分析',agent:'llm',body:'LLM 结合 C7:Events 推理',details:[['tKeyValid','超时 ❌','err'],['KeyValidSt','INVALID ❌','err'],['Flag_BLE','1 (计时中)','warn']]},{title:'L3 BLE认证链路定位',agent:'ont',body:'深入 L3 ECU 层定位',details:[['BLE_ErrorCode','0x05 AUTH_ERROR ❌','err'],['keyPSValue','Invalid ❌','err']]},{title:'LLM 综合推理',agent:'llm',body:'综合证据链计算置信度',details:[['根因链路','BLE AUTH_ERR → KeyValidSt=INVALID','err'],['置信度','90%','ok']]},{title:'最终结论',agent:'out',body:'T_1_2 触发失败：BLE认证失败',details:[]}],rules:[{id:'T_1_2',text:'IF BrkPedalStVD=VALID AND GE_Fahrstufe=P AND ZATPressed → tKeyValid(30s)',conf:'0.98',src:'VEEA-SysR-2117'},{id:'R-KEY001',text:'IF tKeyValid超时 AND KeyValidSt=INVALID → Off保持',conf:'0.98',src:'VEEA-SysR-2147'},{id:'R-BLE001',text:'IF BLE_ErrorCode=AUTH_ERR → BLE认证失败',conf:'0.95',src:'VEEA-SysR-2123'}],hypos:[{name:'手机BLE认证失败',pct:55,cls:'p'},{name:'BLE配对信息丢失',pct:30,cls:'s'},{name:'TBOX BLE异常',pct:15,cls:'t'}],conf:{target:90,factors:[{label:'Symptom Match',val:0.90,display:'0.90'},{label:'Rule Match',val:0.95,display:'0.95'},{label:'Data Support',val:0.92,display:'0.92'},{label:'Ontology Coverage',val:0.88,display:'0.88'}]},ontoSummary:'<div style="color:var(--accent);font-weight:600">// L1 整车层</div><div><span style="color:var(--tx3)">LDCU_PowerMode:</span> <span style="color:var(--red)">0:Off</span> · <span style="color:var(--tx3)">GE_Fahrstufe:</span> <span style="color:var(--green)">P</span></div><div style="color:var(--yellow);margin-top:4px;font-weight:600">// L2 子系统层</div><div><span style="color:var(--tx3)">KeyValidSt:</span> <span style="color:var(--red)">INVALID</span> · <span style="color:var(--tx3)">Flag_BLE:</span> <span style="color:var(--yellow)">1</span></div><div style="color:var(--red);margin-top:4px;font-weight:600">// L3 ECU层</div><div><span style="color:var(--tx3)">BLE_ErrorCode:</span> <span style="color:var(--red)">0x05</span></div>',outputs:{owner:'<div class="conc">📱 手机蓝牙钥匙认证失败</div><p style="margin-top:8px">车辆检测到手机但认证失败。</p><div class="action-list"><div class="ai"><div class="an">1</div>关闭蓝牙等5秒后重开</div><div class="ai"><div class="an">2</div>检查App蓝牙权限</div><div class="ai"><div class="an">3</div>用NFC钥匙卡应急</div></div>',technician:'<div class="conc">【诊断结论】T_1_2 失败 — BLE认证失败</div><div class="action-list" style="margin-top:8px"><div class="ai"><div class="an">P1</div>重开BLE，确认RSSI>-80dBm</div><div class="ai"><div class="an">P2</div>OBD读取 BLE_ErrorCode</div><div class="ai"><div class="an">P3</div>App解绑重新配对</div></div>',customer_service:'<div class="conc">【系统诊断】蓝牙钥匙认证异常</div><p style="color:var(--tx2)">"请重开蓝牙再试"</p>'},escalation:{customer_service:'操作3次仍失败 → 升级技术支持'}},key_timeout:{symptom:'按启动按钮后"钥匙未找到"，蓝牙未开',signals:{'sv-pm':['err','0:Off'],'sv-kv':['err','INVALID'],'sv-brk':['dim','NOT_PRESSED'],'sv-gear':['ok','P'],'sv-ble':['err','NOT_DETECTED'],'sv-bleerr':['err','TIMEOUT']},ontoCounts:{cls:38,prop:72,ind:128},steps:[{title:'症状解析',agent:'sym',body:'ZAT单按 → KeySearch启动',details:[['动作','ZAT单按','warn']]},{title:'前置条件',agent:'ont',body:'C3校验',details:[['BrkPedalSt','NOT_PRESSED','warn']]},{title:'BLE未发现',agent:'llm',body:'Flag_BLE=0',details:[['Flag_BLE','0 ❌','err']]},{title:'超时',agent:'ont',body:'C7匹配',details:[['KeySearchingSt','Timeout ❌','err']]},{title:'推理',agent:'llm',body:'蓝牙未开启',details:[['根因','蓝牙未开启','err']]},{title:'结论',agent:'out',body:'蓝牙未开→keyNotFound',details:[]}],rules:[{id:'R-KEY001',text:'IF Flag_BLE=0 → Timeout → keyNotFound',conf:'0.95',src:'VEEA-SysR-2147'}],hypos:[{name:'蓝牙未开启',pct:75,cls:'p'},{name:'超出范围',pct:20,cls:'s'},{name:'模块故障',pct:5,cls:'t'}],conf:{target:88,factors:[{label:'Symptom Match',val:0.92,display:'0.92'},{label:'Rule Match',val:0.95,display:'0.95'},{label:'Data Support',val:0.90,display:'0.90'},{label:'Ontology Coverage',val:0.85,display:'0.85'}]},ontoSummary:'<div style="color:var(--red);font-weight:600">// BLE_Status: NOT_DETECTED</div>',outputs:{owner:'<div class="conc">📱 蓝牙未开启</div><div class="action-list"><div class="ai"><div class="an">1</div>开启蓝牙，靠近车辆</div></div>',technician:'<div class="conc">【结论】Flag_BLE=0</div>',customer_service:'<div class="conc">请开蓝牙</div>'},escalation:{}},forced_off:{symptom:'强制下电后无法上电',signals:{'sv-pm':['err','0:Off'],'sv-kv':['ok','VALID'],'sv-brk':['ok','PRESSED'],'sv-gear':['err','0xD: ERR'],'sv-ble':['ok','CONNECTED'],'sv-bleerr':['dim','NONE']},ontoCounts:{cls:45,prop:92,ind:168},steps:[{title:'症状解析',agent:'sym',body:'ForcePoweroff已执行',details:[['前置动作','ForcePoweroff ⚠️','warn']]},{title:'条件校验',agent:'ont',body:'C3:档位',details:[['GE_Fahrstufe','0xD Error ❌','err']]},{title:'PowerCtrl分析',agent:'llm',body:'LDCU_PowerCtrlError',details:[['Error','power off Error ❌','err']]},{title:'EEPROM',agent:'ont',body:'L3',details:[['EEPROM','Force_Power_Off','warn']]},{title:'推理',agent:'llm',body:'档位残留',details:[['根因','GE=Error → T_1_2阻断','err']]},{title:'结论',agent:'out',body:'档位残留 → T_1_2阻断',details:[]}],rules:[{id:'T_1_2-G',text:'IF GE!=P/N → 禁止上电',conf:'0.99',src:'VEEA-SysR-2117'}],hypos:[{name:'档位未复位',pct:60,cls:'p'},{name:'EmergencySw粘连',pct:25,cls:'s'},{name:'EEPROM延迟',pct:15,cls:'t'}],conf:{target:82,factors:[{label:'Symptom Match',val:0.88,display:'0.88'},{label:'Rule Match',val:0.99,display:'0.99'},{label:'Data Support',val:0.88,display:'0.88'},{label:'Ontology Coverage',val:0.82,display:'0.82'}]},ontoSummary:'<div style="color:var(--red)">GE_Fahrstufe: 0xD Error</div>',outputs:{owner:'<div class="conc">⚠️ 档位异常</div><div class="action-list"><div class="ai"><div class="an">1</div>拨至P档重试</div></div>',technician:'<div class="conc">【结论】T_1_2阻断</div>',customer_service:'<div class="conc">拨P档再试</div>'},escalation:{customer_service:'仍失败→工单'}},bms_charging:{symptom:'充电停止，APP显示"温度过高"',signals:{'sv-pm':['ok','2:RemoteOn'],'sv-kv':['ok','VALID'],'sv-brk':['dim','—'],'sv-gear':['ok','P'],'sv-ble':['ok','CONNECTED'],'sv-bleerr':['warn','TEMP 52°C']},ontoCounts:{cls:56,prop:118,ind:203},steps:[{title:'症状解析 — BMS',agent:'sym',body:'充电中断+温度告警',details:[['cellTempMax','52°C (>45°C)','err']]},{title:'BMS Ontology',agent:'ont',body:'NMC阈值',details:[['NMC阈值','≤45°C','ok'],['当前','52°C ❌','err'],['SOPCharge','0 kW','err']]},{title:'热管理分析',agent:'llm',body:'降额策略',details:[['降额','超阈值','err']]},{title:'L3 ECU',agent:'ont',body:'SOP曲线',details:[['SOPCharge','0kW','err']]},{title:'推理',agent:'llm',body:'52°C > 45°C → 保护',details:[['根因','温度超阈值→SOP=0','err']]},{title:'结论',agent:'out',body:'BMS热保护正常',details:[]}],rules:[{id:'R-BMS-T1',text:'IF cellTempMax>45°C → SOPCharge=0',conf:'0.99',src:'BMS-Spec-3.2'}],hypos:[{name:'温度超阈值(正常)',pct:80,cls:'p'},{name:'冷却不足',pct:15,cls:'s'},{name:'传感器偏差',pct:5,cls:'t'}],conf:{target:92,factors:[{label:'Symptom Match',val:0.95,display:'0.95'},{label:'Rule Match',val:0.99,display:'0.99'},{label:'Data Support',val:0.94,display:'0.94'},{label:'Ontology Coverage',val:0.90,display:'0.90'}]},ontoSummary:'<div style="color:var(--red)">cellTempMax: 52°C (>45°C NMC)</div><div>packSOPCharge: <span style="color:var(--red)">0 kW</span></div>',outputs:{owner:'<div class="conc">🔋 电池温度保护</div><p style="margin-top:8px">52°C超安全阈值。</p><div class="action-list"><div class="ai"><div class="an">1</div>等待冷却至40°C以下</div></div>',technician:'<div class="conc">【结论】BMS热保护 52°C>45°C</div>',customer_service:'<div class="conc">请等冷却后充电</div>'},escalation:{}}};

function animateNum(id,s,e,d){const el=document.getElementById(id);if(!el)return;let t0=null;const step=ts=>{if(!t0)t0=ts;const p=Math.min((ts-t0)/d,1);el.textContent=Math.floor(p*(e-s)+s);if(p<1)requestAnimationFrame(step);else el.textContent=e};requestAnimationFrame(step)}
function loadScenario(k){scenarioKey=k;const sc=SCENARIOS[k];document.getElementById('symptomInput').value=sc.symptom;for(const[id,[cls,val]]of Object.entries(sc.signals)){const el=document.getElementById(id);if(el){el.className='sig-val '+cls;el.textContent=val}}}
function setRole(r){role=r;document.querySelectorAll('.rbtn').forEach(b=>{b.classList.remove('active')});document.getElementById({owner:'btn-owner',technician:'btn-tech',customer_service:'btn-cs'}[r]).classList.add('active')}

function mapAgentId(id){return ({orch:'master',orchestrator:'master',sym:'symptom',symptom_parser:'symptom',ont:'ontology',ontology_fetcher:'ontology',rule:'rule',conf:'rule',confidence_calc:'rule',out:'output',output_adapter:'output',llm:'llm',llm_diagnosis_agent:'llm',ALL:'master'})[id]||id}

function renderPairs(pairs){return(pairs||[]).map(({k,v,cls})=>`<div class="bus-kv"><span class="bus-k">${k}:</span><span class="bus-v ${cls||''}">${v}</span></div>`).join('')}

function appendRule(rule){const rl=document.getElementById('ruleList');if(!rl)return;const empty=rl.querySelector('div[style*="等待规则匹配"]');if(empty)rl.innerHTML='';const el=document.createElement('div');el.className='rule-item';el.innerHTML=`<span class="rule-id">${rule.id}</span><span class="rule-text">${rule.text}<span class="rule-src">${rule.src||''}</span></span><span class="rule-conf">${rule.conf||''}</span>`;rl.appendChild(el);setTimeout(()=>el.classList.add('vis'),50)}

function appendHypothesis(hypothesis){const hl=document.getElementById('hypoList');if(!hl)return;const empty=hl.querySelector('div[style*="等待假设生成"]');if(empty)hl.innerHTML='';const pct=hypothesis.pct??Math.round((hypothesis.conf||0)*100);const cls=hypothesis.cls||'p';const name=hypothesis.name||hypothesis.desc||'未命名假设';const el=document.createElement('div');el.className='hypo-item';el.innerHTML=`<div class="hypo-row"><span class="hypo-name">${name}</span><span class="hypo-pct">${pct}%</span></div><div class="hypo-bar"><div class="hypo-fill ${cls}"></div></div>`;hl.appendChild(el);setTimeout(()=>{el.classList.add('vis');el.querySelector('.hypo-fill').style.width=pct+'%'},50)}

function updateConfidenceFactors(factors){const cf=document.getElementById('confFactors');if(!cf)return;cf.innerHTML='';(factors||[]).forEach(f=>{const label=f.label||f.key||'';const val=f.val??f.value??0;const display=f.display||`${Math.round(val*100)}%`;const row=document.createElement('div');row.className='cf-row';row.innerHTML=`<span class="cf-lbl">${label}</span><div class="cf-bar"><div class="cf-fill" style="width:${val*100}%"></div></div><span class="cf-val">${display}</span>`;cf.appendChild(row)})}

function updateFinalConfidence(confidence,level){const pct=confidence>1?confidence:Math.round(confidence*100);document.getElementById('confNum').textContent=pct+'%';document.getElementById('confBarFill').style.width=pct+'%';document.getElementById('confLabel').textContent=level==='high'?'🔴 高置信度':level==='medium'?'🟡 中置信度':'⚪ 低置信度'}

function updateOutputMessage(msg){const ob=document.getElementById('outputBox');const text=(msg.output&&msg.output.text)||msg.html||'';ob.innerHTML=text||'<div style="font-size:10px;color:var(--tx3);text-align:center;padding:10px 0">无输出</div>';ob.classList.add('vis');const hint=msg.escalation||(msg.output&&msg.output.escalation);const esc=document.getElementById('escalationHint');if(hint){esc.textContent='⚠️ '+hint;esc.style.display='block';esc.classList.add('vis')}}

function updateOntologySummary(msg){if(msg.counts){animateNum('os-cls',0,msg.counts.classes||0,700);animateNum('os-prop',0,msg.counts.properties||0,900);animateNum('os-ind',0,msg.counts.rules||0,1100);document.getElementById('ontoBarFill').style.width='100%'}if(msg.summary){document.getElementById('ontoDetail').innerHTML=msg.summary;document.getElementById('ontoDetail').classList.add('vis')}}

function handleBackendMessage(msg){switch(msg.type){case 'agent_status':setAgent(mapAgentId(msg.agent),msg.state||msg.status,msg.progress);break;case 'msg_bus':pushMsg(mapAgentId(msg.from),mapAgentId(msg.to),renderPairs(msg.pairs));break;case 'wire_animate':animateWire(mapAgentId(msg.from),mapAgentId(msg.to));break;case 'onto_summary':updateOntologySummary(msg);break;case 'reasoning_step':addChain({title:msg.step.title,body:msg.step.body,agent:'llm',details:[]},stepIndex++);break;case 'rule_matched':appendRule(msg.rule);break;case 'hypothesis':appendHypothesis(msg.hypothesis||msg.hypo);break;case 'conf_factors':updateConfidenceFactors(msg.factors);break;case 'conf_final':updateFinalConfidence(msg.confidence,msg.level);break;case 'output':updateOutputMessage(msg);break;case 'pipeline_done':document.getElementById('goBtn').disabled=false;document.getElementById('goBtn').innerHTML='⚡ 重新运行诊断';running=false;setAgent('master','done',100);break;case 'error':document.getElementById('sysStatus').textContent='● ERROR';document.getElementById('goBtn').disabled=false;document.getElementById('goBtn').innerHTML='⚡ 重新运行诊断';running=false;break;case 'backend_status':document.getElementById('sysStatus').textContent='● '+String(msg.status||'READY').toUpperCase();updateOntologySummary({counts:msg.ontology_stats,summary:msg.ontology_loaded?'知识库已挂载':''});break;case 'llm_thinking':break;default:console.log('Unhandled backend message',msg)}}

function connectWebSocket(){if(ws&&[WebSocket.OPEN,WebSocket.CONNECTING].includes(ws.readyState))return;ws=new WebSocket('ws://localhost:8765/ws');ws.onopen=()=>{document.getElementById('sysStatus').textContent='● ONLINE';ws.send(JSON.stringify({type:'client_ready',client_version:'cea-demo'}))};ws.onmessage=(event)=>{handleBackendMessage(JSON.parse(event.data))};ws.onclose=()=>{document.getElementById('sysStatus').textContent='● OFFLINE'};ws.onerror=()=>{document.getElementById('sysStatus').textContent='● ERROR'}}

const CONNECTIONS=[['master','symptom'],['master','ontology'],['symptom','llm'],['ontology','llm'],['llm','rule'],['llm','ontology'],['rule','output'],['llm','output']];
function drawWires(){
  const svg=document.getElementById('topoSvg');
  svg.innerHTML='';
  const c=document.getElementById('topoInner');
  const cr=c.getBoundingClientRect();
  svg.setAttribute('viewBox',`0 0 ${cr.width} ${cr.height}`);

  function getBox(id){
    const el=document.getElementById('ac-'+id);
    const r=el.getBoundingClientRect();
    return {
      cx:r.left-cr.left+r.width/2,
      cy:r.top-cr.top+r.height/2,
      t:r.top-cr.top,
      b:r.top-cr.top+r.height,
      l:r.left-cr.left,
      r:r.left-cr.left+r.width
    };
  }

  // Find best edge point between two boxes
  function edgePoint(from,to){
    const dx=to.cx-from.cx, dy=to.cy-from.cy;
    // Determine which edge to exit from
    if(Math.abs(dx)>Math.abs(dy)){
      // Horizontal dominant
      if(dx>0) return {x:from.r, y:from.cy};
      else return {x:from.l, y:from.cy};
    } else {
      // Vertical dominant
      if(dy>0) return {x:from.cx, y:from.b};
      else return {x:from.cx, y:from.t};
    }
  }

  for(const[a,b]of CONNECTIONS){
    try{
      const ba=getBox(a), bb=getBox(b);
      const pa=edgePoint(ba,bb);
      const pb=edgePoint(bb,ba);
      const mx=(pa.x+pb.x)/2, my=(pa.y+pb.y)/2;
      const d=`M ${pa.x} ${pa.y} Q ${mx} ${pa.y} ${mx} ${my} Q ${mx} ${pb.y} ${pb.x} ${pb.y}`;

      const path=document.createElementNS('http://www.w3.org/2000/svg','path');
      path.setAttribute('d',d);path.setAttribute('class','wire');path.id=`wire-${a}-${b}`;
      svg.appendChild(path);

      const pulse=document.createElementNS('http://www.w3.org/2000/svg','path');
      pulse.setAttribute('d',d);pulse.setAttribute('class','wire-pulse');pulse.id=`pulse-${a}-${b}`;
      svg.appendChild(pulse);
    }catch(e){}
  }
}

async function animateWire(f,t,s){const w=document.getElementById(`wire-${f}-${t}`);const p=document.getElementById(`pulse-${f}-${t}`);const cls=s||'active';if(w)w.setAttribute('class',`wire ${cls}`);if(p){p.setAttribute('class',`wire-pulse ${s==='ont-active'?'ont':s==='llm-active'?'llm':''}`);p.classList.add('go');await delay(700);p.classList.remove('go')}if(w)w.setAttribute('class','wire done')}

function showLabel(f,t,text,cc){const c=document.getElementById('topoInner');const cr=c.getBoundingClientRect();const a=document.getElementById('ac-'+f).getBoundingClientRect();const b=document.getElementById('ac-'+t).getBoundingClientRect();const mx=(a.left+a.width/2+b.left+b.width/2)/2-cr.left;const my=(a.top+a.height/2+b.top+b.height/2)/2-cr.top;const l=document.createElement('div');l.className=`wire-label ${cc}`;l.textContent=text;l.style.left=mx+'px';l.style.top=my+'px';l.style.transform='translate(-50%,-50%)';c.appendChild(l);setTimeout(()=>l.classList.add('vis'),50);setTimeout(()=>{l.classList.remove('vis');setTimeout(()=>l.remove(),300)},2200)}

function setAgent(id,state,pg){const c=document.getElementById('ac-'+id);const s=document.getElementById('st-'+id);const p=document.getElementById('pg-'+id);c.classList.remove('active','done');if(state==='running'){c.classList.add('active');s.className='ac-status s-run';s.innerHTML='<span class="tdots"><span></span><span></span><span></span></span> running'}else if(state==='done'){c.classList.add('done');s.className='ac-status s-done';s.innerHTML='✓ done'}else{s.className='ac-status s-idle';s.innerHTML='⏸ idle'}if(pg!==undefined){p.classList.add('show');p.querySelector('.ac-progress-fill').style.width=pg+'%'}}

async function loadOntology(sc){const ls=['l1','l2','l3'];ls.forEach(l=>{document.getElementById('ol-'+l).classList.remove('loading','loaded');const s=document.getElementById('ols-'+l);s.className='ol-status idle';s.textContent='IDLE'});document.getElementById('ontoBarFill').style.width='0%';await delay(200);for(let i=0;i<3;i++){const l=ls[i],el=document.getElementById('ol-'+l),st=document.getElementById('ols-'+l);el.classList.add('loading');st.className='ol-status loading';st.textContent='LOADING...';document.getElementById('ontoBarFill').style.width=((i+.5)/3*100)+'%';await delay(400+Math.random()*200);el.classList.remove('loading');el.classList.add('loaded');st.className='ol-status loaded';st.textContent='✓ LOADED';document.getElementById('ontoBarFill').style.width=((i+1)/3*100)+'%'}animateNum('os-cls',0,sc.ontoCounts.cls,700);animateNum('os-prop',0,sc.ontoCounts.prop,900);animateNum('os-ind',0,sc.ontoCounts.ind,1100);await delay(300)}

function addChain(step,i){const ch=document.getElementById('reasonChain');const idle=document.getElementById('chainIdle');if(idle)idle.style.display='none';const tag=step.agent==='llm'?'<span class="prov-tag llm">LLM</span>':step.agent==='ont'?'<span class="prov-tag ont">Ontology</span>':step.agent==='sym'?'<span class="prov-tag llm">NLU</span>':'<span class="prov-tag rule">Output</span>';let dh='';if(step.details&&step.details.length)dh='<div style="margin-top:3px">'+step.details.map(([k,v,c])=>`<div class="cs-kv"><span class="cs-k">${k}:</span><span class="cs-v ${c||''}">${v}</span></div>`).join('')+'</div>';const el=document.createElement('div');el.className='chain-step';el.innerHTML=`<div class="cs-line"><div class="cs-dot">${i+1}</div><div class="cs-conn"></div></div><div class="cs-body"><div class="cs-title">[S${i+1}] ${step.title} ${tag}</div><div class="cs-content">${step.body}${dh}</div></div>`;ch.appendChild(el);setTimeout(()=>{el.classList.add('vis');el.querySelector('.cs-dot').classList.add('active')},50);setTimeout(()=>{el.querySelector('.cs-dot').classList.remove('active');el.querySelector('.cs-dot').classList.add('done');el.querySelector('.cs-conn').classList.add('done');el.querySelector('.cs-title').classList.add('done')},800)}

function resetAll(){['master','symptom','ontology','llm','rule','output'].forEach(id=>{document.getElementById('ac-'+id).classList.remove('active','done');document.getElementById('st-'+id).className='ac-status s-idle';document.getElementById('st-'+id).innerHTML='⏸ idle';document.getElementById('pg-'+id).classList.remove('show')});document.getElementById('reasonChain').innerHTML='<div class="idle" id="chainIdle"><div class="idle-icon">🔗</div><div class="idle-txt">启动诊断查看推理链</div></div>';document.getElementById('ruleList').innerHTML='<div style="font-size:10px;color:var(--tx3);text-align:center;padding:10px 0">等待规则匹配</div>';document.getElementById('hypoList').innerHTML='<div style="font-size:10px;color:var(--tx3);text-align:center;padding:10px 0">等待假设生成</div>';document.getElementById('confNum').textContent='0%';document.getElementById('confLabel').textContent='等待计算';document.getElementById('confBarFill').style.width='0%';document.getElementById('confFactors').innerHTML='';document.getElementById('outputBox').innerHTML='<div style="font-size:10px;color:var(--tx3);text-align:center;padding:10px 0">等待诊断完成</div>';document.getElementById('outputBox').classList.remove('vis');document.getElementById('escalationHint').classList.remove('vis');document.getElementById('escalationHint').style.display='none';document.getElementById('ontoDetail').classList.remove('vis');document.getElementById('ontoDetail').innerHTML='';document.querySelectorAll('.wire-label').forEach(l=>{l.remove()});
// Reset message bus
document.getElementById('msgBus').innerHTML='<div class="idle" style="padding:16px"><div class="idle-icon" style="font-size:20px">📡</div><div class="idle-txt" style="font-size:10px">等待 Pipeline 启动</div></div>';
// Reset C1-C10
for(let i=1;i<=10;i++){const item=document.getElementById('oc-c'+i);const dot=document.getElementById('ocd-c'+i);if(item)item.classList.remove('hit');if(dot)dot.classList.remove('on')}
drawWires()}

// ═══ MESSAGE BUS ═══
const AGENT_NAMES={master:'Master',symptom:'Symptom',ontology:'Ontology',llm:'LLM',rule:'RuleEngine',output:'Output'};
const AGENT_CLS={master:'f-master',symptom:'f-sym',ontology:'f-ont',llm:'f-llm',rule:'f-rule',output:'f-out'};
function pushMsg(from,to,content){
  const bus=document.getElementById('msgBus');
  const idle=bus.querySelector('.idle');if(idle)idle.remove();
  const el=document.createElement('div');el.className='bus-msg';
  el.innerHTML=`<div class="bus-head"><span class="bus-from ${AGENT_CLS[from]||''}">${AGENT_NAMES[from]||from}</span><span class="bus-arrow">→</span><span class="bus-to">${AGENT_NAMES[to]||to}</span></div><div class="bus-content">${content}</div>`;
  bus.appendChild(el);bus.scrollTop=bus.scrollHeight;
  setTimeout(()=>el.classList.add('show'),30);
}

// ═══ C1-C10 HIGHLIGHT ═══
function highlightC(cats){
  cats.forEach(c=>{
    const item=document.getElementById('oc-c'+c);
    const dot=document.getElementById('ocd-c'+c);
    if(item)item.classList.add('hit');
    if(dot)dot.classList.add('on');
  });
}

async function startPipeline(){if(running)return;connectWebSocket();if(!ws||ws.readyState!==WebSocket.OPEN){document.getElementById('sysStatus').textContent='● CONNECTING';return;}running=true;stepIndex=0;const btn=document.getElementById('goBtn');btn.disabled=true;btn.innerHTML='<span class="tdots"><span></span><span></span><span></span></span> 诊断中...';resetAll();setAgent('master','running',10);ws.send(JSON.stringify({type:'start',symptom:document.getElementById('symptomInput').value,role:role,signals:Object.fromEntries(Object.entries(SCENARIOS[scenarioKey].signals).map(([key,[,value]])=>[key.replace('sv-',''),value]))}))}

window.addEventListener('load',()=>{loadScenario('ble_auth');connectWebSocket();setTimeout(drawWires,200);setTimeout(drawWires,500);document.fonts&&document.fonts.ready.then(()=>setTimeout(drawWires,200))});
window.addEventListener('resize',()=>setTimeout(drawWires,50));
