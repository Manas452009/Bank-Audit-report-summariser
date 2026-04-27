import io
import re
import pandas as pd
import pdfplumber
from typing import Dict,List,Optional
from fastapi import FastAPI,File,HTTPException,UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
def clean_text(t):
 if not t:return ''
 t=re.sub(r'(.)\\1{2,}',r'\\1',t);t=re.sub(r'\\s+',' ',t);return t.strip()
def extract_text_and_tables(b):
 td,tt=[],[]
 with pdfplumber.open(io.BytesIO(b)) as p:
  for pn,pg in enumerate(p.pages):
   rt=pg.extract_text()
   if rt:
    for pr in re.split(r'\\n\\s*\\n',rt):
     pr=clean_text(pr)
     if len(pr)>=100 and pr.count('.')>=1:td.append({'page':pn+1,'text':pr})
   for tb in pg.extract_tables({'vertical_strategy':'lines','horizontal_strategy':'lines'}):
    if not tb:continue
    ct=[]
    for r in tb:
     if any(c is not None and str(c).strip()!='' for c in r):
       ct.append([str(c).strip() if c else '' for c in r])
    if len(ct)>=2:tt.append({'page':pn+1,'table':ct})
 return td,tt
def is_high_value_financial_table(t):
 txt=' '.join([' '.join(r) for r in t]).lower()
 sh=['npa','gross npa','net npa','provision','write off','advances','liabilities','assets','borrowings','exposure']
 rk=['strategy','strategic','customer','esg','sustainability','value creation','stakeholder','digital','governance','subsidiary','market positioning','progress','target','penetration']
 if any(k in txt for k in rk):return False
 if not any(k in txt for k in sh):return False
 n=re.findall(r'\\d+\\.?\\d*',txt)
 if len(n)<15:return False
 if txt.count('%')>0 and len(n)<10:return False
 if len(t)<3 or max(len(r) for r in t)<2:return False
 return True
def clean_field_name(n):
 n=re.sub(r'\\d+','',n);n=re.sub(r'[^a-zA-Z\\s]','',n);n=re.sub(r'\\s+',' ',n)
 return n.strip()
def clean_value(v):
 return v.replace(',','').strip()
def table_to_structured_text(t):
 h,r=t[0],t[1:]
 sd=[]
 for rw in r:
  rt=[]
  for hv,rv in zip(h,rw):
   if rv and rv!='-':
    ch=clean_field_name(hv);cv=clean_value(rv)
    if ch:rt.append(f'{ch}: {cv}')
  if rt:sd.append(', '.join(rt))
 return sd
def convert_all_tables(ft):
 cv=[]
 for i in ft:
  ps,tt=i['page'],i['table']
  for r in table_to_structured_text(tt):cv.append({'page':ps,'text':r})
 return cv
def risk_level(l):
 if pd.isna(l):return 'Unknown'
 elif l>0.90:return 'High'
 elif l>0.70:return 'Moderate'
 return 'Low'
def comments(r):
 n=[]
 if r['LDR']>1:n.append('Advances exceed deposits')
 elif r['LDR']>0.85:n.append('Aggressive lending')
 elif r['LDR']<0.60:n.append('Conservative lending')
 if r['INV_RATIO']>2:n.append('Very high investment concentration')
 elif r['INV_RATIO']>1:n.append('High investments')
 if r['deposits']<10000:n.append('Low deposit base')
 return '; '.join(n)
def perform_audit_analysis(sd):
 rw=[]
 for i in sd:
  t=i['text']
  d=re.search(r'Deposits:\\s*([\\d\\.]+)',t)
  a=re.search(r'Advances:\\s*([\\d\\.]+)',t)
  iv=re.search(r'Investments:\\s*([\\d\\.]+)',t)
  rw.append({'page':i['page'],'deposits':float(d.group(1))if d else None,'advances':float(a.group(1))if a else None,'investments':float(iv.group(1))if iv else None})
 df=pd.DataFrame(rw)
 df=df.dropna(subset=['deposits','advances','investments'],how='all')
 import numpy as np
 df['LDR']=np.where(df['deposits']>0,df['advances']/df['deposits'],np.nan)
 df['INV_RATIO']=np.where(df['deposits']>0,df['investments']/df['deposits'],np.nan)
 df['risk_level']=df['LDR'].apply(risk_level)
 df['observations']=df.apply(comments,axis=1)
 td=df['deposits'].sum();ta=df['advances'].sum();ti=df['investments'].sum()
 oldr=ta/td if td>0 else 0;oir=ti/td if td>0 else 0
 ors='High'if oldr>0.90 else('Moderate'if oldr>0.70 else'Low')
 s={'total_rows_analyzed':len(df),'total_deposits':round(float(td),2),'total_advances':round(float(ta),2),'total_investments':round(float(ti),2),'overall_ldr':round(float(oldr),4),'overall_investment_ratio':round(float(oir),4),'overall_risk':ors,'high_risk_rows':int((df['risk_level']=='High').sum()),'moderate_risk_rows':int((df['risk_level']=='Moderate').sum()),'low_risk_rows':int((df['risk_level']=='Low').sum())}
 return df,s
app=FastAPI(title='Bank Audit Report Summarizer API',description='REST API for bank audit PDF reports',version='1.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
_ac={}
@app.get('/')
def root():return{'service':'Bank Audit Report Summarizer','version':'1.0.0','status':'ready','endpoints':{'POST /process-pdf':'Upload PDF for full analysis','POST /analyze-text':'Submit text rows','GET /health':'Health check','GET /summary':'Get cached summary','POST /query':'Query cached results'}}
@app.get('/health')
def health_check():return{'status':'healthy','cached_results':len(_ac)}
@app.post('/process-pdf')
async def process_pdf(file:UploadFile=File(...)):
 if not file.filename.lower().endswith('.pdf'):raise HTTPException(status_code=400,detail='File must be a PDF')
 try:
  pb=await file.read();td,tt=extract_text_and_tables(pb)
  ft=[t for t in tt if is_high_value_financial_table(t['table'])]
  sd=convert_all_tables(ft)
  if not sd and td:sd=td
  df,s=perform_audit_analysis(sd);ck=file.filename
  _ac[ck]={'df':df.to_dict(orient='records'),'summary':s}
  return JSONResponse(status_code=200,content={'success':True,'message':'PDF processed successfully','extracted_data':{'text_paragraphs':len(td),'tables':len(tt),'financial_tables':len(ft),'structured_rows':len(sd)},'summary':s})
 except Exception as e:raise HTTPException(status_code=500,detail=f'PDF processing failed:{str(e)}')
@app.post('/analyze-text')
async def analyze_text(data:dict):
 sr=data.get('structured_rows',[])
 if not sr:raise HTTPException(status_code=400,detail='structured_rows required')
 try:
  df,s=perform_audit_analysis(sr)
  return JSONResponse(status_code=200,content={'success':True,'message':'Text analysis completed','extracted_data':{'structured_rows':len(sr)},'summary':s})
 except Exception as e:raise HTTPException(status_code=500,detail=f'Analysis failed:{str(e)}')
@app.post('/query')
async def query_audit_results(source_file:Optional[str]=None,page:Optional[int]=None,min_deposits:Optional[float]=None,max_deposits:Optional[float]=None,min_advances:Optional[float]=None,max_advances:Optional[float]=None,risk_level_str:Optional[str]=None):
 ck=source_file or 'latest'
 if ck not in _ac and _ac:ck=list(_ac.keys())[0]
 if ck not in _ac:raise HTTPException(status_code=404,detail='No cached analysis found.')
 rr=_ac[ck]['df'];rs=rr
 if page is not None:rs=[r for r in rs if r.get('page')==page]
 if min_deposits is not None:rs=[r for r in rs if(r.get('deposits')or 0)>=min_deposits]
 if max_deposits is not None:rs=[r for r in rs if(r.get('deposits')or 0)<=max_deposits]
 if min_advances is not None:rs=[r for r in rs if(r.get('advances')or 0)>=min_advances]
 if max_advances is not None:rs=[r for r in rs if(r.get('advances')or 0)<=max_advances]
 if risk_level_str:rs=[r for r in rs if(r.get('risk_level')or '').lower()==risk_level_str.lower()]
 return{'success':True,'message':f'Found {len(rs)} rows','total_matching':len(rs),'results':rs}
@app.get('/summary')
async def get_summary(source_file:Optional[str]=None):
 ck=source_file or 'latest'
 if ck not in _ac and _ac:ck=list(_ac.keys())[0]
 if ck not in _ac:raise HTTPException(status_code=404,detail='No cached summary found.')
 d=_ac[ck]
 return{'success':True,'source_file':ck,'summary':d['summary'],'total_detailed_rows':len(d['df'])}
if __name__=='__main__':
 import uvicorn;uvicorn.run(app,host='0.0.0.0',port=8000)
